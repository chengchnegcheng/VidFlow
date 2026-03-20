"""
WinDivert 状态检查工具

这个脚本会全面检查 WinDivert 的状态，包括：
1. 管理员权限
2. WinDivert DLL 和驱动文件
3. pydivert 模块
4. 基本的流量捕获测试
5. 微信进程检测
6. 代理软件检测
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(check_name: str, passed: bool, details: str = ""):
    """打印检查结果"""
    status = "✓" if passed else "✗"
    print(f"{status} {check_name}")
    if details:
        for line in details.split('\n'):
            print(f"  {line}")


def check_admin_privileges() -> bool:
    """检查管理员权限"""
    print_section("1. 管理员权限检查")
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        print_result(
            "管理员权限",
            is_admin,
            "应用以管理员权限运行" if is_admin else "应用未以管理员权限运行\n请右键点击应用，选择\"以管理员身份运行\""
        )
        return is_admin
    except Exception as e:
        print_result("管理员权限", False, f"无法检查管理员权限: {e}")
        return False


def check_windivert_files() -> bool:
    """检查 WinDivert 文件"""
    print_section("2. WinDivert 文件检查")
    try:
        from src.core.channels.driver_manager import DriverManager

        driver_manager = DriverManager()

        # 检查 DLL
        dll_path = driver_manager.get_dll_path()
        dll_exists = dll_path and dll_path.exists()
        print_result(
            "WinDivert DLL",
            dll_exists,
            f"路径: {dll_path}" if dll_exists else f"未找到 DLL\n预期路径: {dll_path}"
        )

        # 检查驱动文件
        if dll_path:
            driver_dir = dll_path.parent
            sys_file = driver_dir / "WinDivert64.sys"
            sys_exists = sys_file.exists()
            print_result(
                "WinDivert 驱动",
                sys_exists,
                f"路径: {sys_file}" if sys_exists else f"未找到驱动文件\n预期路径: {sys_file}"
            )

            return dll_exists and sys_exists

        return False
    except Exception as e:
        print_result("WinDivert 文件", False, f"检查失败: {e}")
        return False


def check_pydivert_module() -> bool:
    """检查 pydivert 模块"""
    print_section("3. pydivert 模块检查")
    try:
        import pydivert
        version = getattr(pydivert, '__version__', '未知')
        print_result(
            "pydivert 模块",
            True,
            f"已安装，版本: {version}"
        )
        return True
    except ImportError as e:
        print_result(
            "pydivert 模块",
            False,
            f"未安装: {e}\n请运行: pip install pydivert"
        )
        return False


def check_wechat_processes() -> tuple:
    """检查微信进程"""
    print_section("4. 微信进程检查")
    try:
        import psutil

        wechat_names = [
            'WeChat.exe', 'WeChatAppEx.exe', 'WeChatApp.exe',
            'WeChatBrowser.exe', 'WeChatPlayer.exe', 'Weixin.exe'
        ]

        found_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                name = proc.info['name']
                if name and any(x in name for x in wechat_names):
                    found_processes.append({
                        'pid': proc.info['pid'],
                        'name': name,
                        'exe': proc.info['exe']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if found_processes:
            details = f"找到 {len(found_processes)} 个微信进程:\n"
            for proc in found_processes:
                details += f"  - {proc['name']} (PID: {proc['pid']})\n"
            print_result("微信进程", True, details.strip())
        else:
            print_result(
                "微信进程",
                False,
                "未检测到微信进程\n请先启动 Windows PC 端微信"
            )

        return len(found_processes) > 0, found_processes
    except Exception as e:
        print_result("微信进程", False, f"检查失败: {e}")
        return False, []


def check_proxy_software() -> tuple:
    """检查代理软件"""
    print_section("5. 代理软件检查")
    try:
        import psutil

        proxy_names = [
            'clash', 'clash-verge', 'verge-mihomo', 'mihomo',
            'clash-core', 'clash-meta', 'v2ray', 'xray', 'v2rayn',
            'sing-box', 'shadowsocks', 'ssr', 'surge'
        ]

        found_proxies = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name']
                if name:
                    name_lower = name.lower()
                    for proxy_name in proxy_names:
                        if proxy_name in name_lower:
                            found_proxies.append({
                                'pid': proc.info['pid'],
                                'name': name
                            })
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if found_proxies:
            details = f"⚠️  检测到 {len(found_proxies)} 个代理软件:\n"
            for proc in found_proxies:
                details += f"  - {proc['name']} (PID: {proc['pid']})\n"
            details += "\n建议：关闭代理软件以获得最佳捕获效果"
            print_result("代理软件", False, details.strip())
        else:
            print_result("代理软件", True, "未检测到代理软件（推荐）")

        return len(found_proxies) > 0, found_proxies
    except Exception as e:
        print_result("代理软件", False, f"检查失败: {e}")
        return False, []


def test_windivert_capture() -> bool:
    """测试 WinDivert 捕获功能"""
    print_section("6. WinDivert 捕获测试")
    try:
        import pydivert

        # 使用简单的过滤规则：捕获所有出站 TCP 流量
        filter_str = "outbound and tcp"
        print(f"过滤规则: {filter_str}")
        print("正在捕获 5 秒钟的流量...")
        print("提示：请在浏览器中打开任意网页以产生流量\n")

        with pydivert.WinDivert(filter_str) as w:
            packet_count = 0
            start_time = time.time()
            timeout = 5  # 5 秒超时

            # 统计信息
            ports = {}
            ips = {}

            while time.time() - start_time < timeout:
                try:
                    packet = w.recv()

                    if packet:
                        packet_count += 1

                        # 统计目标端口
                        dst_port = packet.dst_port
                        ports[dst_port] = ports.get(dst_port, 0) + 1

                        # 统计目标 IP
                        dst_ip = packet.dst_addr
                        ips[dst_ip] = ips.get(dst_ip, 0) + 1

                        # 重新注入数据包（不修改）
                        w.send(packet)

                        # 每捕获 50 个包输出一次进度
                        if packet_count % 50 == 0:
                            print(f"  已捕获 {packet_count} 个数据包...")

                except Exception:
                    pass

            print()  # 换行

            if packet_count > 0:
                details = f"捕获成功！共捕获 {packet_count} 个数据包\n"
                details += f"不同目标端口: {len(ports)}\n"
                details += f"不同目标 IP: {len(ips)}\n"

                # 显示前 5 个最常见的端口
                if ports:
                    details += "\n最常见的目标端口:\n"
                    sorted_ports = sorted(ports.items(), key=lambda x: x[1], reverse=True)[:5]
                    for port, count in sorted_ports:
                        details += f"  端口 {port}: {count} 个数据包\n"

                # 显示前 5 个最常见的 IP
                if ips:
                    details += "\n最常见的目标 IP:\n"
                    sorted_ips = sorted(ips.items(), key=lambda x: x[1], reverse=True)[:5]
                    for ip, count in sorted_ips:
                        details += f"  {ip}: {count} 个数据包\n"

                print_result("流量捕获", True, details.strip())
                return True
            else:
                details = "⚠️  未捕获到任何数据包\n"
                details += "可能的原因:\n"
                details += "  1. 没有网络活动（请在浏览器中打开网页）\n"
                details += "  2. 代理软件拦截了流量（请关闭 v2rayN/Clash）\n"
                details += "  3. 防火墙阻止了 WinDivert"
                print_result("流量捕获", False, details)
                return False

    except PermissionError as e:
        print_result("流量捕获", False, f"权限错误: {e}\n请确保以管理员身份运行")
        return False
    except Exception as e:
        print_result("流量捕获", False, f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_recommendations(results: dict):
    """生成诊断建议"""
    print_section("诊断建议")

    recommendations = []

    if not results['admin']:
        recommendations.append({
            'level': '❌ 严重',
            'message': '应用未以管理员权限运行',
            'action': '请右键点击应用图标，选择"以管理员身份运行"'
        })

    if not results['files']:
        recommendations.append({
            'level': '❌ 严重',
            'message': 'WinDivert 文件缺失',
            'action': '请重新安装应用或联系技术支持'
        })

    if not results['pydivert']:
        recommendations.append({
            'level': '❌ 严重',
            'message': 'pydivert 模块未安装',
            'action': '请运行: pip install pydivert'
        })

    if not results['wechat']:
        recommendations.append({
            'level': '⚠️  警告',
            'message': '未检测到微信进程',
            'action': '请先启动 Windows PC 端微信'
        })

    if results['proxy']:
        recommendations.append({
            'level': '⚠️  警告',
            'message': '检测到代理软件正在运行',
            'action': '建议关闭代理软件（v2rayN/Clash/Surge 等）以获得最佳捕获效果'
        })

    if not results['capture']:
        recommendations.append({
            'level': '❌ 严重',
            'message': 'WinDivert 无法捕获流量',
            'action': '请检查防火墙设置，确保允许 WinDivert 运行'
        })

    if not recommendations:
        print("✅ 所有检查通过！WinDivert 工作正常")
        print("\n如果视频号捕获仍然不工作，请检查：")
        print("  1. 是否在微信视频号中播放了视频")
        print("  2. 视频是否使用了 ECH 加密（这是正常的，系统会使用 IP 识别）")
        print("  3. 查看应用日志以获取更多信息")
    else:
        print("发现以下问题，请按优先级解决：\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['level']} - {rec['message']}")
            print(f"   解决方案: {rec['action']}\n")


def main():
    """主函数"""
    print("=" * 70)
    print("  WinDivert 状态检查工具")
    print("=" * 70)
    print("\n这个工具会全面检查 WinDivert 的状态和配置")
    print("请耐心等待所有检查完成...\n")

    results = {
        'admin': False,
        'files': False,
        'pydivert': False,
        'wechat': False,
        'proxy': False,
        'capture': False
    }

    # 执行所有检查
    results['admin'] = check_admin_privileges()
    results['files'] = check_windivert_files()
    results['pydivert'] = check_pydivert_module()
    results['wechat'], _ = check_wechat_processes()
    results['proxy'], _ = check_proxy_software()

    # 只有在前面的检查都通过时才进行捕获测试
    if results['admin'] and results['files'] and results['pydivert']:
        results['capture'] = test_windivert_capture()
    else:
        print_section("6. WinDivert 捕获测试")
        print("⊘ 跳过捕获测试（前置条件未满足）")

    # 生成建议
    generate_recommendations(results)

    # 总结
    print_section("检查完成")
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    if passed_count == total_count:
        print(f"✅ 所有检查通过 ({passed_count}/{total_count})")
    else:
        print(f"⚠️  部分检查未通过 ({passed_count}/{total_count})")

    print("=" * 70)


if __name__ == "__main__":
    main()
