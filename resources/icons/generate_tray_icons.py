"""
生成托盘图标（不依赖 cairo）
使用 PIL 直接绘制简洁的下载图标
"""

from PIL import Image, ImageDraw
import os

def create_download_icon(size, line_width=2):
    """
    创建简洁的下载图标

    Args:
        size: 图标尺寸 (width, height)
        line_width: 线条宽度

    Returns:
        PIL Image 对象
    """
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    w, h = size
    # 计算比例
    scale = w / 22.0
    lw = max(1, int(line_width * scale))

    # 中心点
    cx = w // 2

    # 箭头顶部 Y
    top_y = int(3 * scale)
    # 箭头底部 Y
    arrow_bottom_y = int(14 * scale)
    # 箭头尖端 Y
    arrow_tip_y = int(15 * scale)
    # 箭头两侧 Y
    arrow_side_y = int(10 * scale)
    # 箭头宽度
    arrow_half_width = int(5 * scale)
    # 底部横线 Y
    line_y = int(18 * scale)
    # 底部横线宽度
    line_half_width = int(6 * scale)

    # 绘制垂直线（箭头杆）
    draw.line([(cx, top_y), (cx, arrow_bottom_y)], fill='black', width=lw)

    # 绘制箭头（V 形）
    draw.line([(cx - arrow_half_width, arrow_side_y), (cx, arrow_tip_y)], fill='black', width=lw)
    draw.line([(cx + arrow_half_width, arrow_side_y), (cx, arrow_tip_y)], fill='black', width=lw)

    # 绘制底部横线
    draw.line([(cx - line_half_width, line_y), (cx + line_half_width, line_y)], fill='black', width=lw)

    return img


def generate_tray_icons():
    """生成所有托盘图标"""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 生成标准托盘图标 (用于 Windows/Linux)
    print("生成托盘图标...")

    # 标准尺寸
    sizes = {
        'tray-icon.png': (22, 22),
        'tray-iconTemplate.png': (18, 18),
        'tray-iconTemplate@2x.png': (36, 36),
    }

    for filename, size in sizes.items():
        output_path = os.path.join(script_dir, filename)
        icon = create_download_icon(size, line_width=2)
        icon.save(output_path, 'PNG')
        print(f"✓ 已生成: {filename} ({size[0]}x{size[1]})")

    # 生成 Windows ICO 格式
    print("\n生成 Windows 托盘图标...")
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48)]
    ico_images = [create_download_icon(s, line_width=2) for s in ico_sizes]

    ico_path = os.path.join(script_dir, 'tray-icon.ico')
    ico_images[0].save(ico_path, format='ICO', sizes=ico_sizes)
    print(f"✓ 已生成: tray-icon.ico (多尺寸)")

    print("\n✓ 所有托盘图标生成完成！")


if __name__ == "__main__":
    generate_tray_icons()
