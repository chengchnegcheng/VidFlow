# VidFlow Desktop 图标生成器

基于 VidFlow Desktop 软件界面设计的多尺寸图标生成工具。

## 📁 文件说明

- `icon.svg` - SVG 矢量图标源文件
- `generate_icons.py` - Python 图标生成脚本（跨平台）
- `generate_icons.bat` - Windows 批处理脚本
- `icon_preview.html` - 图标预览页面
- `README.md` - 本说明文件

## 🚀 快速开始

### 🎯 最简单方案 (推荐)

**运行一键安装脚本**：
```cmd
easy_setup.bat
```
脚本会自动检测并安装必要工具，然后生成所有图标。

### 📋 详细方案

#### Windows 用户

**方案 1: 自动安装**
1. 双击运行 `easy_setup.bat`
2. 选择自动安装 Inkscape
3. 等待图标生成完成

**方案 2: 手动安装**
1. 安装 [Inkscape](https://inkscape.org/)
2. 运行 `generate_icons.bat`

**方案 3: 在线转换**
1. 查看 `manual_conversion_guide.md`
2. 使用在线工具转换 SVG

#### 其他系统用户

```bash
# Ubuntu/Debian
sudo apt install inkscape imagemagick
python generate_icons.py

# macOS
brew install inkscape imagemagick
python generate_icons.py
```

## 📐 生成的图标尺寸

### PNG 文件
- **16×16, 24×24, 32×32** - 小图标（工具栏、列表）
- **48×48, 64×64** - 中等图标（桌面快捷方式）
- **96×96, 128×128** - 大图标（高DPI显示）
- **256×256, 512×512, 1024×1024** - 超高清图标

### 特殊格式
- **ICO 文件** - Windows 应用程序图标
- **ICNS 文件** - macOS 应用程序图标（仅在 macOS 上生成）

## 🎨 设计特色

- **主色调**：黑白简约风格，深灰渐变背景 (#2c2c2c 到 #1a1a1a)
- **核心元素**：白色下载箭头，体现下载管理功能
- **设计风格**：现代简约，圆角矩形背景，符合软件界面风格
- **装饰元素**：简约线条，暗示数据流动和传输

## 📂 输出目录结构

```
icons/
├── png/           # PNG 格式图标
│   ├── vidflow-16x16.png
│   ├── vidflow-24x24.png
│   ├── vidflow-32x32.png
│   └── ...
├── ico/           # Windows ICO 文件
│   └── vidflow.ico
├── icns/          # macOS ICNS 文件
│   └── vidflow.icns
└── README.md      # 图标使用说明
```

## 🔧 自定义修改

如需修改图标设计：

1. 编辑 `icon.svg` 文件
2. 重新运行生成脚本
3. 在 `icon_preview.html` 中预览效果

## 📋 使用建议

- **Windows 应用**：使用 `icons/ico/vidflow.ico`
- **macOS 应用**：使用 `icons/icns/vidflow.icns`
- **网页应用**：根据需要选择合适尺寸的 PNG
- **高DPI 显示**：使用 2x 或更大尺寸的图标

## 🛠️ 故障排除

### 常见问题

1. **"未找到 Inkscape"**
   - 运行 `easy_setup.bat` 自动安装
   - 或手动下载：https://inkscape.org/
   - 确保添加到系统 PATH

2. **"Python 依赖安装失败"**
   - 使用 `easy_setup.bat` 避免 Python 依赖
   - 或查看 `manual_conversion_guide.md`

3. **"Cairo 库错误"**
   - 这是 Windows 上的常见问题
   - 推荐使用 Inkscape 方案
   - 或使用在线转换工具

4. **图标显示异常**
   - 检查 SVG 文件是否正确
   - 确认输出目录权限

### 替代方案

如果所有自动脚本都失败：

1. **在线转换** (最简单)
   - 访问：https://convertio.co/svg-png/
   - 上传 `icon.svg`
   - 下载不同尺寸的 PNG

2. **手动 Inkscape 命令**
   ```cmd
   inkscape --export-type=png --export-filename=output.png --export-width=256 --export-height=256 icon.svg
   ```

3. **图像编辑软件**
   - GIMP (免费)
   - Photoshop
   - Figma (在线)

## 📄 许可证

本图标设计基于 VidFlow Desktop 软件界面，仅供学习和参考使用。