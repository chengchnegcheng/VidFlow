"""测试 Selenium 导入是否正常"""
import sys
import traceback
import io

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 60)
print("测试 Selenium 导入")
print("=" * 60)

# 测试 1: 导入 selenium
print("\n[测试 1] 导入 selenium...")
try:
    import selenium
    print(f"✅ 成功导入 selenium")
    print(f"   版本: {selenium.__version__}")
    print(f"   路径: {selenium.__file__}")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 2: 导入 selenium.webdriver
print("\n[测试 2] 导入 selenium.webdriver...")
try:
    from selenium import webdriver
    print(f"✅ 成功导入 selenium.webdriver")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 导入 Chrome 相关模块
print("\n[测试 3] 导入 Chrome webdriver 模块...")
try:
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    print(f"✅ 成功导入 Chrome webdriver 模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 4: 导入 Edge 相关模块
print("\n[测试 4] 导入 Edge webdriver 模块...")
try:
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    print(f"✅ 成功导入 Edge webdriver 模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 5: 导入 Firefox 相关模块
print("\n[测试 5] 导入 Firefox webdriver 模块...")
try:
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    print(f"✅ 成功导入 Firefox webdriver 模块")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 6: 导入 webdriver-manager
print("\n[测试 6] 导入 webdriver-manager...")
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    print(f"✅ 成功导入 webdriver-manager")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试 7: 测试 cookie_helper 的 is_selenium_available
print("\n[测试 7] 测试 CookieBrowserManager.is_selenium_available()...")
try:
    sys.path.insert(0, 'd:\\Coding Project\\VidFlow\\VidFlow-Desktop\\backend\\src')
    from core.cookie_helper import CookieBrowserManager

    manager = CookieBrowserManager()
    is_available = manager.is_selenium_available()

    if is_available:
        print(f"✅ is_selenium_available() 返回 True")
    else:
        print(f"❌ is_selenium_available() 返回 False")
        sys.exit(1)
except Exception as e:
    print(f"❌ 测试失败: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有测试通过！Selenium 功能正常。")
print("=" * 60)
