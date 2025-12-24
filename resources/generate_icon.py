"""
生成高质量的 Windows ICO 图标文件
包含多种尺寸：16, 32, 48, 64, 128, 256
"""
from PIL import Image
import os

def generate_ico_from_png(source_png, output_ico):
    """从 PNG 文件生成包含多种尺寸的 ICO 文件"""
    # 打开源图片
    img = Image.open(source_png)

    # 如果是 RGBA 模式，保持原样；否则转换为 RGBA
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # 生成所有需要的尺寸
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # 保存为 ICO 文件（使用 BMP 格式以获得最佳兼容性）
    # Windows 图标建议使用 BMP 而不是 PNG 以提高兼容性
    icon_sizes_bmp = []
    for size in sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        # 转换为 RGB 模式（BMP 不支持 alpha 通道）
        # 对于图标，保留 RGBA 更好
        icon_sizes_bmp.append(resized)

    # 保存，使用所有尺寸
    icon_sizes_bmp[0].save(
        output_ico,
        format='ICO',
        sizes=sizes,
        append_images=icon_sizes_bmp[1:]
    )

    print(f"[OK] Successfully generated icon: {output_ico}")
    print(f"     Sizes included: {', '.join([f'{s[0]}x{s[1]}' for s in sizes])}")

if __name__ == '__main__':
    # 当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 使用 256x256 的源图片生成 ICO
    source_png = os.path.join(current_dir, 'icon.png')  # 使用主 PNG 文件
    output_ico = os.path.join(current_dir, 'icon.ico')

    if not os.path.exists(source_png):
        print(f"[ERROR] Source file not found: {source_png}")
        exit(1)

    # 生成图标
    generate_ico_from_png(source_png, output_ico)

    # 显示文件大小
    file_size = os.path.getsize(output_ico)
    print(f"     File size: {file_size / 1024:.1f} KB")
