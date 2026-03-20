"""
快速检查视频号功能状态
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def check_status():
    """检查视频号功能状态"""
    from src.core.channels.proxy_sniffer import ProxySniffer

    logger.info("=" * 60)
    logger.info("检查视频号功能状态")
    logger.info("=" * 60)

    # 创建嗅探器实例（不启动，只检查状态）
    sniffer = ProxySniffer(port=8889, transparent_mode=True)

    # 获取状态
    status = sniffer.get_status()

    logger.info(f"\n嗅探器状态:")
    logger.info(f"  - 状态: {status.state.value}")
    logger.info(f"  - 代理地址: {status.proxy_address}")
    logger.info(f"  - 代理端口: {status.proxy_port}")
    logger.info(f"  - 检测到的视频数: {status.videos_detected}")

    if status.started_at:
        logger.info(f"  - 启动时间: {status.started_at}")

    if status.error_message:
        logger.info(f"  - 错误信息: {status.error_message}")

    # 获取视频列表
    videos = sniffer.get_detected_videos()

    logger.info(f"\n检测到的视频列表: ({len(videos)} 个)")

    if videos:
        for i, video in enumerate(videos, 1):
            logger.info(f"\n视频 {i}:")
            logger.info(f"  - ID: {video.id}")
            logger.info(f"  - 标题: {video.title}")
            logger.info(f"  - URL: {video.url[:80]}...")
            logger.info(f"  - 缩略图: {video.thumbnail[:60] if video.thumbnail else '无'}...")
            logger.info(f"  - 时长: {video.duration}秒" if video.duration else "  - 时长: 未知")
            logger.info(f"  - 文件大小: {video.filesize}字节" if video.filesize else "  - 文件大小: 未知")
            logger.info(f"  - 分辨率: {video.resolution}" if video.resolution else "  - 分辨率: 未知")
            logger.info(f"  - 检测时间: {video.detected_at}")
            logger.info(f"  - 加密类型: {video.encryption_type.value}")

            if video.decryption_key:
                logger.info(f"  - 解密密钥: {video.decryption_key[:20]}...")
    else:
        logger.info("  暂无检测到的视频")
        logger.info("\n提示:")
        logger.info("  1. 确保嗅探器已启动（在应用中点击'启动嗅探器'）")
        logger.info("  2. 在微信视频号中播放视频")
        logger.info("  3. 等待几秒钟让系统捕获视频链接")

    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(check_status())
