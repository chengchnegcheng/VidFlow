#!/usr/bin/env node
/**
 * 生成 macOS .icns 图标文件
 * 使用 PNG 图标生成 Apple ICNS 格式
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const rootDir = path.join(__dirname, '..', '..');
const sourceIcon = path.join(rootDir, 'Docs', 'Ioc', 'icons', 'png', 'vidflow-1024x1024.png');
const outputIcon = path.join(rootDir, 'resources', 'icon.icns');

// 检查源图标是否存在
if (!fs.existsSync(sourceIcon)) {
  console.error(`错误: 源图标文件不存在: ${sourceIcon}`);
  process.exit(1);
}

console.log('生成 macOS .icns 图标文件...');
console.log(`源文件: ${sourceIcon}`);
console.log(`目标文件: ${outputIcon}`);

// 方案 1: 尝试使用 png2icons (跨平台，推荐)
try {
  console.log('\n尝试使用 png2icons...');

  // 检查是否已安装
  try {
    execSync('npm list png2icons --depth=0', { stdio: 'ignore' });
  } catch {
    console.log('安装 png2icons...');
    execSync('npm install --save-dev png2icons', { stdio: 'inherit' });
  }

  const png2icons = require('png2icons');
  const input = fs.readFileSync(sourceIcon);
  const output = png2icons.createICNS(input, png2icons.BILINEAR, 0);

  fs.writeFileSync(outputIcon, output);
  console.log(`✅ 成功生成 ICNS 图标: ${outputIcon}`);
  process.exit(0);

} catch (error) {
  console.log(`png2icons 方案失败: ${error.message}`);
}

// 方案 2: 尝试使用 iconutil (仅 macOS)
if (process.platform === 'darwin') {
  try {
    console.log('\n尝试使用 iconutil (macOS)...');

    const iconsetDir = path.join(rootDir, 'icon.iconset');

    // 创建 iconset 目录
    if (fs.existsSync(iconsetDir)) {
      fs.rmSync(iconsetDir, { recursive: true });
    }
    fs.mkdirSync(iconsetDir);

    // 使用 sips 生成各种尺寸
    const sizes = [
      { size: 16, name: 'icon_16x16.png' },
      { size: 32, name: 'icon_16x16@2x.png' },
      { size: 32, name: 'icon_32x32.png' },
      { size: 64, name: 'icon_32x32@2x.png' },
      { size: 128, name: 'icon_128x128.png' },
      { size: 256, name: 'icon_128x128@2x.png' },
      { size: 256, name: 'icon_256x256.png' },
      { size: 512, name: 'icon_256x256@2x.png' },
      { size: 512, name: 'icon_512x512.png' },
      { size: 1024, name: 'icon_512x512@2x.png' },
    ];

    for (const { size, name } of sizes) {
      const outputPath = path.join(iconsetDir, name);
      execSync(`sips -z ${size} ${size} "${sourceIcon}" --out "${outputPath}"`, { stdio: 'inherit' });
    }

    // 使用 iconutil 生成 icns
    execSync(`iconutil -c icns "${iconsetDir}" -o "${outputIcon}"`, { stdio: 'inherit' });

    // 清理临时目录
    fs.rmSync(iconsetDir, { recursive: true });

    console.log(`✅ 成功生成 ICNS 图标: ${outputIcon}`);
    process.exit(0);

  } catch (error) {
    console.log(`iconutil 方案失败: ${error.message}`);
  }
}

// 方案 3: 使用预先生成的 PNG 尺寸
try {
  console.log('\n尝试使用现有 PNG 文件...');

  const pngDir = path.join(rootDir, 'Docs', 'Ioc', 'icons', 'png');
  const iconsetDir = path.join(rootDir, 'icon.iconset');

  // 创建 iconset 目录
  if (fs.existsSync(iconsetDir)) {
    fs.rmSync(iconsetDir, { recursive: true });
  }
  fs.mkdirSync(iconsetDir);

  // 映射现有的 PNG 到 iconset 文件名
  const mapping = {
    'vidflow-16x16.png': 'icon_16x16.png',
    'vidflow-32x32.png': ['icon_16x16@2x.png', 'icon_32x32.png'],
    'vidflow-64x64.png': 'icon_32x32@2x.png',
    'vidflow-128x128.png': ['icon_128x128.png', 'icon_64x64@2x.png'],
    'vidflow-256x256.png': ['icon_128x128@2x.png', 'icon_256x256.png'],
    'vidflow-512x512.png': ['icon_256x256@2x.png', 'icon_512x512.png'],
    'vidflow-1024x1024.png': 'icon_512x512@2x.png'
  };

  for (const [srcName, destNames] of Object.entries(mapping)) {
    const srcPath = path.join(pngDir, srcName);
    if (fs.existsSync(srcPath)) {
      const destinations = Array.isArray(destNames) ? destNames : [destNames];
      for (const destName of destinations) {
        const destPath = path.join(iconsetDir, destName);
        fs.copyFileSync(srcPath, destPath);
      }
    } else {
      console.log(`警告: 找不到 ${srcName}`);
    }
  }

  // 如果在 macOS 上，使用 iconutil
  if (process.platform === 'darwin') {
    execSync(`iconutil -c icns "${iconsetDir}" -o "${outputIcon}"`, { stdio: 'inherit' });
    fs.rmSync(iconsetDir, { recursive: true });
    console.log(`✅ 成功生成 ICNS 图标: ${outputIcon}`);
  } else {
    console.log('⚠️ 非 macOS 系统，无法使用 iconutil');
    console.log(`请在 macOS 上运行此脚本，或手动生成 ICNS 文件`);
    console.log(`临时 iconset 目录保留在: ${iconsetDir}`);
  }

  process.exit(0);

} catch (error) {
  console.error(`生成失败: ${error.message}`);
  process.exit(1);
}
