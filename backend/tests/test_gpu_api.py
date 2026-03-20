"""测试 GPU 状态 API"""
import asyncio
import sys

async def test_gpu_api():
    """测试 GPU 检测 API 逻辑"""
    print("=" * 60)
    print("测试 GPU 状态检测 API")
    print("=" * 60)

    gpu_info = {
        "available": False,
        "gpu_name": None,
        "cuda_available": False,
        "cuda_version": None,
        "ctranslate2_version": None,
        "compatible": False,
        "status": "未检测到 GPU",
        "recommendation": None
    }

    print("\n步骤 1: 尝试导入 torch...")
    try:
        import torch
        print(f"✓ torch 导入成功: {torch.__version__}")

        print("\n步骤 2: 检查 CUDA 是否可用...")
        if torch.cuda.is_available():
            print("✓ CUDA 可用")
            gpu_info["cuda_available"] = True
            gpu_info["cuda_version"] = torch.version.cuda
            print(f"  CUDA 版本: {gpu_info['cuda_version']}")

            print("\n步骤 3: 获取 GPU 名称...")
            try:
                gpu_name = torch.cuda.get_device_name(0)
                gpu_info["gpu_name"] = gpu_name
                gpu_info["available"] = True
                print(f"✓ GPU 名称: {gpu_name}")
            except Exception as e:
                print(f"✗ 获取 GPU 名称失败: {e}")

            print("\n步骤 4: 检查 ctranslate2...")
            try:
                import ctranslate2
                gpu_info["ctranslate2_version"] = ctranslate2.__version__
                print(f"✓ ctranslate2 版本: {ctranslate2.__version__}")

                cuda_major = float(gpu_info["cuda_version"].split('.')[0]) if gpu_info["cuda_version"] else 0
                print(f"  CUDA 主版本: {cuda_major}")

                if cuda_major >= 12:
                    gpu_info["compatible"] = True
                    gpu_info["status"] = "已启用"
                    gpu_info["recommendation"] = "GPU 加速已启用，AI 字幕生成速度提升 5-10 倍"
                    print("✓ 版本兼容")
                else:
                    gpu_info["status"] = "CUDA 版本不兼容"
                    gpu_info["recommendation"] = f"ctranslate2 {ctranslate2.__version__} 需要 CUDA 12.x，当前为 CUDA {gpu_info['cuda_version']}。应用将自动使用 CPU 模式。若需 GPU 加速，请升级到 CUDA Toolkit 12.x"
                    print("⚠ CUDA 版本过低")
            except ImportError as e:
                print(f"✗ ctranslate2 未安装: {e}")
                gpu_info["status"] = "ctranslate2 未安装"
                gpu_info["recommendation"] = "需要安装 faster-whisper 才能使用 AI 字幕功能"
        else:
            print("✗ CUDA 不可用")
            gpu_info["status"] = "CUDA 不可用"
            gpu_info["recommendation"] = "未检测到 NVIDIA GPU 或 CUDA 驱动未安装。应用将使用 CPU 模式"

    except ImportError as e:
        print(f"✗ torch 导入失败: {e}")
        gpu_info["status"] = "PyTorch 未安装"
        gpu_info["recommendation"] = "需要安装 PyTorch 才能检测 GPU 状态"

    print("\n" + "=" * 60)
    print("最终 GPU 信息:")
    print("=" * 60)
    for key, value in gpu_info.items():
        print(f"{key}: {value}")

    return gpu_info

if __name__ == "__main__":
    asyncio.run(test_gpu_api())
