"""
GPU 加速管理器
检测GPU并提供安装指导
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class GPUManager:
    """GPU 加速管理"""

    def __init__(self):
        self.gpu_info = None
        self._detection_done = False
        self._last_ai_packages_dir: Optional[str] = None
        self._detection_lock = asyncio.Lock()
        self._installing = False  # 安装状态追踪

    async def _detect_gpu(self):
        """检测GPU硬件（异步）"""
        if self._detection_done:
            return

        async with self._detection_lock:
            if self._detection_done:  # 双重检查
                return

            try:
                # 在线程池中检测（避免阻塞）
                check_nvidia = self._check_nvidia_gpu_sync  # 保存引用

                def _sync_detect():
                    try:
                        try:
                            from importlib.metadata import version as get_version, PackageNotFoundError
                        except ImportError:
                            from importlib_metadata import version as get_version, PackageNotFoundError

                        ai_packages_dir = None
                        try:
                            from src.core.tool_manager import AI_PACKAGES_DIR as _AI_PACKAGES_DIR
                            ai_packages_dir = _AI_PACKAGES_DIR
                        except Exception:
                            ai_packages_dir = None

                        if ai_packages_dir:
                            try:
                                if str(ai_packages_dir) not in sys.path:
                                    sys.path.insert(0, str(ai_packages_dir))
                            except Exception:
                                pass

                        try:
                            get_version("torch")
                        except PackageNotFoundError:
                            return {
                                "available": check_nvidia(),
                                "enabled": False,
                                "reason": "PyTorch not installed"
                            }

                        python_exe = sys.executable
                        if getattr(sys, 'frozen', False):
                            base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent / '_internal'
                            embedded_python = base_path / 'python' / 'python.exe'
                            if embedded_python.exists():
                                python_exe = str(embedded_python)

                        env = os.environ.copy()
                        try:
                            if ai_packages_dir:
                                existing_pythonpath = env.get("PYTHONPATH", "")
                                env["PYTHONPATH"] = str(ai_packages_dir) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
                        except Exception:
                            pass

                        code = (
                            'import json, torch; '
                            'data={'
                            '"cuda": bool(torch.cuda.is_available()),'
                            '"device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'
                            '"device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,'
                            '"cuda_version": getattr(torch.version, "cuda", None)'
                            '}; '
                            'print(json.dumps(data))'
                        )

                        kwargs = {
                            'capture_output': True,
                            'text': True,
                            'env': env,
                            'timeout': 15,
                        }
                        if sys.platform == 'win32' and hasattr(subprocess, 'CREATE_NO_WINDOW'):
                            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

                        proc = subprocess.run([python_exe, '-c', code], **kwargs)
                        if proc.returncode != 0:
                            return {
                                "available": check_nvidia(),
                                "enabled": False,
                                "reason": (proc.stderr or proc.stdout or "Failed to run torch probe")[:200]
                            }

                        try:
                            data = json.loads((proc.stdout or '').strip() or '{}')
                        except Exception:
                            data = {}

                        if data.get("cuda"):
                            return {
                                "available": True,
                                "device_name": data.get("device_name"),
                                "device_count": data.get("device_count"),
                                "cuda_version": data.get("cuda_version"),
                                "enabled": True
                            }

                        return {
                            "available": check_nvidia(),
                            "enabled": False,
                            "reason": "CUDA not available (torch installed but no GPU)"
                        }

                    except Exception as e:
                        return {
                            "available": check_nvidia(),
                            "enabled": False,
                            "reason": f"Detection failed: {str(e)}"
                        }

                self.gpu_info = await asyncio.to_thread(_sync_detect)

                if self.gpu_info.get("enabled"):
                    logger.info(f"GPU detected: {self.gpu_info.get('device_name')}")

                self._detection_done = True

            except Exception as e:
                logger.error(f"GPU detection failed: {e}")
                self.gpu_info = {
                    "available": False,
                    "enabled": False,
                    "reason": f"Detection failed: {str(e)}"
                }
                self._detection_done = True

    def _check_nvidia_gpu_sync(self) -> bool:
        """检查是否有NVIDIA GPU（不依赖torch，同步版本）"""
        try:
            if sys.platform == 'win32':
                # Windows: 使用 nvidia-smi
                kwargs = {
                    'capture_output': True,
                    'text': True,
                    'timeout': 2
                }
                # Windows 特定：隐藏控制台窗口
                if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                    **kwargs
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
            else:
                # Linux/Mac: 检查 nvidia-smi
                result = subprocess.run(
                    ['which', 'nvidia-smi'],
                    capture_output=True,
                    timeout=2
                )
                return result.returncode == 0
        except Exception as e:
            logger.debug(f"GPU detection failed: {e}")

        return False

    async def get_status(self) -> Dict:
        """获取GPU状态（异步）"""
        try:
            from src.core.tool_manager import AI_PACKAGES_DIR

            current_ai_packages_dir = str(AI_PACKAGES_DIR)
            if current_ai_packages_dir and current_ai_packages_dir != self._last_ai_packages_dir:
                self._last_ai_packages_dir = current_ai_packages_dir
                self._detection_done = False
        except Exception:
            pass

        # 确保检测已完成
        if not self._detection_done:
            await self._detect_gpu()

        # 提供默认值
        if not self.gpu_info:
            self.gpu_info = {
                "available": False,
                "enabled": False,
                "reason": "Detection not completed"
            }

        status = {
            "gpu_available": self.gpu_info.get("available", False),
            "gpu_enabled": self.gpu_info.get("enabled", False),
            "device_name": self.gpu_info.get("device_name"),
            "cuda_version": self.gpu_info.get("cuda_version"),
            "can_install": False,
            "install_guide": None,
            "installing": self._installing  # 添加安装状态
        }

        # 如果有GPU但未启用，提供安装指导
        if status["gpu_available"] and not status["gpu_enabled"]:
            status["can_install"] = True
            status["install_guide"] = self._get_install_guide()

        return status

    def _get_install_guide(self) -> Dict:
        """生成安装指导"""
        guide = {
            "title": "GPU 加速插件安装",
            "description": "检测到NVIDIA GPU，安装GPU加速可提升字幕处理速度5-10倍",
            "benefits": [
                "处理速度提升 5-10 倍",
                "78分钟视频从 40分钟 缩短到 5分钟",
                "更流畅的体验"
            ],
            "requirements": [
                "NVIDIA GPU (已检测到 ✓)",
                "NVIDIA 驱动程序 (请自行安装)",
                "约 3GB 磁盘空间"
            ],
            "steps": [
                {
                    "step": 1,
                    "title": "下载 GPU 加速包",
                    "description": "点击下载按钮，软件将自动下载并安装",
                    "action": "download_gpu_package"
                },
                {
                    "step": 2,
                    "title": "安装",
                    "description": "安装过程需要 5-10 分钟",
                    "action": "install_gpu_package"
                },
                {
                    "step": 3,
                    "title": "重启软件",
                    "description": "安装完成后重启软件生效",
                    "action": "restart_app"
                }
            ],
            "manual_install": {
                "title": "手动安装（高级用户）",
                "command": self._get_install_command(),
                "note": "在命令行中运行此命令"
            }
        }

        return guide

    def _get_install_command(self) -> str:
        """获取安装命令"""
        python_exe = sys.executable

        # 检测CUDA版本（简化版，实际应该检测驱动版本）
        cuda_version = "cu118"  # 默认CUDA 11.8

        cmd = f'"{python_exe}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/{cuda_version}'

        return cmd

    async def install_gpu_package(self, progress_callback=None) -> Dict:
        """安装GPU加速包"""
        self._installing = True

        try:
            if progress_callback:
                await progress_callback(0, "开始安装 GPU 加速包...")

            if not self._detection_done:
                await self._detect_gpu()

            if not (self.gpu_info and self.gpu_info.get("available")):
                return {"success": False, "error": "未检测到 NVIDIA GPU，无法安装 GPU 加速包"}

            # 获取正确的 Python 解释器路径（打包环境优先使用嵌入式 Python）
            python_exe = sys.executable
            if getattr(sys, 'frozen', False):
                base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent / '_internal'
                embedded_python = base_path / 'python' / 'python.exe'
                if embedded_python.exists():
                    python_exe = str(embedded_python)
                    logger.info(f"[GPU Install] Found embedded Python: {python_exe}")
                else:
                    return {
                        "success": False,
                        "error": f"未找到嵌入式 Python\n\n预期路径: {embedded_python}\n\n请重新安装应用"
                    }

            from src.core.tool_manager import AI_PACKAGES_DIR

            # 根据检测到的 CUDA 版本选择 PyTorch CUDA 版本
            detected_cuda = self.gpu_info.get("cuda_version") if self.gpu_info else None
            cuda_major = None
            if detected_cuda:
                try:
                    cuda_major = int(str(detected_cuda).split('.')[0])
                except Exception:
                    cuda_major = None

            if cuda_major is not None and cuda_major >= 12:
                cuda_version = "cu121"
            elif cuda_major == 11:
                cuda_version = "cu118"
            else:
                cuda_version = "cu118"

            logger.info(f"Detected CUDA {detected_cuda}, using PyTorch with {cuda_version}")

            if progress_callback:
                await progress_callback(10, f"下载 PyTorch ({cuda_version})，请耐心等待...")

            torch_cmd = [
                python_exe, '-m', 'pip', 'install',
                '--target', str(AI_PACKAGES_DIR),
                '--upgrade',
                '--no-warn-script-location',
                '--progress-bar', 'on',  # Enable progress bar to get download output
                '--default-timeout=600',  # Increase timeout for large downloads
                '-v',
                # 指定版本号确保从镜像下载CUDA版本（镜像最高到2.5.1）
                'torch==2.5.1', 'torchvision==0.20.1', 'torchaudio==2.5.1',
                # 使用阿里云镜像的 find-links 服务（-f 参数而非 --index-url）
                '-f', f'https://mirrors.aliyun.com/pytorch-wheels/{cuda_version}/',
                '--retries', '5',
                '--no-cache-dir',  # 强制从源下载，避免使用缓存的旧版本
            ]

            process = await asyncio.create_subprocess_exec(
                *torch_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            output_lines: list[str] = []
            current_progress = 10
            loop = asyncio.get_running_loop()
            last_output_time = loop.time()

            async def read_output():
                nonlocal current_progress, last_output_time
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break

                    line_text = line.decode('utf-8', errors='ignore').strip()
                    if not line_text:
                        continue

                    output_lines.append(line_text)
                    last_output_time = loop.time()
                    logger.info(f"[GPU Install] {line_text}")

                    lower_text = line_text.lower()
                    if 'successfully installed' in lower_text:
                        current_progress = 95
                        if progress_callback:
                            await progress_callback(95, "PyTorch 安装完成！")
                    elif any(k in lower_text for k in ['downloading', 'collecting', 'obtaining', 'fetching', 'receiving']):
                        current_progress = min(current_progress + 2, 60)
                        if progress_callback:
                            await progress_callback(current_progress, "下载 PyTorch 依赖包...")
                    elif any(k in lower_text for k in ['installing', 'building', 'processing', 'preparing']):
                        current_progress = min(max(current_progress, 60) + 2, 95)
                        if progress_callback:
                            await progress_callback(current_progress, "安装 PyTorch...")

            async def heartbeat():
                nonlocal last_output_time
                start_time = loop.time()
                download_started = False
                while process.returncode is None:
                    await asyncio.sleep(10)
                    if process.returncode is not None:
                        break

                    elapsed = int(loop.time() - start_time)
                    time_since_output = int(loop.time() - last_output_time)

                    # Check if we've seen download starting
                    if current_progress >= 60:
                        download_started = True

                    # 下载大文件（如 PyTorch CUDA 版本 2.8GB）可能需要很长时间且无输出
                    # 在下载阶段（progress >= 60）使用更长的超时：20分钟
                    # 在依赖收集阶段使用较短超时：10分钟
                    timeout_seconds = 1200 if download_started else 600

                    if time_since_output >= timeout_seconds:
                        timeout_minutes = timeout_seconds // 60
                        logger.error(f"[GPU Install] No output for {timeout_minutes} minutes, killing process")
                        process.kill()
                        return

                    if progress_callback:
                        if time_since_output > 60:
                            await progress_callback(current_progress, f"正在下载大文件... (已等待{elapsed}s, {time_since_output}s无输出)")
                        else:
                            await progress_callback(current_progress, f"正在安装 GPU 加速包... (已等待{elapsed}s)")

            try:
                await asyncio.wait_for(
                    asyncio.gather(read_output(), heartbeat(), process.wait()),
                    timeout=1800  # 30 minutes total timeout for large CUDA downloads
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": "GPU 加速包安装超时（超过30分钟）\n\n可能原因：网络速度太慢或被防火墙/代理拦截"
                }

            if process.returncode != 0:
                error_output = '\n'.join(output_lines[-20:])
                logger.error(f"GPU package installation failed: {error_output}")
                return {
                    "success": False,
                    "error": f"GPU 加速包安装失败\n\n{error_output[:300]}"
                }

            # 重新检测 GPU（异步）
            self._detection_done = False
            await self._detect_gpu()

            if progress_callback:
                await progress_callback(100, "安装成功！请重启软件")

            return {
                "success": True,
                "message": "GPU 加速包安装成功，请重启软件"
            }

        except Exception as e:
            logger.error(f"Failed to install GPU package: {e}")
            return {"success": False, "error": f"安装失败: {str(e)}"}
        finally:
            self._installing = False


# 全局实例
_gpu_manager = None

def get_gpu_manager() -> GPUManager:
    """获取 GPU 管理器单例"""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUManager()
    return _gpu_manager
