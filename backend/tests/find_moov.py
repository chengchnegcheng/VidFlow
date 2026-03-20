"""
查找 moov box（包含视频元数据）
"""
from pathlib import Path
import struct

# 读取原始加密文件（可能是 .mp4 或 .encrypted）
encrypted_file = Path('backend/data/downloads/视频号_2139289cb4ece765.mp4')
if not encrypted_file.exists():
    encrypted_file = Path('backend/data/downloads/视频号_2139289cb4ece765.mp4.encrypted')

if not encrypted_file.exists():
    print("文件不存在！")
    exit(1)

data = encrypted_file.read_bytes()
print(f'文件大小: {len(data)} 字节 ({len(data)/1024/1024:.2f} MB)\n')

# 搜索所有 MP4 box
boxes = [b'ftyp', b'moov', b'mdat', b'free', b'skip', b'wide', b'moof', b'sidx', b'mvhd', b'trak']

print('搜索所有 MP4 Box:')
print('=' * 70)

found_boxes = []
for box_type in boxes:
    pos = 0
    while True:
        pos = data.find(box_type, pos)
        if pos == -1:
            break

        # 检查是否是有效的 box（前4字节是大小）
        if pos >= 4:
            try:
                box_size = struct.unpack('>I', data[pos-4:pos])[0]
                # Box 大小应该合理
                if 8 <= box_size <= len(data) and box_size < 100000000:
                    found_boxes.append({
                        'type': box_type.decode(),
                        'pos': pos - 4,
                        'size': box_size
                    })
                    print(f'{box_type.decode():6s} @ 0x{pos-4:08X} ({pos-4:10d}) - 大小: {box_size:12d} 字节')
            except:
                pass
        pos += 1

if not found_boxes:
    print('未找到任何 MP4 Box！')
else:
    print(f'\n找到 {len(found_boxes)} 个 Box')

    # 检查是否有 moov
    moov_boxes = [b for b in found_boxes if b['type'] == 'moov']
    if moov_boxes:
        print(f'\n✓ 找到 {len(moov_boxes)} 个 moov box（包含视频元数据）')
        for moov in moov_boxes:
            print(f"  位置: 0x{moov['pos']:X}, 大小: {moov['size']} 字节")
    else:
        print('\n✗ 未找到 moov box！这就是为什么播放器无法播放')
        print('  moov box 包含视频的元数据（时长、编码、轨道等）')
        print('  没有 moov box，播放器无法知道如何解析 mdat 中的数据')

        # 检查是否有 moof（fragmented MP4）
        moof_boxes = [b for b in found_boxes if b['type'] == 'moof']
        if moof_boxes:
            print(f'\n  但找到了 {len(moof_boxes)} 个 moof box（分片 MP4）')
            print('  这可能是一个 fragmented MP4 文件')
