import sys
import os

# Add AI packages directory
ai_packages_path = r"D:\Coding Project\VidFlow\VidFlow-Desktop\backend\data\ai_packages_1766253744802_23952"
sys.path.insert(0, ai_packages_path)

print(f"Using AI packages: {ai_packages_path}\n")

try:
    import torch

    print("=== PyTorch Environment Check ===")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"\n=== CUDA Information ===")
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"GPU Count: {torch.cuda.device_count()}")
        print(f"GPU Name: {torch.cuda.get_device_name(0)}")
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

        print(f"\n=== GPU Test ===")
        x = torch.tensor([1.0, 2.0, 3.0]).cuda()
        result = x * 2
        print(f"Input: [1.0, 2.0, 3.0]")
        print(f"Result: {result.cpu().tolist()}")
        print(f"Device: {result.device}")

        print("\nSUCCESS: GPU acceleration is working!")
    else:
        print("\nWARNING: CUDA is not available")
        print("This might be a CPU version of PyTorch")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
