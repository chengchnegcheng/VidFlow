/**
 * VidFlow 模拟更新服务器
 * 用于本地测试或部署更新服务
 * 
 * 本地测试：
 * 1. npm install express
 * 2. node scripts/mock-update-server.js
 * 3. 修改 electron/main.js 中的 updateServerUrl 为 http://localhost:8321
 * 
 * 公网部署：
 * 1. SERVER_URL=http://shcrystal.top:8321 node scripts/mock-update-server.js
 * 2. 或者设置环境变量: export SERVER_URL=http://your-domain:8321
 * 3. 确保安装包文件在 dist-output 目录下
 * 
 * 环境变量：
 * - PORT: 服务器监听端口 (默认: 8321)
 * - SERVER_URL: 服务器公网地址 (默认: http://localhost:PORT)
 */

const express = require('express');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 8321;

// 服务器地址配置（支持环境变量）
// 本地测试: http://localhost:8321
// 公网部署: http://shcrystal.top:8321
const SERVER_URL = process.env.SERVER_URL || `http://localhost:${PORT}`;

// 中间件
app.use(express.json());
app.use(express.static('dist-output')); // 静态文件服务（安装包）

// 配置：当前发布的版本
const RELEASE_CONFIG = {
  version: '1.1.0',
  releaseNotes: `
    <h3>🎉 新功能</h3>
    <ul>
      <li>✨ 添加自动更新功能</li>
      <li>✨ 支持灰度发布控制</li>
      <li>✨ 添加更新统计上报</li>
    </ul>
    <h3>🎨 优化改进</h3>
    <ul>
      <li>⚡ 优化下载速度</li>
      <li>🎨 改进用户界面</li>
    </ul>
    <h3>🐛 问题修复</h3>
    <ul>
      <li>🐛 修复某个问题</li>
      <li>🐛 修复另一个问题</li>
    </ul>
  `,
  isMandatory: false, // 是否强制更新
  rolloutPercentage: 100, // 灰度发布百分比 (0-100)
};

// 文件信息缓存
let fileInfoCache = null;

/**
 * 获取安装包信息
 */
function getFileInfo() {
  if (fileInfoCache) return fileInfoCache;

  const fileName = `VidFlow-${RELEASE_CONFIG.version}-win-x64.exe`;
  const filePath = path.join(__dirname, '..', 'dist-output', fileName);

  if (!fs.existsSync(filePath)) {
    console.warn(`⚠️  安装包不存在: ${fileName}`);
    return null;
  }

  const stats = fs.statSync(filePath);
  const fileBuffer = fs.readFileSync(filePath);
  const hash = crypto.createHash('sha512').update(fileBuffer).digest('hex');

  fileInfoCache = {
    fileName,
    fileSize: stats.size,
    fileHash: hash,
    downloadUrl: `${SERVER_URL}/${fileName}`
  };

  console.log('✅ 安装包信息已缓存:');
  console.log(`   文件名: ${fileInfoCache.fileName}`);
  console.log(`   大小: ${(fileInfoCache.fileSize / 1024 / 1024).toFixed(2)} MB`);
  console.log(`   哈希: ${fileInfoCache.fileHash.substring(0, 16)}...`);
  console.log(`   下载: ${fileInfoCache.downloadUrl}`);

  return fileInfoCache;
}

/**
 * 检查用户是否在灰度名单中
 */
function isInRollout(userId) {
  if (RELEASE_CONFIG.rolloutPercentage >= 100) return true;
  if (RELEASE_CONFIG.rolloutPercentage <= 0) return false;

  // 基于用户 ID 的一致性哈希
  const hash = crypto.createHash('md5').update(userId).digest('hex');
  const value = parseInt(hash.substring(0, 8), 16) % 100;
  return value < RELEASE_CONFIG.rolloutPercentage;
}

/**
 * 比较版本号
 */
function compareVersions(v1, v2) {
  const parts1 = v1.split('.').map(Number);
  const parts2 = v2.split('.').map(Number);
  
  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return 1;
    if (p1 < p2) return -1;
  }
  return 0;
}

// ========================================
// API 路由
// ========================================

/**
 * 检查更新 API
 */
app.post('/api/v1/updates/check', (req, res) => {
  const { current_version, platform, arch, user_id, channel } = req.body;

  console.log('\n📡 收到更新检查请求:');
  console.log(`   当前版本: ${current_version}`);
  console.log(`   平台: ${platform} (${arch})`);
  console.log(`   用户ID: ${user_id}`);
  console.log(`   频道: ${channel}`);

  // 检查是否有新版本
  const hasUpdate = compareVersions(RELEASE_CONFIG.version, current_version) > 0;

  if (!hasUpdate) {
    console.log('✅ 已是最新版本');
    return res.json({
      data: {
        has_update: false,
        latest_version: current_version
      }
    });
  }

  // 检查灰度发布
  const inRollout = isInRollout(user_id);
  if (!inRollout) {
    console.log(`⚠️  用户不在灰度名单中 (当前灰度: ${RELEASE_CONFIG.rolloutPercentage}%)`);
    return res.json({
      data: {
        has_update: true,
        latest_version: RELEASE_CONFIG.version,
        rollout_blocked: true,
        rollout_message: `新版本正在灰度发布中 (当前 ${RELEASE_CONFIG.rolloutPercentage}%)，您的设备暂未进入更新名单`
      }
    });
  }

  // 获取文件信息
  const fileInfo = getFileInfo();
  if (!fileInfo) {
    console.log('❌ 安装包文件不存在');
    return res.status(500).json({
      error: 'Release file not found'
    });
  }

  console.log(`✅ 发现新版本: ${RELEASE_CONFIG.version}`);
  console.log(`   灰度状态: 已通过 (${RELEASE_CONFIG.rolloutPercentage}%)`);

  // 返回更新信息
  res.json({
    data: {
      has_update: true,
      latest_version: RELEASE_CONFIG.version,
      release_notes: RELEASE_CONFIG.releaseNotes,
      file_size: fileInfo.fileSize,
      file_name: fileInfo.fileName,
      file_hash: fileInfo.fileHash,
      download_url: fileInfo.downloadUrl,
      is_mandatory: RELEASE_CONFIG.isMandatory,
      rollout_blocked: false
    }
  });
});

/**
 * 下载统计 API
 */
app.post('/api/v1/stats/download', (req, res) => {
  const { user_id, version, from_version, status, platform, arch } = req.body;

  console.log('\n📊 下载统计:');
  console.log(`   用户ID: ${user_id}`);
  console.log(`   版本: ${from_version} → ${version}`);
  console.log(`   状态: ${status}`);
  console.log(`   平台: ${platform} (${arch})`);

  res.json({ success: true });
});

/**
 * 安装统计 API
 */
app.post('/api/v1/stats/install', (req, res) => {
  const { user_id, from_version, to_version, status, error_message, platform, arch } = req.body;

  console.log('\n📊 安装统计:');
  console.log(`   用户ID: ${user_id}`);
  console.log(`   版本: ${from_version} → ${to_version}`);
  console.log(`   状态: ${status}`);
  if (error_message) {
    console.log(`   错误: ${error_message}`);
  }
  console.log(`   平台: ${platform} (${arch})`);

  res.json({ success: true });
});

/**
 * 管理界面 - 查看配置
 */
app.get('/admin/config', (req, res) => {
  res.json({
    release: RELEASE_CONFIG,
    fileInfo: getFileInfo()
  });
});

/**
 * 管理界面 - 修改配置
 */
app.post('/admin/config', (req, res) => {
  const { version, isMandatory, rolloutPercentage } = req.body;

  if (version) RELEASE_CONFIG.version = version;
  if (typeof isMandatory === 'boolean') RELEASE_CONFIG.isMandatory = isMandatory;
  if (typeof rolloutPercentage === 'number') RELEASE_CONFIG.rolloutPercentage = rolloutPercentage;

  // 清除缓存
  fileInfoCache = null;

  console.log('\n⚙️  配置已更新:');
  console.log(`   版本: ${RELEASE_CONFIG.version}`);
  console.log(`   强制更新: ${RELEASE_CONFIG.isMandatory}`);
  console.log(`   灰度百分比: ${RELEASE_CONFIG.rolloutPercentage}%`);

  res.json({ success: true, config: RELEASE_CONFIG });
});

// ========================================
// 启动服务器
// ========================================

app.listen(PORT, () => {
  console.log('\n========================================');
  console.log('🚀 VidFlow 模拟更新服务器');
  console.log('========================================');
  console.log(`   监听端口: ${PORT}`);
  console.log(`   服务器地址: ${SERVER_URL}`);
  console.log(`   版本: ${RELEASE_CONFIG.version}`);
  console.log(`   强制更新: ${RELEASE_CONFIG.isMandatory ? '是' : '否'}`);
  console.log(`   灰度百分比: ${RELEASE_CONFIG.rolloutPercentage}%`);
  console.log('========================================\n');

  // 检查安装包
  const fileInfo = getFileInfo();
  if (fileInfo) {
    console.log(`   下载地址: ${fileInfo.downloadUrl}`);
  }

  console.log('\n💡 使用方法:');
  console.log('   本地测试:');
  console.log('     node scripts/mock-update-server.js');
  console.log(`     修改 electron/main.js 中的 updateServerUrl 为: ${SERVER_URL}`);
  console.log('\n   公网部署:');
  console.log('     SERVER_URL=http://shcrystal.top:8321 node scripts/mock-update-server.js');
  console.log('\n   管理接口:');
  console.log('     查看配置: GET /admin/config');
  console.log('     修改配置: POST /admin/config');
  console.log('\n✨ 服务器已就绪，等待更新请求...\n');
});

