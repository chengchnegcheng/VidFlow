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
   * 由于应用运行时无法替换正在使用的 exe 文件，
   * 我们将差异包解压到 pending 目录，重启时再应用
   */
  async applyDelta(deltaPath, targetDir) {
    console.log('[DeltaUpdater] Preparing delta update...');
    console.log('[DeltaUpdater] Target directory:', targetDir);
    this.emit('delta-apply-start');

    try {
      // 解压差异包到 pending 目录
      const zip = new AdmZip(deltaPath);
      const pendingDir = path.join(this.customUpdater.downloadPath, 'pending_update');

      if (fs.existsSync(pendingDir)) {
        fs.rmSync(pendingDir, { recursive: true });
      }
      fs.mkdirSync(pendingDir, { recursive: true });

      zip.extractAllTo(pendingDir, true);

      // 读取清单
      const manifestPath = path.join(pendingDir, 'manifest.json');
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

      console.log('[DeltaUpdater] Manifest loaded:', manifest.files.length, 'files');
      console.log('[DeltaUpdater] Source version:', manifest.source_version);
      console.log('[DeltaUpdater] Target version:', manifest.version);

      // 保存更新信息，供重启后使用
      const updateInfoPath = path.join(this.customUpdater.downloadPath, 'pending_update.json');
      fs.writeFileSync(updateInfoPath, JSON.stringify({
        pendingDir,
        targetDir,
        manifest,
        deltaPath,
        createdAt: new Date().toISOString()
      }, null, 2));

      console.log('[DeltaUpdater] Delta update prepared, will apply on restart');
      this.emit('delta-apply-complete');

      // 注意：这里只是准备完成，实际应用在重启后的 applyPendingUpdate 中
      // 上报移到 applyPendingUpdate 成功后

      return true;

    } catch (error) {
      console.error('[DeltaUpdater] Delta prepare failed:', error);
      this.emit('error', error);
      await this.reportUpdateResult(false, error.message);
      throw error;
    }
  }

  /**
   * 在应用启动时检查并应用待处理的增量更新
   * 应该在应用启动早期、后端启动之前调用
   */
  async applyPendingUpdate() {
    const updateInfoPath = path.join(this.customUpdater.downloadPath, 'pending_update.json');
    
    if (!fs.existsSync(updateInfoPath)) {
      return false;
    }

    console.log('[DeltaUpdater] Found pending update, applying...');

    let updateInfo;
    try {
      updateInfo = JSON.parse(fs.readFileSync(updateInfoPath, 'utf8'));
      const { pendingDir, targetDir, manifest } = updateInfo;

      if (!fs.existsSync(pendingDir)) {
        console.log('[DeltaUpdater] Pending directory not found, skipping');
        fs.unlinkSync(updateInfoPath);
        return false;
      }

      // 创建备份
      const backupDir = await this.createBackup(targetDir, manifest.files);

      try {
        // 应用变更
        for (const fileChange of manifest.files) {
          await this.applyFileChange(fileChange, pendingDir, targetDir);
        }

        // 更新 package.json 中的版本号（关键步骤！）
        await this.updatePackageVersion(targetDir, manifest.version);

        // 验证完整性（可选，因为文件可能还没被加载）
        // const valid = await this.verifyTargetFiles(manifest, targetDir);

        // 清理
        fs.rmSync(backupDir, { recursive: true });
        fs.rmSync(pendingDir, { recursive: true });
        fs.unlinkSync(updateInfoPath);
        
        // 清理旧的 delta 包
        if (updateInfo.deltaPath && fs.existsSync(updateInfo.deltaPath)) {
          try {
            fs.unlinkSync(updateInfo.deltaPath);
            console.log('[DeltaUpdater] Cleaned delta package:', updateInfo.deltaPath);
          } catch (err) {
            console.warn('[DeltaUpdater] Failed to clean delta package:', err.message);
          }
        }

        console.log('[DeltaUpdater] Pending update applied successfully');
        
        // 上报更新成功
        await this.reportPendingUpdateResult(updateInfo, true);
        
        return true;

      } catch (error) {
        console.error('[DeltaUpdater] Apply pending update failed, rolling back...', error);
        await this.rollback(backupDir, targetDir);
        
        // 清理失败的更新
        if (fs.existsSync(pendingDir)) {
          fs.rmSync(pendingDir, { recursive: true });
        }
        fs.unlinkSync(updateInfoPath);
        
        // 上报更新失败
        await this.reportPendingUpdateResult(updateInfo, false, error.message);
        
        throw error;
      }

    } catch (error) {
      console.error('[DeltaUpdater] Failed to apply pending update:', error);
      // 清理更新信息文件
      try {
        fs.unlinkSync(updateInfoPath);
      } catch {}
      return false;
    }
  }

  /**
   * 应用差异包 - 旧方法，保留用于直接应用（非 exe 文件）
   */
  async applyDeltaDirect(deltaPath, targetDir) {
    console.log('[DeltaUpdater] Applying delta package directly...');
    console.log('[DeltaUpdater] Target directory:', targetDir);
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
      console.log('[DeltaUpdater] Source version:', manifest.source_version);
      console.log('[DeltaUpdater] Target version:', manifest.version);

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
   * 更新 package.json 中的版本号
   * 这是增量更新的关键步骤，确保 app.getVersion() 返回新版本号
   */
  async updatePackageVersion(targetDir, newVersion) {
    // package.json 位于 resources/app/package.json
    const packageJsonPath = path.join(targetDir, 'app', 'package.json');
    
    if (!fs.existsSync(packageJsonPath)) {
      console.warn('[DeltaUpdater] package.json not found at:', packageJsonPath);
      return false;
    }

    try {
      const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
      const oldVersion = packageJson.version;
      packageJson.version = newVersion;
      
      fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 4), 'utf8');
      console.log(`[DeltaUpdater] Updated package.json version: ${oldVersion} -> ${newVersion}`);
      return true;
    } catch (error) {
      console.error('[DeltaUpdater] Failed to update package.json:', error);
      throw error;
    }
  }

  /**
   * 将差异包路径映射到实际安装路径
   * 差异包路径格式: backend/xxx 或 frontend/dist/xxx
   * 安装目录结构 (asar: false): 
   *   - resources/backend/xxx (后端)
   *   - resources/app/frontend/dist/xxx (前端)
   */
  mapToInstallPath(deltaPath, targetDir) {
    if (deltaPath.startsWith('backend/')) {
      // backend/xxx -> resources/backend/xxx
      // targetDir 已经是 resources 目录
      return path.join(targetDir, deltaPath);
    } else if (deltaPath.startsWith('frontend/')) {
      // frontend/dist/xxx -> resources/app/frontend/dist/xxx
      // 禁用 asar 后，前端文件在 resources/app/ 目录下
      return path.join(targetDir, 'app', deltaPath);
    }
    // 其他路径直接使用
    return path.join(targetDir, deltaPath);
  }

  /**
   * 应用单个文件变更
   */
  async applyFileChange(fileChange, tempDir, targetDir) {
    // 映射到实际安装路径
    const targetPath = this.mapToInstallPath(fileChange.path, targetDir);

    switch (fileChange.action) {
      case 'add':
      case 'replace':
        // 添加或替换文件（新格式统一放在 files/ 目录）
        const filePath = path.join(tempDir, 'files', fileChange.path);
        if (fs.existsSync(filePath)) {
          fs.mkdirSync(path.dirname(targetPath), { recursive: true });
          fs.copyFileSync(filePath, targetPath);
          console.log(`[DeltaUpdater] ${fileChange.action}: ${fileChange.path} -> ${targetPath}`);
        } else {
          console.warn(`[DeltaUpdater] File not found in delta: ${fileChange.path}`);
        }
        break;

      case 'delete':
        // 删除文件
        if (fs.existsSync(targetPath)) {
          fs.unlinkSync(targetPath);
          console.log(`[DeltaUpdater] delete: ${fileChange.path}`);
        }
        break;

      default:
        console.warn(`[DeltaUpdater] Unknown action: ${fileChange.action}`);
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

      const sourcePath = this.mapToInstallPath(fileChange.path, targetDir);
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
      const targetPath = this.mapToInstallPath(relativePath, targetDir);
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

      const targetPath = this.mapToInstallPath(fileChange.path, targetDir);
      if (!fs.existsSync(targetPath)) {
        console.error('[DeltaUpdater] Missing file:', fileChange.path, '->', targetPath);
        return false;
      }

      if (fileChange.target_hash) {
        // manifest 中的 target_hash 是 SHA-256（由 delta_generator.py 生成）
        const hash = await this.calculateFileSha256(targetPath);
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
   * 计算文件哈希 (SHA-256，与 delta_generator.py 保持一致)
   * 用于验证下载的差异包完整性
   */
  async calculateFileHash(filePath) {
    return new Promise((resolve, reject) => {
      const hash = crypto.createHash('sha256');
      const stream = fs.createReadStream(filePath);

      stream.on('data', (data) => hash.update(data));
      stream.on('end', () => resolve(hash.digest('hex')));
      stream.on('error', reject);
    });
  }

  /**
   * 计算文件 SHA-256 哈希（与 delta_generator.py 保持一致）
   * 用于验证 manifest 中的文件哈希
   */
  async calculateFileSha256(filePath) {
    return this.calculateFileHash(filePath);
  }

  /**
   * 上报更新结果（用于下载/准备阶段）
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

  /**
   * 上报待处理更新的应用结果（用于重启后应用阶段）
   */
  async reportPendingUpdateResult(updateInfo, success, error = null) {
    try {
      const { manifest } = updateInfo;
      await axios.post(
        `${this.customUpdater.updateServerUrl}/api/v1/updates/deltas/report`,
        {
          source_version: manifest.source_version,
          target_version: manifest.version,
          platform: this.customUpdater.platform,
          arch: this.customUpdater.arch,
          update_type: 'delta_apply',
          success,
          error
        },
        { timeout: 5000 }
      );
    } catch (err) {
      console.error('[DeltaUpdater] Failed to report pending update result:', err);
    }
  }
}

module.exports = { DeltaUpdater };
