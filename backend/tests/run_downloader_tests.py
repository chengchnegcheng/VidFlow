"""
下载器测试运行脚本
运行所有下载器相关的单元测试和集成测试
"""
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_unit_tests():
    """运行单元测试"""
    print("=" * 60)
    print("运行下载器单元测试...")
    print("=" * 60)

    args = [
        'tests/test_core/test_downloader_new.py',
        '-v',
        '-m', 'unit',
        '--tb=short',
        '--color=yes',
        '-p', 'no:warnings'
    ]

    return pytest.main(args)


def run_integration_tests():
    """运行集成测试（需要网络）"""
    print("\n" + "=" * 60)
    print("运行下载器集成测试...")
    print("=" * 60)
    print("注意：集成测试需要网络连接，已跳过")
    print("=" * 60)

    # 集成测试默认跳过，需要手动启用
    args = [
        'tests/test_core/test_downloader_new.py',
        '-v',
        '-m', 'integration',
        '--tb=short',
        '--color=yes'
    ]

    # return pytest.main(args)
    return 0  # 跳过集成测试


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("VidFlow 下载器测试套件")
    print("=" * 60)

    # 运行单元测试
    unit_result = run_unit_tests()

    if unit_result == 0:
        print("\n✅ 单元测试全部通过！")
    else:
        print(f"\n❌ 单元测试失败 (退出码: {unit_result})")
        return unit_result

    # 运行集成测试
    integration_result = run_integration_tests()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"单元测试: {'✅ 通过' if unit_result == 0 else '❌ 失败'}")
    print(f"集成测试: {'⏭️  已跳过' if integration_result == 0 else '❌ 失败'}")
    print("=" * 60)

    return unit_result


def run_quick_test():
    """快速测试（只测试核心功能）"""
    print("=" * 60)
    print("快速测试模式")
    print("=" * 60)

    args = [
        'tests/test_core/test_downloader_new.py',
        '-v',
        '-k', 'test_supports_url or test_cache_initialization or test_get_downloader',
        '--tb=line',
        '--color=yes',
        '-p', 'no:warnings'
    ]

    return pytest.main(args)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='VidFlow 下载器测试运行器')
    parser.add_argument(
        '--mode',
        choices=['all', 'unit', 'integration', 'quick'],
        default='all',
        help='测试模式 (默认: all)'
    )

    args = parser.parse_args()

    if args.mode == 'all':
        exit_code = run_all_tests()
    elif args.mode == 'unit':
        exit_code = run_unit_tests()
    elif args.mode == 'integration':
        exit_code = run_integration_tests()
    elif args.mode == 'quick':
        exit_code = run_quick_test()

    sys.exit(exit_code)
