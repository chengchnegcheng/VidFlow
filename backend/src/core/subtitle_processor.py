"""
字幕处理核心模块 - 使用 faster-whisper 生成字幕
"""
import os
import sys
import json
import importlib.util
import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any
from datetime import datetime
from importlib.metadata import version as get_version, PackageNotFoundError

logger = logging.getLogger(__name__)


def _cleanup_conflicting_packages():
    """
    处理 AI 包目录中与打包环境可能冲突的包（numpy 等）
    错误: ImportError: cannot load module more than once per process

    这个问题发生在 PyInstaller 打包的应用中：
    1. 主应用已经内置了 numpy（作为依赖）
    2. AI 包目录中又安装了另一个版本的 numpy
    3. 当 faster-whisper/torch 尝试导入 numpy 时，C 扩展模块冲突

    新策略：预先导入内置的 numpy，这样后续导入会复用已加载的模块
    """
    if not getattr(sys, 'frozen', False):
        return  # 只在打包环境中执行

    # 预先导入内置的 numpy
    try:
        import numpy
        logger.info(f"[SubtitleProcessor] Pre-loaded numpy {numpy.__version__} from {numpy.__file__}")
    except ImportError as e:
        logger.warning(f"[SubtitleProcessor] Failed to pre-load numpy: {e}")


# 在模块加载时清理冲突的包
_cleanup_conflicting_packages()

class SubtitleProcessor:
    """字幕处理器"""

    def __init__(self):
        self.model = None
        self.model_name = "base"
        self.device = "cpu"

    async def _ensure_model_downloaded(
        self,
        model_name: str,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """
        确保模型已下载，返回本地模型路径

        支持多镜像源自动切换和真实下载进度显示
        """
        # 模型名称到 Hugging Face repo 的映射
        model_repo_map = {
            "tiny": "Systran/faster-whisper-tiny",
            "tiny.en": "Systran/faster-whisper-tiny.en",
            "base": "Systran/faster-whisper-base",
            "base.en": "Systran/faster-whisper-base.en",
            "small": "Systran/faster-whisper-small",
            "small.en": "Systran/faster-whisper-small.en",
            "medium": "Systran/faster-whisper-medium",
            "medium.en": "Systran/faster-whisper-medium.en",
            "large-v1": "Systran/faster-whisper-large-v1",
            "large-v2": "Systran/faster-whisper-large-v2",
            "large-v3": "Systran/faster-whisper-large-v3",
            "large": "Systran/faster-whisper-large-v3",
            "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
            "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
        }

        repo_id = model_repo_map.get(model_name)
        if not repo_id:
            logger.info(f"Model {model_name} not in repo map, assuming local path")
            return None

        # 模型大小（MB）
        model_sizes_mb = {
            "tiny": 75, "tiny.en": 75,
            "base": 145, "base.en": 145,
            "small": 465, "small.en": 465,
            "medium": 1500, "medium.en": 1500,
            "large-v1": 3000, "large-v2": 3000, "large-v3": 3000, "large": 3000,
            "distil-large-v2": 1500, "distil-large-v3": 1500,
        }
        estimated_size_mb = model_sizes_mb.get(model_name, 500)

        try:
            import huggingface_hub
            from huggingface_hub import snapshot_download, try_to_load_from_cache

            cache_dir = huggingface_hub.constants.HF_HUB_CACHE

            if progress_callback:
                await progress_callback(21.0, f"检查模型 {model_name} (~{estimated_size_mb}MB)...")

            # 首先检查模型是否已经在本地缓存中
            try:
                # 检查关键文件是否存在
                model_bin = try_to_load_from_cache(repo_id, "model.bin")
                if model_bin is not None:
                    # 模型已经下载，直接获取本地路径
                    logger.info(f"Model {model_name} found in cache")
                    if progress_callback:
                        await progress_callback(28.0, f"模型 {model_name} 已在本地缓存")

                    # 使用 local_files_only 快速获取路径
                    local_dir = await asyncio.to_thread(
                        snapshot_download,
                        repo_id,
                        cache_dir=cache_dir,
                        local_files_only=True,
                    )
                    if progress_callback:
                        await progress_callback(29.0, f"模型 {model_name} 准备完成")
                    return local_dir
            except Exception as e:
                logger.debug(f"Cache check failed, will download: {e}")

            # 镜像源列表
            mirror_endpoints = [
                ("https://hf-mirror.com", "国内镜像"),
                ("https://huggingface.co", "官方源"),
            ]

            # 尝试启用 hf_transfer 加速
            try:
                import hf_transfer
                os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
                logger.info("hf_transfer enabled")
            except ImportError:
                os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

            # 下载状态
            download_state = {
                'current_mirror': '',
                'error': None,
                'local_dir': None,
            }

            async def try_download_from_mirror(endpoint: str, name: str) -> Optional[str]:
                """尝试从指定镜像下载"""
                os.environ["HF_ENDPOINT"] = endpoint
                logger.info(f"Trying mirror: {name} ({endpoint})")
                download_state['current_mirror'] = name

                try:
                    local_dir = await asyncio.to_thread(
                        snapshot_download,
                        repo_id,
                        cache_dir=cache_dir,
                        local_files_only=False,
                        resume_download=True,
                    )
                    return local_dir
                except Exception as e:
                    logger.warning(f"Download from {name} failed: {e}")
                    download_state['error'] = str(e)
                    return None

            # 启动下载任务（尝试多个镜像），添加 15 分钟超时
            async def download_with_fallback():
                for endpoint, name in mirror_endpoints:
                    if progress_callback:
                        await progress_callback(22.0, f"尝试 {name}...")

                    try:
                        # 单个镜像最多尝试 10 分钟
                        result = await asyncio.wait_for(
                            try_download_from_mirror(endpoint, name),
                            timeout=600.0
                        )
                        if result:
                            download_state['local_dir'] = result
                            return result
                    except asyncio.TimeoutError:
                        logger.warning(f"Download from {name} timed out after 10 minutes")
                        download_state['error'] = f"{name} 下载超时"

                    # 等待一下再尝试下一个
                    await asyncio.sleep(1)

                raise RuntimeError(f"所有镜像源下载失败: {download_state['error']}")

            # 启动下载
            download_task = asyncio.create_task(download_with_fallback())

            # 进度更新循环
            start_time = asyncio.get_event_loop().time()
            last_size = 0
            last_time = start_time
            stall_count = 0  # 下载停滞计数

            while not download_task.done():
                await asyncio.sleep(1.0)

                if progress_callback:
                    current_time = asyncio.get_event_loop().time()
                    elapsed = current_time - start_time
                    elapsed_min = int(elapsed // 60)
                    elapsed_sec = int(elapsed % 60)
                    if elapsed_min > 0:
                        time_str = f"{elapsed_min}分{elapsed_sec}秒"
                    else:
                        time_str = f"{elapsed_sec}秒"

                    mirror_name = download_state['current_mirror'] or "准备中"

                    # 检查缓存目录大小来估算进度
                    try:
                        cache_path = Path(cache_dir)
                        repo_cache = cache_path / f"models--{repo_id.replace('/', '--')}"
                        if repo_cache.exists():
                            # 只计算 blobs 目录中的文件（实际下载的文件）
                            blobs_dir = repo_cache / "blobs"
                            if blobs_dir.exists():
                                total_size = sum(f.stat().st_size for f in blobs_dir.iterdir() if f.is_file())
                            else:
                                total_size = 0
                            downloaded_mb = total_size / (1024 * 1024)

                            # 计算实时速度（基于最近一次更新）
                            time_diff = current_time - last_time
                            size_diff = total_size - last_size
                            if time_diff > 0:
                                current_speed = size_diff / time_diff / (1024 * 1024)  # MB/s
                            else:
                                current_speed = 0
                            last_size = total_size
                            last_time = current_time

                            # 格式化速度
                            if current_speed > 1:
                                speed_str = f"{current_speed:.1f} MB/s"
                            elif current_speed > 0.001:
                                speed_str = f"{current_speed * 1024:.0f} KB/s"
                            else:
                                speed_str = "..."

                            # 检查是否下载接近完成（超过95%或超过预估大小）
                            if downloaded_mb >= estimated_size_mb * 0.95:
                                # 下载基本完成，正在校验/处理
                                progress_value = 28.0
                                msg = f"[{mirror_name}] 校验文件中... 已用 {time_str}"
                            else:
                                # 正常下载中
                                progress_pct = min(downloaded_mb / estimated_size_mb, 0.99)
                                progress_value = 21.0 + progress_pct * 7.0

                                # 预计剩余时间
                                if current_speed > 0.01:
                                    remaining_mb = max(0, estimated_size_mb - downloaded_mb)
                                    eta_sec = remaining_mb / current_speed
                                    if eta_sec > 60:
                                        eta_str = f"{int(eta_sec // 60)}分{int(eta_sec % 60)}秒"
                                    else:
                                        eta_str = f"{int(eta_sec)}秒"
                                else:
                                    eta_str = "计算中"

                                msg = f"[{mirror_name}] {downloaded_mb:.1f}/{estimated_size_mb}MB | {speed_str} | 剩余 {eta_str}"

                            await progress_callback(progress_value, msg)
                        else:
                            # 缓存目录还不存在
                            await progress_callback(22.0, f"[{mirror_name}] 连接中... 已用 {time_str}")
                    except Exception as e:
                        # 无法读取缓存大小，显示简单进度
                        await progress_callback(23.0, f"[{mirror_name}] 下载中... 已用 {time_str}")

            # 获取结果
            local_dir = await download_task

            if progress_callback:
                await progress_callback(29.0, f"模型 {model_name} 下载完成")

            logger.info(f"Model {model_name} ready at: {local_dir}")
            return local_dir

        except ImportError:
            logger.warning("huggingface_hub not available")
            return None
        except Exception as e:
            logger.warning(f"Pre-download failed: {e}")
            return None

    async def initialize_model(
        self,
        model_name: str = "base",
        device: str = "auto",
        progress_callback: Optional[Callable] = None
    ):
        """初始化 Whisper 模型

        Args:
            model_name: 模型名称 (tiny, base, small, medium, large, large-v2, large-v3)
            device: 设备类型 (auto, cpu, cuda)
            progress_callback: 进度回调函数，签名为 async def callback(progress: float, message: str)
        """
        try:
            # 在打包环境中，确保内置 numpy 优先于 AI 包目录中的 numpy
            # 这可以避免 "cannot load module more than once per process" 错误
            if getattr(sys, 'frozen', False):
                try:
                    # 临时将 AI 包目录从 sys.path 开头移到后面
                    from src.core.tool_manager import AI_PACKAGES_DIR
                    ai_pkg_str = str(AI_PACKAGES_DIR)

                    # 先导入内置 numpy（在调整 sys.path 之前它应该已经可用）
                    # 如果内置 numpy 不在 sys.path 中，我们需要找到它
                    if ai_pkg_str in sys.path:
                        # 临时移除 AI 包目录
                        sys.path.remove(ai_pkg_str)
                        try:
                            import numpy
                            logger.info(f"[Model Init] Pre-loaded numpy {numpy.__version__} from {numpy.__file__}")
                        except ImportError:
                            logger.warning("[Model Init] Built-in numpy not found")
                        finally:
                            # 恢复 AI 包目录到 sys.path（但放到后面而不是开头）
                            if ai_pkg_str not in sys.path:
                                sys.path.append(ai_pkg_str)
                except Exception as e:
                    logger.warning(f"[Model Init] Failed to adjust sys.path for numpy: {e}")

            # Windows 平台修复：让 ctranslate2 能找到 PyTorch 的 CUDA 库
            if sys.platform == 'win32':
                try:
                    torch_spec = importlib.util.find_spec("torch")
                    torch_pkg_dir: Optional[Path] = None
                    if torch_spec and torch_spec.origin:
                        torch_pkg_dir = Path(torch_spec.origin).parent
                    if torch_pkg_dir:
                        torch_lib_path = torch_pkg_dir / "lib"
                        if torch_lib_path.exists():
                            if hasattr(os, 'add_dll_directory'):
                                os.add_dll_directory(str(torch_lib_path))
                            os.environ['PATH'] = str(torch_lib_path) + os.pathsep + os.environ.get('PATH', '')
                            logger.info(f"Added torch lib to DLL search path: {torch_lib_path}")
                except Exception as e:
                    logger.warning(f"Failed to add torch lib path: {e}")

            # 在导入 faster_whisper 之前，确保 AI_PACKAGES_DIR 在 sys.path 中
            try:
                from src.core.tool_manager import AI_PACKAGES_DIR
                ai_pkg_str = str(AI_PACKAGES_DIR)
                if ai_pkg_str not in sys.path:
                    logger.info(f"[Model Init] Adding AI_PACKAGES_DIR to sys.path: {ai_pkg_str}")
                    sys.path.append(ai_pkg_str)
                logger.info(f"[Model Init] sys.path contains AI_PACKAGES_DIR: {ai_pkg_str in sys.path}")
                logger.info(f"[Model Init] AI_PACKAGES_DIR exists: {Path(ai_pkg_str).exists()}")

                # Windows 平台：添加 av.libs 和 ctranslate2 DLL 到搜索路径
                if sys.platform == 'win32':
                    ai_pkg_path = Path(ai_pkg_str)

                    # 添加 av.libs 目录（PyAV 的 FFmpeg DLL）
                    av_libs_path = ai_pkg_path / "av.libs"
                    if av_libs_path.exists():
                        if hasattr(os, 'add_dll_directory'):
                            os.add_dll_directory(str(av_libs_path))
                        os.environ['PATH'] = str(av_libs_path) + os.pathsep + os.environ.get('PATH', '')
                        logger.info(f"[Model Init] Added av.libs to DLL search path: {av_libs_path}")

                    # 添加 ctranslate2 目录（ctranslate2 的 CUDA DLL）
                    ct2_path = ai_pkg_path / "ctranslate2"
                    if ct2_path.exists():
                        if hasattr(os, 'add_dll_directory'):
                            os.add_dll_directory(str(ct2_path))
                        os.environ['PATH'] = str(ct2_path) + os.pathsep + os.environ.get('PATH', '')
                        logger.info(f"[Model Init] Added ctranslate2 to DLL search path: {ct2_path}")

                    # 添加 numpy.libs 目录
                    numpy_libs_path = ai_pkg_path / "numpy.libs"
                    if numpy_libs_path.exists():
                        if hasattr(os, 'add_dll_directory'):
                            os.add_dll_directory(str(numpy_libs_path))
                        os.environ['PATH'] = str(numpy_libs_path) + os.pathsep + os.environ.get('PATH', '')
                        logger.info(f"[Model Init] Added numpy.libs to DLL search path: {numpy_libs_path}")
            except Exception as e:
                logger.warning(f"[Model Init] Failed to check AI_PACKAGES_DIR: {e}")

            logger.info("[Model Init] Attempting to import faster_whisper...")
            import faster_whisper
            logger.info(f"[Model Init] faster_whisper imported successfully from {faster_whisper.__file__}")

            # 自动检测设备
            if device == "auto":
                device = "cpu"
                logger.info(f"[Device Detection] Starting auto-detection, frozen={getattr(sys, 'frozen', False)}")

                # 开发环境：直接导入 torch 检测（更简单可靠）
                if not getattr(sys, 'frozen', False):
                    try:
                        import torch
                        cuda_available = torch.cuda.is_available()
                        cuda_version = getattr(torch.version, 'cuda', None)
                        logger.info(f"[Device Detection] Direct torch check: cuda_available={cuda_available}, cuda_version={cuda_version}")

                        if cuda_available:
                            device = "cuda"
                            logger.info(f"[Device Detection] ✓ Using CUDA (GPU mode)")
                        else:
                            device = "cpu"
                            logger.info(f"[Device Detection] CUDA not available, using CPU")
                    except Exception as e:
                        logger.warning(f"[Device Detection] Direct torch check failed: {e}, using CPU")
                        device = "cpu"
                else:
                    # 打包环境：使用子进程检测
                    try:
                        try:
                            ctranslate2_version = get_version("ctranslate2")
                        except PackageNotFoundError:
                            ctranslate2_version = "unknown"

                        python_exe: Optional[str] = sys.executable
                        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent / '_internal'
                        python_name = 'python.exe' if sys.platform == 'win32' else 'python'
                        embedded_python = base_path / 'python' / python_name
                        if embedded_python.exists():
                            python_exe = str(embedded_python)
                        else:
                            python_exe = None

                        from src.core.tool_manager import AI_PACKAGES_DIR

                        env = os.environ.copy()
                        env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

                        # 直接在代码中插入 sys.path，而不是依赖 PYTHONPATH 环境变量
                        # 这对打包后的嵌入式 Python 更可靠（与 tool_manager.py 保持一致）
                        code = f'''
import sys
sys.path.insert(0, r"{AI_PACKAGES_DIR}")
import json, torch
print(json.dumps({{
    "cuda": bool(torch.cuda.is_available()),
    "mps": bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available()),
    "cuda_version": getattr(torch.version, "cuda", None)
}}))
'''

                        if not python_exe:
                            raise RuntimeError("embedded python not found for torch probe")

                        logger.info(f"[Device Detection] Using python: {python_exe}")
                        logger.info(f"[Device Detection] AI_PACKAGES_DIR: {AI_PACKAGES_DIR}")

                        process = await asyncio.create_subprocess_exec(
                            python_exe,
                            '-c',
                            code,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            env=env,
                        )

                        try:
                            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
                        except asyncio.TimeoutError:
                            process.kill()
                            stdout, stderr = await process.communicate()
                            raise RuntimeError("torch probe timeout")

                        if process.returncode != 0:
                            stderr_text = stderr.decode('utf-8', errors='ignore').strip() if stderr else ''
                            logger.warning(f"[Device Detection] torch probe failed with code {process.returncode}")
                            if stderr_text:
                                logger.warning(f"[Device Detection] stderr: {stderr_text[:500]}")
                            device = "cpu"
                        else:
                            try:
                                data = json.loads(stdout.decode('utf-8', errors='ignore').strip() or '{}')
                            except Exception:
                                data = {}

                            cuda_available = bool(data.get("cuda"))
                            mps_available = bool(data.get("mps"))
                            cuda_version = data.get("cuda_version")
                            logger.info(f"System CUDA version: {cuda_version}")
                            logger.info(f"System MPS available: {mps_available}")
                            logger.info(f"ctranslate2 version: {ctranslate2_version}")

                            if cuda_available:
                                cuda_major: Optional[int] = None
                                try:
                                    cuda_major = int(str(cuda_version).split('.')[0]) if cuda_version else None
                                except Exception:
                                    cuda_major = None

                                # ctranslate2 版本兼容性检查
                                # ctranslate2 3.x: 支持 CUDA 11.x
                                # ctranslate2 4.x: 需要 CUDA 12.x
                                ct2_major = None
                                try:
                                    ct2_major = int(str(ctranslate2_version).split('.')[0])
                                except Exception:
                                    ct2_major = None

                                # 检查版本兼容性
                                if ct2_major is not None and cuda_major is not None:
                                    if ct2_major >= 4 and cuda_major < 12:
                                        # ctranslate2 4.x 需要 CUDA 12.x，但系统是 CUDA 11.x
                                        logger.warning(f"⚠ ctranslate2 {ctranslate2_version} requires CUDA 12.x")
                                        logger.warning(f"  Your system has CUDA {cuda_version}")
                                        logger.info("→ Forcing CPU mode to avoid runtime errors")
                                        logger.info("→ 建议运行 FIX_CTRANSLATE2_CUDA11.bat 修复此问题以启用 GPU")
                                        device = "cpu"
                                    elif ct2_major == 3 and cuda_major < 12:
                                        # ctranslate2 3.x 兼容 CUDA 11.x - 可以使用 GPU
                                        logger.info(f"✓ ctranslate2 {ctranslate2_version} is compatible with CUDA {cuda_version}")
                                        device = "cuda"
                                    else:
                                        # 其他情况：CUDA 12.x 或更高版本，使用 GPU
                                        device = "cuda"
                                else:
                                    # 无法判断版本，使用 GPU 尝试
                                    device = "cuda"
                            else:
                                device = "cpu"
                    except Exception as e:
                        logger.warning(f"[Device Detection] Auto-detect failed: {e}")
                        logger.warning(f"[Device Detection] Falling back to CPU")
                        device = "cpu"

            logger.info(f"Loading Whisper model: {model_name} on {device}")

            # 预下载模型（带进度反馈）
            # 对于非 base 模型，首次使用需要从 Hugging Face 下载
            if model_name != "base":
                if progress_callback:
                    await progress_callback(21.0, f"正在准备模型 {model_name}...")
                local_model_path = await self._ensure_model_downloaded(model_name, progress_callback)
                # 如果成功获取本地路径，使用本地路径加载
                if local_model_path:
                    model_name_or_path = local_model_path
                else:
                    model_name_or_path = model_name
            else:
                model_name_or_path = model_name

            if progress_callback:
                await progress_callback(29.0, "正在初始化模型...")

            # 尝试加载模型，如果 CUDA 失败则自动回退到 CPU
            try:
                # 在线程池中加载模型（避免阻塞）
                self.model = await asyncio.to_thread(
                    faster_whisper.WhisperModel,
                    model_name_or_path,
                    device=device,
                    compute_type="float16" if device == "cuda" else "int8"
                )

                self.model_name = model_name
                self.device = device

                logger.info(f"✓ Model loaded successfully on {device}")
                return True

            except Exception as e:
                # 如果 CUDA 模式失败，尝试 CPU 模式
                if device == "cuda" and ("cublas" in str(e).lower() or "cuda" in str(e).lower()):
                    logger.warning(f"⚠ CUDA initialization failed: {e}")
                    logger.info("→ ctranslate2 was built for a different CUDA version than your system")
                    logger.info("→ Retrying with CPU mode...")

                    if progress_callback:
                        await progress_callback(29.0, "CUDA 初始化失败，切换到 CPU 模式...")

                    # 重试 CPU 模式
                    self.model = await asyncio.to_thread(
                        faster_whisper.WhisperModel,
                        model_name_or_path,
                        device="cpu",
                        compute_type="int8"
                    )

                    self.model_name = model_name
                    self.device = "cpu"

                    logger.info(f"✓ Model loaded successfully on CPU (fallback mode)")
                    return True
                else:
                    # 其他错误，直接抛出
                    raise

        except ImportError as e:
            logger.error(f"faster-whisper import failed: {e}")
            logger.error(f"sys.path: {sys.path}")
            # 尝试获取更详细的错误信息
            try:
                from src.core.tool_manager import AI_PACKAGES_DIR
                logger.error(f"AI_PACKAGES_DIR: {AI_PACKAGES_DIR}")
                logger.error(f"AI_PACKAGES_DIR exists: {Path(AI_PACKAGES_DIR).exists()}")
                if Path(AI_PACKAGES_DIR).exists():
                    # 列出 AI 包目录中的内容
                    contents = list(Path(AI_PACKAGES_DIR).iterdir())[:20]
                    logger.error(f"AI_PACKAGES_DIR contents (first 20): {[c.name for c in contents]}")
            except Exception as debug_e:
                logger.error(f"Debug info collection failed: {debug_e}")
            raise RuntimeError(f"faster-whisper 导入失败: {e}\n请检查日志中心获取详细信息")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    async def extract_audio(self, video_path: str, audio_path: str) -> bool:
        """从视频中提取音频"""
        try:
            from src.core.tool_manager import get_tool_manager

            tool_mgr = get_tool_manager()
            ffmpeg_path = tool_mgr.get_ffmpeg_path()

            if not ffmpeg_path:
                raise RuntimeError("FFmpeg 未安装")

            # 确保路径使用正确的编码
            # Windows 需要处理中文路径
            if sys.platform == 'win32':
                # 在 Windows 上，确保路径是 str 类型（Python 3 会自动处理 Unicode）
                video_path = str(video_path)
                audio_path = str(audio_path)

            # FFmpeg 命令：提取音频为 WAV
            cmd = [
                str(ffmpeg_path),
                '-i', video_path,
                '-vn',  # 不处理视频
                '-acodec', 'pcm_s16le',  # PCM 16-bit
                '-ar', '16000',  # 16kHz 采样率
                '-ac', '1',  # 单声道
                '-y',  # 覆盖输出
                audio_path
            ]

            logger.info(f"Extracting audio: {video_path} -> {audio_path}")

            # 执行 FFmpeg
            # 不指定编码，让它返回 bytes，然后根据平台解码
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300.0  # 5 分钟超时
                )
            except asyncio.TimeoutError:
                logger.warning("FFmpeg extraction timed out after 300s, terminating process...")
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    logger.info("FFmpeg process killed successfully")
                except asyncio.TimeoutError:
                    logger.error("Failed to kill FFmpeg process within 5s, attempting terminate...")
                    try:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except Exception as terminate_err:
                        logger.critical(f"FFmpeg process could not be terminated: {terminate_err}")
                except Exception as kill_err:
                    logger.error(f"Error killing FFmpeg process: {kill_err}")
                raise RuntimeError("FFmpeg 处理超时 (300s)")

            if process.returncode == 0:
                logger.info("Audio extracted successfully")
                return True
            else:
                # 根据平台选择合适的编码解码错误信息
                try:
                    if sys.platform == 'win32':
                        # Windows 可能使用 GBK 或 UTF-8
                        try:
                            error_msg = stderr.decode('utf-8')
                        except UnicodeDecodeError:
                            error_msg = stderr.decode('gbk', errors='ignore')
                    else:
                        error_msg = stderr.decode('utf-8', errors='ignore')
                except Exception:
                    error_msg = str(stderr)

                logger.error(f"FFmpeg error: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"Failed to extract audio: {e}")
            raise

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback = None
    ) -> List[Dict]:
        """转录音频为文字"""
        try:
            if not self.model:
                await self.initialize_model()

            # 安全记录路径（避免编码问题）
            try:
                logger.info(f"Transcribing: {audio_path}")
            except Exception:
                logger.info(f"Transcribing audio file...")

            # 转录参数 - 优化以提高识别质量
            transcribe_options = {
                "language": language if language and language != "auto" else None,
                "beam_size": 5,
                "best_of": 5,
                "temperature": 0.0,
                "condition_on_previous_text": True,
                "compression_ratio_threshold": 2.4,
                "log_prob_threshold": -1.0,
                "no_speech_threshold": 0.6,
                "word_timestamps": False,
                # VAD 过滤 - 使用 Silero VAD 过滤无语音段落，防止幻觉
                "vad_filter": True,
                "vad_parameters": {
                    "threshold": 0.5,           # 语音检测阈值 (0-1)，越高越严格
                    "min_speech_duration_ms": 250,  # 最小语音持续时间（毫秒）
                    "min_silence_duration_ms": 2000,  # 最小静音持续时间（毫秒）
                    "speech_pad_ms": 400,       # 语音段落前后填充（毫秒）
                },
            }

            # 使用队列在线程和异步之间传递进度
            import queue
            progress_queue: queue.Queue = queue.Queue()

            # 在线程池中执行转录并收集所有结果
            def do_transcribe():
                logger.info(f"[Transcribe] Starting transcription with options: {transcribe_options}")
                logger.info(f"[Transcribe] Device: {self.device}, Model: {self.model_name}")

                segments_gen, info = self.model.transcribe(
                    audio_path,
                    **transcribe_options
                )

                duration = getattr(info, 'duration', 0) or 0
                logger.info(f"[Transcribe] Got generator, audio duration: {duration}s")
                logger.info(f"[Transcribe] Detected language: {getattr(info, 'language', 'unknown')}")

                # 在同一线程中消费生成器，收集所有结果
                segments_list = []
                last_progress_time = 0

                for i, seg in enumerate(segments_gen):
                    segments_list.append(seg)

                    # 每 10 段或每 30 秒音频打印一次日志
                    if (i + 1) % 10 == 0:
                        logger.info(f"[Transcribe] Processed {i + 1} segments, last: {seg.end:.1f}s")

                    # 更频繁地发送进度更新：每段都发送（队列会自动合并）
                    if duration > 0:
                        # 每处理 20 秒音频或每 5 段发送一次进度
                        if seg.end - last_progress_time >= 20 or (i + 1) % 5 == 0:
                            last_progress_time = seg.end
                            progress = 32.0 + min((seg.end / duration) * 46.0, 46.0)
                            # 格式化时间显示
                            current_min = int(seg.end // 60)
                            current_sec = int(seg.end % 60)
                            total_min = int(duration // 60)
                            total_sec = int(duration % 60)
                            progress_queue.put((
                                progress,
                                f"语音识别中… {current_min}:{current_sec:02d}"
                            ))

                logger.info(f"[Transcribe] Finished collecting {len(segments_list)} segments")
                # 发送完成信号
                progress_queue.put(None)
                return segments_list, info

            logger.info(f"[Transcribe] Starting transcription thread...")

            # 启动转录任务
            import concurrent.futures
            loop = asyncio.get_event_loop()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            transcribe_future = loop.run_in_executor(executor, do_transcribe)

            # 同时处理进度更新
            last_update_time = asyncio.get_event_loop().time()
            transcription_done = False
            while not transcription_done:
                # 批量处理队列中的进度更新（取最新的）
                latest_progress = None
                got_done_signal = False
                try:
                    while True:
                        progress_data = progress_queue.get_nowait()
                        if progress_data is None:
                            # 转录完成信号
                            got_done_signal = True
                            break
                        latest_progress = progress_data
                except queue.Empty:
                    pass

                # 发送最新的进度更新
                if latest_progress is not None and progress_callback:
                    progress, message = latest_progress
                    await progress_callback(progress, message)
                    last_update_time = asyncio.get_event_loop().time()

                if got_done_signal:
                    # 收到完成信号
                    transcription_done = True
                    break

                # 检查转录是否完成
                if transcribe_future.done():
                    # 处理队列中剩余的进度更新
                    while True:
                        try:
                            progress_data = progress_queue.get_nowait()
                            if progress_data is None:
                                break
                            if progress_callback:
                                progress, message = progress_data
                                await progress_callback(progress, message)
                        except queue.Empty:
                            break
                    break

                # 短暂等待，避免忙等（每 200ms 检查一次）
                await asyncio.sleep(0.2)

            # 获取结果
            segments_list, info = await transcribe_future
            executor.shutdown(wait=False)

            logger.info(f"[Transcribe] Thread completed")
            logger.info(f"Raw transcription: {len(segments_list)} segments")

            # 收集结果
            results = []
            duration = getattr(info, "duration", None) if info else None
            last_text = ""  # 用于去重

            for i, segment in enumerate(segments_list):
                text = segment.text.strip()

                # 跳过空文本
                if not text:
                    continue

                # 跳过与上一段完全相同的文本（去重）
                if text == last_text:
                    logger.debug(f"Skipping duplicate segment: {text[:50]}...")
                    continue

                result = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": text
                }
                results.append(result)
                last_text = text

            if progress_callback:
                await progress_callback(78.0, f"识别完成，共 {len(results)} 段")

            logger.info(f"Transcription completed: {len(results)} segments (filtered from {len(segments_list)})")

            # 返回语言信息
            detected_language = info.language if hasattr(info, 'language') else 'unknown'

            return {
                "segments": results,
                "language": detected_language,
                "duration": info.duration if hasattr(info, 'duration') else 0
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def format_srt(self, segments: List[Dict]) -> str:
        """格式化为 SRT 字幕"""
        srt_content = []

        for i, segment in enumerate(segments, 1):
            # 时间格式：00:00:00,000
            start_time = self._format_timestamp(segment['start'])
            end_time = self._format_timestamp(segment['end'])

            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(segment['text'])
            srt_content.append("")  # 空行

        return "\n".join(srt_content)

    def format_vtt(self, segments: List[Dict]) -> str:
        """格式化为 WebVTT 字幕"""
        vtt_content = ["WEBVTT", ""]

        for segment in segments:
            start_time = self._format_timestamp(segment['start'], vtt=True)
            end_time = self._format_timestamp(segment['end'], vtt=True)

            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(segment['text'])
            vtt_content.append("")

        return "\n".join(vtt_content)

    def _format_timestamp(self, seconds: float, vtt: bool = False) -> str:
        """格式化时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        if vtt:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    async def translate_subtitle(
        self,
        segments: List[Dict],
        target_language: str
    ) -> List[Dict]:
        """翻译字幕（简单实现，可接入翻译API）"""
        # TODO: 集成翻译 API（Google Translate, DeepL, etc.）
        logger.warning("Translation not implemented yet")
        return segments

    async def _translate_srt_file(self, srt_path: Path, target_lang: str, source_lang: str = "en") -> str:
        """翻译 SRT 文件内容（支持多引擎自动切换）

        Args:
            srt_path: SRT 文件路径
            target_lang: 目标语言代码
            source_lang: 源语言代码（默认英文）
        """
        try:
            from deep_translator import GoogleTranslator, MyMemoryTranslator

            # GoogleTranslator 语言代码映射
            google_lang_map = {
                'zh': 'zh-CN',
                'zh-CN': 'zh-CN',
                'zh-TW': 'zh-TW',
                'en': 'en',
                'ja': 'ja',
                'ko': 'ko',
                'es': 'es',
                'fr': 'fr',
                'de': 'de',
                'ru': 'ru'
            }

            # MyMemory 需要完整的语言代码
            mymemory_lang_map = {
                'zh': 'zh-CN',
                'zh-CN': 'zh-CN',
                'zh-TW': 'zh-TW',
                'en': 'en-GB',
                'ja': 'ja-JP',
                'ko': 'ko-KR',
                'es': 'es-ES',
                'fr': 'fr-FR',
                'de': 'de-DE',
                'ru': 'ru-RU'
            }

            target_google = google_lang_map.get(target_lang, target_lang)
            source_google = google_lang_map.get(source_lang, source_lang)
            target_mymemory = mymemory_lang_map.get(target_lang, target_lang)
            source_mymemory = mymemory_lang_map.get(source_lang, source_lang)

            logger.info(f"Translating from {source_lang} to {target_lang}")
            logger.info(f"MyMemory codes: source={source_mymemory}, target={target_mymemory}")

            # 尝试多个翻译引擎（自动回退）
            # GoogleTranslator 支持 source='auto'
            # MyMemory 不支持 auto，必须传递具体语言代码
            translators = [
                (GoogleTranslator(source='auto', target=target_google), 'Google Translate'),
                (MyMemoryTranslator(source=source_mymemory, target=target_mymemory), 'MyMemory')
            ]

            # 测试哪个翻译引擎可用
            working_translator = None
            translator_name = None

            for trans, name in translators:
                try:
                    # 测试翻译（在线程池中执行）
                    test_result = await asyncio.to_thread(trans.translate, "Hello")
                    if test_result and 'INVALID' not in test_result.upper() and 'NO SUPPORT' not in test_result.upper():
                        working_translator = trans
                        translator_name = name
                        logger.info(f"Using {name} for translation (test result: {test_result})")
                        break
                    else:
                        logger.warning(f"{name} returned invalid result: {test_result[:100] if test_result else 'None'}")
                except Exception as e:
                    logger.warning(f"{name} not available: {e}")
                    continue

            if not working_translator:
                raise Exception("所有翻译服务均不可用，请检查网络连接")

            # 读取 SRT 文件
            content = srt_path.read_text(encoding='utf-8')

            # 解析 SRT：匹配序号、时间戳和文本
            pattern = re.compile(
                r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\Z)',
                re.DOTALL
            )

            # 收集所有需要翻译的文本
            segments_to_translate = []
            for match in pattern.finditer(content):
                index = match.group(1)
                timestamp = match.group(2)
                text = match.group(3).strip()
                segments_to_translate.append((index, timestamp, text))

            logger.info(f"Found {len(segments_to_translate)} segments to translate")

            if not segments_to_translate:
                logger.warning("No segments found in SRT file")
                return content

            # 批量翻译函数（在线程池中执行）
            def translate_all_segments():
                translated_blocks = []
                success_count = 0
                fail_count = 0

                for index, timestamp, text in segments_to_translate:
                    if text:
                        try:
                            # 按行翻译（保持换行）
                            lines = text.split('\n')
                            translated_lines = []
                            for line in lines:
                                if line.strip():
                                    # 翻译限制每次5000字符
                                    if len(line) <= 5000:
                                        translated = working_translator.translate(line.strip())
                                        if translated:
                                            translated_lines.append(translated)
                                        else:
                                            translated_lines.append(line.strip())
                                    else:
                                        # 超长文本分块翻译
                                        chunks = [line[i:i+4000] for i in range(0, len(line), 4000)]
                                        translated_chunks = [working_translator.translate(chunk) for chunk in chunks]
                                        translated_lines.append(''.join(translated_chunks))

                            translated_text = '\n'.join(translated_lines)
                            success_count += 1
                        except Exception as e:
                            logger.warning(f"Translation failed for segment {index}: {e}")
                            translated_text = text
                            fail_count += 1
                    else:
                        translated_text = text

                    # 重建 SRT 块
                    block = f"{index}\n{timestamp}\n{translated_text}\n"
                    translated_blocks.append(block)

                logger.info(f"Translation stats: {success_count} success, {fail_count} failed")
                return '\n'.join(translated_blocks)

            # 在线程池中执行翻译，避免阻塞事件循环
            result = await asyncio.to_thread(translate_all_segments)
            logger.info(f"Translation completed using {translator_name}")
            return result

        except ImportError:
            logger.error("deep-translator not installed. Run: pip install deep-translator")
            raise Exception("翻译库未安装，请联系管理员")
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise

    async def process_video(
        self,
        video_path: str,
        output_dir: str,
        source_language: str = "auto",
        target_languages: List[str] = None,
        model_name: str = "base",
        formats: List[str] = None,
        progress_callback=None
    ) -> Dict:
        """完整的视频字幕处理流程"""
        try:
            video_path = Path(video_path)
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 默认参数
            if formats is None:
                formats = ["srt"]
            if target_languages is None:
                target_languages = []

            # 1. 提取音频 (0-20%)
            if progress_callback:
                await progress_callback(10.0, "正在提取音频...")
            audio_path = output_dir / f"{video_path.stem}_audio.wav"
            logger.info("Step 1/3: Extracting audio...")
            await self.extract_audio(str(video_path), str(audio_path))
            if progress_callback:
                await progress_callback(20.0, "音频提取完成")

            # 2. 初始化模型 (20-30%)
            if not self.model or self.model_name != model_name:
                logger.info("Step 2/3: Loading model...")
                if progress_callback:
                    await progress_callback(21.0, f"正在准备模型 {model_name}...")
                await self.initialize_model(model_name, progress_callback=progress_callback)
                if progress_callback:
                    await progress_callback(30.0, "模型加载完成")

            # 3. 转录 (30-80%)
            logger.info("Step 3/3: Transcribing...")
            if progress_callback:
                await progress_callback(32.0, "开始语音识别...")
            result = await self.transcribe(
                str(audio_path),
                language=source_language,
                progress_callback=progress_callback
            )

            segments = result['segments']
            detected_language = result['language']

            logger.info(f"Transcription result: {len(segments)} segments, language: {detected_language}")

            # 检查是否有识别到的内容
            if not segments:
                logger.warning("No speech detected in the video")
                if progress_callback:
                    await progress_callback(85.0, "未检测到语音内容")

            if progress_callback:
                await progress_callback(80.0, f"识别完成，检测到语言: {detected_language}")

            # 4. 生成字幕文件 (80-85%)
            output_files = []

            logger.info(f"Generating subtitle files in formats: {formats}")

            # 原始语言字幕
            for fmt in formats:
                if fmt == "srt":
                    content = self.format_srt(segments)
                    ext = "srt"
                elif fmt == "vtt":
                    content = self.format_vtt(segments)
                    ext = "vtt"
                else:
                    continue

                output_file = output_dir / f"{video_path.stem}.{detected_language}.{ext}"
                output_file.write_text(content, encoding='utf-8')
                output_files.append(str(output_file))
                logger.info(f"Generated subtitle file: {output_file}")

            if progress_callback:
                await progress_callback(85.0, "字幕文件生成完成")

            # 5. 翻译（如果需要）(85-95%)
            logger.info(f"Target languages: {target_languages}, detected: {detected_language}")

            if target_languages and segments:  # 只有在有字幕内容时才翻译
                # 过滤掉与检测语言相同的目标语言
                langs_to_translate = [l for l in target_languages if l != detected_language]
                logger.info(f"Languages to translate: {langs_to_translate}")

                if not langs_to_translate:
                    logger.info("No translation needed - target language same as detected language")
                    if progress_callback:
                        await progress_callback(90.0, "无需翻译（目标语言与原语言相同）")
                else:
                    total_langs = len(langs_to_translate)
                    lang_idx = 0

                    for target_lang in langs_to_translate:
                        lang_idx += 1
                        logger.info(f"Translating subtitles to {target_lang} ({lang_idx}/{total_langs})...")

                        if progress_callback:
                            progress = 85.0 + (lang_idx / max(total_langs, 1)) * 10.0
                            await progress_callback(progress, f"翻译字幕到 {target_lang}...")

                        try:
                            # 读取原始 SRT 文件进行翻译
                            srt_file = output_dir / f"{video_path.stem}.{detected_language}.srt"
                            logger.info(f"Looking for SRT file: {srt_file}")
                            if srt_file.exists():
                                logger.info(f"Found SRT file, starting translation...")
                                # 添加超时机制（最多 5 分钟）
                                try:
                                    translated_content = await asyncio.wait_for(
                                        self._translate_srt_file(srt_file, target_lang, detected_language),
                                        timeout=300.0
                                    )
                                    # 保存翻译后的文件
                                    translated_file = output_dir / f"{video_path.stem}.{target_lang}.srt"
                                    translated_file.write_text(translated_content, encoding='utf-8')
                                    output_files.append(str(translated_file))
                                    logger.info(f"Translation to {target_lang} completed, saved to: {translated_file}")
                                except asyncio.TimeoutError:
                                    logger.warning(f"Translation to {target_lang} timed out after 5 minutes, skipping")
                                    if progress_callback:
                                        await progress_callback(progress, f"翻译 {target_lang} 超时，已跳过")
                            else:
                                logger.error(f"SRT file not found: {srt_file}")
                                if progress_callback:
                                    await progress_callback(progress, f"找不到原始字幕文件，无法翻译")
                        except Exception as e:
                            logger.error(f"Translation to {target_lang} failed: {e}")
                            if progress_callback:
                                await progress_callback(progress, f"翻译 {target_lang} 失败: {str(e)[:50]}")

            if progress_callback:
                await progress_callback(98.0, "清理临时文件...")

            # 6. 清理临时文件
            if audio_path.exists():
                audio_path.unlink()

            if progress_callback:
                await progress_callback(100.0, "处理完成")

            logger.info(f"Video processing completed: {len(output_files)} files generated")

            return {
                "success": True,
                "output_files": output_files,
                "language": detected_language,
                "segments_count": len(segments),
                "duration": result.get('duration', 0) if isinstance(result, dict) else 0
            }

        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            raise

# 全局处理器实例
_subtitle_processor = None

def get_subtitle_processor() -> SubtitleProcessor:
    """获取字幕处理器实例"""
    global _subtitle_processor
    if _subtitle_processor is None:
        _subtitle_processor = SubtitleProcessor()
    return _subtitle_processor
