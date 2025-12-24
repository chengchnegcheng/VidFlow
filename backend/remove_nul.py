import os
import sys

# 获取当前目录
current_dir = os.getcwd()
nul_path = os.path.join(current_dir, 'nul')
print(f'尝试删除: {nul_path}')

# Windows 扩展路径前缀
extended_path = '\\\\?\\' + nul_path
print(f'使用扩展路径: {extended_path}')

try:
    os.remove(extended_path)
    print('成功删除 nul 文件')
except Exception as e:
    print(f'删除失败: {e}')
    sys.exit(1)
