const { EventEmitter } = require('events');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const axios = require('axios');
const AdmZip = require('adm-zip');

class DeltaUpdater extends EventEmitter {
  constructor(customUpdater) {
    super();
    this.customUpdater = customUpdater;
    this.updateInfo = null;
    this.deltaInfo = null;
    this.downloading = false;
  }

  /**
   * 检查是否有增量更新
   */
  async checkDeltaUpdate() {
    const updateInfo = this.customUpdater.updateInfo;
    if (!updateInfo || !updateInfo.delta_available) {
      return null;
    }

    this.updateInfo = updateInfo;
    this.deltaInfo = updateInfo.delta_info;
    return this.deltaInfo;
  }

  /**
   * 获取推荐的更新方式
   */
  getRecommendedUpdateType() {
    if (!this.updateInfo) return 'full';
    return this.updateInfo.recommended_update_type || 'full';
  }

  /**
   * 下载差异包
   */
  async downloadDelta() {
    if (!this.deltaInfo) {
      throw new Error('No delta update available');
    }

    if (this.downloading) {
      console.log('[DeltaUpdater] Download already in progress');
      return;
    }

    this.downloading = true;
    const { delta_url, delta_hash, delta_size } = this.deltaInfo;
    const fileName = path.basename(delta_url);
    const localFilePath = path.join(this.customUpdater.downloadPath, fileName);

    console.log('[DeltaUpdater] Starting delta download:', delta_url);
    this.emit('delta-download-start');

    try {
      // 检查是否已下载
      if (fs.existsSync(localFilePath)) {
        const existingHash = await this.calculateFileHash(localFilePath);
        if (existingHash === delta_hash) {
          console.log('[DeltaUpdater] Delta already downloaded');
          this.emit('delta-download-complete', { path: localFilePath });
          this.downloading = false;
          return localFilePath;
        }
        fs.unlinkSync(localFilePath);
      }

      // 下载差异包
      const response = await axios({
        method: 'GET',
        url: delta_url,
        responseType: 'stream',
        onDownloadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / delta_size);
          this.emit('delta-download-progress', {
            percent,
            transferred: progressEvent.loaded,
            total: delta_size
          });
        }
      });

      const writer = fs.createWriteStream(localFilePath);
      response.data.pipe(writer);

      await new Promise((resolve, reject) => {
        writer.on('finish', resolve);
        writer.on('error', reject);
      });

      // 验证哈希
      const downloadedHash = await this.calculateFileHash(localFilePath);
      if (downloadedHash !== delta_hash) {
        fs.unlinkSync(localFilePath);
        throw new Error('Delta hash verification failed');
      }

      console.log('[DeltaUpdater] Delta download completed');
      this.emit('delta-download-complete', { path: localFilePath });
      return localFilePath;

    } catch (error) {
      console.error('[DeltaUpdater] Delta download failed:', error);
      this.emit('error', error);
      throw error;
    } finally {
      this.downloading = false;
    }
  }

  /**
   * 应用差异包
   */
  async applyDelta(deltaPath, targetDir) {
    console.log('[DeltaUpdater] Applying delta package...');
    this.emit('delta-apply-start');

    try {
      // 解压差异包
      const zip = new AdmZip(deltaPath);
      const tempDir = path.join(this.customUpdater.downloadPath, 'delta_temp');

      if (fs.existsSync(tempDir)) {
        fs.rmSync(tempDir, { recursive: true });
      }
      fs.mkdirSync(tempDir, { recursive: true });

      zip.extractAllTo(tempDir, true);

      // 读取清单
      const manifestPath = path.join(tempDir, 'manifest.json');
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

      console.log('[DeltaUpdater] Manifest loaded:', manifest.files.length, 'files');

      // 创建备份
      const backupDir = await this.createBackup(targetDir, manifest.files);

      try {
        // 应用变更
        for (const fileChange of manifest.files) {
          await this.applyFileChange(fileChange, tempDir, targetDir);
        }

        // 验证完整性
        const valid = await this.verifyTargetFiles(manifest, targetDir);
        if (!valid) {
          throw new Error('Target files verification failed');
        }

        // 清理备份
        fs.rmSync(backupDir, { recursive: true });
        fs.rmSync(tempDir, { recursive: true });

        console.log('[DeltaUpdater] Delta applied successfully');
        this.emit('delta-apply-complete');

        // 上报成功
        await this.reportUpdateResult(true);

        return true;

      } catch (error) {
        // 回滚
        console.error('[DeltaUpdater] Apply failed, rolling back...', error);
        await this.rollback(backupDir, targetDir);
        await this.reportUpdateResult(false, error.message);
        throw error;
      }

    } catch (error) {
      console.error('[DeltaUpdater] Delta apply failed:', error);
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * 应用单个文件变更
   */
  async applyFileChange(fileChange, tempDir, targetDir) {
    const targetPath = path.join(targetDir, fileChange.path);

    switch (fileChange.action) {
      case 'add':
        // 添加新文件
        const newFilePath = path.join(tempDir, 'new', fileChange.path);
        fs.mkdirSync(path.dirname(targetPath), { recursive: true });
        fs.copyFileSync(newFilePath, targetPath);
        break;

      case 'delete':
        // 删除文件
        if (fs.existsSync(targetPath)) {
          fs.unlinkSync(targetPath);
        }
        break;

      case 'patch':
        // 应用补丁（简化版：直接替换）
        const patchFilePath = path.join(tempDir, 'patches', fileChange.patch_file);
        if (fs.existsSync(patchFilePath)) {
          fs.copyFileSync(patchFilePath, targetPath);
        }
        break;

      case 'replace':
        // 替换文件
        const replaceFilePath = path.join(tempDir, 'new', fileChange.path);
        fs.copyFileSync(replaceFilePath, targetPath);
        break;
    }
  }

  /**
   * 创建备份
   */
  async createBackup(targetDir, files) {
    const backupDir = path.join(this.customUpdater.downloadPath, `backup_${Date.now()}`);
    fs.mkdirSync(backupDir, { recursive: true });

    for (const fileChange of files) {
      if (fileChange.action === 'add') continue;

      const sourcePath = path.join(targetDir, fileChange.path);
      if (fs.existsSync(sourcePath)) {
        const backupPath = path.join(backupDir, fileChange.path);
        fs.mkdirSync(path.dirname(backupPath), { recursive: true });
        fs.copyFileSync(sourcePath, backupPath);
      }
    }

    return backupDir;
  }

  /**
   * 回滚
   */
  async rollback(backupDir, targetDir) {
    console.log('[DeltaUpdater] Rolling back...');

    const files = this.getAllFiles(backupDir);
    for (const file of files) {
      const relativePath = path.relative(backupDir, file);
      const targetPath = path.join(targetDir, relativePath);
      fs.mkdirSync(path.dirname(targetPath), { recursive: true });
      fs.copyFileSync(file, targetPath);
    }

    console.log('[DeltaUpdater] Rollback complete');
  }

  /**
   * 验证目标文件
   */
  async verifyTargetFiles(manifest, targetDir) {
    for (const fileChange of manifest.files) {
      if (fileChange.action === 'delete') continue;

      const targetPath = path.join(targetDir, fileChange.path);
      if (!fs.existsSync(targetPath)) {
        console.error('[DeltaUpdater] Missing file:', fileChange.path);
        return false;
      }

      if (fileChange.target_hash) {
        const hash = await this.calculateFileHash(targetPath);
        if (hash !== fileChange.target_hash) {
          console.error('[DeltaUpdater] Hash mismatch:', fileChange.path);
          return false;
        }
      }
    }

    return true;
  }

  /**
   * 获取目录下所有文件
   */
  getAllFiles(dir) {
    const files = [];
    const items = fs.readdirSync(dir);

    for (const item of items) {
      const fullPath = path.join(dir, item);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory()) {
        files.push(...this.getAllFiles(fullPath));
      } else {
        files.push(fullPath);
      }
    }

    return files;
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
   * 上报更新结果
   */
  async reportUpdateResult(success, error = null) {
    try {
      await axios.post(
        `${this.customUpdater.updateServerUrl}/api/v1/updates/deltas/report`,
        {
          source_version: this.customUpdater.currentVersion,
          target_version: this.updateInfo.latest_version,
          platform: this.customUpdater.platform,
          arch: this.customUpdater.arch,
          update_type: 'delta',
          success,
          error
        },
        { timeout: 5000 }
      );
    } catch (err) {
      console.error('[DeltaUpdater] Failed to report result:', err);
    }
  }
}

module.exports = { DeltaUpdater };
