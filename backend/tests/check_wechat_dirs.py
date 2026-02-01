"""
检查微信目录结构
"""

import os
from pathlib import Path

def check_directory(base_path):
    """检查目录结构"""
    print(f"\n{'='*60}")
    print(f"检查目录: {base_path}")
    print(f"{'='*60}")
    
    if not base_path.exists():
        print("❌ 目录不存在")
        return
    
    print("✅ 目录存在")
    
    # 列出所有子目录
    try:
        subdirs = [d for d in base_path.iterdir() if d.is_dir()]
        print(f"\n包含 {len(subdirs)} 个子目录:")
        for subdir in subdirs[:20]:  # 只显示前 20 个
            print(f"  📁 {subdir.name}")
            
            # 检查是否有视频相关目录
            video_paths = [
                subdir / 'FileStorage' / 'Video',
                subdir / 'FileStorage' / 'Cache' / 'Video',
                subdir / 'Video',
                subdir / 'Sns' / 'Video',
                subdir / 'Cache' / 'Video',
            ]
            
            for video_path in video_paths:
                if video_path.exists():
                    print(f"     📹 {video_path.relative_to(base_path)}")
                    
                    # 统计文件
                    try:
                        files = list(video_path.rglob('*'))
                        file_count = len([f for f in files if f.is_file()])
                        large_files = [f for f in files if f.is_file() and f.stat().st_size > 1024*1024]
                        
                        print(f"        文件数: {file_count}")
                        if large_files:
                            print(f"        大文件 (>1MB): {len(large_files)}")
                            for lf in large_files[:3]:
                                size_mb = lf.stat().st_size / 1024 / 1024
                                print(f"          - {lf.name} ({size_mb:.2f} MB)")
                    except Exception as e:
                        print(f"        ⚠️  无法访问: {e}")
    except PermissionError:
        print("❌ 没有访问权限")
    except Exception as e:
        print(f"❌ 错误: {e}")


def main():
    """主函数"""
    userprofile = os.environ.get('USERPROFILE', '')
    appdata = os.environ.get('APPDATA', '')
    
    # 检查找到的两个目录
    dirs_to_check = [
        Path(userprofile) / 'Documents' / 'Tencent Files',
        Path(appdata) / 'Tencent' / 'WeChat',
    ]
    
    for dir_path in dirs_to_check:
        check_directory(dir_path)
    
    print(f"\n{'='*60}")
    print("检查完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
