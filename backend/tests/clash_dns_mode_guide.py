"""
Clash DNS 模式配置指南

帮助用户将 Clash 的 DNS 模式从 fake-ip 改为 redir-host
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    """主函数"""
    print("=" * 70)
    print("  Clash DNS 模式配置指南")
    print("=" * 70)
    
    print("\n当前问题：")
    print("  Clash 使用 fake-ip 模式，导致无法获取真实域名和完整视频 URL")
    
    print("\n解决方案：")
    print("  将 DNS 模式改为 redir-host，这样可以：")
    print("  ✓ 获取真实的域名（SNI）")
    print("  ✓ 获取完整的视频下载 URL")
    print("  ✓ 提高视频捕获的准确性")
    
    print_section("配置步骤")
    
    print("\n【方法 1】使用 Clash Verge 界面修改（推荐）")
    print("\n1. 打开 Clash Verge")
    print("2. 点击左侧菜单的 \"配置\" 或 \"Profiles\"")
    print("3. 找到当前使用的配置文件")
    print("4. 点击 \"编辑\" 或 \"Edit\" 按钮")
    print("5. 找到 dns 配置部分，通常在文件开头")
    print("6. 修改配置：")
    
    print("\n   修改前（fake-ip 模式）：")
    print("   " + "-" * 66)
    print("""   dns:
     enable: true
     enhanced-mode: fake-ip
     fake-ip-range: 198.18.0.1/16
     nameserver:
       - 223.5.5.5
       - 119.29.29.29""")
    print("   " + "-" * 66)
    
    print("\n   修改后（redir-host 模式）：")
    print("   " + "-" * 66)
    print("""   dns:
     enable: true
     enhanced-mode: redir-host
     nameserver:
       - 223.5.5.5
       - 119.29.29.29""")
    print("   " + "-" * 66)
    
    print("\n7. 保存配置文件")
    print("8. 重新加载配置或重启 Clash Verge")
    
    print("\n" + "=" * 70)
    
    print("\n【方法 2】手动编辑配置文件")
    print("\n1. 找到 Clash 配置文件位置：")
    print("   - Clash Verge: %USERPROFILE%\\.config\\clash-verge\\profiles\\")
    print("   - Clash for Windows: %USERPROFILE%\\.config\\clash\\")
    
    print("\n2. 用文本编辑器打开配置文件（通常是 .yaml 或 .yml 文件）")
    
    print("\n3. 找到 dns 部分，修改 enhanced-mode：")
    print("   将 enhanced-mode: fake-ip")
    print("   改为 enhanced-mode: redir-host")
    
    print("\n4. 删除或注释掉 fake-ip-range 行（可选）")
    
    print("\n5. 保存文件")
    
    print("\n6. 重启 Clash 或重新加载配置")
    
    print_section("验证配置")
    
    print("\n修改完成后，运行以下命令验证：")
    print("  python tests/quick_capture_test.py")
    
    print("\n如果配置正确，你应该看到：")
    print("  ✓ 不再有 \"Detected fake IP\" 警告")
    print("  ✓ 能够检测到真实的域名（SNI）")
    print("  ✓ 能够获取完整的视频 URL")
    
    print_section("注意事项")
    
    print("\n1. redir-host 模式的优缺点：")
    print("   ✓ 优点：可以获取真实域名，兼容性更好")
    print("   ✗ 缺点：DNS 查询速度可能稍慢（通常感觉不到）")
    
    print("\n2. 如果修改后无法上网：")
    print("   - 检查 nameserver 配置是否正确")
    print("   - 尝试使用其他 DNS 服务器（如 8.8.8.8, 1.1.1.1）")
    print("   - 恢复原配置并重启 Clash")
    
    print("\n3. 保留原配置备份：")
    print("   - 修改前先复制一份配置文件")
    print("   - 如果出问题可以快速恢复")
    
    print("\n" + "=" * 70)
    print("\n配置完成后，请重新运行视频捕获测试")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
