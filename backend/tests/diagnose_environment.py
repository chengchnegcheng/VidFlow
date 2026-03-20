#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
环境诊断脚本 - 检查是否有代理软件干扰
"""

import sys
import socket
import psutil
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_proxy_processes():
    """检查是否有代理软件在运行"""
    proxy_names = [
        'clash', 'clash-verge', 'verge', 'mihomo',
        'v2ray', 'v2rayn', 'xray',
        'sing-box', 'shadowsocks', 'ssr',
        'surge', 'quantumult', 'loon',
        'proxifier', 'sockscap',
    ]

    found = []
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = proc.info['name'].lower() if proc.info['name'] else ''
            exe = proc.info['exe'].lower() if proc.info['exe'] else ''

            for proxy_name in proxy_names:
                if proxy_name in name or proxy_name in exe:
                    found.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'exe': proc.info['exe']
                    })
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return found

def check_dns():
    """检查 DNS 解析"""
    test_domains = [
        'channels.weixin.qq.com',
        'finder.video.qq.com',
        'www.qq.com',
        'www.baidu.com',
    ]

    results = {}
    for domain in test_domains:
        try:
            ip = socket.gethostbyname(domain)
            results[domain] = {'success': True, 'ip': ip}
        except socket.gaierror as e:
            results[domain] = {'success': False, 'error': str(e)}

    return results

def check_wechat_processes():
    """检查微信进程"""
    wechat_names = ['wechat', 'weixin', 'wxwork']
    found = []

    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = proc.info['name'].lower() if proc.info['name'] else ''

            for wechat_name in wechat_names:
                if wechat_name in name:
                    found.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'exe': proc.info['exe']
                    })
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return found

def main():
    print("=" * 60)
    print("环境诊断")
    print("=" * 60)

    # 1. 检查代理软件
    print("\n[1/3] 检查代理软件...")
    proxy_procs = check_proxy_processes()

    if proxy_procs:
        print(f"  ⚠️  发现 {len(proxy_procs)} 个代理软件进程:")
        for proc in proxy_procs:
            print(f"    - {proc['name']} (PID: {proc['pid']})")
            if proc['exe']:
                print(f"      路径: {proc['exe']}")
        print("\n  ⚠️  警告: 代理软件会干扰 WinDivert 捕获!")
        print("  建议: 暂时关闭代理软件，然后重新测试")
    else:
        print("  ✓ 未发现代理软件")

    # 2. 检查 DNS
    print("\n[2/3] 检查 DNS 解析...")
    dns_results = check_dns()

    success_count = sum(1 for r in dns_results.values() if r['success'])
    print(f"  成功解析: {success_count}/{len(dns_results)}")

    for domain, result in dns_results.items():
        if result['success']:
            print(f"  ✓ {domain} -> {result['ip']}")
        else:
            print(f"  ✗ {domain} -> {result['error']}")

    if success_count < len(dns_results):
        print("\n  ⚠️  部分域名无法解析")
        print("  可能原因:")
        print("    1. 代理软件劫持了 DNS")
        print("    2. 网络连接问题")
        print("    3. 防火墙阻止")

    # 3. 检查微信进程
    print("\n[3/3] 检查微信进程...")
    wechat_procs = check_wechat_processes()

    if wechat_procs:
        print(f"  ✓ 发现 {len(wechat_procs)} 个微信进程:")
        for proc in wechat_procs:
            print(f"    - {proc['name']} (PID: {proc['pid']})")
    else:
        print("  ✗ 未发现微信进程")
        print("  请先启动微信 PC 端")

    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)

    issues = []

    if proxy_procs:
        issues.append("发现代理软件在运行")

    if success_count < len(dns_results):
        issues.append("DNS 解析异常")

    if not wechat_procs:
        issues.append("微信未运行")

    if issues:
        print("\n⚠️  发现以下问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

        print("\n建议操作:")
        if proxy_procs:
            print("  1. 关闭所有代理软件（Clash/v2rayN 等）")
        if not wechat_procs:
            print("  2. 启动微信 PC 端")
        print("  3. 重新运行测试脚本")
    else:
        print("\n✓ 环境检查通过，可以开始测试")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
