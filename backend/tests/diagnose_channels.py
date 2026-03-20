"""
视频号功能诊断脚本
用于检查视频号嗅探功能的各个组件是否正常工作
"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.channels.traffic_capture import WinDivertCapture
from src.core.channels.proxy_sniffer import ProxySniffer
from src.core.channels.wechat_process_manager import WeChatProcessManager

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def diagnose():
    """运行诊断"""
    print("=" * 60)
    print("视频号功能诊断")
    print("=" * 60)

    # 1. 检查微信进程
    print("\n[1] 检查微信进程...")
    process_manager = WeChatProcessManager()
    processes = process_manager.get_wechat_processes()

    if not processes:
        print("❌ 未检测到微信进程！请确保微信正在运行。")
        return

    print(f"✓ 检测到 {len(processes)} 个微信进程:")
    for proc in processes:
        print(f"  - PID: {proc['pid']}, 名称: {proc['name']}, 路径: {proc['exe']}")

    # 2. 检查 WinDivert 驱动
    print("\n[2] 检查 WinDivert 驱动...")
    try:
        import pydivert
        print("✓ pydivert 模块已安装")

        # 尝试创建一个测试句柄
        try:
            with pydivert.WinDivert("false") as w:
                print("✓ WinDivert 驱动可以正常加载")
        except Exception as e:
            print(f"❌ WinDivert 驱动加载失败: {e}")
            print("   请以管理员权限运行程序！")
            return
    except ImportError:
        print("❌ pydivert 模块未安装")
        print("   请运行: pip install pydivert")
        return

    # 3. 检查透明捕获配置
    print("\n[3] 检查透明捕获配置...")
    capture = WinDivertCapture(proxy_port=8888)

    print(f"  - 目标域名数量: {len(capture.target_domains)}")
    print(f"  - 前5个域名: {capture.target_domains[:5]}")
    print(f"  - 目标进程: {capture.target_processes}")

    # 4. 测试 SNI 检测
    print("\n[4] 测试 SNI 检测...")
    test_snis = [
        "finder.video.qq.com",
        "findermp.video.qq.com",
        "wxapp.tc.qq.com",
        "stodownload.wxapp.tc.qq.com",
        "www.baidu.com",  # 非视频域名
    ]

    for sni in test_snis:
        is_video = capture._is_video_sni(sni)
        status = "✓" if is_video else "✗"
        print(f"  {status} {sni}: {'是视频域名' if is_video else '不是视频域名'}")

    # 5. 检查代理嗅探器
    print("\n[5] 检查代理嗅探器...")
    sniffer = ProxySniffer(proxy_port=8888)

    test_urls = [
        "https://finder.video.qq.com/xxx.mp4",
        "https://wxapp.tc.qq.com/xxx.mp4?encfilekey=xxx",
        "https://stodownload.wxapp.tc.qq.com/xxx.mp4",
    ]

    for url in test_urls:
        is_video = sniffer.is_video_url(url)
        status = "✓" if is_video else "✗"
        print(f"  {status} {url[:60]}...: {'是视频URL' if is_video else '不是视频URL'}")

    print("\n" + "=" * 60)
    print("诊断完成！")
    print("=" * 60)

    print("\n建议:")
    print("1. 确保以管理员权限运行程序")
    print("2. 确保微信正在运行")
    print("3. 启动嗅探器后，在微信视频号中浏览视频")
    print("4. 查看后端日志，搜索 'Intercepted request' 或 'Matched channels video URL'")
    print("5. 如果看不到任何拦截日志，说明流量没有被捕获")


if __name__ == "__main__":
    asyncio.run(diagnose())
