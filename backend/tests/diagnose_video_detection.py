"""
视频检测诊断工具

快速检查透明捕获和视频检测的状态
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.channels.traffic_capture import WinDivertCapture
from src.core.channels.proxy_sniffer import ProxySniffer
from src.core.channels.driver_manager import DriverManager
from src.core.channels.platform_detector import PlatformDetector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def check_driver_status():
    """检查 WinDivert 驱动状态"""
    logger.info("\n=== 检查 WinDivert 驱动 ===")

    driver_manager = DriverManager()
    status = driver_manager.get_status()

    logger.info(f"驱动状态: {status.state.value}")
    logger.info(f"是否有管理员权限: {status.is_admin}")

    if status.version:
        logger.info(f"驱动版本: {status.version}")
    if status.path:
        logger.info(f"驱动路径: {status.path}")
    if status.error_message:
        logger.error(f"错误信息: {status.error_message}")

    return status.state.value == "installed" and status.is_admin


async def check_proxy_status():
    """检查代理服务器状态"""
    logger.info("\n=== 检查代理服务器 ===")

    sniffer = ProxySniffer(port=8888)
    status = sniffer.get_status()

    logger.info(f"代理状态: {status.state.value}")
    logger.info(f"代理端口: {status.proxy_port}")

    if status.proxy_address:
        logger.info(f"代理地址: {status.proxy_address}")
    if status.error_message:
        logger.error(f"错误信息: {status.error_message}")

    return status.state.value in ["running", "stopped"]


async def check_capture_status():
    """检查透明捕获状态"""
    logger.info("\n=== 检查透明捕获 ===")

    capture = WinDivertCapture(
        proxy_port=8888,
        target_processes=["WeChat.exe", "WeChatAppEx.exe"]
    )

    status = capture.get_status()

    logger.info(f"捕获状态: {status.state.value}")
    logger.info(f"捕获模式: {status.mode.value}")

    if status.statistics:
        logger.info(f"拦截包数: {status.statistics.packets_intercepted}")
        logger.info(f"重定向连接数: {status.statistics.connections_redirected}")
        logger.info(f"检测到的视频数: {status.statistics.videos_detected}")

    if status.error_message:
        logger.error(f"错误信息: {status.error_message}")

    return status.state.value in ["running", "stopped"]


def check_url_patterns():
    """检查 URL 匹配模式"""
    logger.info("\n=== 检查 URL 匹配模式 ===")

    # 测试 URL
    test_urls = [
        "https://finder.video.qq.com/251/20304/stodownload?encfilekey=xxx",
        "https://channels.weixin.qq.com/video/xxx.mp4",
        "https://findermp.video.qq.com/xxx/xxx.mp4",
        "https://vweixinf.tc.qq.com/xxx.mp4",
        "https://wxsnsdy.tc.qq.com/xxx.mp4",
        "https://www.example.com/video.mp4",  # 不应该匹配
    ]

    logger.info("测试 URL 匹配:")
    for url in test_urls:
        is_match = PlatformDetector.is_channels_video_url(url)
        status = "✓ 匹配" if is_match else "✗ 不匹配"
        logger.info(f"  {status}: {url}")

    return True


def check_content_types():
    """检查 Content-Type 匹配"""
    logger.info("\n=== 检查 Content-Type 匹配 ===")

    # 测试 Content-Type
    test_types = [
        "video/mp4",
        "video/x-flv",
        "application/octet-stream",
        "application/vnd.apple.mpegurl",
        "video/mp2t",
        "text/html",  # 不应该匹配
        "application/json",  # 不应该匹配
    ]

    logger.info("测试 Content-Type 匹配:")
    for content_type in test_types:
        is_match = PlatformDetector.is_video_content_type(content_type)
        status = "✓ 匹配" if is_match else "✗ 不匹配"
        logger.info(f"  {status}: {content_type}")

    return True


async def run_diagnostics():
    """运行完整诊断"""
    logger.info("=" * 60)
    logger.info("视频检测诊断工具")
    logger.info("=" * 60)

    results = {}

    # 检查驱动
    try:
        results['driver'] = await check_driver_status()
    except Exception as e:
        logger.exception("驱动检查失败")
        results['driver'] = False

    # 检查代理
    try:
        results['proxy'] = await check_proxy_status()
    except Exception as e:
        logger.exception("代理检查失败")
        results['proxy'] = False

    # 检查捕获
    try:
        results['capture'] = await check_capture_status()
    except Exception as e:
        logger.exception("捕获检查失败")
        results['capture'] = False

    # 检查 URL 模式
    try:
        results['url_patterns'] = check_url_patterns()
    except Exception as e:
        logger.exception("URL 模式检查失败")
        results['url_patterns'] = False

    # 检查 Content-Type
    try:
        results['content_types'] = check_content_types()
    except Exception as e:
        logger.exception("Content-Type 检查失败")
        results['content_types'] = False

    # 总结
    logger.info("\n" + "=" * 60)
    logger.info("诊断结果总结")
    logger.info("=" * 60)

    all_passed = True
    for check, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info(f"{check:20s}: {status}")
        if not passed:
            all_passed = False

    logger.info("=" * 60)

    if all_passed:
        logger.info("✓ 所有检查通过！")
        logger.info("\n如果仍然无法检测到视频，请：")
        logger.info("1. 确保已启动透明捕获")
        logger.info("2. 确保已安装并信任 CA 证书")
        logger.info("3. 在微信视频号中播放视频")
        logger.info("4. 查看后台日志中的详细信息")
    else:
        logger.error("✗ 部分检查失败，请查看上面的错误信息")
        logger.info("\n建议：")
        if not results.get('driver'):
            logger.info("- 以管理员身份运行程序")
            logger.info("- 安装 WinDivert 驱动")
        if not results.get('proxy') or not results.get('capture'):
            logger.info("- 检查端口 8888 是否被占用")
            logger.info("- 检查防火墙设置")

    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
