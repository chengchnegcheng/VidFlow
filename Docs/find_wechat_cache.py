"""查找微信视频缓存"""
import os
from pathlib import Path

def find_wechat_dirs():
    """查找微信相关目录"""
    results = []
    
    # 常见位置
    search_paths = [
        Path(os.environ.get('USERPROFILE', '')) / 'Documents',
        Path(os.environ.get('APPDATA', '')),
        Path(os.environ.get('LOCALAPPDATA', '')),
        Path('C:/'),
        Path('D:/'),
    ]
    
    keywords = ['WeChat', 'Weixin', 'Tencent']
    
    for base in search_paths:
        if not base.exists():
            continue
        
        try:
            for item in base.iterdir():
                if item.is_dir():
                    name_lower = item.name.lower()
                    if any(kw.lower() in name_lower for kw in keywords):
                        results.append(item)
        except PermissionError:
            pass
    
    return results


def find_video_cache(wechat_dir: Path):
    """在微信目录中查找视频缓存"""
    video_dirs = []
    
    try:
        for item in wechat_dir.rglob('*'):
            if item.is_dir():
                name_lower = item.name.lower()
                if 'video' in name_lower or 'finder' in name_lower or 'cache' in name_lower:
                    # 检查是否有视频文件
                    has_videos = False
                    try:
                        for f in item.iterdir():
                            if f.is_file() and f.stat().st_size > 100 * 1024:
                                has_videos = True
                                break
                    except:
                        pass
                    
                    if has_videos:
                        video_dirs.append(item)
    except PermissionError:
        pass
    
    return video_dirs


def main():
    print("=" * 60)
    print("查找微信视频缓存")
    print("=" * 60)
    
    # 查找微信目录
    wechat_dirs = find_wechat_dirs()
    print(f"\n找到 {len(wechat_dirs)} 个微信相关目录:")
    for d in wechat_dirs:
        print(f"  - {d}")
    
    # 在每个目录中查找视频缓存
    print("\n查找视频缓存目录...")
    all_video_dirs = []
    
    for wechat_dir in wechat_dirs:
        video_dirs = find_video_cache(wechat_dir)
        all_video_dirs.extend(video_dirs)
    
    print(f"\n找到 {len(all_video_dirs)} 个可能的视频缓存目录:")
    for d in all_video_dirs:
        # 统计文件数量和大小
        try:
            files = list(d.iterdir())
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            print(f"  - {d}")
            print(f"    文件数: {len(files)}, 总大小: {total_size / 1024 / 1024:.1f} MB")
        except:
            print(f"  - {d} (无法访问)")
    
    # 查找最近的视频文件
    print("\n查找最近的视频文件...")
    recent_videos = []
    
    for video_dir in all_video_dirs:
        try:
            for f in video_dir.iterdir():
                if f.is_file() and f.stat().st_size > 100 * 1024:
                    recent_videos.append({
                        'path': f,
                        'size': f.stat().st_size,
                        'mtime': f.stat().st_mtime,
                    })
        except:
            pass
    
    # 按修改时间排序
    recent_videos.sort(key=lambda x: x['mtime'], reverse=True)
    
    print(f"\n最近的 10 个视频文件:")
    for v in recent_videos[:10]:
        import datetime
        mtime = datetime.datetime.fromtimestamp(v['mtime'])
        print(f"  - {v['path'].name}")
        print(f"    大小: {v['size'] / 1024 / 1024:.1f} MB, 修改时间: {mtime}")
        print(f"    路径: {v['path']}")


if __name__ == "__main__":
    main()
