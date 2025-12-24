# Selenium 安装问题修复

## 问题描述

自动Cookie获取功能报错：
```
Error: Selenium 未安装。请运行: pip install selenium
```

## 根本原因

虽然 `requirements.txt` 中包含了 `selenium>=4.15.0`，但：
1. 用户可能没有运行 `scripts\INSTALL_ALL.bat` 重新安装依赖
2. 或者后端服务启动于 Selenium 安装之前

## 解决方案

### ✅ 已完成的修复

1. **在 venv 中安装 Selenium**：
   ```bash
   cd backend
   .\venv\Scripts\python.exe -m pip install selenium>=4.15.0
   ```
   
2. **验证安装**：
   - Selenium 4.38.0 已成功安装
   - ChromeDriver 模块导入正常

### 🔄 用户需要执行的操作

**重启后端服务**以加载新安装的 Selenium：

#### 方法 1：使用启动脚本（推荐）
```batch
# 1. 关闭所有 VidFlow 相关窗口
# 2. 重新运行
scripts\START.bat
```

#### 方法 2：手动重启后端
```batch
# 1. 关闭后端命令窗口
# 2. 重新启动后端
cd backend
venv\Scripts\activate
set PYTHONPATH=%CD%
python -m src.main
```

## 自动Cookie获取功能使用说明

重启后端后，Cookie管理页面的"🤖 自动获取Cookie"按钮将正常工作：

1. **点击"自动获取Cookie"按钮**
2. **系统会自动打开Chrome浏览器**（受控模式）
3. **在浏览器中手动登录目标平台**（如抖音、小红书等）
4. **登录完成后，点击"提取Cookie"按钮**
5. **Cookie将自动保存到配置文件**

## ChromeDriver 说明

Selenium 4.6+ 版本内置了自动管理 ChromeDriver 的功能：
- 首次使用时会自动下载匹配系统 Chrome 版本的 ChromeDriver
- 无需手动下载或配置 ChromeDriver
- 前提是系统中已安装 Google Chrome 浏览器

如果系统中没有安装 Chrome，请下载安装：
https://www.google.com/chrome/

## 技术细节

### 为什么会出现这个问题？

1. **后端使用虚拟环境**：
   ```batch
   # START.bat 中的启动命令
   venv\Scripts\activate && python -m src.main
   ```

2. **系统Python ≠ venv Python**：
   - 系统Python: `Python 3.14.0`
   - venv Python: `Python 3.11.x`（独立环境）
   - **Selenium必须安装在venv中**

3. **运行时检测**：
   ```python
   # backend/src/core/cookie_helper.py
   def is_selenium_available(self) -> bool:
       try:
           import selenium
           from selenium import webdriver
           return True
       except ImportError:
           return False
   ```

### 安装验证

```batch
cd backend
.\venv\Scripts\python.exe -c "import selenium; print('Selenium:', selenium.__version__)"
# 输出: Selenium: 4.38.0
```

## 相关文件

- `backend/requirements.txt` - 包含 `selenium>=4.15.0`
- `backend/src/core/cookie_helper.py` - Cookie自动获取实现
- `frontend/src/components/CookieManager.tsx` - Cookie管理UI
- `scripts/INSTALL_ALL.bat` - 自动安装脚本

## 未来改进

为避免此类问题，建议：
1. ✅ 在 `INSTALL_ALL.bat` 中明确提示 Selenium 安装状态
2. ✅ 在UI中显示更友好的Selenium未安装提示
3. 🔄 添加后端健康检查API，包含Selenium状态
4. 🔄 在系统设置中显示依赖状态（Selenium、ChromeDriver等）

---

**修复时间**：2025-11-01  
**修复人员**：AI Assistant  
**影响范围**：Cookie自动获取功能

