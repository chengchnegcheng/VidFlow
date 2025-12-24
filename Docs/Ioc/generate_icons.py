#!/usr/bin/env python3
"""
VidFlow Desktop 图标生成器
根据 SVG 源文件生成多种尺寸的图标
"""

import os
import sys
from pathlib import Path

# 检查并安装必要的依赖
def install_dependencies():
    """检查并安装必要的Python包"""
    required_packages = ['Pillow', 'cairosvg']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'Pillow':
                import PIL
            elif package == 'cairosvg':
                import cairosvg
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"📦 需要安装以下Python包: {', '.join(missing_packages)}")
        print("正在自动安装...")
        
        for package in missing_packages:
            try:
                import subprocess
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✓ {package} 安装成功")
            except subprocess.CalledProcessError:
                print(f"❌ {package} 安装失败，请手动安装: pip install {package}")
                return False
    
    return True

# 定义需要生成的图标尺寸
ICON_SIZES = {
    # Windows ICO 标准尺寸
    'ico': [16, 24, 32, 48, 64, 128, 256],
    
    # PNG 各种用途尺寸
    'png': [
        16,   # 小图标
        24,   # 小图标
        32,   # 标准图标
        48,   # 中等图标
        64,   # 大图标
        96,   # 高DPI小图标
        128,  # 高DPI中等图标
        256,  # 高DPI大图标
        512,  # 超高清图标
        1024  # 最大尺寸
    ],
    
    # macOS 应用图标尺寸
    'icns': [16, 32, 64, 128, 256, 512, 1024]
}

def svg_to_png(svg_file, output_file, size):
    """使用 cairosvg 将 SVG 转换为 PNG"""
    try:
        import cairosvg
        cairosvg.svg2png(
            url=str(svg_file),
            write_to=str(output_file),
            output_width=size,
            output_height=size
        )
        return True
    except Exception as e:
        print(f"❌ 转换失败 {svg_file} -> {output_file}: {e}")
        return False

def generate_png_icons(svg_file):
    """生成 PNG 图标"""
    output_dir = Path('icons/png')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    for size in ICON_SIZES['png']:
        output_file = output_dir / f'vidflow-{size}x{size}.png'
        
        if svg_to_png(svg_file, output_file, size):
            print(f"✓ 生成 PNG {size}x{size}")
            success_count += 1
        else:
            print(f"❌ 生成 PNG {size}x{size} 失败")
    
    return success_count > 0

def generate_ico_file():
    """生成 Windows ICO 文件"""
    try:
        from PIL import Image
        
        # 收集 PNG 文件
        images = []
        for size in ICON_SIZES['ico']:
            png_file = f'icons/png/vidflow-{size}x{size}.png'
            if os.path.exists(png_file):
                img = Image.open(png_file)
                images.append(img)
        
        if images:
            output_dir = Path('icons/ico')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存为 ICO 文件
            images[0].save(
                'icons/ico/vidflow.ico',
                format='ICO',
                sizes=[(img.width, img.height) for img in images]
            )
            print("✓ 生成 ICO 文件")
        else:
            print("❌ 未找到 PNG 文件，无法生成 ICO")
            
    except Exception as e:
        print(f"❌ 生成 ICO 失败: {e}")

def generate_icns_file():
    """生成 macOS ICNS 文件"""
    try:
        import shutil
        
        # 创建 iconset 目录
        iconset_dir = Path('icons/vidflow.iconset')
        iconset_dir.mkdir(parents=True, exist_ok=True)
        
        # macOS iconset 命名规则
        icns_mapping = {
            16: 'icon_16x16.png',
            32: ['icon_16x16@2x.png', 'icon_32x32.png'],
            64: 'icon_32x32@2x.png',
            128: 'icon_128x128.png',
            256: ['icon_128x128@2x.png', 'icon_256x256.png'],
            512: ['icon_256x256@2x.png', 'icon_512x512.png'],
            1024: 'icon_512x512@2x.png'
        }
        
        for size, names in icns_mapping.items():
            src_file = f'icons/png/vidflow-{size}x{size}.png'
            if os.path.exists(src_file):
                if isinstance(names, list):
                    for name in names:
                        dst_file = iconset_dir / name
                        shutil.copy2(src_file, dst_file)
                else:
                    dst_file = iconset_dir / names
                    shutil.copy2(src_file, dst_file)
        
        # 尝试生成 ICNS 文件 (仅在 macOS 上)
        if sys.platform == 'darwin':
            import subprocess
            output_dir = Path('icons/icns')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            cmd = ['iconutil', '-c', 'icns', str(iconset_dir), 
                   '-o', 'icons/icns/vidflow.icns']
            subprocess.run(cmd, check=True)
            print("✓ 生成 ICNS 文件")
        else:
            print("⚠️  ICNS 文件生成需要 macOS 系统，已创建 iconset 目录")
        
    except Exception as e:
        print(f"❌ 生成 ICNS 失败: {e}")

def create_readme():
    """创建说明文档"""
    readme_content = """# VidFlow Desktop 图标文件

## 文件结构

```
icons/
├── png/           # PNG 格式图标 (各种尺寸)
├── ico/           # Windows ICO 文件
├── icns/          # macOS ICNS 文件
└── README.md      # 本文件
```

## 图标尺寸说明

### PNG 文件
- 16x16, 24x24, 32x32: 小图标，用于工具栏、列表等
- 48x48, 64x64: 中等图标，用于桌面快捷方式
- 96x96, 128x128: 大图标，用于高DPI显示
- 256x256, 512x512, 1024x1024: 超高清图标

### ICO 文件 (Windows)
- vidflow.ico: 包含多种尺寸的 Windows 图标文件

### ICNS 文件 (macOS)
- vidflow.icns: macOS 应用程序图标文件

## 使用方法

1. **Windows 应用程序**: 使用 `icons/ico/vidflow.ico`
2. **macOS 应用程序**: 使用 `icons/icns/vidflow.icns`
3. **网页/文档**: 根据需要选择合适尺寸的 PNG 文件
4. **高DPI 显示**: 使用 2x 或更大尺寸的图标

## 设计说明

图标设计基于 VidFlow Desktop 的黑白简约界面风格:
- 主色调: 深灰渐变背景 (#2c2c2c 到 #1a1a1a)
- 核心元素: 白色下载箭头，体现软件的下载管理功能
- 设计风格: 现代简约，圆角矩形背景，符合软件黑白风格
- 装饰元素: 简约线条，暗示数据流动和传输
"""
    
    icons_dir = Path('icons')
    icons_dir.mkdir(exist_ok=True)
    
    with open(icons_dir / 'README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("✓ 创建说明文档")

def main():
    """主函数"""
    print("🎨 VidFlow Desktop 图标生成器")
    print("=" * 40)
    
    # 安装必要的依赖
    if not install_dependencies():
        print("❌ 依赖安装失败，请手动安装: pip install Pillow cairosvg")
        return
    
    # 检查 SVG 源文件
    svg_file = Path('icon.svg')
    if not svg_file.exists():
        print("❌ 未找到 icon.svg 文件")
        return
    
    print("\n📦 开始生成图标...")
    
    # 生成 PNG 图标
    if generate_png_icons(svg_file):
        print("✓ PNG 图标生成完成")
        
        # 生成 ICO 文件
        generate_ico_file()
        
        # 生成 ICNS 文件
        generate_icns_file()
        
        # 创建说明文档
        create_readme()
        
        print("\n✅ 图标生成完成!")
        print("📁 查看 icons/ 目录获取所有生成的图标文件")
    else:
        print("❌ PNG 图标生成失败")

if __name__ == '__main__':
    main()