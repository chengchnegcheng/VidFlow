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
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from importlib.metadata import version as get_version, PackageNotFoundError

logger = logging.getLogger(__name__)

class SubtitleProcessor:
    """字幕处理器"""
    
    def __init__(self):
        self.model = None
        self.model_name = "base"
        self.device = "cpu"
        
    async def initialize_model(self, model_name: str = "base", device: str = "auto"):
        """初始化 Whisper 模型"""
        try:
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

            import faster_whisper

            # 自动检测设备
            if device == "auto":
                device = "cpu"
                try:
                    try:
                        ctranslate2_version = get_version("ctranslate2")
                    except PackageNotFoundError:
                        ctranslate2_version = "unknown"

                    python_exe: Optional[str] = sys.executable
                    if getattr(sys, 'frozen', False):
                        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent / '_internal'
                        embedded_python = base_path / 'python' / 'python.exe'
                        if embedded_python.exists():
                            python_exe = str(embedded_python)
                        else:
                            python_exe = None

                    from src.core.tool_manager import AI_PACKAGES_DIR

                    env = os.environ.copy()
                    existing_pythonpath = env.get("PYTHONPATH", "")
                    env["PYTHONPATH"] = str(AI_PACKAGES_DIR) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
                    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

                    code = (
                        'import json, torch; '
                        'print(json.dumps({'
                        '"cuda": bool(torch.cuda.is_available()),'
                        '"cuda_version": getattr(torch.version, "cuda", None)'
                        '}))'
                    )

                    if not python_exe:
                        raise RuntimeError("embedded python.exe not found for torch probe")

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
                        if stderr_text:
                            logger.debug(f"torch probe failed: {stderr_text[:200]}")
                        device = "cpu"
                    else:
                        try:
                            data = json.loads(stdout.decode('utf-8', errors='ignore').strip() or '{}')
                        except Exception:
                            data = {}

                        cuda_available = bool(data.get("cuda"))
                        cuda_version = data.get("cuda_version")
                        logger.info(f"System CUDA version: {cuda_version}")
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
                    logger.debug(f"Device auto-detect failed, falling back to CPU: {e}")
                    device = "cpu"
            
            logger.info(f"Loading Whisper model: {model_name} on {device}")
            
            # 尝试加载模型，如果 CUDA 失败则自动回退到 CPU
            try:
                # 在线程池中加载模型（避免阻塞）
                self.model = await asyncio.to_thread(
                    faster_whisper.WhisperModel,
                    model_name,
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
                    
                    # 重试 CPU 模式
                    self.model = await asyncio.to_thread(
                        faster_whisper.WhisperModel,
                        model_name,
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
            
        except ImportError:
            logger.error("faster-whisper not installed")
            raise RuntimeError("请先安装 faster-whisper: pip install faster-whisper")
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
                # 如果路径记录失败，使用安全的方式
                logger.info(f"Transcribing audio file...")
            
            # 转录参数
            transcribe_options = {
                "language": language if language != "auto" else None,
                "beam_size": 3,  # 降低到3，速度提升约30%
                "best_of": 3,    # 降低到3
                "temperature": 0.0,
            }
            
            # 在线程池中执行转录
            segments, info = await asyncio.to_thread(
                self.model.transcribe,
                audio_path,
                **transcribe_options
            )
            
            # 收集结果
            results = []
            duration = getattr(info, "duration", None) if info else None
            for segment in segments:
                result = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                }
                results.append(result)
                
                # 进度回调：按时间占比估算
                if progress_callback and duration:
                    progress = 30.0 + min((segment.end / duration) * 50.0, 50.0)
                    await progress_callback(progress, f"识别中… {segment.end:.1f}/{duration:.1f}s")
            
            logger.info(f"Transcription completed: {len(results)} segments")
            
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
    
    async def _translate_srt_file(self, srt_path: Path, target_lang: str) -> str:
        """翻译 SRT 文件内容（支持多引擎自动切换）"""
        try:
            from deep_translator import GoogleTranslator, MyMemoryTranslator
            
            # 语言代码映射
            lang_map = {
                'zh': 'zh-CN',
                'en': 'en',
                'ja': 'ja',
                'ko': 'ko',
                'es': 'es',
                'fr': 'fr',
                'de': 'de',
                'ru': 'ru'
            }
            target_code = lang_map.get(target_lang, target_lang)
            
            # 尝试多个翻译引擎（自动回退）
            translators = [
                (GoogleTranslator(source='auto', target=target_code), 'Google Translate'),
                (MyMemoryTranslator(source='auto', target=target_code), 'MyMemory')
            ]
            
            # 测试哪个翻译引擎可用
            working_translator = None
            translator_name = None
            
            for trans, name in translators:
                try:
                    # 测试翻译
                    test_result = trans.translate("Hello")
                    if test_result:
                        working_translator = trans
                        translator_name = name
                        logger.info(f"Using {name} for translation")
                        break
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
            
            translated_blocks = []
            
            for match in pattern.finditer(content):
                index = match.group(1)
                timestamp = match.group(2)
                text = match.group(3).strip()
                
                # 翻译文本（分段处理，避免超长）
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
                                    translated_lines.append(translated)
                                else:
                                    # 超长文本分块翻译
                                    chunks = [line[i:i+4000] for i in range(0, len(line), 4000)]
                                    translated_chunks = [working_translator.translate(chunk) for chunk in chunks]
                                    translated_lines.append(''.join(translated_chunks))
                        
                        translated_text = '\n'.join(translated_lines)
                    except Exception as e:
                        logger.warning(f"Translation failed for segment {index}, using original: {e}")
                        translated_text = text
                else:
                    translated_text = text
                
                # 重建 SRT 块
                block = f"{index}\n{timestamp}\n{translated_text}\n"
                translated_blocks.append(block)
            
            # 组合所有块
            result = '\n'.join(translated_blocks)
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
                    await progress_callback(25.0, "正在加载模型...")
                await self.initialize_model(model_name)
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
            
            # 4. 生成字幕文件 (80-95%)
            output_files = []
            
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
            
            # 5. 翻译（如果需要）(95-100 以内)
            for target_lang in target_languages:
                if target_lang != detected_language:
                    logger.info(f"Translating subtitles to {target_lang}...")
                    try:
                        # 读取原始 SRT 文件进行翻译
                        srt_file = output_dir / f"{video_path.stem}.{detected_language}.srt"
                        if srt_file.exists():
                            translated_content = await self._translate_srt_file(
                                srt_file, 
                                target_lang
                            )
                            # 保存翻译后的文件
                            translated_file = output_dir / f"{video_path.stem}.{target_lang}.srt"
                            translated_file.write_text(translated_content, encoding='utf-8')
                            output_files.append(str(translated_file))
                            logger.info(f"Translation to {target_lang} completed")
                    except Exception as e:
                        logger.error(f"Translation to {target_lang} failed: {e}")
            
            # 6. 清理临时文件
            if audio_path.exists():
                audio_path.unlink()
            
            return {
                "success": True,
                "output_files": output_files,
                "language": detected_language,
                "segments_count": len(segments),
                "duration": result.get('duration', 0)
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
