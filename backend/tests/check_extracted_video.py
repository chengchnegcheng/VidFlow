"""
检查提取的视频文件
"""

from pathlib import Path

# 检查文件
video_path = Path("D:/Coding Project/VidFlow/VidFlow/backend/tests/output/视频号_缓存_20260125_202632.mp4")

if video_path.exists():
    print(f"✅ 文件存在: {video_path}")
    print(f"文件大小: {video_path.stat().st_size / 1024 / 1024:.2f} MB")

    # 检查文件头
    with open(video_path, 'rb') as f:
        header = f.read(12)
        print(f"文件头: {header.hex()}")

        # 检查是否是 MP4
        if header[4:8] == b'ftyp':
            print("✅ 这是一个有效的 MP4 文件")
        else:
            print("❌ 这不是一个有效的 MP4 文件")

        # 检查是否有 moov box
        f.seek(0)
        content = f.read(min(10 * 1024 * 1024, video_path.stat().st_size))  # 读取前 10MB 或整个文件
        if b'moov' in content:
            print("✅ 包含 moov box，可以播放")
            moov_pos = content.find(b'moov')
            print(f"   moov box 位置: {moov_pos}")
        else:
            print("❌ 缺少 moov box，无法播放")
else:
    print(f"❌ 文件不存在: {video_path}")
