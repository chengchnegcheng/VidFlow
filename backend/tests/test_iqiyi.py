"""测试爱奇艺下载器"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.core.downloaders.iqiyi_downloader import IqiyiDownloader


async def test():
    downloader = IqiyiDownloader()
    url = 'https://www.iqiyi.com/v_1d74ab0t9ug.html'
    
    print('Testing iQiyi downloader...')
    print(f'URL: {url}')
    
    try:
        info = await downloader.get_video_info(url)
        print(f'Title: {info.get("title", "N/A")}')
        print(f'Duration: {info.get("duration", 0)} seconds')
        print(f'Video URLs found: {len(info.get("video_urls", []))}')
        if info.get('video_urls'):
            for i, vurl in enumerate(info['video_urls'][:3]):
                print(f'  URL {i+1}: {vurl[:80]}...')
        print('SUCCESS!')
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    asyncio.run(test())
