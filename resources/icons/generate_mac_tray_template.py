"""
生成 macOS 托盘 Template 图标

这个脚本将现有的托盘图标转换为 macOS Template 格式。
macOS Template 图标要求：
- 使用黑色作为图形颜色
- 透明背景
- 系统会根据菜单栏亮/暗模式自动调整颜色
"""

from PIL import Image
import os

def generate_mac_tray_template():
    """生成 macOS 托盘 Template 图标"""

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 输入文件
    input_file = os.path.join(script_dir, "tray-icon.png")

    # 输出文件
    output_1x = os.path.join(script_dir, "tray-iconTemplate.png")
    output_2x = os.path.join(script_dir, "tray-iconTemplate@2x.png")

    if not os.path.exists(input_file):
        print(f"错误: 找不到输入文件 {input_file}")
        return

    try:
        # 打开原始图标
        img = Image.open(input_file)

        # 转换为 RGBA（如果不是的话）
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 创建标准分辨率版本 (18x18 是 macOS 推荐的托盘图标尺寸)
        size_1x = (18, 18)
        img_1x = img.resize(size_1x, Image.Resampling.LANCZOS)

        # macOS Template 图标：保持原始 alpha 通道，将所有非透明像素变成黑色
        # 这样系统可以根据菜单栏颜色自动调整
        result_1x = Image.new('RGBA', size_1x, (0, 0, 0, 0))

        for x in range(size_1x[0]):
            for y in range(size_1x[1]):
                r, g, b, a = img_1x.getpixel((x, y))
                if a > 0:
                    # 保持 alpha 值，但将颜色设为黑色
                    result_1x.putpixel((x, y), (0, 0, 0, a))

        # 保存标准分辨率
        result_1x.save(output_1x, 'PNG')
        print(f"✓ 已生成: {output_1x} ({size_1x[0]}x{size_1x[1]})")

        # 创建 Retina 分辨率版本 (2x)
        size_2x = (36, 36)
        img_2x = img.resize(size_2x, Image.Resampling.LANCZOS)

        result_2x = Image.new('RGBA', size_2x, (0, 0, 0, 0))

        for x in range(size_2x[0]):
            for y in range(size_2x[1]):
                r, g, b, a = img_2x.getpixel((x, y))
                if a > 0:
                    # 保持 alpha 值，但将颜色设为黑色
                    result_2x.putpixel((x, y), (0, 0, 0, a))

        # 保存 Retina 分辨率
        result_2x.save(output_2x, 'PNG')
        print(f"✓ 已生成: {output_2x} ({size_2x[0]}x{size_2x[1]})")

        print("\n✓ macOS Template 图标生成完成！")
        print("这些图标将在 macOS 菜单栏中自动适应亮/暗模式。")

    except Exception as e:
        print(f"错误: 生成图标时出错 - {str(e)}")

if __name__ == "__main__":
    generate_mac_tray_template()
