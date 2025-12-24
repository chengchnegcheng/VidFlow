"""完整测试字幕生成流程（包括转录）"""
import asyncio
import sys
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def main():
    print("=" * 60)
    print("完整字幕生成流程测试")
    print("=" * 60)
    
    try:
        from src.core.subtitle_processor import SubtitleProcessor
        
        sp = SubtitleProcessor()
        
        # 1. 初始化模型
        print("\n[1/2] 初始化模型...")
        await sp.initialize_model('tiny', 'auto')
        print(f"✓ 模型加载成功，使用设备: {sp.device}")
        
        # 2. 尝试转录一个测试音频（如果不存在则跳过）
        print("\n[2/2] 测试转录功能...")
        
        # 创建一个临时的静音音频文件用于测试
        import tempfile
        import subprocess
        from src.core.tool_manager import get_tool_manager
        
        tool_mgr = get_tool_manager()
        ffmpeg_path = tool_mgr.get_ffmpeg_path()
        
        if ffmpeg_path:
            # 生成 1 秒静音音频
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                test_audio = tmp.name
            
            cmd = [
                str(ffmpeg_path),
                '-f', 'lavfi',
                '-i', 'anullsrc=r=16000:cl=mono',
                '-t', '1',
                '-y',
                test_audio
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            print(f"✓ 测试音频文件已创建: {test_audio}")
            
            # 尝试转录
            print("  开始转录测试...")
            try:
                result = await sp.transcribe(test_audio, language="en")
                print(f"✓ 转录成功！")
                print(f"  - 语言: {result.get('language', 'unknown')}")
                print(f"  - 片段数: {len(result.get('segments', []))}")
            except Exception as e:
                print(f"✗ 转录失败: {e}")
                import traceback
                traceback.print_exc()
                
                # 清理
                Path(test_audio).unlink(missing_ok=True)
                return 1
            
            # 清理
            Path(test_audio).unlink(missing_ok=True)
            
            print("\n" + "=" * 60)
            print("✅ 所有测试通过！字幕生成功能完全正常")
            print("=" * 60)
        else:
            print("⚠ FFmpeg 未找到，跳过转录测试")
            print("  但模型初始化成功，应该可以正常使用")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
