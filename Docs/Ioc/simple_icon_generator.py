#!/usr/bin/env python3
"""
VidFlow Desktop 简易图标生成器
使用 wand (ImageMagick Python 绑定) 来转换 SVG
"""

import os
import sys
from pathlib import Path

def install_wand():
    """安装 Wand 库"""
    try:
        import subprocess
        print("📦 正在安装 Wand 库...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'Wand'])
        print("✓ Wand 安装成功")
        return True
    except subprocess.CalledProcessError:
        print("❌ Wand 安装失败")
        return False

def check_imagemagick():
    """检查 ImageMagick 是否安装"""
    try:
        import subprocess
        result = subprocess.run(['magick', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ 找到 ImageMagick")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ 未找到 ImageMagick")
    print("请安装 ImageMagick: https://imagemagick.org/script/download.php#windows")
    print("安装时请确保选择 'Install development headers and libraries for C and C++'")
    return False

def svg_to_png_wand(svg_file, output_file, size):
    """使用 Wand 将 SVG 转换为 PNG"""
    try:
        from wand.image import Image
        from wand.color import Color
        
        with Image() as img:
            img.format = 'svg'
            img.background_color = Color('transparent')
            
            # 读取 SVG 文件
            with open(svg_file, 'rb') as f:
                img.blob = f.read()
            
            # 设置尺寸
            img.resize(size, size)
            img.format = 'png'
            
            # 保存 PNG
            img.save(filename=str(output_file))
        
        return True
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return False

def generate_icons():
    """生成图标"""
    # 图标尺寸
    sizes = [16, 24, 32, 48, 64, 96, 128, 256, 512, 1024]
    
    # 检查 SVG 文件
    svg_file = Path('icon.svg')
    if not svg_file.exists():
        print("❌ 未找到 icon.svg 文件")
        return False
    
    # 创建输出目录
    output_dir = Path('icons/png')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查依赖
    if not check_imagemagick():
        return False
    
    try:
        import wand
    except ImportError:
        if not install_wand():
            return False
        import wand
    
    # 生成 PNG 文件
    success_count = 0
    for size in sizes:
        output_file = output_dir / f'vidflow-{size}x{size}.png'
        
        if svg_to_png_wand(svg_file, output_file, size):
            print(f"✓ 生成 PNG {size}x{size}")
            success_count += 1
        else:
            print(f"❌ 生成 PNG {size}x{size} 失败")
    
    return success_count > 0

def create_ico():
    """创建 ICO 文件"""
    try:
        from PIL import Image
        
        ico_sizes = [16, 24, 32, 48, 64, 128, 256]
        images = []
        
        for size in ico_sizes:
            png_file = f'icons/png/vidflow-{size}x{size}.png'
            if os.path.exists(png_file):
                img = Image.open(png_file)
                images.append(img)
        
        if images:
            output_dir = Path('icons/ico')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            images[0].save(
                'icons/ico/vidflow.ico',
                format='ICO',
                sizes=[(img.width, img.height) for img in images]
            )
            print("✓ 生成 ICO 文件")
            return True
    except Exception as e:
        print(f"❌ 生成 ICO 失败: {e}")
    
    return False

def main():
    """主函数"""
    print("🎨 VidFlow Desktop 简易图标生成器")
    print("=" * 45)
    
    if generate_icons():
        print("\n✓ PNG 图标生成完成")
        create_ico()
        print("\n✅ 图标生成完成!")
        print("📁 查看 icons/ 目录获取所有生成的图标文件")
    else:
        print("\n❌ 图标生成失败")
        print("\n💡 替代方案:")
        print("1. 安装 Inkscape: https://inkscape.org/")
        print("2. 使用在线 SVG 转换工具")
        print("3. 手动使用图像编辑软件")

if __name__ == '__main__':
    main()