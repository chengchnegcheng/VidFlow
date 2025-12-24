/**
 * Electron 主进程集成示例
 * 
 * 在 Electron 的 main.js 中使用自定义更新器
 */

const { app, ipcMain } = require('electron');
const { CustomUpdater } = require('./updater-custom');

// 创建更新器实例
const updater = new CustomUpdater({
  updateServerUrl: 'http://shcrystal.top:8321',
  autoCheck: true,
  autoDownload: false  // 不自动下载，等用户确认
});

/**
 * 初始化更新器
 */
function initUpdater(mainWindow) {
  // 监听更新事件
  updater.on('checking-for-update', () => {
    console.log('Checking for updates...');
    mainWindow.webContents.send('update-checking');
  });

  updater.on('update-available', (info) => {
    console.log('Update available:', info);
    mainWindow.webContents.send('update-available', info);
  });

  updater.on('update-not-available', (info) => {
    console.log('No update available');
    mainWindow.webContents.send('update-not-available', info);
  });

  updater.on('download-progress', (progress) => {
    mainWindow.webContents.send('download-progress', progress);
  });

  updater.on('update-downloaded', (info) => {
    console.log('Update downloaded:', info);
    mainWindow.webContents.send('update-downloaded', info);
  });

  updater.on('error', (error) => {
    console.error('Update error:', error);
    mainWindow.webContents.send('update-error', error.message);
  });

  // 应用启动时检查更新（延迟5秒）
  setTimeout(() => {
    updater.checkForUpdates().catch(console.error);
  }, 5000);
}

/**
 * 注册 IPC 处理器
 */
function registerIpcHandlers() {
  // 手动检查更新
  ipcMain.handle('custom-update-check', async () => {
    try {
      const result = await updater.checkForUpdates();
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  // 开始下载更新
  ipcMain.handle('custom-update-download', async () => {
    try {
      await updater.downloadUpdate();
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  // 退出并安装
  ipcMain.handle('custom-update-install', async () => {
    try {
      await updater.quitAndInstall();
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });
}

module.exports = {
  initUpdater,
  registerIpcHandlers
};
