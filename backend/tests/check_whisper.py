# -*- coding: utf-8 -*-
import sys
import os

# 设置 UTF-8 输出（兼容 Windows 控制台）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 检查 faster-whisper
try:
    import faster_whisper
    print(f"✓ faster-whisper 版本: {faster_whisper.__version__}")
except ImportError as e:
    print(f"✗ faster-whisper 未安装: {e}")

# 检查 ctranslate2（faster-whisper 的核心依赖）
try:
    import ctranslate2
    print(f"✓ ctranslate2 版本: {ctranslate2.__version__}")
except ImportError as e:
    print(f"✗ ctranslate2 未安装: {e}")

# 检查 torch
try:
    import torch
    print(f"✓ PyTorch 版本: {torch.__version__}")
    print(f"  - CUDA 编译版本: {torch.version.cuda}")
    print(f"  - CUDA 可用: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"✗ PyTorch 未安装: {e}")

# 尝试测试 faster-whisper 是否能初始化
print("\n测试 faster-whisper 初始化...")
try:
    from faster_whisper import WhisperModel
    print("尝试加载模型（CPU 模式）...")
    model = WhisperModel("tiny", device="cpu")
    print("✓ CPU 模式初始化成功")
except Exception as e:
    print(f"✗ 初始化失败: {e}")
