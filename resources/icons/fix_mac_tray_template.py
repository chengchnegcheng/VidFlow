"""
修复 macOS 托盘 Template 图标

直接从 SVG 生成正确的 Template 图标，确保：
- 透明背景
- 黑色图形（下载箭头）
- 正确的尺寸 (18x18 和 36x36)
"""

from PIL import Image, ImageDraw
import os

def create_download_icon(size):
    """创建下载箭头图标"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 根据尺寸计算比例
    scale = size / 22.0
    stroke_width = max(2, int(2 * scale))
    
    # 中心点
    cx = size // 2
    
    # 箭头垂直线 (从顶部到中间偏下)
    y_start = int(3 * scale)
    y_end = int(14 * scale)
    draw.line([(cx, y_start), (cx, y_end)], fill=(0, 0, 0, 255), width=stroke_width)
    
    # 箭头头部 (V 形)
    arrow_top = int(10 * scale)
    arrow_bottom = int(15 * scale)
    arrow_width = int(5 * scale)
    draw.line([(cx - arrow_width, arrow_top), (cx, arrow_bottom)], fill=(0, 0, 0, 255), width=stroke_width)
    draw.line([(cx + arrow_width, arrow_top), (cx, arrow_bottom)], fill=(0, 0, 0, 255), width=stroke_width)
    
    # 底部横线
    y_bottom = int(18 * scale)
    x_left = int(5 * scale)
    x_right = int(17 * scale)
    draw.line([(x_left, y_bottom), (x_right, y_bottom)], fill=(0, 0, 0, 255), width=stroke_width)
    
    return img

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 生成 1x 版本 (18x18)
    img_1x = create_download_icon(18)
    output_1x = os.path.join(script_dir, "tray-iconTemplate.png")
    img_1x.save(output_1x, 'PNG')
    print(f"✓ 已生成: {output_1x} (18x18)")
    
    # 生成 2x 版本 (36x36)
    img_2x = create_download_icon(36)
    output_2x = os.path.join(script_dir, "tray-iconTemplate@2x.png")
    img_2x.save(output_2x, 'PNG')
    print(f"✓ 已生成: {output_2x} (36x36)")
    
    print("\n✓ macOS Template 图标修复完成！")
    print("图标现在是透明背景 + 黑色下载箭头")

if __name__ == "__main__":
    main()
