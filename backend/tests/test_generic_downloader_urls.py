"""
通用下载器 URL 测试脚本
测试多个平台的视频链接
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.downloaders.generic_downloader import GenericDownloader
from src.core.downloaders.smart_download_manager import SmartDownloadManager


# 测试 URL 列表
TEST_URLS = [
    {
        "name": "Bilibili 番剧",
        "url": "https://www.bilibili.com/bangumi/play/ep733317?from_spmid=666.25.episode.0",
        "platform": "bilibili"
    },
    {
        "name": "爱奇艺",
        "url": "https://www.iqiyi.com/v_1d74ab0t9ug.html",
        "platform": "iqiyi"
    },
    {
        "name": "腾讯视频",
        "url": "https://v.qq.com/x/cover/mzc0020027yzd9e/q0043cz9x20.html",
        "platform": "tencent"
    },
    {
        "name": "优酷",
        "url": "https://v.youku.com/v_show/id_XNjUxNjI2NTU0MA==.html",
        "platform": "youku"
    },
]


async def test_get_info_generic(url_info: dict):
    """使用通用下载器测试获取视频信息"""
    print(f"\n{'='*60}")
    print(f"测试: {url_info['name']}")
    print(f"平台: {url_info['platform']}")
    print(f"URL: {url_info['url'][:80]}...")
    print(f"{'='*60}")
    
    downloader = GenericDownloader()
    
    try:
        info = await downloader.get_video_info(url_info['url'])
        print(f"✅ 成功获取视频信息:")
        print(f"   标题: {info.get('title', 'N/A')}")
        print(f"   时长: {info.get('duration', 0)} 秒")
        print(f"   上传者: {info.get('uploader', 'N/A')}")
        print(f"   平台: {info.get('platform', 'N/A')}")
        print(f"   格式数量: {len(info.get('formats', []))}")
        return {"success": True, "info": info}
    except Exception as e:
        print(f"❌ 获取信息失败: {str(e)[:200]}")
        return {"success": False, "error": str(e)}


async def test_get_info_smart(url_info: dict):
    """使用智能下载管理器测试获取视频信息（带回退）"""
    print(f"\n{'='*60}")
    print(f"[智能模式] 测试: {url_info['name']}")
    print(f"平台: {url_info['platform']}")
    print(f"URL: {url_info['url'][:80]}...")
    print(f"{'='*60}")
    
    # 检查 Cookie 状态
    from src.core.downloaders.cookie_manager import has_cookie_for_platform, get_cookie_path_for_platform
    has_cookie = has_cookie_for_platform(url_info['platform'])
    cookie_path = get_cookie_path_for_platform(url_info['platform'])
    print(f"Cookie 已配置: {has_cookie}")
    if cookie_path:
        print(f"Cookie 路径: {cookie_path}")
    
    manager = SmartDownloadManager()
    
    try:
        info = await manager.get_info_with_fallback(url_info['url'])
        print(f"✅ 成功获取视频信息:")
        print(f"   标题: {info.get('title', 'N/A')}")
        print(f"   时长: {info.get('duration', 0)} 秒")
        print(f"   上传者: {info.get('uploader', 'N/A')}")
        print(f"   平台: {info.get('platform', 'N/A')}")
        print(f"   使用下载器: {info.get('downloader_used', 'N/A')}")
        print(f"   是否回退: {info.get('fallback_used', False)}")
        if info.get('fallback_reason'):
            print(f"   回退原因: {info.get('fallback_reason', '')[:100]}")
        return {"success": True, "info": info}
    except Exception as e:
        print(f"❌ 获取信息失败: {str(e)[:300]}")
        return {"success": False, "error": str(e)}


async def test_download_without_cookie(url_info: dict):
    """测试没有 Cookie 时能否下载（仅获取信息，不实际下载）"""
    print(f"\n{'='*60}")
    print(f"[无Cookie测试] 测试: {url_info['name']}")
    print(f"平台: {url_info['platform']}")
    print(f"URL: {url_info['url'][:80]}...")
    print(f"{'='*60}")
    
    # 直接使用通用下载器（不带 Cookie）
    from src.core.downloaders.downloader_factory import DownloaderFactory
    downloader = DownloaderFactory.get_generic_downloader()
    
    try:
        info = await downloader.get_video_info(url_info['url'])
        print(f"✅ 无Cookie也能获取视频信息:")
        print(f"   标题: {info.get('title', 'N/A')}")
        print(f"   时长: {info.get('duration', 0)} 秒")
        print(f"   格式数量: {len(info.get('formats', []))}")
        
        # 检查是否有可下载的格式
        formats = info.get('formats', [])
        if formats:
            # 找出最高画质
            video_formats = [f for f in formats if f.get('height', 0) > 0]
            if video_formats:
                max_height = max(f.get('height', 0) for f in video_formats)
                print(f"   最高画质: {max_height}p")
        
        return {"success": True, "info": info, "can_download": True}
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 无Cookie获取信息失败: {error_msg[:150]}")
        
        # 判断是否是需要登录的错误
        needs_login = any(kw in error_msg.lower() for kw in ['login', '登录', 'sign in', '会员', 'vip', 'member'])
        if needs_login:
            print(f"   💡 该视频需要登录才能下载")
        
        return {"success": False, "error": error_msg, "needs_login": needs_login}


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("通用下载器 URL 测试")
    print("="*70)
    
    results = []
    
    # 测试1: 使用智能下载管理器（带 Cookie 优先）
    print("\n" + "="*70)
    print("【测试1】智能下载管理器测试（有Cookie时使用专用下载器）")
    print("="*70)
    
    for url_info in TEST_URLS:
        result = await test_get_info_smart(url_info)
        results.append({
            "name": url_info['name'],
            "platform": url_info['platform'],
            "test_type": "smart",
            **result
        })
    
    # 测试2: 直接使用通用下载器（无 Cookie）
    print("\n" + "="*70)
    print("【测试2】通用下载器测试（无Cookie）")
    print("="*70)
    
    no_cookie_results = []
    for url_info in TEST_URLS:
        result = await test_download_without_cookie(url_info)
        no_cookie_results.append({
            "name": url_info['name'],
            "platform": url_info['platform'],
            "test_type": "no_cookie",
            **result
        })
    
    # 打印总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    
    # 智能模式结果
    print("\n【智能模式】（有Cookie时使用专用下载器）:")
    success_count = sum(1 for r in results if r['success'])
    fail_count = len(results) - success_count
    
    for r in results:
        status = "✅" if r['success'] else "❌"
        downloader = r.get('info', {}).get('downloader_used', 'N/A') if r['success'] else 'N/A'
        print(f"{status} {r['name']} ({r['platform']}) - 下载器: {downloader}")
        if not r['success']:
            print(f"   错误: {r.get('error', 'Unknown')[:80]}")
    
    print(f"\n智能模式: {success_count} 成功, {fail_count} 失败")
    
    # 无Cookie模式结果
    print("\n【无Cookie模式】（直接使用通用下载器）:")
    no_cookie_success = sum(1 for r in no_cookie_results if r['success'])
    no_cookie_fail = len(no_cookie_results) - no_cookie_success
    
    for r in no_cookie_results:
        status = "✅" if r['success'] else "❌"
        extra = ""
        if r['success']:
            extra = f"- 可下载"
        elif r.get('needs_login'):
            extra = "- 需要登录"
        print(f"{status} {r['name']} ({r['platform']}) {extra}")
    
    print(f"\n无Cookie模式: {no_cookie_success} 成功, {no_cookie_fail} 失败")
    print("="*70)
    
    return results, no_cookie_results


if __name__ == "__main__":
    asyncio.run(run_all_tests())
