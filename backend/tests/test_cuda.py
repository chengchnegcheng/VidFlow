import sys
import os

# 添加 AI packages 路径
ai_packages_dir = r"D:\Coding Project\VidFlow\VidFlow-Desktop\backend\data"
# 查找最新的 ai_packages 目录
ai_dirs = [d for d in os.listdir(ai_packages_dir) if d.startswith('ai_packages_')]
if ai_dirs:
    ai_dirs.sort(reverse=True)  # 按时间戳排序，最新的在前
    latest_ai_dir = os.path.join(ai_packages_dir, ai_dirs[0])
    sys.path.insert(0, latest_ai_dir)
    print(f"使用 AI packages 目录: {latest_ai_dir}\n")

try:
    import torch

    print("=== PyTorch 环境检查 ===")
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"PyTorch 安装路径: {torch.__file__}")
    print(f"CUDA 是否可用: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"\n=== CUDA 信息 ===")
        print(f"CUDA 版本: {torch.version.cuda}")
        print(f"cuDNN 版本: {torch.backends.cudnn.version()}")
        print(f"GPU 数量: {torch.cuda.device_count()}")
        print(f"当前 GPU: {torch.cuda.current_device()}")
        print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
        print(f"GPU 显存总量: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

        print(f"\n=== GPU 计算测试 ===")
        # 测试GPU计算
        x = torch.tensor([1.0, 2.0, 3.0])
        x_gpu = x.cuda()
        result = x_gpu * 2
        print(f"输入: {x}")
        print(f"GPU计算结果: {result.cpu()}")
        print(f"计算设备: {result.device}")

        print("\n✅ GPU 加速完全可用！")
    else:
        print("\n⚠️ CUDA 不可用")
        print("可能原因:")
        print("1. 安装的是 CPU 版本的 PyTorch")
        print("2. CUDA 运行时库未正确加载")
        print("3. Python 环境路径配置问题")

except ImportError as e:
    print(f"❌ 无法导入 torch: {e}")
    print("\nPython 搜索路径:")
    for p in sys.path:
        print(f"  {p}")
