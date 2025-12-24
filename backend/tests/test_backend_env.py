"""测试后端运行环境"""
import sys
import os

print("=" * 60)
print("后端运行环境检查")
print("=" * 60)

print(f"\nPython 可执行文件: {sys.executable}")
print(f"Python 版本: {sys.version}")
print(f"当前工作目录: {os.getcwd()}")

# 检查是否在虚拟环境中
in_venv = hasattr(sys, 'real_prefix') or (
    hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
)
print(f"\n是否在虚拟环境: {in_venv}")
print(f"sys.prefix: {sys.prefix}")
if hasattr(sys, 'base_prefix'):
    print(f"sys.base_prefix: {sys.base_prefix}")

# 检查关键包
print("\n" + "=" * 60)
print("关键包检查")
print("=" * 60)

packages = ['torch', 'ctranslate2', 'faster_whisper', 'fastapi']
for pkg in packages:
    try:
        module = __import__(pkg)
        version = getattr(module, '__version__', 'Unknown')
        location = getattr(module, '__file__', 'Unknown')
        print(f"\n✓ {pkg}:")
        print(f"  版本: {version}")
        print(f"  位置: {location}")
    except ImportError:
        print(f"\n✗ {pkg}: 未安装")

# 如果 torch 存在，检查 CUDA
print("\n" + "=" * 60)
print("CUDA 检查")
print("=" * 60)
try:
    import torch
    print(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA 版本: {torch.version.cuda}")
        print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"CUDA 检查失败: {e}")
