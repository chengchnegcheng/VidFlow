"""检查 GPU 状态"""
import sys
from pathlib import Path

# 设置 AI 包路径
AI_PACKAGES_DIR = Path(r"D:\Coding Project\VidFlow\VidFlow\backend\data\ai_packages_1768110313110_38140")
if AI_PACKAGES_DIR.exists():
    sys.path.insert(0, str(AI_PACKAGES_DIR))

print("=" * 50)
print("GPU 检查")
print("=" * 50)

try:
    import torch
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA 版本: {torch.version.cuda}")
        print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
        print(f"GPU 数量: {torch.cuda.device_count()}")
except Exception as e:
    print(f"PyTorch 错误: {e}")

try:
    import ctranslate2
    print(f"\nctranslate2 版本: {ctranslate2.__version__}")
    print(f"支持的设备: {ctranslate2.get_supported_compute_types('cuda')}")
except Exception as e:
    print(f"ctranslate2 错误: {e}")

try:
    import faster_whisper
    print(f"\nfaster_whisper 已导入")
except Exception as e:
    print(f"faster_whisper 错误: {e}")
