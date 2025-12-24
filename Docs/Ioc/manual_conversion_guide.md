# VidFlow Desktop 图标手动转换指南

由于在 Windows 上自动转换 SVG 需要复杂的依赖配置，这里提供几种简单的手动转换方法。

## 🎯 快速方案

### 方案 1: 使用在线转换工具 (推荐)

1. **打开在线 SVG 转换器**:
   - https://convertio.co/svg-png/
   - https://cloudconvert.com/svg-to-png
   - https://www.aconvert.com/image/svg-to-png/

2. **上传 `icon.svg` 文件**

3. **批量转换多个尺寸**:
   - 16×16, 24×24, 32×32, 48×48, 64×64
   - 96×96, 128×128, 256×256, 512×512, 1024×1024

4. **下载并重命名**:
   ```
   vidflow-16x16.png
   vidflow-24x24.png
   vidflow-32x32.png
   ... 等等
   ```

5. **放入目录**:
   ```
   icons/
   └── png/
       ├── vidflow-16x16.png
       ├── vidflow-24x24.png
       ├── vidflow-32x32.png
       └── ...
   ```

### 方案 2: 使用 Inkscape (一次性安装)

1. **下载安装 Inkscape**: https://inkscape.org/release/

2. **批量转换命令** (在命令行中运行):
   ```cmd
   mkdir icons\png
   
   inkscape --export-type=png --export-filename=icons\png\vidflow-16x16.png --export-width=16 --export-height=16 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-24x24.png --export-width=24 --export-height=24 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-32x32.png --export-width=32 --export-height=32 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-48x48.png --export-width=48 --export-height=48 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-64x64.png --export-width=64 --export-height=64 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-96x96.png --export-width=96 --export-height=96 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-128x128.png --export-width=128 --export-height=128 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-256x256.png --export-width=256 --export-height=256 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-512x512.png --export-width=512 --export-height=512 icon.svg
   inkscape --export-type=png --export-filename=icons\png\vidflow-1024x1024.png --export-width=1024 --export-height=1024 icon.svg
   ```

3. **生成 ICO 文件** (如果安装了 ImageMagick):
   ```cmd
   mkdir icons\ico
   magick icons\png\vidflow-16x16.png icons\png\vidflow-24x24.png icons\png\vidflow-32x32.png icons\png\vidflow-48x48.png icons\png\vidflow-64x64.png icons\png\vidflow-128x128.png icons\png\vidflow-256x256.png icons\ico\vidflow.ico
   ```

### 方案 3: 使用图像编辑软件

1. **推荐软件**:
   - GIMP (免费): https://www.gimp.org/
   - Adobe Illustrator
   - Figma (在线): https://figma.com/

2. **操作步骤**:
   - 导入 `icon.svg` 文件
   - 导出为不同尺寸的 PNG
   - 保存到 `icons/png/` 目录

## 🔧 生成 ICO 文件

如果你有了 PNG 文件，可以使用以下方法生成 ICO:

### 在线 ICO 生成器
- https://www.favicon-generator.org/
- https://convertio.co/png-ico/
- https://icoconvert.com/

### 使用 Python 脚本
```python
from PIL import Image

# 收集 PNG 文件
sizes = [16, 24, 32, 48, 64, 128, 256]
images = []

for size in sizes:
    try:
        img = Image.open(f'icons/png/vidflow-{size}x{size}.png')
        images.append(img)
    except:
        pass

# 生成 ICO
if images:
    images[0].save(
        'icons/ico/vidflow.ico',
        format='ICO',
        sizes=[(img.width, img.height) for img in images]
    )
    print("✓ ICO 文件生成成功")
```

## 📁 最终目录结构

```
VidFlow/
├── icon.svg                    # 源 SVG 文件
├── icons/
│   ├── png/                   # PNG 图标
│   │   ├── vidflow-16x16.png
│   │   ├── vidflow-24x24.png
│   │   ├── vidflow-32x32.png
│   │   ├── vidflow-48x48.png
│   │   ├── vidflow-64x64.png
│   │   ├── vidflow-96x96.png
│   │   ├── vidflow-128x128.png
│   │   ├── vidflow-256x256.png
│   │   ├── vidflow-512x512.png
│   │   └── vidflow-1024x1024.png
│   └── ico/                   # ICO 文件
│       └── vidflow.ico
├── icon_preview.html          # 预览页面
└── manual_conversion_guide.md # 本指南
```

## 💡 使用建议

- **Windows 应用**: 使用 `icons/ico/vidflow.ico`
- **网页应用**: 使用合适尺寸的 PNG 文件
- **高DPI 显示**: 使用 2x 尺寸的图标 (如 64×64 代替 32×32)

## 🎨 图标预览

完成转换后，打开 `icon_preview.html` 查看所有图标的效果。