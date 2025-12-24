"""
使用更可靠的方法生成 Windows ICO 文件
"""
from PIL import Image
import struct
import os

def create_ico_file(output_path, images_with_sizes):
    """
    手动创建 ICO 文件
    images_with_sizes: [(PIL.Image, (width, height)), ...]
    """
    # ICO 文件头
    icon_count = len(images_with_sizes)

    # 准备每个图标的数据
    icon_data_list = []
    for img, (width, height) in images_with_sizes:
        # 将图片转换为 PNG 格式的字节流
        from io import BytesIO
        png_data = BytesIO()
        img.save(png_data, format='PNG')
        png_bytes = png_data.getvalue()
        icon_data_list.append(png_bytes)

    # 构建 ICO 文件
    with open(output_path, 'wb') as f:
        # 文件头：reserved (2 bytes), type (2 bytes), count (2 bytes)
        f.write(struct.pack('<HHH', 0, 1, icon_count))

        # 计算每个图标目录条目的偏移量
        offset = 6 + (16 * icon_count)  # header + directory entries

        # 写入图标目录条目
        for i, ((img, (width, height)), png_bytes) in enumerate(zip(images_with_sizes, icon_data_list)):
            # 目录条目：width, height, colors, reserved, planes, bpp, size, offset
            w = 0 if width == 256 else width
            h = 0 if height == 256 else height
            f.write(struct.pack('<BBBBHHII',
                w, h,           # width, height (0 表示 256)
                0, 0,           # color count, reserved
                1, 32,          # color planes, bits per pixel
                len(png_bytes), # image data size
                offset))        # offset to image data
            offset += len(png_bytes)

        # 写入实际的图标数据（PNG格式）
        for png_bytes in icon_data_list:
            f.write(png_bytes)

def generate_ico_from_png(source_png, output_ico):
    """从 PNG 文件生成包含多种尺寸的 ICO 文件"""
    # 打开源图片
    img = Image.open(source_png)

    # 如果是 RGBA 模式，保持原样；否则转换为 RGBA
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # 生成所有需要的尺寸
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

    # 创建不同尺寸的图片
    images_with_sizes = []
    for size in sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        images_with_sizes.append((resized, size))

    # 创建 ICO 文件
    create_ico_file(output_ico, images_with_sizes)

    print(f"[OK] Successfully generated icon: {output_ico}")
    print(f"     Sizes included: {', '.join([f'{s[0]}x{s[1]}' for s in sizes])}")

    # 显示文件大小
    file_size = os.path.getsize(output_ico)
    print(f"     File size: {file_size / 1024:.1f} KB")

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    source_png = os.path.join(current_dir, 'icon.png')
    output_ico = os.path.join(current_dir, 'icon.ico')

    if not os.path.exists(source_png):
        print(f"[ERROR] Source file not found: {source_png}")
        exit(1)

    generate_ico_from_png(source_png, output_ico)
