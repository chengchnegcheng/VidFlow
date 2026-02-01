"""
尝试从加密文件中提取 MP4 部分
"""
from pathlib import Path
import struct

# 读取文件
input_file = Path('backend/data/downloads/视频号_2139289cb4ece765.mp4.encrypted')
data = input_file.read_bytes()

print(f'文件大小: {len(data)} 字节')

# 找到 free box 的位置
free_pos = data.find(b'free')
print(f'\n找到 free 标记在位置: {free_pos} (0x{free_pos:X})')

# free box 前4字节应该是 box 大小
if free_pos > 4:
    box_size_bytes = data[free_pos-4:free_pos]
    box_size = struct.unpack('>I', box_size_bytes)[0]
    print(f'free box 大小: {box_size} 字节')
    print(f'free box 开始位置: {free_pos-4}')
    
    # 显示 free box 前面的数据
    print(f'\nfree box 前面的32字节:')
    print(' '.join(f'{b:02X}' for b in data[free_pos-36:free_pos-4]))
    
    # 尝试往前查找 ftyp
    # MP4 文件通常以 ftyp box 开始
    search_start = max(0, free_pos - 100000)  # 往前搜索 100KB
    search_data = data[search_start:free_pos]
    
    ftyp_pos_in_search = search_data.find(b'ftyp')
    if ftyp_pos_in_search >= 0:
        ftyp_pos = search_start + ftyp_pos_in_search
        print(f'\n找到 ftyp 标记在位置: {ftyp_pos} (0x{ftyp_pos:X})')
        
        # ftyp 前4字节是 box 大小
        if ftyp_pos >= 4:
            ftyp_box_size_bytes = data[ftyp_pos-4:ftyp_pos]
            ftyp_box_size = struct.unpack('>I', ftyp_box_size_bytes)[0]
            print(f'ftyp box 大小: {ftyp_box_size} 字节')
            
            # 这应该是文件的真正开始
            mp4_start = ftyp_pos - 4
            print(f'\nMP4 文件开始位置: {mp4_start} (0x{mp4_start:X})')
            print(f'前面有 {mp4_start} 字节的加密数据')
            
            # 提取 MP4 部分
            mp4_data = data[mp4_start:]
            output_file = input_file.with_name('视频号_extracted.mp4')
            output_file.write_bytes(mp4_data)
            
            print(f'\n✓ 已提取 MP4 文件到: {output_file}')
            print(f'  提取的文件大小: {len(mp4_data)} 字节 ({len(mp4_data)/1024/1024:.2f} MB)')
            print(f'  文件头: {" ".join(f"{b:02X}" for b in mp4_data[:20])}')
            
            # 验证文件头
            if mp4_data[4:8] == b'ftyp':
                print('\n✓ 文件头验证成功！这是有效的 MP4 文件')
            else:
                print('\n✗ 文件头验证失败')
    else:
        print('\n未找到 ftyp 标记')
        
        # 尝试另一种方法：从 free box 开始提取
        print('\n尝试从 free box 开始提取...')
        mp4_start = free_pos - 4
        mp4_data = data[mp4_start:]
        output_file = input_file.with_name('视频号_from_free.mp4')
        output_file.write_bytes(mp4_data)
        print(f'已保存到: {output_file}')
