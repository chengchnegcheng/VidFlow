const { app, BrowserWindow, ipcMain } = require('electron');
const { EventEmitter } = require('events');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const axios = require('axios');
const { DeltaUpdater } = require('./delta-updater');

class CustomUpdater extends EventEmitter {
  constructor(options = {}) {
    super();
    
    this.updateServerUrl = options.updateServerUrl || 'http://shcrystal.top:8321';
    this.currentVersion = app.getVersion();
    this.platform = process.platform;
    this.arch = process.arch;
    this.userId = this.getUserId();
    
    // 更新文件下载路径：使用用户的 Downloads 文件夹
    this.downloadPath = path.join(app.getPath('downloads'), 'VidFlow', 'updates');
    this.autoCheck = options.autoCheck !== false;
    this.autoDownload = options.autoDownload !== false;
    
    this.downloading = false;
    this.downloadProgress = 0;
    this.updateInfo = null;
    this.downloadedFilePath = null;
    this.deltaUpdateApplied = false; // 标记增量更新是否已应用
    
    // 增量更新器
    this.deltaUpdater = new DeltaUpdater(this);
    this.useDeltaUpdate = options.useDeltaUpdate !== false; // 默认启用增量更新
    
    // 确保下载目录存在
    if (!fs.existsSync(this.downloadPath)) {
      fs.mkdirSync(this.downloadPath, { recursive: true });
    }
    
    // 启动时清理旧的更新文件
    this.cleanOldUpdateFiles();
    
    // 转发增量更新事件
    this._setupDeltaEvents();
  }
  
  /**
   * 设置增量更新事件转发
   */
  _setupDeltaEvents() {
    this.deltaUpdater.on('delta-download-start', () => {
      this.emit('download-start', { type: 'delta' });
    });
    
    this.deltaUpdater.on('delta-download-progress', (progress) => {
      this.emit('download-progress', {
        ...progress,
        type: 'delta'
      });
    });
    
    this.deltaUpdater.on('delta-download-complete', (info) => {
      this.emit('delta-download-complete', info);
    });
    
    this.deltaUpdater.on('delta-apply-start', () => {
      this.emit('delta-apply-start');
    });
    
    this.deltaUpdater.on('delta-apply-complete', () => {
      this.emit('delta-apply-complete');
    });
    
    this.deltaUpdater.on('error', (error) => {
      console.error('[CustomUpdater] Delta update error:', error);
      // 增量更新失败时，回退到全量更新
      this.emit('delta-fallback', { reason: error.message });
    });
  }
  
  /**
   * 清理旧的更新文件（7天前）
   */
  cleanOldUpdateFiles() {
    try {
      if (!fs.existsSync(this.downloadPath)) {
        return;
      }
      
      const files = fs.readdirSync(this.downloadPath);
      let cleanedCount = 0;
      
      files.forEach(file => {
        const filePath = path.join(this.downloadPath, file);
        const stats = fs.statSync(filePath);
        
        // 删除7天前的更新文件
        const daysSinceModified = (Date.now() - stats.mtime.getTime()) / (1000 * 60 * 60 * 24);
        if (daysSinceModified > 7) {
          console.log(`[CustomUpdater] Cleaning old update file: ${file}`);
          fs.unlinkSync(filePath);
          cleanedCount++;
        }
      });
      
      if (cleanedCount > 0) {
        console.log(`[CustomUpdater] Cleaned ${cleanedCount} old update file(s)`);
      }
    } catch (error) {
      console.error('[CustomUpdater] Failed to clean old files:', error);
    }
  }
  
  /**
   * 手动清理所有更新文件
   */
  cleanAllUpdateFiles() {
    try {
      if (!fs.existsSync(this.downloadPath)) {
        return { success: true, message: 'No update files to clean' };
      }
      
      const files = fs.readdirSync(this.downloadPath);
      let cleanedCount = 0;
      let totalSize = 0;
      
      files.forEach(file => {
        const filePath = path.join(this.downloadPath, file);
        const stats = fs.statSync(filePath);
        totalSize += stats.size;
        fs.unlinkSync(filePath);
        cleanedCount++;
      });
      
      const message = `Cleaned ${cleanedCount} file(s), freed ${(totalSize / 1024 / 1024).toFixed(2)} MB`;
      console.log(`[CustomUpdater] ${message}`);
      
      return { 
        success: true, 
        message, 
        count: cleanedCount, 
        size: totalSize 
      };
    } catch (error) {
      console.error('[CustomUpdater] Failed to clean all files:', error);
      return { 
        success: false, 
        message: error.message 
      };
    }
  }
  
  /**
   * 获取或生成用户 ID
   */
  getUserId() {
    const userDataPath = app.getPath('userData');
    const userIdFile = path.join(userDataPath, 'user_id.txt');
    
    if (fs.existsSync(userIdFile)) {
      return fs.readFileSync(userIdFile, 'utf8').trim();
    } else {
      const userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      fs.writeFileSync(userIdFile, userId);
      return userId;
    }
  }
  
  /**
   * 检查更新
   */
  async checkForUpdates() {
    console.log('[CustomUpdater] Checking for updates...');
    this.emit('checking-for-update');
    
    try {
      const response = await axios.post(
        `${this.updateServerUrl}/api/v1/updates/check`,
        {
          current_version: this.currentVersion,
          platform: this.platform,
          arch: this.arch,
          user_id: this.userId,
          channel: 'stable'
        },
        {
          timeout: 10000,
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': `VidFlow/${this.currentVersion} (${this.platform})`
          }
        }
      );
      
      const updateInfo = response.data.data;
      
      if (updateInfo.has_update) {
        console.log('[CustomUpdater] Update available:', updateInfo.latest_version);
        this.updateInfo = updateInfo;
        this.emit('update-available', updateInfo);
        
        // 如果灰度阻止，则不自动下载
        if (updateInfo.rollout_blocked) {
          console.log('[CustomUpdater] Update blocked by rollout policy');
          return updateInfo;
        }
        
        // 自动下载
        if (this.autoDownload) {
          // 检查是否有增量更新可用
          if (this.useDeltaUpdate && updateInfo.delta_available && updateInfo.delta_info) {
            console.log('[CustomUpdater] Delta update available, size:', updateInfo.delta_info.delta_size);
            try {
              await this.downloadDeltaUpdate();
            } catch (deltaError) {
              console.error('[CustomUpdater] Delta update failed, falling back to full update:', deltaError);
              this.emit('delta-fallback', { reason: deltaError.message });
              await this.downloadUpdate();
            }
          } else {
            await this.downloadUpdate();
          }
        }
      } else {
        console.log('[CustomUpdater] Already up to date');
        this.emit('update-not-available', { version: this.currentVersion });
      }
      
      return updateInfo;
    } catch (error) {
      console.error('[CustomUpdater] Check failed:', error);
      this.emit('error', error);
      throw error;
    }
  }
  
  /**
   * 下载增量更新
   */
  async downloadDeltaUpdate() {
    const deltaInfo = await this.deltaUpdater.checkDeltaUpdate();
    if (!deltaInfo) {
      throw new Error('No delta update available');
    }
    
    const deltaPath = await this.deltaUpdater.downloadDelta();
    
    // 获取应用安装目录
    const appPath = app.getAppPath();
    const resourcesPath = process.resourcesPath;
    
    // 应用增量更新
    await this.deltaUpdater.applyDelta(deltaPath, resourcesPath);
    
    // 标记增量更新已完成，只需重启
    this.deltaUpdateApplied = true;
    this.downloadedFilePath = null; // 增量更新不需要安装程序
    
    this.emit('update-downloaded', {
      version: this.updateInfo.latest_version,
      type: 'delta',
      requiresRestart: true
    });
  }
  
  /**
   * 下载更新
   */
  async downloadUpdate() {
    if (!this.updateInfo || !this.updateInfo.has_update) {
      throw new Error('No update available');
    }
    
    if (this.downloading) {
      console.log('[CustomUpdater] Download already in progress');
      return;
    }
    
    this.downloading = true;
    const { download_url, file_name, file_hash, file_size } = this.updateInfo;
    const localFilePath = path.join(this.downloadPath, file_name);
    
    console.log('[CustomUpdater] Starting download:', download_url);
    this.emit('download-start');
    
    try {
      // 检查是否已下载且完整
      if (fs.existsSync(localFilePath)) {
        const existingHash = await this.calculateFileHash(localFilePath);
        if (existingHash === file_hash) {
          console.log('[CustomUpdater] File already downloaded and verified');
          this.downloadedFilePath = localFilePath;
          this.emit('update-downloaded', {
            version: this.updateInfo.latest_version,
            path: localFilePath
          });
          this.downloading = false;
          return;
        } else {
          console.log('[CustomUpdater] Existing file corrupted, re-downloading...');
          fs.unlinkSync(localFilePath);
        }
      }
      
      // 下载文件
      const response = await axios({
        method: 'GET',
        url: download_url,
        responseType: 'stream',
        headers: {
          'User-Agent': `VidFlow/${this.currentVersion} (${this.platform})`
        },
        onDownloadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / file_size
          );
          this.downloadProgress = percentCompleted;
          
          this.emit('download-progress', {
            bytesPerSecond: progressEvent.rate || 0,
            percent: percentCompleted,
            transferred: progressEvent.loaded,
            total: file_size
          });
        }
      });
      
      // 写入文件
      const writer = fs.createWriteStream(localFilePath);
      response.data.pipe(writer);
      
      await new Promise((resolve, reject) => {
        writer.on('finish', resolve);
        writer.on('error', reject);
      });
      
      // 验证文件
      console.log('[CustomUpdater] Verifying download...');
      const downloadedHash = await this.calculateFileHash(localFilePath);
      
      if (downloadedHash !== file_hash) {
        fs.unlinkSync(localFilePath);
        throw new Error('File hash verification failed');
      }
      
      console.log('[CustomUpdater] Download completed and verified');
      this.downloadedFilePath = localFilePath;
      
      // 记录下载统计
      await this.reportDownloadComplete();
      
      this.emit('update-downloaded', {
        version: this.updateInfo.latest_version,
        path: localFilePath
      });
      
    } catch (error) {
      console.error('[CustomUpdater] Download failed:', error);
      this.emit('error', error);
      throw error;
    } finally {
      this.downloading = false;
    }
  }
  
  /**
   * 计算文件哈希
   */
  async calculateFileHash(filePath) {
    return new Promise((resolve, reject) => {
      const hash = crypto.createHash('sha512');
      const stream = fs.createReadStream(filePath);
      
      stream.on('data', (data) => hash.update(data));
      stream.on('end', () => resolve(hash.digest('hex')));
      stream.on('error', reject);
    });
  }
  
  /**
   * 退出并安装/重启
   */
  async quitAndInstall() {
    // 增量更新已应用，只需重启
    if (this.deltaUpdateApplied) {
      console.log('[CustomUpdater] Delta update applied, restarting app...');
      app.relaunch();
      app.quit();
      return;
    }
    
    // 全量更新需要安装程序
    if (!this.downloadedFilePath) {
      throw new Error('No update downloaded');
    }

    console.log('[CustomUpdater] Starting installation...');
    
    try {
      // 记录安装开始
      await this.reportInstallStarted();
      
      // 在 Windows 上启动安装程序
      if (this.platform === 'win32') {
        const { spawn } = require('child_process');
        spawn(this.downloadedFilePath, ['/S'], {
          detached: true,
          stdio: 'ignore'
        }).unref();
        
        // 退出当前应用
        setTimeout(() => {
          app.quit();
        }, 1000);
      } else if (this.platform === 'darwin') {
        // macOS 安装逻辑
        const { shell } = require('electron');
        await shell.openPath(this.downloadedFilePath);
        app.quit();
      } else {
        throw new Error('Platform not supported yet');
      }
    } catch (error) {
      console.error('[CustomUpdater] Installation failed:', error);
      await this.reportInstallFailed(error.message);
      throw error;
    }
  }
  
  /**
   * 报告下载完成
   */
  async reportDownloadComplete() {
    try {
      await axios.post(
        `${this.updateServerUrl}/api/v1/stats/download`,
        {
          user_id: this.userId,
          version: this.updateInfo.latest_version,
          from_version: this.currentVersion,
          status: 'completed',
          platform: this.platform,
          arch: this.arch
        },
        { timeout: 5000 }
      );
    } catch (error) {
      console.error('[CustomUpdater] Failed to report download:', error);
    }
  }
  
  /**
   * 报告安装开始
   */
  async reportInstallStarted() {
    try {
      await axios.post(
        `${this.updateServerUrl}/api/v1/stats/install`,
        {
          user_id: this.userId,
          from_version: this.currentVersion,
          to_version: this.updateInfo.latest_version,
          status: 'started',
          platform: this.platform,
          arch: this.arch
        },
        { timeout: 5000 }
      );
    } catch (error) {
      console.error('[CustomUpdater] Failed to report install start:', error);
    }
  }
  
  /**
   * 报告安装失败
   */
  async reportInstallFailed(errorMessage) {
    try {
      await axios.post(
        `${this.updateServerUrl}/api/v1/stats/install`,
        {
          user_id: this.userId,
          from_version: this.currentVersion,
          to_version: this.updateInfo.latest_version,
          status: 'failed',
          error_message: errorMessage,
          platform: this.platform,
          arch: this.arch
        },
        { timeout: 5000 }
      );
    } catch (error) {
      console.error('[CustomUpdater] Failed to report install failure:', error);
    }
  }
}

module.exports = { CustomUpdater };

