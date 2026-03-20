"""
诊断 Clash 代理配置和网络环境

检查：
1. Clash 进程是否运行
2. Clash API 是否可访问
3. DNS 模式（Fake-IP vs Redir-Host）
4. 微信进程是否运行
5. 网络连接状态
"""

import sys
import os
import json
import socket
import psutil
import requests
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_clash_process():
    """检查 Clash 进程"""
    print("\n=== 检查 Clash 进程 ===")
    
    clash_processes = []
    clash_names = ['clash', 'clash-verge', 'verge-mihomo', 'mihomo', 'clash-core', 'clash-meta']
    
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            name = proc.info['name']
            if name:
                name_lower = name.lower()
                for clash_name in clash_names:
                    if clash_name in name_lower:
                        clash_processes.append({
                            'pid': proc.info['pid'],
                            'name': name,
                            'exe': proc.info['exe'],
                            'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        })
                        break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if clash_processes:
        print(f"✓ 找到 {len(clash_processes)} 个 Clash 进程：")
        for proc in clash_processes:
            print(f"  - {proc['name']} (PID: {proc['pid']})")
            if proc['exe']:
                print(f"    路径: {proc['exe']}")
        return True
    else:
        print("✗ 未找到 Clash 进程")
        print("  建议：请启动 Clash 代理软件")
        return False


def check_clash_api():
    """检查 Clash API"""
    print("\n=== 检查 Clash API ===")
    
    # 常见的 Clash API 地址
    api_addresses = [
        "http://127.0.0.1:9090",
        "http://127.0.0.1:9097",
        "http://127.0.0.1:7890",
    ]
    
    for api_url in api_addresses:
        try:
            print(f"尝试连接: {api_url}")
            response = requests.get(f"{api_url}/version", timeout=2)
            if response.status_code == 200:
                version_info = response.json()
                print(f"✓ Clash API 可访问: {api_url}")
                print(f"  版本: {version_info.get('version', 'unknown')}")
                print(f"  Meta: {version_info.get('meta', False)}")
                
                # 获取配置信息
                try:
                    config_response = requests.get(f"{api_url}/configs", timeout=2)
                    if config_response.status_code == 200:
                        config = config_response.json()
                        print(f"  端口: {config.get('port', 'unknown')}")
                        print(f"  Socks 端口: {config.get('socks-port', 'unknown')}")
                        print(f"  模式: {config.get('mode', 'unknown')}")
                        
                        # 检查 DNS 配置
                        dns_config = config.get('dns', {})
                        if dns_config:
                            print(f"  DNS 启用: {dns_config.get('enable', False)}")
                            print(f"  DNS 模式: {dns_config.get('enhanced-mode', 'unknown')}")
                            
                            # 重点检查是否是 Fake-IP 模式
                            enhanced_mode = dns_config.get('enhanced-mode', '').lower()
                            if enhanced_mode == 'fake-ip':
                                print("\n⚠️  警告：检测到 Fake-IP 模式！")
                                print("  Fake-IP 模式会导致 DNS 解析返回假 IP (198.18.x.x)")
                                print("  这会影响视频捕获功能")
                                print("\n  解决方案：")
                                print("  1. 临时关闭 Clash 代理，测试视频捕获")
                                print("  2. 或修改 Clash 配置，将 DNS 模式改为 'redir-host'")
                                print("     在 Clash 配置文件中找到 dns.enhanced-mode")
                                print("     将 'fake-ip' 改为 'redir-host'")
                            elif enhanced_mode == 'redir-host':
                                print("✓ DNS 模式为 redir-host，兼容性良好")
                        
                        return True, api_url
                except Exception as e:
                    print(f"  无法获取配置: {e}")
                    return True, api_url
        except requests.exceptions.ConnectionError:
            print(f"  无法连接")
        except Exception as e:
            print(f"  错误: {e}")
    
    print("✗ 无法访问 Clash API")
    print("  建议：检查 Clash 是否启用了 External Controller")
    return False, None


def check_dns_resolution():
    """检查 DNS 解析"""
    print("\n=== 检查 DNS 解析 ===")
    
    test_domains = [
        "finder.video.qq.com",
        "wxapp.tc.qq.com",
        "channels.weixin.qq.com",
    ]
    
    fake_ip_count = 0
    
    for domain in test_domains:
        try:
            ip = socket.gethostbyname(domain)
            print(f"{domain} -> {ip}")
            
            # 检查是否是 Fake-IP
            if ip.startswith("198.18.") or ip.startswith("198.19."):
                print(f"  ⚠️  这是 Fake-IP！")
                fake_ip_count += 1
            else:
                print(f"  ✓ 真实 IP")
        except socket.gaierror as e:
            print(f"{domain} -> 解析失败: {e}")
    
    if fake_ip_count > 0:
        print(f"\n⚠️  检测到 {fake_ip_count} 个 Fake-IP")
        print("  这表明 Clash 正在使用 Fake-IP 模式")
        print("  建议：")
        print("  1. 临时关闭 Clash，测试视频捕获")
        print("  2. 或修改 Clash DNS 模式为 'redir-host'")
    else:
        print("\n✓ 所有域名解析为真实 IP")
    
    return fake_ip_count == 0


def check_wechat_process():
    """检查微信进程"""
    print("\n=== 检查微信进程 ===")
    
    wechat_processes = []
    wechat_names = ['wechat', 'weixin']
    
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = proc.info['name']
            if name:
                name_lower = name.lower()
                for wechat_name in wechat_names:
                    if wechat_name in name_lower:
                        wechat_processes.append({
                            'pid': proc.info['pid'],
                            'name': name,
                            'exe': proc.info['exe']
                        })
                        break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if wechat_processes:
        print(f"✓ 找到 {len(wechat_processes)} 个微信进程：")
        for proc in wechat_processes:
            print(f"  - {proc['name']} (PID: {proc['pid']})")
        return True
    else:
        print("✗ 未找到微信进程")
        print("  建议：请启动 Windows PC 端微信")
        return False


def check_admin_privileges():
    """检查管理员权限"""
    print("\n=== 检查管理员权限 ===")
    
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        
        if is_admin:
            print("✓ 应用以管理员权限运行")
            return True
        else:
            print("✗ 应用未以管理员权限运行")
            print("  建议：右键点击应用图标，选择\"以管理员身份运行\"")
            return False
    except Exception as e:
        print(f"✗ 无法检查管理员权限: {e}")
        return False


def check_network_connections():
    """检查网络连接"""
    print("\n=== 检查网络连接 ===")
    
    try:
        # 检查是否能访问腾讯视频服务器
        test_hosts = [
            ("video.qq.com", 443),
            ("qq.com", 443),
        ]
        
        for host, port in test_hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    print(f"✓ 可以连接到 {host}:{port}")
                else:
                    print(f"✗ 无法连接到 {host}:{port}")
            except Exception as e:
                print(f"✗ 连接 {host}:{port} 失败: {e}")
        
        return True
    except Exception as e:
        print(f"✗ 网络连接检查失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("微信视频号捕获 - Clash 代理诊断工具")
    print("=" * 60)
    
    results = {
        'clash_running': False,
        'clash_api_accessible': False,
        'dns_ok': False,
        'wechat_running': False,
        'is_admin': False,
        'network_ok': False,
    }
    
    # 执行检查
    results['clash_running'] = check_clash_process()
    results['clash_api_accessible'], api_url = check_clash_api()
    results['dns_ok'] = check_dns_resolution()
    results['wechat_running'] = check_wechat_process()
    results['is_admin'] = check_admin_privileges()
    results['network_ok'] = check_network_connections()
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    all_ok = all(results.values())
    
    if all_ok:
        print("✓ 所有检查通过！")
        print("\n建议：")
        print("1. 如果仍然无法捕获视频，请尝试关闭 Clash 代理")
        print("2. 或修改 Clash DNS 模式为 'redir-host'")
    else:
        print("⚠️  发现以下问题：")
        if not results['is_admin']:
            print("  - 需要管理员权限")
        if not results['wechat_running']:
            print("  - 微信未运行")
        if not results['dns_ok']:
            print("  - DNS 解析返回 Fake-IP")
        if not results['network_ok']:
            print("  - 网络连接异常")
        
        print("\n推荐解决方案：")
        print("1. 以管理员身份运行应用")
        print("2. 启动微信 PC 端")
        print("3. 临时关闭 Clash 代理，测试视频捕获")
        print("4. 如果需要使用 Clash，修改 DNS 模式为 'redir-host'：")
        print("   - 打开 Clash 配置文件")
        print("   - 找到 dns.enhanced-mode")
        print("   - 将 'fake-ip' 改为 'redir-host'")
        print("   - 重启 Clash")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
