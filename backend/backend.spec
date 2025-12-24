# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# 收集数据文件
import glob
datas = []
binaries = []  # 初始化 binaries 列表

# 如果 tools/bin 目录存在且有文件，则打包工具
tools_bin = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'tools', 'bin')
if os.path.exists(tools_bin) and os.listdir(tools_bin):
    # 打包所有工具文件
    for tool_file in glob.glob(os.path.join(tools_bin, '*')):
        if os.path.isfile(tool_file):
            datas.append((tool_file, 'tools/bin'))
    print(f"已打包工具目录: {tools_bin}")
else:
    print("警告: tools/bin 目录为空，工具将在首次运行时自动下载")

# 打包嵌入式 Python 3.11
python_embedded = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'python_embedded')
if os.path.exists(python_embedded):
    for root, dirs, files in os.walk(python_embedded):
        for file in files:
            src = os.path.join(root, file)
            rel_path = os.path.relpath(root, python_embedded)
            dest = os.path.join('python', rel_path) if rel_path != '.' else 'python'
            datas.append((src, dest))
    print(f"已打包嵌入式 Python: {python_embedded}")
else:
    print("警告: python_embedded 目录不存在，请运行 download_embedded_python.py")

# 收集隐藏导入
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    # 'faster_whisper',  # 已移除：作为可选工具，按需安装
    'aiohttp',
    'sqlalchemy',
    'aiosqlite',
    'httpx',
    'httpx._client',
    'httpx._config',
    'httpx._models',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    # Selenium 依赖 (Selenium 4.x 需要)
    'trio',
    'trio_websocket',
    'certifi',
    'typing_extensions',
    'browser_cookie3',
    # Selenium 和 WebDriver Manager（用于受控浏览器获取 Cookie）
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.edge',
    'selenium.webdriver.edge.service',
    'selenium.webdriver.edge.options',
    'selenium.webdriver.firefox',
    'selenium.webdriver.firefox.service',
    'selenium.webdriver.firefox.options',
    'selenium.webdriver.common',
    'selenium.webdriver.common.service',
    'selenium.webdriver.remote',
    'selenium.webdriver.support',
    'selenium.common.exceptions',
    'webdriver_manager',
    'webdriver_manager.chrome',
    'webdriver_manager.microsoft',
    'webdriver_manager.firefox',
    'webdriver_manager.core',
]

# 收集 pip 的所有内容（用于 -m pip 模式）
pip_datas, pip_binaries, pip_hiddenimports = collect_all('pip')
datas += pip_datas
hiddenimports += pip_hiddenimports

# 收集 setuptools
setuptools_datas, setuptools_binaries, setuptools_hiddenimports = collect_all('setuptools')
datas += setuptools_datas
hiddenimports += setuptools_hiddenimports

# 收集 Selenium 关键依赖（必须在 Selenium 之前）
# Selenium 4.x 依赖 trio 进行异步操作
try:
    trio_datas, trio_binaries, trio_hiddenimports = collect_all('trio')
    datas += trio_datas
    binaries += trio_binaries
    hiddenimports += trio_hiddenimports
    print(f"已收集 trio 模块（Selenium 核心依赖）")
except Exception as e:
    print(f"警告: 收集 trio 失败 - {e}")

try:
    trio_ws_datas, trio_ws_binaries, trio_ws_hiddenimports = collect_all('trio_websocket')
    datas += trio_ws_datas
    binaries += trio_ws_binaries
    hiddenimports += trio_ws_hiddenimports
    print(f"已收集 trio_websocket 模块")
except Exception as e:
    print(f"警告: 收集 trio_websocket 失败 - {e}")

# 收集 Selenium 的数据文件（JavaScript 脚本等）
try:
    selenium_datas, selenium_binaries, selenium_hiddenimports = collect_all('selenium')
    datas += selenium_datas
    binaries += selenium_binaries
    hiddenimports += selenium_hiddenimports
    print(f"已收集 Selenium 数据文件和模块")
except Exception as e:
    print(f"警告: 收集 Selenium 失败 - {e}")

# 收集 webdriver-manager 的数据文件
try:
    wdm_datas, wdm_binaries, wdm_hiddenimports = collect_all('webdriver_manager')
    datas += wdm_datas
    binaries += wdm_binaries
    hiddenimports += wdm_hiddenimports
    print(f"已收集 webdriver-manager 数据文件和模块")
except Exception as e:
    print(f"警告: 收集 webdriver-manager 失败 - {e}")

# 排除 AI 组件（作为可选工具，用户按需安装）
excludes = [
    # AI 组件
    'torch',
    'torchvision',
    'torchaudio',
    'faster_whisper',
    'ctranslate2',
    'onnxruntime',
    # 其他大型依赖
    'matplotlib',
    'scipy',
    'pandas',
    'numpy.testing',
    # 不需要的标准库模块
    # 'tkinter',         # ❌ 不能排除：某些依赖需要
    'unittest',          # 测试框架
    'pydoc',            # 文档生成
    'doctest',          # 文档测试
    'test',             # 测试模块
    # 'setuptools',     # ❌ 不能排除：pip 需要
    # 'pip',            # ❌ 不能排除：需要用于 -m pip 模式
    'wheel',            # 打包格式
    'distutils',        # 分发工具
    # 'email',          # ❌ 不能排除：uvicorn 需要
    'xml.dom',          # XML DOM（如果不用）
    'xml.sax',          # XML SAX（如果不用）
    'pdb',              # 调试器
    'profile',          # 性能分析
    'pstats',           # 性能统计
]

excludes = [name for name in excludes if name not in ('xml.dom', 'xml.sax')]

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=binaries,  # 使用收集的二进制文件
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,  # 应用排除列表
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VidFlow-Backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台窗口以查看日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../resources/icons/icon.ico' if sys.platform == 'win32' else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VidFlow-Backend',
)
