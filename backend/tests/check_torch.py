import torch

print(f"PyTorch 版本: {torch.__version__}")
print(f"CUDA 是否可用: {torch.cuda.is_available()}")
print(f"PyTorch 编译使用的 CUDA 版本: {torch.version.cuda}")

if torch.cuda.is_available():
    print(f"检测到的 GPU 数量: {torch.cuda.device_count()}")
    print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
