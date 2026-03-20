"""
测试视频格式和清晰度
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.downloaders.generic_downloader import GenericDownloader
from src.core.downloaders.bilibili_downloader import BilibiliDownloader
from src.core.downloaders.downloader_factory import DownloaderFactory


async def test_formats_comparison(url: str, name: str):
    """对比有无 Cookie 时的可用格式"""
    print(f"\n{'='*70}")
    print(f"测试: {name}")
    print(f"URL: {url[:80]}...")
    print(f"{'='*70}")

    # 1. 无 Cookie 的通用下载器
    print("\n【无Cookie - 通用下载器】")
    generic = DownloaderFactory.get_generic_downloader()  # 不使用 Cookie

    try:
        info = await generic.get_video_info(url)
        formats = info.get('formats', [])
        print(f"标题: {info.get('title', 'N/A')}")
        print(f"格式数量: {len(formats)}")

        # 分析视频格式
        video_formats = [f for f in formats if f.get('height', 0) > 0]
        audio_formats = [f for f in formats if f.get('acodec', 'none') != 'none' and f.get('vcodec', 'none') == 'none']

        if video_formats:
            heights = sorted(set(f.get('height', 0) for f in video_formats), reverse=True)
            print(f"可用视频画质: {heights}")
            print(f"最高画质: {max(heights)}p")

        # 显示详细格式
        print("\n详细格式列表:")
        for f in formats[:10]:  # 只显示前10个
            height = f.get('height', 0)
            width = f.get('width', 0)
            ext = f.get('ext', '?')
            quality = f.get('quality', '')
            vcodec = f.get('vcodec', 'none')[:10] if f.get('vcodec') else 'none'
            acodec = f.get('acodec', 'none')[:10] if f.get('acodec') else 'none'
            filesize = f.get('filesize', 0)
            size_mb = f"{filesize / 1024 / 1024:.1f}MB" if filesize else "?"

            if height > 0:
                print(f"  {width}x{height} ({ext}) - V:{vcodec} A:{acodec} - {size_mb}")
            elif acodec != 'none':
                print(f"  音频 ({ext}) - A:{acodec} - {size_mb}")

    except Exception as e:
        print(f"❌ 失败: {str(e)[:150]}")

    # 2. 有 Cookie 的专用下载器
    print("\n【有Cookie - 专用下载器】")
    specialized = DownloaderFactory.get_specialized_downloader(url)

    try:
        info = await specialized.get_video_info(url)
        formats = info.get('formats', [])
        print(f"标题: {info.get('title', 'N/A')}")
        print(f"格式数量: {len(formats)}")

        # 分析视频格式
        video_formats = [f for f in formats if f.get('height', 0) > 0]

        if video_formats:
            heights = sorted(set(f.get('height', 0) for f in video_formats), reverse=True)
            print(f"可用视频画质: {heights}")
            print(f"最高画质: {max(heights)}p")

        # 显示详细格式
        print("\n详细格式列表:")
        for f in formats[:10]:
            height = f.get('height', 0)
            width = f.get('width', 0)
            ext = f.get('ext', '?')
            vcodec = f.get('vcodec', 'none')[:10] if f.get('vcodec') else 'none'
            acodec = f.get('acodec', 'none')[:10] if f.get('acodec') else 'none'
            filesize = f.get('filesize', 0)
            size_mb = f"{filesize / 1024 / 1024:.1f}MB" if filesize else "?"

            if height > 0:
                print(f"  {width}x{height} ({ext}) - V:{vcodec} A:{acodec} - {size_mb}")
            elif acodec != 'none':
                print(f"  音频 ({ext}) - A:{acodec} - {size_mb}")

    except Exception as e:
        print(f"❌ 失败: {str(e)[:150]}")


async def main():
    # 测试 Bilibili 番剧（你提供的链接）
    await test_formats_comparison(
        "https://www.bilibili.com/bangumi/play/ep733317",
        "Bilibili 番剧 - 凡人风起天南"
    )

    # 测试腾讯视频
    await test_formats_comparison(
        "https://v.qq.com/x/cover/mzc0020027yzd9e/q0043cz9x20.html",
        "腾讯视频 - 斗破苍穹"
    )

    # 测试优酷
    await test_formats_comparison(
        "https://v.youku.com/v_show/id_XNjUxNjI2NTU0MA==.html",
        "优酷"
    )


if __name__ == "__main__":
    asyncio.run(main())
