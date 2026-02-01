"""
深度分析加密文件
"""
from pathlib import Path
import struct

input_file = Path('backend/data/downloads/视频号_2139289cb4ece765.mp4.encrypted')
data = input_file.read_bytes()

print('=' * 60)
print('深度分析微信视频号加密文件')
print('=' * 60)

# 搜索所有可能的 MP4 标记
markers = {
    b'ftyp': 'File Type Box',
    b'moov': 'Movie Box',
    b'mdat': 'Media Data Box',
    b'free': 'Free Space Box',
    b'skip': 'Skip Box',
    b'wide': 'Wide Box',
    b'moof': 'Movie Fragment Box',
    b'sidx': 'Segment Index Box',
}

print('\n搜索所有 MP4 Box 标记:')
print('-' * 60)

found_positions = []
for marker, description in markers.items():
    pos = 0
    count = 0
    while True:
        pos = data.find(marker, pos)
        if pos == -1:
            break
        
        # 检查前4字节是否是合理的 box 大小
        if pos >= 4:
            try:
                box_size = struct.unpack('>I', data[pos-4:pos])[0]
                # Box 大小应该是合理的（8字节到文件大小之间）
                if 8 <= box_size <= len(data):
                    print(f'{marker.decode():6s} @ 0x{pos:08X} ({pos:10d}) - {description}')
                    print(f'       Box 大小: {box_size} 字节')
                    found_positions.append((pos-4, marker, box_size))
                    count += 1
            except:
                pass
        pos += 1
    
    if count == 0:
        print(f'{marker.decode():6s} - 未找到')

# 如果找到了任何 box，尝试重建文件
if found_positions:
    print('\n' + '=' * 60)
    print('尝试重建 MP4 文件')
    print('=' * 60)
    
    # 按位置排序
    found_positions.sort()
    
    # 找到最早的 box
    first_box_pos, first_marker, first_size = found_positions[0]
    print(f'\n最早的 Box: {first_marker.decode()} 在位置 0x{first_box_pos:X}')
    
    # 从这个位置开始提取
    extracted_data = data[first_box_pos:]
    output_file = input_file.with_name('视频号_rebuilt.mp4')
    output_file.write_bytes(extracted_data)
    
    print(f'\n✓ 已保存重建的文件到: {output_file}')
    print(f'  文件大小: {len(extracted_data)} 字节 ({len(extracted_data)/1024/1024:.2f} MB)')
    print(f'  文件头: {" ".join(f"{b:02X}" for b in extracted_data[:32])}')
    
    # 检查是否是有效的 MP4
    if extracted_data[4:8] == b'ftyp':
        print('\n✓✓✓ 成功！这是有效的 MP4 文件！')
        print('请尝试播放: backend/data/downloads/视频号_rebuilt.mp4')
    elif extracted_data[4:8] in [b'free', b'skip', b'wide']:
        print(f'\n文件以 {extracted_data[4:8].decode()} box 开始')
        print('这可能是有效的 MP4，但不是标准格式')
    else:
        print('\n文件头不是标准 MP4 格式')
else:
    print('\n未找到任何有效的 MP4 Box 标记')
    print('文件可能使用了更复杂的加密方式')
