"""
测试打包后的应用是否能正确导入 Selenium
这个脚本模拟 PyInstaller 打包后的导入环境
"""
import sys
import os
import traceback
import io

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 70)
print("PyInstaller 打包环境 Selenium 导入测试")
print("=" * 70)

# 显示当前 Python 环境信息
print(f"\n当前 Python 版本: {sys.version}")
print(f"当前 Python 路径: {sys.executable}")
print(f"\nPython 搜索路径:")
for i, path in enumerate(sys.path, 1):
    print(f"  {i}. {path}")

print("\n" + "=" * 70)
print("开始导入测试")
print("=" * 70)

# 测试 1: 基础导入
print("\n[测试 1] 导入 selenium 模块...")
try:
    import selenium
    print(f"✓ 成功导入 selenium")
    print(f"  版本: {getattr(selenium, '__version__', '未知')}")
    print(f"  路径: {getattr(selenium, '__file__', '未知')}")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    print(f"  详细错误信息:")
    traceback.print_exc()
    print("\n可能的原因:")
    print("  1. PyInstaller 打包时未正确收集 selenium 模块")
    print("  2. 缺少 selenium 的依赖模块")
    print("  3. 模块路径配置有问题")
    sys.exit(1)

# 测试 2: 导入 webdriver
print("\n[测试 2] 导入 selenium.webdriver...")
try:
    from selenium import webdriver
    print(f"✓ 成功导入 selenium.webdriver")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 导入各个浏览器的 webdriver
browsers = [
    ('Chrome', 'selenium.webdriver.chrome.options', 'Options'),
    ('Chrome Service', 'selenium.webdriver.chrome.service', 'Service'),
    ('Edge', 'selenium.webdriver.edge.options', 'Options'),
    ('Edge Service', 'selenium.webdriver.edge.service', 'Service'),
    ('Firefox', 'selenium.webdriver.firefox.options', 'Options'),
    ('Firefox Service', 'selenium.webdriver.firefox.service', 'Service'),
]

print("\n[测试 3] 导入各浏览器 WebDriver 模块...")
for name, module_path, class_name in browsers:
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"✓ {name:20s} - {module_path}")
    except ImportError as e:
        print(f"✗ {name:20s} - 导入失败: {e}")
        sys.exit(1)

# 测试 4: 导入 webdriver-manager
print("\n[测试 4] 导入 webdriver-manager...")
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    print(f"✓ 成功导入 webdriver-manager")
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    traceback.print_exc()
    print("\n注意: webdriver-manager 是可选的，如果缺失可能影响自动下载驱动功能")

# 测试 5: 检查 selenium 的关键依赖
print("\n[测试 5] 检查 Selenium 的关键依赖...")
dependencies = [
    'trio',
    'trio_websocket',
    'urllib3',
    'certifi',
    'typing_extensions',
]

missing_deps = []
for dep in dependencies:
    try:
        __import__(dep)
        print(f"✓ {dep:20s} - 已安装")
    except ImportError:
        print(f"✗ {dep:20s} - 缺失")
        missing_deps.append(dep)

if missing_deps:
    print(f"\n警告: 缺少 {len(missing_deps)} 个依赖模块")
    print("  这可能导致 Selenium 功能异常")
    print("  缺失的模块:", ", ".join(missing_deps))

# 测试 6: 模拟 cookie_helper 的检测逻辑
print("\n[测试 6] 模拟 CookieBrowserManager.is_selenium_available()...")
try:
    import selenium
    from selenium import webdriver
    is_available = True
    print(f"✓ is_selenium_available() 会返回: True")
except ImportError:
    is_available = False
    print(f"✗ is_selenium_available() 会返回: False")
    print("  这就是为什么会提示 'Selenium 未安装'")

print("\n" + "=" * 70)
if is_available and not missing_deps:
    print("✓ 所有测试通过！Selenium 功能应该可以正常工作")
elif is_available and missing_deps:
    print("⚠ Selenium 可以导入，但缺少依赖模块，可能会有问题")
else:
    print("✗ Selenium 导入失败，需要修复打包配置")
print("=" * 70)
