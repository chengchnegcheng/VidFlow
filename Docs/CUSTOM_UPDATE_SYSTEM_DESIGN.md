# VidFlow Desktop - 自研更新系统设计文档

**版本:** 1.0  
**日期:** 2025-11-01  
**状态:** 设计阶段  
**部署环境:** Alma Linux 9  
**服务地址:** http://shcrystal.top:8321/updates/

---

## 📋 目录

1. [系统概述](#系统概述)
2. [架构设计](#架构设计)
3. [服务端设计](#服务端设计)
4. [客户端设计](#客户端设计)
5. [API 接口规范](#api-接口规范)
6. [安全机制](#安全机制)
7. [部署配置](#部署配置)
8. [监控和维护](#监控和维护)
9. [灰度发布](#灰度发布)
10. [故障处理](#故障处理)

---

## 系统概述

### 设计目标

与 electron-updater 相比，自研更新系统提供：
- ✅ **完全自主控制** - 不依赖第三方服务
- ✅ **灵活的更新策略** - 支持复杂的业务逻辑
- ✅ **精细化灰度发布** - 按用户特征分发
- ✅ **详细的数据分析** - 完整的更新统计
- ✅ **私有部署** - 数据安全可控
- ✅ **多版本管理** - 支持回滚和多渠道

### 技术栈

#### 服务端
- **操作系统:** Alma Linux 9
- **Web 框架:** FastAPI (Python 3.11+)
- **数据库:** PostgreSQL 15 / MySQL 8.0
- **缓存:** Redis 7
- **Web 服务器:** Nginx
- **反向代理:** Nginx
- **进程管理:** Systemd
- **文件存储:** 本地文件系统 / MinIO (可选)

#### 客户端
- **Electron 主进程:** 更新控制逻辑
- **前端 React:** 更新 UI 界面
- **网络请求:** Axios / Fetch API
- **文件下载:** Electron DownloadItem API

---

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    VidFlow Desktop 客户端                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  前端 UI     │───▶│ Electron     │───▶│  自研更新    │  │
│  │  更新界面    │    │ Main Process │    │  管理器      │  │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘  │
│                              │                     │          │
└──────────────────────────────┼─────────────────────┼──────────┘
                               │                     │
                               │   HTTPS API         │
                               ▼                     ▼
                    ┌────────────────────────────────────┐
                    │    Nginx (shcrystal.top:8321)      │
                    └───────────────┬────────────────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    │   FastAPI 更新服务             │
                    ├────────────────────────────────┤
                    │  • 版本检查 API                │
                    │  • 文件下载 API                │
                    │  • 灰度控制 API                │
                    │  • 统计分析 API                │
                    └───────────────┬────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌────────────┐
│  PostgreSQL   │         │     Redis       │         │  文件存储   │
│  数据库       │         │     缓存        │         │  /updates/  │
├───────────────┤         ├─────────────────┤         │  releases/  │
│• 版本信息     │         │• 会话缓存       │         │  • v1.0.0/  │
│• 用户统计     │         │• 热点数据       │         │  • v1.1.0/  │
│• 灰度配置     │         │• 限流控制       │         │  • latest/  │
│• 下载日志     │         └─────────────────┘         └────────────┘
└───────────────┘
```

### 核心组件

#### 1. 版本管理服务
- 版本信息存储和查询
- 变更日志管理
- 发布渠道管理（stable/beta/alpha）

#### 2. 灰度控制服务
- 用户分组策略
- 灰度比例控制
- 黑白名单管理

#### 3. 文件下载服务
- 断点续传支持
- CDN 加速（可选）
- 下载流量统计

#### 4. 统计分析服务
- 更新成功率统计
- 版本分布分析
- 用户行为追踪

---

## 服务端设计

### 目录结构

```
/opt/vidflow-update-server/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── version.py          # 版本模型
│   │   ├── user.py             # 用户模型
│   │   └── download_log.py     # 下载日志模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── version.py          # 版本相关 API
│   │   ├── download.py         # 下载相关 API
│   │   └── stats.py            # 统计相关 API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── version_service.py  # 版本服务
│   │   ├── rollout_service.py  # 灰度服务
│   │   └── analytics_service.py # 分析服务
│   └── utils/
│       ├── __init__.py
│       ├── security.py         # 安全工具
│       ├── file_handler.py     # 文件处理
│       └── cache.py            # 缓存工具
├── data/
│   ├── releases/               # 发布文件存储
│   │   ├── v1.0.0/
│   │   │   ├── VidFlow-1.0.0-win-x64.exe
│   │   │   ├── manifest.json
│   │   │   └── CHANGELOG.md
│   │   └── v1.1.0/
│   │       ├── VidFlow-1.1.0-win-x64.exe
│   │       ├── manifest.json
│   │       └── CHANGELOG.md
│   └── metadata/               # 元数据文件
│       ├── latest.json
│       ├── channels.json
│       └── rollout.json
├── logs/
│   ├── access.log              # 访问日志
│   ├── error.log               # 错误日志
│   └── download.log            # 下载日志
├── scripts/
│   ├── deploy.sh               # 部署脚本
│   ├── backup.sh               # 备份脚本
│   └── rollback.sh             # 回滚脚本
├── tests/
│   ├── test_api.py
│   └── test_services.py
├── requirements.txt            # Python 依赖
├── .env                        # 环境变量
└── README.md
```

### 数据库设计

#### 版本表 (versions)
```sql
CREATE TABLE versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    channel VARCHAR(20) NOT NULL DEFAULT 'stable',  -- stable/beta/alpha
    platform VARCHAR(20) NOT NULL,                   -- win32/darwin/linux
    arch VARCHAR(20) NOT NULL,                       -- x64/arm64
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_hash VARCHAR(128) NOT NULL,                 -- SHA-512
    download_url TEXT NOT NULL,
    release_notes TEXT,
    is_mandatory BOOLEAN DEFAULT FALSE,
    minimum_version VARCHAR(20),                     -- 最低兼容版本
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    download_count INTEGER DEFAULT 0,
    install_success_count INTEGER DEFAULT 0,
    install_failure_count INTEGER DEFAULT 0,
    metadata JSONB                                   -- 扩展字段
);

-- 索引
CREATE INDEX idx_versions_channel ON versions(channel);
CREATE INDEX idx_versions_platform ON versions(platform, arch);
CREATE INDEX idx_versions_published ON versions(published_at DESC);
```

#### 灰度配置表 (rollout_config)
```sql
CREATE TABLE rollout_config (
    id SERIAL PRIMARY KEY,
    version_id INTEGER REFERENCES versions(id),
    rollout_percentage INTEGER DEFAULT 0,           -- 0-100
    target_users TEXT[],                             -- 目标用户 ID 列表
    excluded_users TEXT[],                           -- 排除用户 ID 列表
    conditions JSONB,                                -- 条件规则
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 下载日志表 (download_logs)
```sql
CREATE TABLE download_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),                            -- 匿名或用户 ID
    version_id INTEGER REFERENCES versions(id),
    from_version VARCHAR(20),
    platform VARCHAR(20),
    arch VARCHAR(20),
    ip_address INET,
    user_agent TEXT,
    download_started_at TIMESTAMP,
    download_completed_at TIMESTAMP,
    download_size BIGINT,
    download_speed_kbps INTEGER,
    status VARCHAR(20),                              -- pending/completed/failed
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_download_logs_user ON download_logs(user_id);
CREATE INDEX idx_download_logs_version ON download_logs(version_id);
CREATE INDEX idx_download_logs_status ON download_logs(status);
CREATE INDEX idx_download_logs_created ON download_logs(created_at DESC);
```

#### 更新统计表 (update_stats)
```sql
CREATE TABLE update_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    from_version VARCHAR(20),
    to_version VARCHAR(20),
    status VARCHAR(20),                              -- success/failed/cancelled
    error_code VARCHAR(50),
    error_message TEXT,
    update_duration INTEGER,                         -- 更新耗时（秒）
    retry_count INTEGER DEFAULT 0,
    platform VARCHAR(20),
    arch VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_update_stats_version ON update_stats(to_version);
CREATE INDEX idx_update_stats_status ON update_stats(status);
CREATE INDEX idx_update_stats_created ON update_stats(created_at DESC);
```

### 配置文件

#### .env
```bash
# 应用配置
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8321
APP_DEBUG=false

# 数据库配置
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=vidflow_updates
DB_USER=vidflow_user
DB_PASSWORD=your_secure_password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# 文件存储
STORAGE_TYPE=local
STORAGE_PATH=/opt/vidflow-update-server/data/releases
STORAGE_URL=http://shcrystal.top:8321/updates/files

# 安全配置
SECRET_KEY=your_secret_key_here_change_in_production
JWT_SECRET=your_jwt_secret_here
API_KEY_REQUIRED=false
ALLOWED_ORIGINS=*

# 下载配置
MAX_DOWNLOAD_SPEED_MBPS=0  # 0 = 不限速
ENABLE_RESUME=true
CHUNK_SIZE=1048576  # 1MB

# 灰度发布
ENABLE_ROLLOUT=true
DEFAULT_ROLLOUT_PERCENTAGE=100

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/opt/vidflow-update-server/logs/app.log

# 监控配置
ENABLE_METRICS=true
METRICS_PORT=9090
```

### 核心 API 实现示例

#### app/main.py
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, init_db
from app.api import version, download, stats

# 日志配置
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Initializing VidFlow Update Server...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # 关闭时清理
    logger.info("Shutting down VidFlow Update Server...")

app = FastAPI(
    title="VidFlow Update Server",
    description="自研软件更新服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(version.router, prefix="/api/v1/updates", tags=["version"])
app.include_router(download.router, prefix="/api/v1/downloads", tags=["download"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "VidFlow Update Server",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc)
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG
    )
```

---

## 客户端设计

### 更新管理器 (Electron 主进程)

#### electron/updater-custom.js
```javascript
const { app, BrowserWindow, ipcMain } = require('electron');
const { EventEmitter } = require('events');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const axios = require('axios');

class CustomUpdater extends EventEmitter {
  constructor(options = {}) {
    super();
    
    this.updateServerUrl = options.updateServerUrl || 'http://shcrystal.top:8321/updates';
    this.currentVersion = app.getVersion();
    this.platform = process.platform;
    this.arch = process.arch;
    this.userId = this.getUserId();
    
    this.downloadPath = path.join(app.getPath('temp'), 'vidflow-updates');
    this.autoCheck = options.autoCheck !== false;
    this.autoDownload = options.autoDownload !== false;
    
    this.downloading = false;
    this.downloadProgress = 0;
    
    // 确保下载目录存在
    if (!fs.existsSync(this.downloadPath)) {
      fs.mkdirSync(this.downloadPath, { recursive: true });
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
      
      const updateInfo = response.data;
      
      if (updateInfo.has_update) {
        console.log('[CustomUpdater] Update available:', updateInfo.latest_version);
        this.updateInfo = updateInfo;
        this.emit('update-available', updateInfo);
        
        // 自动下载
        if (this.autoDownload && !updateInfo.rollout_blocked) {
          await this.downloadUpdate();
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
   * 退出并安装
   */
  async quitAndInstall() {
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
        }
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
        }
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
        }
      );
    } catch (error) {
      console.error('[CustomUpdater] Failed to report install failure:', error);
    }
  }
}

module.exports = { CustomUpdater };
```

### 前端更新组件

#### frontend/src/components/CustomUpdateNotification.tsx
```typescript
import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';

interface UpdateInfo {
  has_update: boolean;
  latest_version: string;
  release_notes: string;
  file_size: number;
  is_mandatory: boolean;
  download_url: string;
}

export function CustomUpdateNotification() {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [showModal, setShowModal] = useState(false);
  
  useEffect(() => {
    // 监听更新事件
    if (window.electron) {
      window.electron.on('update-available', (info: UpdateInfo) => {
        setUpdateInfo(info);
        setShowModal(true);
        toast.info(`发现新版本 ${info.latest_version}`);
      });
      
      window.electron.on('download-progress', (progress: any) => {
        setDownloadProgress(progress.percent);
      });
      
      window.electron.on('update-downloaded', () => {
        setDownloading(false);
        toast.success('更新下载完成，准备安装');
      });
      
      window.electron.on('update-error', (error: Error) => {
        setDownloading(false);
        toast.error('更新失败', {
          description: error.message
        });
      });
    }
  }, []);
  
  const handleDownload = async () => {
    setDownloading(true);
    await window.electron.invoke('custom-update-download');
  };
  
  const handleInstall = async () => {
    await window.electron.invoke('custom-update-install');
  };
  
  // ... 其他 UI 逻辑
}
```

---

## API 接口规范

### 基础响应格式

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功",
  "timestamp": "2025-11-01T10:00:00Z"
}
```

### 1. 检查更新

#### POST /api/v1/updates/check

**请求:**
```json
{
  "current_version": "1.0.0",
  "platform": "win32",
  "arch": "x64",
  "user_id": "user_1730462400_abc123",
  "channel": "stable"
}
```

**响应 - 有更新:**
```json
{
  "success": true,
  "data": {
    "has_update": true,
    "latest_version": "1.1.0",
    "release_notes": "## 新功能\n- 自动更新\n- GPU 加速",
    "release_date": "2025-11-01T00:00:00Z",
    "file_name": "VidFlow-1.1.0-win-x64.exe",
    "file_size": 125829120,
    "file_hash": "abc123def456...",
    "download_url": "http://shcrystal.top:8321/updates/files/v1.1.0/VidFlow-1.1.0-win-x64.exe",
    "is_mandatory": false,
    "minimum_version": "1.0.0",
    "rollout_percentage": 50,
    "rollout_blocked": false
  },
  "timestamp": "2025-11-01T10:00:00Z"
}
```

**响应 - 无更新:**
```json
{
  "success": true,
  "data": {
    "has_update": false,
    "current_version": "1.1.0",
    "message": "您已经是最新版本"
  },
  "timestamp": "2025-11-01T10:00:00Z"
}
```

**响应 - 灰度阻止:**
```json
{
  "success": true,
  "data": {
    "has_update": true,
    "latest_version": "1.1.0",
    "rollout_blocked": true,
    "rollout_message": "您的设备暂未进入更新名单，请稍后再试"
  },
  "timestamp": "2025-11-01T10:00:00Z"
}
```

### 2. 下载文件

#### GET /api/v1/downloads/file/{version}/{filename}

**支持特性:**
- ✅ 断点续传 (Range 请求)
- ✅ 流量统计
- ✅ 下载限速（可配置）

**请求头:**
```
Range: bytes=0-1048575
User-Agent: VidFlow/1.0.0 (win32)
```

**响应头:**
```
Content-Type: application/octet-stream
Content-Length: 125829120
Accept-Ranges: bytes
Content-Range: bytes 0-1048575/125829120
X-Content-SHA512: abc123def456...
```

### 3. 记录下载统计

#### POST /api/v1/stats/download

**请求:**
```json
{
  "user_id": "user_1730462400_abc123",
  "version": "1.1.0",
  "from_version": "1.0.0",
  "status": "completed",
  "platform": "win32",
  "arch": "x64",
  "download_size": 125829120,
  "download_time": 180
}
```

### 4. 记录安装统计

#### POST /api/v1/stats/install

**请求:**
```json
{
  "user_id": "user_1730462400_abc123",
  "from_version": "1.0.0",
  "to_version": "1.1.0",
  "status": "success",
  "platform": "win32",
  "arch": "x64",
  "install_time": 60
}
```

### 5. 获取版本列表

#### GET /api/v1/updates/versions

**查询参数:**
- `channel`: stable/beta/alpha
- `platform`: win32/darwin/linux
- `limit`: 默认 20

**响应:**
```json
{
  "success": true,
  "data": {
    "versions": [
      {
        "version": "1.1.0",
        "channel": "stable",
        "platform": "win32",
        "release_date": "2025-11-01T00:00:00Z",
        "download_count": 1250,
        "install_success_rate": 98.5
      },
      {
        "version": "1.0.0",
        "channel": "stable",
        "platform": "win32",
        "release_date": "2025-10-01T00:00:00Z",
        "download_count": 5000,
        "install_success_rate": 99.2
      }
    ],
    "total": 2
  }
}
```

### 6. 获取统计数据

#### GET /api/v1/stats/overview

**响应:**
```json
{
  "success": true,
  "data": {
    "total_users": 10000,
    "active_users_24h": 3500,
    "version_distribution": {
      "1.1.0": 4500,
      "1.0.0": 5500
    },
    "update_success_rate": 98.5,
    "average_download_speed_mbps": 2.5,
    "total_downloads_today": 250
  }
}
```

---

## 安全机制

### 1. 文件完整性验证

#### SHA-512 校验
```python
import hashlib

def calculate_file_hash(file_path: str) -> str:
    """计算文件 SHA-512 哈希"""
    sha512 = hashlib.sha512()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha512.update(chunk)
    return sha512.hexdigest()
```

#### 客户端验证流程
```javascript
// 1. 下载完成后验证
const downloadedHash = await calculateFileHash(localFilePath);
const expectedHash = updateInfo.file_hash;

if (downloadedHash !== expectedHash) {
  fs.unlinkSync(localFilePath);
  throw new Error('文件校验失败，可能已被篡改');
}
```

### 2. 传输安全

#### HTTPS 强制
```nginx
# Nginx 配置
server {
    listen 80;
    server_name shcrystal.top;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name shcrystal.top;
    
    ssl_certificate /etc/ssl/certs/shcrystal.top.crt;
    ssl_certificate_key /etc/ssl/private/shcrystal.top.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
}
```

### 3. 访问控制

#### IP 白名单（可选）
```python
from fastapi import Request, HTTPException

ALLOWED_IPS = [
    "0.0.0.0/0",  # 允许所有（生产环境应限制）
]

async def ip_whitelist_middleware(request: Request, call_next):
    client_ip = request.client.host
    if not is_ip_allowed(client_ip):
        raise HTTPException(status_code=403, detail="IP not allowed")
    return await call_next(request)
```

#### API Key 认证（可选）
```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key
```

### 4. 速率限制

#### Redis 限流
```python
import redis
from fastapi import HTTPException

redis_client = redis.Redis(host='localhost', port=6379, db=0)

async def rate_limit(user_id: str, max_requests: int = 100, window: int = 3600):
    """限流：每小时最多 100 次请求"""
    key = f"rate_limit:{user_id}"
    current = redis_client.get(key)
    
    if current and int(current) >= max_requests:
        raise HTTPException(status_code=429, detail="请求过于频繁")
    
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()
```

### 5. 防止降级攻击

```python
from packaging import version

def validate_version_upgrade(current: str, target: str) -> bool:
    """确保只能升级，不能降级"""
    return version.parse(target) > version.parse(current)
```

---

## 部署配置

### 1. 系统准备

#### 安装依赖 (Alma Linux 9)
```bash
#!/bin/bash

# 更新系统
sudo dnf update -y

# 安装 Python 3.11
sudo dnf install python3.11 python3.11-pip -y

# 安装 PostgreSQL 15
sudo dnf install postgresql15-server postgresql15-contrib -y
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 安装 Redis
sudo dnf install redis -y
sudo systemctl enable redis
sudo systemctl start redis

# 安装 Nginx
sudo dnf install nginx -y
sudo systemctl enable nginx

# 安装 Git
sudo dnf install git -y

# 安装构建工具
sudo dnf install gcc python3.11-devel -y
```

### 2. 数据库初始化

```bash
# 切换到 postgres 用户
sudo -u postgres psql

-- 创建数据库和用户
CREATE DATABASE vidflow_updates;
CREATE USER vidflow_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE vidflow_updates TO vidflow_user;

-- 退出
\q
```

### 3. 应用部署

```bash
#!/bin/bash

# 创建应用目录
sudo mkdir -p /opt/vidflow-update-server
sudo chown $USER:$USER /opt/vidflow-update-server

# 克隆代码（或上传代码）
cd /opt/vidflow-update-server

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 创建必要的目录
mkdir -p data/releases
mkdir -p data/metadata
mkdir -p logs

# 复制配置文件
cp .env.example .env
# 编辑 .env 文件，填入实际配置
nano .env

# 初始化数据库
python -m app.database init

# 测试运行
python -m app.main
```

### 4. Systemd 服务配置

#### /etc/systemd/system/vidflow-update.service
```ini
[Unit]
Description=VidFlow Update Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=vidflow
Group=vidflow
WorkingDirectory=/opt/vidflow-update-server
Environment="PATH=/opt/vidflow-update-server/venv/bin"
EnvironmentFile=/opt/vidflow-update-server/.env
ExecStart=/opt/vidflow-update-server/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8321 --workers 4
Restart=always
RestartSec=10

# 安全配置
PrivateTmp=true
NoNewPrivileges=true

# 日志
StandardOutput=append:/opt/vidflow-update-server/logs/service.log
StandardError=append:/opt/vidflow-update-server/logs/service-error.log

[Install]
WantedBy=multi-user.target
```

**启动服务:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable vidflow-update
sudo systemctl start vidflow-update
sudo systemctl status vidflow-update
```

### 5. Nginx 配置

#### /etc/nginx/conf.d/vidflow-update.conf
```nginx
upstream vidflow_update_backend {
    server 127.0.0.1:8321;
    keepalive 32;
}

server {
    listen 80;
    server_name shcrystal.top;
    
    # 日志
    access_log /var/log/nginx/vidflow-update-access.log;
    error_log /var/log/nginx/vidflow-update-error.log;
    
    # 客户端最大上传大小
    client_max_body_size 500M;
    
    # 静态文件（发布包）
    location /updates/files/ {
        alias /opt/vidflow-update-server/data/releases/;
        
        # 启用断点续传
        add_header Accept-Ranges bytes;
        
        # 缓存设置
        expires 30d;
        add_header Cache-Control "public, immutable";
        
        # 安全头
        add_header X-Content-Type-Options nosniff;
        
        # 限速（可选）
        # limit_rate 10m;
    }
    
    # API 代理
    location /api/ {
        proxy_pass http://vidflow_update_backend;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket 支持（如需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 健康检查
    location /health {
        proxy_pass http://vidflow_update_backend;
        access_log off;
    }
}
```

**启用配置:**
```bash
sudo nginx -t
sudo systemctl restart nginx
```

### 6. 防火墙配置

```bash
# 开放端口
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8321/tcp  # 如果需要直接访问
sudo firewall-cmd --reload

# 查看规则
sudo firewall-cmd --list-all
```

### 7. SSL 证书配置（可选但推荐）

#### 使用 Let's Encrypt
```bash
# 安装 Certbot
sudo dnf install certbot python3-certbot-nginx -y

# 获取证书
sudo certbot --nginx -d shcrystal.top

# 自动续期
sudo systemctl enable certbot-renew.timer
```

---

## 监控和维护

### 1. 日志管理

#### 日志轮转配置
```bash
# /etc/logrotate.d/vidflow-update
/opt/vidflow-update-server/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 vidflow vidflow
    sharedscripts
    postrotate
        systemctl reload vidflow-update > /dev/null 2>&1 || true
    endscript
}
```

### 2. 监控指标

#### Prometheus 集成（可选）
```python
from prometheus_client import Counter, Histogram, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# 定义指标
update_checks = Counter('update_checks_total', 'Total update checks')
downloads = Counter('downloads_total', 'Total downloads')
download_size = Histogram('download_size_bytes', 'Download size in bytes')
active_downloads = Gauge('active_downloads', 'Current active downloads')

# 集成到 FastAPI
Instrumentator().instrument(app).expose(app)
```

### 3. 健康检查

```python
@app.get("/health")
async def health_check():
    """健康检查"""
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "storage": check_storage(),
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
    )
```

### 4. 备份策略

#### 数据库备份
```bash
#!/bin/bash
# /opt/vidflow-update-server/scripts/backup_db.sh

BACKUP_DIR="/opt/vidflow-update-server/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vidflow_updates_$TIMESTAMP.sql"

mkdir -p $BACKUP_DIR

# 备份数据库
pg_dump -U vidflow_user vidflow_updates > $BACKUP_FILE

# 压缩
gzip $BACKUP_FILE

# 删除 7 天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

#### 定时任务
```bash
# 添加到 crontab
crontab -e

# 每天凌晨 2 点备份
0 2 * * * /opt/vidflow-update-server/scripts/backup_db.sh
```

### 5. 性能优化

#### 数据库索引优化
```sql
-- 分析查询性能
EXPLAIN ANALYZE SELECT * FROM versions WHERE channel = 'stable' ORDER BY published_at DESC LIMIT 1;

-- 创建必要的索引
CREATE INDEX CONCURRENTLY idx_versions_channel_published 
ON versions(channel, published_at DESC);
```

#### Redis 缓存策略
```python
import json
from functools import wraps

def cache_result(ttl=3600):
    """Redis 缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 尝试从缓存获取
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 缓存结果
            redis_client.setex(cache_key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

@cache_result(ttl=300)  # 缓存 5 分钟
async def get_latest_version(channel: str):
    # 数据库查询逻辑
    pass
```

---

## 灰度发布

### 1. 灰度策略

#### 基于百分比
```python
import hashlib

def should_receive_update(user_id: str, rollout_percentage: int) -> bool:
    """
    基于用户 ID 的一致性哈希决定是否推送更新
    确保同一用户多次检查得到相同结果
    """
    if rollout_percentage >= 100:
        return True
    if rollout_percentage <= 0:
        return False
    
    # 计算用户 ID 的哈希值
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    user_percentage = (hash_value % 100) + 1
    
    return user_percentage <= rollout_percentage
```

#### 基于用户分组
```python
async def check_rollout_eligibility(
    user_id: str,
    version_id: int,
    platform: str
) -> dict:
    """检查用户是否符合灰度发布条件"""
    config = await get_rollout_config(version_id)
    
    if not config.enabled:
        return {"eligible": False, "reason": "rollout_disabled"}
    
    # 检查白名单
    if user_id in config.target_users:
        return {"eligible": True, "reason": "whitelist"}
    
    # 检查黑名单
    if user_id in config.excluded_users:
        return {"eligible": False, "reason": "blacklist"}
    
    # 检查百分比
    if should_receive_update(user_id, config.rollout_percentage):
        return {"eligible": True, "reason": "percentage"}
    
    return {"eligible": False, "reason": "not_in_rollout"}
```

### 2. 灰度管理 API

#### 更新灰度配置
```python
@router.post("/api/v1/admin/rollout/update")
async def update_rollout_config(
    version: str,
    rollout_percentage: int,
    target_users: List[str] = None,
    excluded_users: List[str] = None
):
    """更新灰度配置"""
    # 验证管理员权限
    # ...
    
    config = await get_or_create_rollout_config(version)
    config.rollout_percentage = rollout_percentage
    config.target_users = target_users or []
    config.excluded_users = excluded_users or []
    
    await save_rollout_config(config)
    
    # 清除相关缓存
    clear_version_cache(version)
    
    return {"success": True, "config": config}
```

### 3. 灰度阶段建议

| 阶段 | 比例 | 持续时间 | 监控重点 |
|------|------|---------|---------|
| Alpha | 1% | 1-2 天 | 崩溃率、关键功能 |
| Beta | 10% | 3-5 天 | 性能指标、用户反馈 |
| 扩展 | 50% | 5-7 天 | 整体稳定性 |
| 全量 | 100% | - | 持续监控 |

---

## 故障处理

### 1. 常见问题

#### 下载失败
**症状:** 客户端报告下载失败  
**排查:**
```bash
# 检查文件是否存在
ls -lh /opt/vidflow-update-server/data/releases/v1.1.0/

# 检查 Nginx 访问日志
tail -f /var/log/nginx/vidflow-update-access.log | grep "GET /updates/files"

# 检查 Nginx 错误日志
tail -f /var/log/nginx/vidflow-update-error.log

# 检查服务状态
sudo systemctl status vidflow-update
```

#### 数据库连接失败
**症状:** API 返回 500 错误  
**排查:**
```bash
# 检查 PostgreSQL 状态
sudo systemctl status postgresql

# 检查连接
psql -U vidflow_user -d vidflow_updates -c "SELECT 1;"

# 查看数据库日志
sudo tail -f /var/lib/pgsql/15/data/log/postgresql-*.log
```

### 2. 紧急回滚

#### 回滚到旧版本
```python
@router.post("/api/v1/admin/rollback/{version}")
async def rollback_version(version: str):
    """紧急回滚指定版本"""
    # 找到前一个稳定版本
    previous_version = await get_previous_stable_version(version)
    
    # 更新 latest.json
    await update_latest_metadata(previous_version)
    
    # 禁用问题版本
    await disable_version(version)
    
    # 通知用户
    await notify_rollback(version, previous_version)
    
    return {
        "success": True,
        "rolled_back_from": version,
        "rolled_back_to": previous_version
    }
```

### 3. 灾难恢复

#### 数据恢复
```bash
#!/bin/bash
# 恢复最近的备份

BACKUP_FILE=$(ls -t /opt/vidflow-update-server/backups/*.sql.gz | head -1)

# 解压
gunzip -c $BACKUP_FILE > /tmp/restore.sql

# 恢复
psql -U vidflow_user vidflow_updates < /tmp/restore.sql

# 清理
rm /tmp/restore.sql
```

---

## 开发计划

### 时间估算

| 阶段 | 任务 | 预计时间 |
|------|------|---------|
| **Phase 1: 基础框架** | | |
| 1.1 | 服务器环境搭建 | 2 天 |
| 1.2 | 数据库设计和实现 | 2 天 |
| 1.3 | 核心 API 开发 | 3 天 |
| **Phase 2: 客户端集成** | | |
| 2.1 | 自定义更新器开发 | 3 天 |
| 2.2 | 前端 UI 实现 | 2 天 |
| 2.3 | 端到端测试 | 2 天 |
| **Phase 3: 高级功能** | | |
| 3.1 | 灰度发布系统 | 2 天 |
| 3.2 | 统计分析功能 | 2 天 |
| 3.3 | 管理后台 | 3 天 |
| **Phase 4: 部署运维** | | |
| 4.1 | 服务器部署 | 1 天 |
| 4.2 | 监控告警 | 1 天 |
| 4.3 | 文档完善 | 1 天 |

**总计:** 约 24 个工作日（5 周）

---

## 总结

### 优势

| 特性 | electron-updater | 自研系统 |
|------|-----------------|---------|
| 开发成本 | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 灵活性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 数据掌控 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 维护成本 | ⭐⭐⭐⭐ | ⭐⭐ |
| 功能扩展 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### 适用场景

**选择自研系统的理由:**
- ✅ 需要精细的灰度发布控制
- ✅ 需要详细的用户行为分析
- ✅ 有私有部署需求
- ✅ 需要自定义更新逻辑
- ✅ 有充足的开发资源

**选择 electron-updater 的理由:**
- ✅ 快速上线需求
- ✅ 团队规模较小
- ✅ 预算有限
- ✅ 对数据隐私要求不高

---

## 下一步行动

1. **评审本方案** - 确认技术栈和架构
2. **准备服务器** - 采购或准备 Alma Linux 9 服务器
3. **开发环境搭建** - 安装必要的软件和工具
4. **开始开发** - 按阶段实施
5. **测试部署** - 在测试环境验证
6. **生产发布** - 逐步推广使用

---

**文档维护:**
- **作者:** VidFlow 开发团队
- **服务器:** http://shcrystal.top:8321/updates/
- **环境:** Alma Linux 9
- **版本历史:**
  - v1.0 (2025-11-01): 初始版本

**参考资料:**
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [PostgreSQL 文档](https://www.postgresql.org/docs/)
- [Nginx 文档](https://nginx.org/en/docs/)
- [Alma Linux 文档](https://wiki.almalinux.org/)

