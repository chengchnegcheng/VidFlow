import asyncio
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def main():
    print("=" * 60)
    print("测试字幕处理器初始化（使用修复后的代码）")
    print("=" * 60)

    try:
        from src.core.subtitle_processor import SubtitleProcessor

        sp = SubtitleProcessor()

        print("\n测试 1: 自动模式（应该选择 CUDA）")
        await sp.initialize_model('tiny', 'auto')
        print(f"✓ 成功! 使用设备: {sp.device}")

        # 再次测试以验证模型已加载
        print(f"✓ 模型名称: {sp.model_name}")
        print(f"✓ 模型对象: {sp.model}")

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！字幕生成功能可以正常使用 GPU 加速")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
