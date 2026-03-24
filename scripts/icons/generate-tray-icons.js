/**
 * 生成任务栏/托盘图标
 * 专门用于系统托盘的小尺寸图标 (16x16, 32x32)
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

// 项目根目录
const projectRoot = path.join(__dirname, '..', '..');
const sourceIcon = path.join(projectRoot, 'resources', 'icon.png');
const iconsDir = path.join(projectRoot, 'resources', 'icons');

// 确保目录存在
if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

console.log('========================================');
console.log('生成任务栏/托盘图标');
console.log('========================================');
console.log('源图标:', sourceIcon);
console.log('输出目录:', iconsDir);
console.log('');

// 检查源文件
if (!fs.existsSync(sourceIcon)) {
  console.error('❌ 源图标文件不存在:', sourceIcon);
  process.exit(1);
}

// 托盘图标需要的尺寸
const traySize = 32;  // 托盘图标标准尺寸

async function generateTrayIcon() {
  try {
    const trayIconPath = path.join(iconsDir, 'tray-icon.png');

    console.log(`生成托盘图标 (${traySize}x${traySize})...`);

    await sharp(sourceIcon)
      .resize(traySize, traySize, {
        fit: 'contain',
        background: { r: 0, g: 0, b: 0, alpha: 0 }
      })
      .png()
      .toFile(trayIconPath);

    const stats = fs.statSync(trayIconPath);
    console.log(`✅ 托盘图标已生成: ${(stats.size / 1024).toFixed(2)} KB`);
    console.log(`   路径: ${trayIconPath}`);

    // 在 Windows 上，还需要生成 .ico 格式
    if (process.platform === 'win32') {
      console.log('');
      console.log('正在生成 Windows .ico 格式的托盘图标...');

      // 生成16x16和32x32两种尺寸的PNG，然后组合成.ico
      const sizes = [16, 32];
      const tempPngs = [];

      for (const size of sizes) {
        const tempPath = path.join(iconsDir, `temp-${size}.png`);
        await sharp(sourceIcon)
          .resize(size, size, {
            fit: 'contain',
            background: { r: 0, g: 0, b: 0, alpha: 0 }
          })
          .png()
          .toFile(tempPath);
        tempPngs.push(tempPath);
      }

      // 使用 png2icons 生成 .ico (如果可用)
      try {
        const png2icons = require('png2icons');
        const input = fs.readFileSync(sourceIcon);
        const output = png2icons.createICO(input, png2icons.BILINEAR, 0, true, true);
        const trayIcoPath = path.join(iconsDir, 'tray-icon.ico');
        fs.writeFileSync(trayIcoPath, output);

        const icoStats = fs.statSync(trayIcoPath);
        console.log(`✅ Windows 托盘图标已生成: ${(icoStats.size / 1024).toFixed(2)} KB`);
        console.log(`   路径: ${trayIcoPath}`);
      } catch (error) {
        console.log('⚠️  png2icons 不可用，跳过 .ico 生成');
        console.log('   将使用现有的 icon.ico 文件');
      }

      // 清理临时文件
      for (const tempPng of tempPngs) {
        if (fs.existsSync(tempPng)) {
          fs.unlinkSync(tempPng);
        }
      }
    }

    console.log('');
    console.log('========================================');
    console.log('✅ 托盘图标生成完成！');
    console.log('========================================');

  } catch (error) {
    console.error('❌ 生成托盘图标失败:', error);
    process.exit(1);
  }
}

generateTrayIcon();
