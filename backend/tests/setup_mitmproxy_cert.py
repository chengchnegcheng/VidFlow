"""
mitmproxy 证书设置工具

帮助用户生成、导出和安装 mitmproxy CA 证书
"""

import sys
import os
import subprocess
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_mitmproxy():
    """检查 mitmproxy 是否已安装"""
    print_section("1. 检查 mitmproxy")
    
    try:
        result = subprocess.run(
            ["mitmdump", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✓ mitmproxy 已安装")
            print(f"  版本: {version}")
            return True
        else:
            print("✗ mitmproxy 未正确安装")
            return False
    except FileNotFoundError:
        print("✗ mitmproxy 未安装")
        print("\n安装方法:")
        print("  pip install mitmproxy")
        return False
    except Exception as e:
        print(f"✗ 检查失败: {e}")
        return False


def generate_cert():
    """生成 mitmproxy 证书"""
    print_section("2. 生成 mitmproxy 证书")
    
    # mitmproxy 证书目录
    cert_dir = Path.home() / ".mitmproxy"
    cert_file = cert_dir / "mitmproxy-ca-cert.pem"
    
    if cert_file.exists():
        print(f"✓ 证书已存在: {cert_file}")
        return cert_dir
    
    print("生成新证书...")
    print("这需要启动一次 mitmproxy 来自动生成证书")
    
    try:
        # 启动 mitmdump 并立即停止，这会生成证书
        print("\n正在启动 mitmdump（会自动停止）...")
        process = subprocess.Popen(
            ["mitmdump", "--set", "confdir=" + str(cert_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待 2 秒让它生成证书
        import time
        time.sleep(2)
        
        # 停止进程
        process.terminate()
        process.wait(timeout=5)
        
        if cert_file.exists():
            print(f"✓ 证书生成成功: {cert_file}")
            return cert_dir
        else:
            print("✗ 证书生成失败")
            return None
            
    except Exception as e:
        print(f"✗ 生成证书失败: {e}")
        return None


def export_cert_for_windows(cert_dir: Path):
    """导出适用于 Windows 的证书格式"""
    print_section("3. 导出 Windows 证书")
    
    pem_file = cert_dir / "mitmproxy-ca-cert.pem"
    cer_file = cert_dir / "mitmproxy-ca-cert.cer"
    
    if not pem_file.exists():
        print(f"✗ 证书文件不存在: {pem_file}")
        return None
    
    # 复制 PEM 为 CER（Windows 可以直接使用）
    try:
        import shutil
        shutil.copy(pem_file, cer_file)
        print(f"✓ 证书已导出: {cer_file}")
        return cer_file
    except Exception as e:
        print(f"✗ 导出失败: {e}")
        return None


def install_cert_guide(cer_file: Path):
    """显示证书安装指南"""
    print_section("4. 安装证书到系统")
    
    print("\n【自动安装】")
    print(f"\n运行以下命令以管理员身份安装证书：")
    print(f"  certutil -addstore -f \"ROOT\" \"{cer_file}\"")
    
    print("\n【手动安装】")
    print("\n1. 双击打开证书文件：")
    print(f"   {cer_file}")
    
    print("\n2. 在弹出的窗口中：")
    print("   - 点击 \"安装证书\"")
    print("   - 选择 \"本地计算机\"（需要管理员权限）")
    print("   - 点击 \"下一步\"")
    
    print("\n3. 选择证书存储位置：")
    print("   - 选择 \"将所有的证书都放入下列存储\"")
    print("   - 点击 \"浏览\"")
    print("   - 选择 \"受信任的根证书颁发机构\"")
    print("   - 点击 \"确定\"")
    
    print("\n4. 点击 \"下一步\"，然后 \"完成\"")
    
    print("\n5. 在安全警告中点击 \"是\"")


def auto_install_cert(cer_file: Path):
    """尝试自动安装证书"""
    print_section("5. 自动安装证书")
    
    try:
        # 检查是否有管理员权限
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        
        if not is_admin:
            print("⚠️  需要管理员权限才能自动安装证书")
            print("   请以管理员身份运行此脚本，或手动安装证书")
            return False
        
        print("正在安装证书到系统信任存储...")
        
        result = subprocess.run(
            ["certutil", "-addstore", "-f", "ROOT", str(cer_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✓ 证书安装成功！")
            return True
        else:
            print(f"✗ 安装失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ 自动安装失败: {e}")
        return False


def test_cert_installation():
    """测试证书是否已正确安装"""
    print_section("6. 验证证书安装")
    
    try:
        result = subprocess.run(
            ["certutil", "-store", "ROOT", "mitmproxy"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "mitmproxy" in result.stdout:
            print("✓ 证书已正确安装到系统信任存储")
            return True
        else:
            print("⚠️  未找到 mitmproxy 证书")
            return False
            
    except Exception as e:
        print(f"⚠️  验证失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("  mitmproxy 证书设置工具")
    print("=" * 70)
    print("\n这个工具会帮助你设置 mitmproxy CA 证书")
    print("安装证书后，mitmproxy 可以解密 HTTPS 流量\n")
    
    # 1. 检查 mitmproxy
    if not check_mitmproxy():
        print("\n请先安装 mitmproxy:")
        print("  pip install mitmproxy")
        return
    
    # 2. 生成证书
    cert_dir = generate_cert()
    if not cert_dir:
        print("\n✗ 证书生成失败，无法继续")
        return
    
    # 3. 导出证书
    cer_file = export_cert_for_windows(cert_dir)
    if not cer_file:
        print("\n✗ 证书导出失败，无法继续")
        return
    
    # 4. 显示安装指南
    install_cert_guide(cer_file)
    
    # 5. 询问是否自动安装
    print("\n" + "=" * 70)
    response = input("\n是否尝试自动安装证书？(需要管理员权限) [y/n]: ")
    
    if response.lower() == 'y':
        if auto_install_cert(cer_file):
            # 6. 验证安装
            test_cert_installation()
        else:
            print("\n自动安装失败，请按照上述指南手动安装")
    else:
        print("\n请按照上述指南手动安装证书")
    
    # 最终说明
    print_section("下一步")
    
    print("\n证书安装完成后：")
    print("  1. 重启微信（让微信加载新的系统证书）")
    print("  2. 运行测试脚本验证捕获功能：")
    print("     python tests/test_mitmproxy_capture.py")
    
    print("\n⚠️  重要提示：")
    print("  - 微信可能不信任自签名证书，即使安装到系统")
    print("  - 如果微信仍然无法连接，说明微信有证书固定（Certificate Pinning）")
    print("  - 这种情况下，只能通过关闭代理或使用其他方法")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
