"""
实际问题诊断脚本

帮助用户诊断微信视频号下载功能的实际问题
"""
import asyncio
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def check_backend_running():
    """检查后端是否运行"""
    print("\n" + "=" * 60)
    print("1. 检查后端服务")
    print("=" * 60)

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/health', timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    print("✓ 后端服务正在运行")
                    return True
                else:
                    print(f"✗ 后端服务响应异常: {resp.status}")
                    return False
    except Exception as e:
        print(f"✗ 后端服务未运行: {e}")
        print("\n请先启动后端服务:")
        print("  cd backend")
        print("  python src/main.py")
        return False


async def check_sniffer_status():
    """检查嗅探器状态"""
    print("\n" + "=" * 60)
    print("2. 检查嗅探器状态")
    print("=" * 60)

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/api/channels/sniffer/status', timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"状态: {data.get('state')}")
                    print(f"代理地址: {data.get('proxy_address')}")
                    print(f"检测到的视频: {data.get('videos_detected')}")

                    if data.get('state') == 'running':
                        print("✓ 嗅探器正在运行")
                        return True
                    else:
                        print("✗ 嗅探器未运行")
                        print("\n请在前端界面点击\"启动嗅探器\"按钮")
                        return False
                else:
                    print(f"✗ 获取状态失败: {resp.status}")
                    return False
    except Exception as e:
        print(f"✗ 无法获取嗅探器状态: {e}")
        return False


async def check_detected_videos():
    """检查检测到的视频"""
    print("\n" + "=" * 60)
    print("3. 检查检测到的视频")
    print("=" * 60)

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:8000/api/channels/videos', timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    videos = await resp.json()
                    print(f"检测到 {len(videos)} 个视频")

                    if len(videos) == 0:
                        print("\n✗ 没有检测到视频")
                        print("\n可能的原因:")
                        print("  1. 嗅探器未启动")
                        print("  2. 系统代理未设置")
                        print("  3. 证书未安装")
                        print("  4. JavaScript 注入未生效")
                        print("  5. 微信未打开或未播放视频")
                        return False

                    print("\n检测到的视频:")
                    for i, video in enumerate(videos[:5], 1):  # 只显示前5个
                        print(f"\n视频 {i}:")
                        print(f"  ID: {video.get('id')}")
                        print(f"  标题: {video.get('title') or '无标题'}")
                        print(f"  URL: {video.get('url')[:80]}...")
                        print(f"  缩略图: {video.get('thumbnail') or '无'}")
                        print(f"  时长: {video.get('duration') or '未知'}")
                        print(f"  文件大小: {video.get('filesize') or '未知'}")
                        print(f"  解密密钥: {video.get('decryption_key')[:20] if video.get('decryption_key') else '无'}...")

                    if len(videos) > 5:
                        print(f"\n... 还有 {len(videos) - 5} 个视频")

                    # 检查视频信息完整性
                    print("\n视频信息完整性检查:")
                    has_title = sum(1 for v in videos if v.get('title'))
                    has_thumbnail = sum(1 for v in videos if v.get('thumbnail'))
                    has_duration = sum(1 for v in videos if v.get('duration'))

                    print(f"  有标题: {has_title}/{len(videos)}")
                    print(f"  有缩略图: {has_thumbnail}/{len(videos)}")
                    print(f"  有时长: {has_duration}/{len(videos)}")

                    if has_title == 0:
                        print("\n✗ 所有视频都没有标题！")
                        print("  这说明 JavaScript 注入可能未生效")
                        return False

                    if has_title < len(videos):
                        print(f"\n⚠ 有 {len(videos) - has_title} 个视频没有标题")
                        print("  部分视频的信息提取可能失败")

                    return True
                else:
                    print(f"✗ 获取视频列表失败: {resp.status}")
                    return False
    except Exception as e:
        print(f"✗ 无法获取视频列表: {e}")
        return False


async def check_system_proxy():
    """检查系统代理设置"""
    print("\n" + "=" * 60)
    print("4. 检查系统代理设置")
    print("=" * 60)

    try:
        import winreg

        # 读取系统代理设置
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_READ
        )

        try:
            proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]

            if proxy_enable == 1:
                print(f"✓ 系统代理已启用")
                print(f"  代理服务器: {proxy_server}")

                if "127.0.0.1:8888" in proxy_server or "localhost:8888" in proxy_server:
                    print("✓ 代理指向正确的地址")
                    return True
                else:
                    print("✗ 代理地址不正确")
                    print("  应该是: 127.0.0.1:8888")
                    return False
            else:
                print("✗ 系统代理未启用")
                print("\n请在前端界面点击\"启动嗅探器\"按钮")
                print("或手动设置系统代理:")
                print("  1. 打开 Windows 设置")
                print("  2. 网络和 Internet → 代理")
                print("  3. 手动设置代理")
                print("  4. 地址: 127.0.0.1  端口: 8888")
                return False
        finally:
            winreg.CloseKey(key)

    except Exception as e:
        print(f"✗ 无法检查系统代理: {e}")
        return False


async def check_certificate():
    """检查证书安装"""
    print("\n" + "=" * 60)
    print("5. 检查 mitmproxy 证书")
    print("=" * 60)

    try:
        import subprocess

        # 检查证书是否安装
        result = subprocess.run(
            ['certutil', '-store', 'Root', 'mitmproxy'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if 'mitmproxy' in result.stdout:
            print("✓ mitmproxy 证书已安装")
            return True
        else:
            print("✗ mitmproxy 证书未安装")
            print("\n请在前端界面点击\"启动嗅探器\"按钮")
            print("系统会自动安装证书（需要管理员权限）")
            return False

    except Exception as e:
        print(f"⚠ 无法检查证书: {e}")
        print("  这可能不是问题，继续检查其他项")
        return None


async def check_admin_rights():
    """检查管理员权限"""
    print("\n" + "=" * 60)
    print("6. 检查管理员权限")
    print("=" * 60)

    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

        if is_admin:
            print("✓ 当前以管理员权限运行")
            return True
        else:
            print("✗ 当前未以管理员权限运行")
            print("\n微信视频号功能需要管理员权限:")
            print("  1. 安装 mitmproxy 证书")
            print("  2. 设置系统代理")
            print("\n请右键点击应用，选择\"以管理员身份运行\"")
            return False

    except Exception as e:
        print(f"✗ 无法检查管理员权限: {e}")
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("微信视频号功能诊断")
    print("=" * 60)

    # 检查后端
    backend_ok = await check_backend_running()
    if not backend_ok:
        return

    # 检查管理员权限
    admin_ok = await check_admin_rights()

    # 检查嗅探器
    sniffer_ok = await check_sniffer_status()

    # 检查系统代理
    proxy_ok = await check_system_proxy()

    # 检查证书
    cert_ok = await check_certificate()

    # 检查视频
    videos_ok = await check_detected_videos()

    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)

    all_checks = [
        ("后端服务", backend_ok),
        ("管理员权限", admin_ok),
        ("嗅探器状态", sniffer_ok),
        ("系统代理", proxy_ok),
        ("证书安装", cert_ok),
        ("视频检测", videos_ok),
    ]

    passed = sum(1 for _, ok in all_checks if ok is True)
    total = len([ok for _, ok in all_checks if ok is not None])

    print(f"\n通过检查: {passed}/{total}")

    for name, ok in all_checks:
        if ok is True:
            status = "✓"
        elif ok is False:
            status = "✗"
        else:
            status = "⚠"
        print(f"  {status} {name}")

    if passed == total:
        print("\n✓ 所有检查都通过了！")
        print("\n如果仍然无法下载视频，请检查:")
        print("  1. 微信是否打开并播放了视频")
        print("  2. 浏览器控制台是否有 [视频号下载助手] 日志")
        print("  3. 后端日志中是否有 \"检测到微信页面\" 消息")
    else:
        print("\n✗ 有检查项未通过，请按照上述提示解决问题")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n诊断已取消")
    except Exception as e:
        print(f"\n\n诊断出错: {e}")
        import traceback
        traceback.print_exc()
