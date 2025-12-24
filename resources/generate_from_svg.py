"""
从新的 SVG 文件生成彩色图标
"""
from PIL import Image
import cairosvg
from io import BytesIO
import struct
import os

def svg_to_png(svg_path, output_path, size):
    """将 SVG 转换为指定尺寸的 PNG"""
    png_data = cairosvg.svg2png(
        url=svg_path,
        output_width=size,
        output_height=size
    )
    img = Image.open(BytesIO(png_data))
    img.save(output_path, 'PNG')
    return img

def create_ico_file(output_path, images_with_sizes):
    """手动创建 ICO 文件"""
    icon_count = len(images_with_sizes)

    # 准备每个图标的数据
    icon_data_list = []
    for img, (width, height) in images_with_sizes:
        png_data = BytesIO()
        img.save(png_data, format='PNG')
        png_bytes = png_data.getvalue()
        icon_data_list.append(png_bytes)

    # 构建 ICO 文件
    with open(output_path, 'wb') as f:
        # 文件头
        f.write(struct.pack('<HHH', 0, 1, icon_count))

        # 计算偏移量
        offset = 6 + (16 * icon_count)

        # 写入图标目录条目
        for i, ((img, (width, height)), png_bytes) in enumerate(zip(images_with_sizes, icon_data_list)):
            w = 0 if width == 256 else width
            h = 0 if height == 256 else height
            f.write(struct.pack('<BBBBHHII',
                w, h, 0, 0, 1, 32,
                len(png_bytes), offset))
            offset += len(png_bytes)

        # 写入图标数据
        for png_bytes in icon_data_list:
            f.write(png_bytes)

def generate_icons_from_svg(svg_path, output_dir):
    """从 SVG 生成所有需要的图标文件"""
    try:
        import cairosvg
    except ImportError:
        print("[ERROR] cairosvg not installed. Install with: pip install cairosvg")
        print("[INFO] Falling back to existing PNG...")
        return False

    sizes = [256, 128, 64, 48, 32, 16]

    print(f"[1/3] Generating PNG files from SVG...")

    # 生成主 PNG
    svg_to_png(svg_path, os.path.join(output_dir, 'icon.png'), 256)
    print(f"  - icon.png (256x256)")

    # 生成 icons 目录下的不同尺寸
    icons_dir = os.path.join(output_dir, 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    images_for_ico = []
    for size in sizes:
        png_path = os.path.join(icons_dir, f'icon-{size}.png')
        img = svg_to_png(svg_path, png_path, size)
        images_for_ico.append((img, (size, size)))
        print(f"  - icon-{size}.png ({size}x{size})")

    print(f"\n[2/3] Creating ICO file...")

    # 生成 ICO 文件
    ico_path = os.path.join(output_dir, 'icon.ico')
    create_ico_file(ico_path, images_for_ico)

    file_size = os.path.getsize(ico_path)
    print(f"  - icon.ico ({file_size / 1024:.1f} KB)")
    print(f"  - Contains {len(sizes)} sizes: {', '.join([f'{s}x{s}' for s in sizes])}")

    print(f"\n[3/3] Done!")
    print(f"\n[OK] All icon files generated successfully!")

    return True

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(current_dir, 'icon-new.svg')

    if not os.path.exists(svg_path):
        print(f"[ERROR] SVG file not found: {svg_path}")
        exit(1)

    success = generate_icons_from_svg(svg_path, current_dir)

    if not success:
        print("[WARNING] Could not generate from SVG, using fallback method...")
