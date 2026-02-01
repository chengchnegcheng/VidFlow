"""
在加密的头部搜索 moov box
"""
from pathlib import Path
import struct

file_path = Path('backend/data/downloads/视频号_2139289cb4ece765.mp4')
data = file_path.read_bytes()

print(f'文件大小: {len(data)} 字节\n')

# 加密头部大约是前 498KB
encrypted_header_size = 498058

print(f'分析前 {encrypted_header_size} 字节（加密部分）')
print('=' * 70)

# 在加密部分搜索 moov 的痕迹
# 尝试所有可能的单字节 XOR 密钥
print('\n尝试用不同的 XOR 密钥解密前 500KB，搜索 moov box...\n')

encrypted_data = data[:encrypted_header_size]

for key in range(256):
    # 解密
    decrypted = bytearray(encrypted_data)
    for i in range(len(decrypted)):
        decrypted[i] ^= key
    
    # 搜索 moov
    moov_pos = decrypted.find(b'moov')
    if moov_pos > 4:
        # 检查是否是有效的 box
        try:
            box_size = struct.unpack('>I', decrypted[moov_pos-4:moov_pos])[0]
            if 8 <= box_size <= len(encrypted_data):
                print(f'✓ 密钥 0x{key:02X}: 在位置 {moov_pos-4} 找到 moov box (大小: {box_size} 字节)')
                
                # 显示解密后的数据
                print(f'  解密后的前32字节:')
                print(f'  {" ".join(f"{b:02X}" for b in decrypted[:32])}')
                
                # 检查是否有 ftyp
                ftyp_pos = decrypted.find(b'ftyp')
                if ftyp_pos > 0:
                    print(f'  也找到 ftyp 在位置 {ftyp_pos}')
                
                # 尝试重建完整文件
                print(f'\n  尝试重建完整的 MP4 文件...')
                
                # 解密整个头部
                full_decrypted = bytearray(data)
                for i in range(encrypted_header_size):
                    full_decrypted[i] ^= key
                
                output_file = file_path.with_name('视频号_完整解密.mp4')
                output_file.write_bytes(full_decrypted)
                
                print(f'  ✓ 已保存到: {output_file}')
                print(f'  文件大小: {len(full_decrypted)} 字节')
                print(f'  文件头: {" ".join(f"{b:02X}" for b in full_decrypted[:32])}')
                
                # 验证文件头
                if full_decrypted[4:8] == b'ftyp':
                    print(f'\n  ✓✓✓ 成功！文件头是有效的 MP4 (ftyp)！')
                    print(f'  请尝试播放: {output_file}')
                    break
        except:
            pass

print('\n搜索完成')
