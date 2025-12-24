# VidFlow 工具脚本

本目录包含用于维护和管理 VidFlow 应用的实用脚本。

## 📋 脚本列表

### 1. `generate_icon.py` - 图标生成器

**用途**: 从 PNG 源文件生成多尺寸的 Windows ICO 图标文件

**功能**:
- 读取 `resources/icons/icon.png`
- 生成包含 5 个尺寸的 ICO 文件：
  - 16x16 (任务栏、标题栏)
  - 32x32 (资源管理器)
  - 48x48 (桌面快捷方式)
  - 128x128 (Alt+Tab)
  - 256x256 (固定到任务栏)

**使用方法**:
```bash
# 在项目根目录运行
python scripts/generate_icon.py
```

**依赖**:
- Python 3.x
- Pillow (PIL)

**输出**:
- `resources/icons/icon.ico`

---

### 2. `clear_icon_cache.bat` - Windows 图标缓存清理

**用途**: 清理 Windows 图标缓存，强制系统重新加载应用图标

**功能**:
- 停止 Windows Explorer
- 删除图标缓存文件
- 重启 Windows Explorer

**使用方法**:
```bash
# 双击运行或在命令行执行
scripts\clear_icon_cache.bat
```

**注意事项**:
- 运行前请关闭所有应用程序
- 脚本会暂时关闭 Windows Explorer（桌面会短暂消失）
- 完成后会自动重启 Explorer

**何时使用**:
- 更新图标后，任务栏仍显示旧图标
- 固定到任务栏的快捷方式图标不正确
- Alt+Tab 切换器显示默认图标

---

## 🔄 常见工作流程

### 更新应用图标

1. 替换 `resources/icons/icon.png` 为新图标
2. 运行图标生成器：
   ```bash
   python scripts/generate_icon.py
   ```
3. 清理图标缓存：
   ```bash
   scripts\clear_icon_cache.bat
   ```
4. 重启 VidFlow 应用

### 首次设置图标

如果是首次运行或图标显示不正确：

1. 确认 `resources/icons/icon.ico` 存在
2. 运行缓存清理脚本
3. 重启应用

---

## 🐛 故障排除

### 图标仍然显示为默认 Electron 图标

**解决方案**:
1. 确认 `icon.ico` 文件存在且大小正常（应该 > 100KB）
2. 运行 `clear_icon_cache.bat`
3. 完全关闭 VidFlow（包括托盘图标）
4. 重启应用

### 生成图标脚本报错

**常见错误**: `ModuleNotFoundError: No module named 'PIL'`

**解决方案**:
```bash
pip install Pillow
```

### 缓存清理脚本无效

**解决方案**:
1. 以管理员身份运行脚本
2. 手动删除缓存文件：
   ```powershell
   del %LOCALAPPDATA%\IconCache.db
   del %LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*.db
   ```
3. 重启计算机（终极方案）

---

## 📚 相关文档

- [图标状态文档](../Development%20process%20record%20document/ICON_STATUS.md)
- [Electron 图标配置](../electron/main.js)
- [构建配置](../electron-builder.json)

---

**维护者**: VidFlow 开发团队
**最后更新**: 2025-12-10
