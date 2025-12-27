"""
生成 macOS 托盘 Template 图标

这个脚本将现有的托盘图标转换为 macOS Template 格式的黑白图标。
"""

from PIL import Image, ImageOps
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

        # 创建标准分辨率版本 (16x16 或 22x22)
        # macOS 托盘图标通常是 16x16 到 22x22
        size_1x = (22, 22)
        img_1x = img.resize(size_1x, Image.Resampling.LANCZOS)

        # 转换为灰度
        gray_1x = ImageOps.grayscale(img_1x.convert('RGB'))

        # 获取原始 alpha 通道
        alpha = img_1x.split()[3] if img_1x.mode == 'RGBA' else None

        # 创建黑白版本（高对比度）
        # 使用点操作提高对比度，使其更接近纯黑白
        bw_1x = gray_1x.point(lambda x: 0 if x < 128 else 255, mode='1').convert('L')

        # 应用原始 alpha 通道
        if alpha:
            result_1x = Image.new('RGBA', size_1x)
            result_1x.paste(bw_1x, (0, 0))
            result_1x.putalpha(alpha.resize(size_1x, Image.Resampling.LANCZOS))
        else:
            result_1x = bw_1x.convert('RGBA')

        # 保存标准分辨率
        result_1x.save(output_1x, 'PNG')
        print(f"✓ 已生成: {output_1x}")

        # 创建 Retina 分辨率版本 (2x)
        size_2x = (44, 44)
        img_2x = img.resize(size_2x, Image.Resampling.LANCZOS)

        # 转换为灰度
        gray_2x = ImageOps.grayscale(img_2x.convert('RGB'))

        # 获取原始 alpha 通道
        alpha_2x = img_2x.split()[3] if img_2x.mode == 'RGBA' else None

        # 创建黑白版本
        bw_2x = gray_2x.point(lambda x: 0 if x < 128 else 255, mode='1').convert('L')

        # 应用原始 alpha 通道
        if alpha_2x:
            result_2x = Image.new('RGBA', size_2x)
            result_2x.paste(bw_2x, (0, 0))
            result_2x.putalpha(alpha_2x.resize(size_2x, Image.Resampling.LANCZOS))
        else:
            result_2x = bw_2x.convert('RGBA')

        # 保存 Retina 分辨率
        result_2x.save(output_2x, 'PNG')
        print(f"✓ 已生成: {output_2x}")

        print("\n✓ macOS Template 图标生成完成！")
        print("这些图标将在 macOS 菜单栏中自动适应亮/暗模式。")

    except Exception as e:
        print(f"错误: 生成图标时出错 - {str(e)}")

if __name__ == "__main__":
    generate_mac_tray_template()
