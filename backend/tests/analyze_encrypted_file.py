"""
分析加密文件，寻找 MP4 标记
"""
from pathlib import Path

# 读取文件
f = Path('backend/data/downloads/视频号_2139289cb4ece765.mp4.encrypted')
data = f.read_bytes()

print(f'文件大小: {len(data)} 字节 ({len(data)/1024/1024:.2f} MB)')
print(f'\n前32字节:')
print(' '.join(f'{b:02X}' for b in data[:32]))
print()

# 尝试查找 MP4 的特征标记
markers = [b'ftyp', b'moov', b'mdat', b'free', b'moof', b'sidx']
print('搜索 MP4 标记:')
for marker in markers:
    pos = data.find(marker)
    if pos > 0:
        print(f'\n找到 {marker.decode()} 在位置 {pos} (0x{pos:X})')
        print(f'  前4字节: {" ".join(f"{b:02X}" for b in data[pos-4:pos])}')
        print(f'  标记: {marker.decode()}')
        print(f'  后8字节: {" ".join(f"{b:02X}" for b in data[pos+4:pos+12])}')
        
        # 如果找到 ftyp，这可能是真正的文件开始
        if marker == b'ftyp' and pos < 1000:
            print(f'\n  *** 可能的文件开始位置: {pos}')
            print(f'  从位置 {pos-4} 开始的完整 box:')
            box_start = pos - 4
            print(f'  {" ".join(f"{b:02X}" for b in data[box_start:box_start+32])}')

# 检查是否整个文件都被加密
print('\n\n检查文件的不同位置:')
positions = [0, 1024, 4096, 10240, 102400, len(data)//2]
for pos in positions:
    if pos < len(data):
        sample = data[pos:pos+16]
        print(f'位置 {pos:8d}: {" ".join(f"{b:02X}" for b in sample)}')

# 统计字节分布
print('\n\n字节值统计（前10000字节）:')
from collections import Counter
byte_freq = Counter(data[:10000])
most_common = byte_freq.most_common(10)
print('最常见的10个字节:')
for byte_val, count in most_common:
    print(f'  0x{byte_val:02X}: {count} 次 ({count/100:.1f}%)')
