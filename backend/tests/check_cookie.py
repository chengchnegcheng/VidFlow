"""检查 Cookie 文件"""
from pathlib import Path

cookie_file = Path('data/cookies/bilibili_cookies.txt')
if cookie_file.exists():
    content = cookie_file.read_text(encoding='utf-8')
    lines = [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
    print(f'Cookie 文件存在，有效行数: {len(lines)}')

    # 检查关键 Cookie
    has_sessdata = any('SESSDATA' in l for l in lines)
    has_bili_jct = any('bili_jct' in l for l in lines)
    has_dedeuserid = any('DedeUserID' in l for l in lines)

    print(f'SESSDATA: {"有" if has_sessdata else "无"}')
    print(f'bili_jct: {"有" if has_bili_jct else "无"}')
    print(f'DedeUserID: {"有" if has_dedeuserid else "无"}')

    if has_sessdata and has_bili_jct and has_dedeuserid:
        print('Cookie 看起来完整')
    else:
        print('Cookie 可能不完整')

    # 显示前几行（隐藏敏感值）
    print('\n前5行内容:')
    for line in lines[:5]:
        parts = line.split('\t')
        if len(parts) >= 6:
            name = parts[5] if len(parts) > 5 else '?'
            print(f'  {parts[0]} - {name}')
else:
    print('Cookie 文件不存在')
