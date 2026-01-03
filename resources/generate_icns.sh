#!/bin/bash
# 在 Mac 上生成 .icns 文件的脚本
# 使用方法: ./generate_icns.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_PNG="$SCRIPT_DIR/icon.png"
ICONSET_DIR="$SCRIPT_DIR/icon.iconset"
OUTPUT_ICNS="$SCRIPT_DIR/icon.icns"

# 检查源文件
if [ ! -f "$SOURCE_PNG" ]; then
    echo "❌ 错误: 找不到源文件 $SOURCE_PNG"
    exit 1
fi

echo "🎨 从 icon.png 生成 icon.icns..."

# 创建 iconset 目录
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

# 生成所有需要的尺寸
# macOS 需要以下尺寸: 16, 32, 64, 128, 256, 512, 1024
# 以及对应的 @2x 版本

echo "📐 生成不同尺寸的图标..."

# 使用 sips 命令调整图片大小
sips -z 16 16     "$SOURCE_PNG" --out "$ICONSET_DIR/icon_16x16.png" > /dev/null
sips -z 32 32     "$SOURCE_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" > /dev/null
sips -z 32 32     "$SOURCE_PNG" --out "$ICONSET_DIR/icon_32x32.png" > /dev/null
sips -z 64 64     "$SOURCE_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" > /dev/null
sips -z 128 128   "$SOURCE_PNG" --out "$ICONSET_DIR/icon_128x128.png" > /dev/null
sips -z 256 256   "$SOURCE_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null
sips -z 256 256   "$SOURCE_PNG" --out "$ICONSET_DIR/icon_256x256.png" > /dev/null
sips -z 512 512   "$SOURCE_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" > /dev/null
sips -z 512 512   "$SOURCE_PNG" --out "$ICONSET_DIR/icon_512x512.png" > /dev/null
sips -z 1024 1024 "$SOURCE_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png" > /dev/null

echo "🔧 使用 iconutil 生成 .icns 文件..."

# 使用 iconutil 生成 .icns 文件
iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICNS"

# 清理临时文件
rm -rf "$ICONSET_DIR"

# 显示结果
if [ -f "$OUTPUT_ICNS" ]; then
    SIZE=$(ls -lh "$OUTPUT_ICNS" | awk '{print $5}')
    echo "✅ 成功生成: $OUTPUT_ICNS ($SIZE)"
else
    echo "❌ 生成失败"
    exit 1
fi
