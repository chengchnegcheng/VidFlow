/**
 * Electron 打包前验证脚本
 *
 * 确保所有必需的资源和构建产物都存在，避免打包失败
 */

const fs = require('fs');
const path = require('path');

// ANSI 颜色代码
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

// 需要检查的文件和目录
const requiredPaths = [
  // 后端构建产物
  {
    path: 'backend/dist/VidFlow-Backend',
    type: 'directory',
    critical: true,
    message: '后端构建产物',
  },

  // 前端构建产物
  {
    path: 'frontend/dist',
    type: 'directory',
    critical: true,
    message: '前端构建产物',
  },

  // Windows 图标
  {
    path: 'resources/icons/icon.ico',
    type: 'file',
    critical: true,
    platform: 'win32',
    message: 'Windows 应用图标',
  },

  // Mac 图标
  {
    path: 'resources/icon.icns',
    type: 'file',
    critical: true,
    platform: 'darwin',
    message: 'macOS 应用图标',
  },

  // Mac entitlements
  {
    path: 'build/entitlements.mac.plist',
    type: 'file',
    critical: true,
    platform: 'darwin',
    message: 'macOS entitlements 配置',
  },

  // 托盘图标
  {
    path: 'resources/icons/tray-icon.ico',
    type: 'file',
    critical: true,
    platform: 'win32',
    message: 'Windows 托盘图标',
  },
  {
    path: 'resources/icons/tray-icon.png',
    type: 'file',
    critical: true,
    platform: 'darwin',
    message: 'macOS 托盘图标',
  },

  // Mac Template 托盘图标（可选但推荐）
  {
    path: 'resources/icons/tray-iconTemplate.png',
    type: 'file',
    critical: false,
    platform: 'darwin',
    message: 'macOS Template 托盘图标（标准分辨率）',
  },
  {
    path: 'resources/icons/tray-iconTemplate@2x.png',
    type: 'file',
    critical: false,
    platform: 'darwin',
    message: 'macOS Template 托盘图标（Retina 分辨率）',
  },

  // Electron 主文件
  {
    path: 'electron/main.js',
    type: 'file',
    critical: true,
    message: 'Electron 主进程文件',
  },

  // package.json
  {
    path: 'package.json',
    type: 'file',
    critical: true,
    message: 'package.json',
  },

  // electron-builder 配置
  {
    path: 'electron-builder.json',
    type: 'file',
    critical: true,
    message: 'electron-builder 配置文件',
  },
];

/**
 * 检查路径是否存在
 */
function checkPath(pathInfo) {
  const fullPath = path.join(__dirname, '..', pathInfo.path);

  // 如果指定了平台，且当前平台不匹配，跳过检查
  if (pathInfo.platform && process.platform !== pathInfo.platform) {
    return { status: 'skipped', message: '平台不匹配，已跳过' };
  }

  try {
    const stats = fs.statSync(fullPath);

    if (pathInfo.type === 'directory' && !stats.isDirectory()) {
      return { status: 'error', message: '路径存在但不是目录' };
    }

    if (pathInfo.type === 'file' && !stats.isFile()) {
      return { status: 'error', message: '路径存在但不是文件' };
    }

    return { status: 'ok', message: '✓' };
  } catch (error) {
    if (error.code === 'ENOENT') {
      return {
        status: pathInfo.critical ? 'error' : 'warning',
        message: '不存在',
      };
    }
    return { status: 'error', message: error.message };
  }
}

/**
 * 主验证函数
 */
function validateBuild() {
  console.log(`${colors.blue}===========================================`);
  console.log('  Electron 打包前验证');
  console.log(`===========================================${colors.reset}\n`);

  let hasErrors = false;
  let hasWarnings = false;

  for (const pathInfo of requiredPaths) {
    const result = checkPath(pathInfo);

    let statusSymbol = '';
    let statusColor = colors.green;

    switch (result.status) {
      case 'ok':
        statusSymbol = '✓';
        statusColor = colors.green;
        break;
      case 'error':
        statusSymbol = '✗';
        statusColor = colors.red;
        hasErrors = true;
        break;
      case 'warning':
        statusSymbol = '⚠';
        statusColor = colors.yellow;
        hasWarnings = true;
        break;
      case 'skipped':
        statusSymbol = '○';
        statusColor = colors.reset;
        break;
    }

    console.log(
      `${statusColor}${statusSymbol}${colors.reset} ${pathInfo.message}`
    );
    console.log(`  路径: ${pathInfo.path}`);

    if (result.status === 'error' || result.status === 'warning') {
      console.log(`  ${statusColor}问题: ${result.message}${colors.reset}`);
    }

    console.log('');
  }

  // 输出汇总
  console.log(`${colors.blue}===========================================${colors.reset}\n`);

  if (hasErrors) {
    console.log(
      `${colors.red}✗ 验证失败！发现关键问题，无法继续打包。${colors.reset}\n`
    );
    console.log('请执行以下操作：');
    console.log('1. 确保后端已构建: npm run build:backend');
    console.log('2. 确保前端已构建: npm run build:frontend');
    console.log('3. 检查所有必需的图标文件是否存在\n');
    process.exit(1);
  }

  if (hasWarnings) {
    console.log(
      `${colors.yellow}⚠ 验证通过，但有一些可选资源缺失。${colors.reset}\n`
    );
    console.log('建议：');
    console.log('- 为 macOS 生成 Template 托盘图标: cd resources/icons && python generate_mac_tray_template.py\n');
  }

  console.log(`${colors.green}✓ 所有关键资源验证通过，可以开始打包！${colors.reset}\n`);
  process.exit(0);
}

// 运行验证
validateBuild();
