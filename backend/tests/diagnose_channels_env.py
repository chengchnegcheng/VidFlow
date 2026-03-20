#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信视频号下载功能环境诊断脚本

检测视频号下载功能所需的环境配置是否正确：
1. 微信进程是否运行
2. 系统代理是否配置
3. CA证书是否安装
4. 端口是否可用
5. QUIC阻断规则是否存在
6. 域名解析是否正常

运行方式: python diagnose_channels_env.py
"""

import os
import sys
import socket
import subprocess
import platform
import ctypes
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_header():
    """打印头部"""
    print("=" * 60)
    print("  VidFlow 微信视频号下载功能环境诊断")
    print("=" * 60)
    print()


def check_admin():
    """检查是否以管理员身份运行"""
    print("1. 检查管理员权限...")
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if is_admin:
            print("   [✓] 以管理员身份运行")
        else:
            print("   [✗] 未以管理员身份运行")
            print("       某些功能可能无法正常工作！")
        return is_admin
    except Exception:
        print("   [?] 无法检测管理员权限（可能不是Windows系统）")
        return False


def check_wechat_processes():
    """检查微信进程"""
    print("\n2. 检查微信进程...")
    try:
        import psutil
        wechat_names = ['wechat', 'wechatapp', 'wechatappex', 'weixin']
        found_processes = []

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                name = proc.info['name'].lower()
                for wechat_name in wechat_names:
                    if wechat_name in name:
                        found_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'exe': proc.info.get('exe', 'N/A')
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if found_processes:
            print(f"   [✓] 检测到 {len(found_processes)} 个微信相关进程:")
            for p in found_processes:
                print(f"       - {p['name']} (PID: {p['pid']})")
            return True
        else:
            print("   [✗] 未检测到微信进程")
            print("       请先启动微信！")
            return False

    except ImportError:
        print("   [?] psutil 未安装，无法检测进程")
        return None


def check_system_proxy():
    """检查系统代理设置"""
    print("\n3. 检查系统代理设置...")
    try:
        if platform.system() == 'Windows':
            import winreg

            # 读取代理设置
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")

            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")

            if proxy_enable:
                try:
                    proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                    print(f"   [✓] 系统代理已启用: {proxy_server}")

                    if '8888' in proxy_server:
                        print("       代理端口为 8888 (VidFlow 默认端口)")
                        return True
                    else:
                        print("       [!] 代理端口不是 8888")
                        return True
                except FileNotFoundError:
                    print("   [!] 代理已启用但未配置服务器地址")
                    return False
            else:
                print("   [✗] 系统代理未启用")
                print("       VidFlow 需要设置系统代理才能捕获微信流量")
                return False

            winreg.CloseKey(key)
        else:
            print("   [?] 非 Windows 系统，跳过代理检查")
            return None

    except Exception as e:
        print(f"   [?] 无法检查代理设置: {e}")
        return None


def check_port_8888():
    """检查端口 8888 是否可用或被 VidFlow 占用"""
    print("\n4. 检查端口 8888...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 8888))
        sock.close()

        if result == 0:
            print("   [✓] 端口 8888 已被占用（VidFlow 嗅探器可能正在运行）")
            return True
        else:
            print("   [?] 端口 8888 可用（VidFlow 嗅探器可能未启动）")
            return None
    except Exception as e:
        print(f"   [?] 无法检查端口: {e}")
        return None


def check_mitmproxy_cert():
    """检查 mitmproxy 证书"""
    print("\n5. 检查 mitmproxy CA 证书...")

    # 检查 mitmproxy 证书目录
    mitmproxy_dir = Path.home() / ".mitmproxy"
    cert_file = mitmproxy_dir / "mitmproxy-ca-cert.pem"

    if cert_file.exists():
        print(f"   [✓] mitmproxy 证书文件存在: {cert_file}")

        # 检查证书是否安装到系统
        if platform.system() == 'Windows':
            try:
                result = subprocess.run(
                    ['certutil', '-store', '-user', 'Root'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if 'mitmproxy' in result.stdout.lower():
                    print("   [✓] mitmproxy 证书已安装到用户受信任根证书")
                    return True
                else:
                    # 检查系统证书存储
                    result = subprocess.run(
                        ['certutil', '-store', 'Root'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if 'mitmproxy' in result.stdout.lower():
                        print("   [✓] mitmproxy 证书已安装到系统受信任根证书")
                        return True
                    else:
                        print("   [✗] mitmproxy 证书未安装到系统")
                        print("       请在 VidFlow 中安装证书")
                        return False
            except Exception as e:
                print(f"   [?] 无法检查证书安装状态: {e}")
                return None
    else:
        print(f"   [✗] mitmproxy 证书文件不存在")
        print(f"       预期位置: {cert_file}")
        return False


def check_quic_blocking():
    """检查 QUIC 阻断规则"""
    print("\n6. 检查 QUIC 阻断规则...")

    if platform.system() != 'Windows':
        print("   [?] 非 Windows 系统，跳过 QUIC 检查")
        return None

    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*QUIC*" -or $_.DisplayName -like "*UDP*443*" -or $_.DisplayName -like "*VidFlow*" } | Select-Object DisplayName,Enabled'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            print("   [✓] QUIC 阻断规则存在:")
            for line in result.stdout.strip().split('\n'):
                if line.strip() and not line.startswith('-'):
                    print(f"       {line.strip()}")
            return True
        else:
            print("   [?] 未找到 QUIC 阻断规则")
            print("       微信可能使用 QUIC 协议绕过代理")
            return False
    except Exception as e:
        print(f"   [?] 无法检查防火墙规则: {e}")
        return None


def check_domain_resolution():
    """检查视频号相关域名解析"""
    print("\n7. 检查视频号相关域名解析...")

    domains = [
        "finder.video.qq.com",
        "wxapp.tc.qq.com",
        "findermp.video.qq.com",
        "channels.weixin.qq.com",
    ]

    all_ok = True
    for domain in domains:
        try:
            ip = socket.gethostbyname(domain)
            print(f"   [✓] {domain} -> {ip}")
        except socket.gaierror:
            print(f"   [✗] {domain} 解析失败")
            all_ok = False

    return all_ok


def check_vidflow_dependencies():
    """检查 VidFlow 依赖"""
    print("\n8. 检查关键依赖...")

    dependencies = [
        ('mitmproxy', 'mitmproxy'),
        ('pydivert', 'WinDivert Python 绑定'),
        ('psutil', 'psutil'),
        ('aiohttp', 'aiohttp'),
        ('cryptography', 'cryptography'),
    ]

    all_ok = True
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"   [✓] {name}")
        except ImportError:
            print(f"   [✗] {name} 未安装")
            all_ok = False

    return all_ok


def print_recommendations():
    """打印建议"""
    print("\n" + "=" * 60)
    print("  诊断总结与建议")
    print("=" * 60)
    print()
    print("如果视频号下载功能不工作，请按以下步骤排查：")
    print()
    print("1. 确保以管理员身份运行 VidFlow")
    print("2. 在 VidFlow 中启动嗅探器")
    print("3. 确保 CA 证书已安装到系统受信任根证书")
    print("4. 重启微信（关闭后重新打开）")
    print("5. 在微信中打开视频号并播放视频")
    print()
    print("如果仍然无法工作：")
    print("- 检查是否有其他代理软件冲突（Clash, v2ray 等）")
    print("- 如使用代理软件，请将微信设为直连")
    print("- 查看 VidFlow 日志获取更多信息")


def main():
    """主函数"""
    print_header()

    results = {}
    results['admin'] = check_admin()
    results['wechat'] = check_wechat_processes()
    results['proxy'] = check_system_proxy()
    results['port'] = check_port_8888()
    results['cert'] = check_mitmproxy_cert()
    results['quic'] = check_quic_blocking()
    results['dns'] = check_domain_resolution()
    results['deps'] = check_vidflow_dependencies()

    print_recommendations()

    # 返回检查结果
    return results


if __name__ == "__main__":
    main()
