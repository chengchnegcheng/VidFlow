"""
测试腾讯视频和优酷视频下载
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.downloader import Downloader


async def test_video_info(url: str, name: str):
    """测试获取视频信息"""
    print(f"\n{'='*60}")
    print(f"测试 {name}: {url[:60]}...")
    print(f"{'='*60}\n")
    
    downloader = Downloader()
    
    try:
        print("正在获取视频信息...")
        info = await downloader.get_video_info(url)
        
        print(f"\n✅ 成功获取视频信息!")
        print(f"标题: {info.get('title', 'N/A')}")
        print(f"时长: {info.get('duration', 'N/A')} 秒")
        print(f"上传者: {info.get('uploader', 'N/A')}")
        print(f"平台: {info.get('platform', 'N/A')}")
        print(f"使用的下载器: {info.get('downloader_used', 'N/A')}")
        print(f"是否使用回退: {info.get('fallback_used', False)}")
        
        formats = info.get('formats', [])
        if formats:
            print(f"\n可用格式数量: {len(formats)}")
            print("前5个格式:")
            for i, fmt in enumerate(formats[:5]):
                format_id = fmt.get('format_id', 'N/A')
                ext = fmt.get('ext', 'N/A')
                resolution = fmt.get('resolution', fmt.get('height', 'N/A'))
                print(f"  {i+1}. ID: {format_id}, 格式: {ext}, 分辨率: {resolution}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 获取视频信息失败: {e}")
        return False


async def main():
    # 腾讯视频
    qq_url = "https://v.qq.com/x/cover/mzc0020027yzd9e/l0047gd6p19.html"
    
    # 优酷视频
    youku_url = "https://v.youku.com/v_show/id_XNjUxNjI2NTU0MA==.html"
    
    results = []
    
    results.append(("腾讯视频", await test_video_info(qq_url, "腾讯视频")))
    results.append(("优酷视频", await test_video_info(youku_url, "优酷视频")))
    
    print(f"\n{'='*60}")
    print("测试结果汇总:")
    print(f"{'='*60}")
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
