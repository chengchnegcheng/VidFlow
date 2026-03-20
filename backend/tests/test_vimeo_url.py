"""
测试 Vimeo URL: https://vimeo.com/1110267241
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.downloader import Downloader


async def test_vimeo_info():
    """测试获取 Vimeo 视频信息"""
    url = "https://vimeo.com/1148930285"

    print(f"\n{'='*60}")
    print(f"测试 Vimeo URL: {url}")
    print(f"{'='*60}\n")

    downloader = Downloader()

    try:
        print("正在获取视频信息...")
        info = await downloader.get_video_info(url)

        print("\n✅ 成功获取视频信息!\n")
        print(f"标题: {info.get('title', 'N/A')}")
        print(f"时长: {info.get('duration', 'N/A')} 秒")
        print(f"上传者: {info.get('uploader', 'N/A')}")
        print(f"描述: {info.get('description', 'N/A')[:200] if info.get('description') else 'N/A'}...")
        print(f"使用的下载器: {info.get('downloader_used', 'N/A')}")
        print(f"是否使用回退: {info.get('fallback_used', False)}")

        # 显示可用格式
        formats = info.get('formats', [])
        if formats:
            print(f"\n可用格式数量: {len(formats)}")
            print("\n前5个格式:")
            for i, fmt in enumerate(formats[:5]):
                format_id = fmt.get('format_id', 'N/A')
                ext = fmt.get('ext', 'N/A')
                resolution = fmt.get('resolution', 'N/A')
                filesize = fmt.get('filesize', 0)
                filesize_str = f"{filesize / 1024 / 1024:.2f} MB" if filesize else "未知"
                print(f"  {i+1}. ID: {format_id}, 格式: {ext}, 分辨率: {resolution}, 大小: {filesize_str}")

        return True

    except Exception as e:
        print(f"\n❌ 获取视频信息失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_vimeo_info())
    sys.exit(0 if result else 1)
