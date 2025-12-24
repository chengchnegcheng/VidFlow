# VidFlow Desktop - 软件更新功能设计文档

**版本:** 1.0  
**日期:** 2025-11-01  
**状态:** 设计阶段

---

## 📋 目录

1. [概述](#概述)
2. [功能需求](#功能需求)
3. [技术方案](#技术方案)
4. [架构设计](#架构设计)
5. [实现细节](#实现细节)
6. [API 设计](#api-设计)
7. [前端界面设计](#前端界面设计)
8. [安全考虑](#安全考虑)
9. [测试方案](#测试方案)
10. [部署流程](#部署流程)
11. [回滚策略](#回滚策略)

---

## 概述

### 背景
VidFlow Desktop 当前缺少自动更新功能，用户需要手动下载新版本并重新安装。这导致：
- 用户体验不佳
- 版本碎片化严重
- 安全补丁无法及时推送
- 新功能采用率低

### 目标
实现一套完整的软件更新系统，支持：
- ✅ 自动检查更新
- ✅ 版本对比和变更日志展示
- ✅ 增量更新（可选）
- ✅ 后台下载
- ✅ 静默安装或用户确认安装
- ✅ 更新失败回滚
- ✅ 更新渠道管理（稳定版/测试版）

---

## 功能需求

### 1. 用户需求

#### 1.1 自动检查更新
- **启动检查**: 应用启动时自动检查更新
- **定期检查**: 后台每24小时检查一次
- **手动检查**: 设置页面提供"检查更新"按钮
- **智能提醒**: 可配置更新提醒频率

#### 1.2 更新信息展示
- 新版本号
- 发布日期
- 更新大小
- 详细的变更日志（Markdown 格式）
- 是否为重要安全更新

#### 1.3 更新方式
- **立即更新**: 用户主动触发
- **稍后提醒**: 延迟到下次启动
- **跳过此版本**: 不再提示该版本
- **静默更新**: 后台下载，重启时安装

#### 1.4 下载进度
- 实时下载进度条
- 下载速度显示
- 剩余时间估算
- 支持暂停/恢复下载

### 2. 技术需求

#### 2.1 更新协议
- 使用 HTTPS 确保安全
- 支持断点续传
- 版本清单签名验证
- 安装包完整性校验

#### 2.2 性能要求
- 检查更新响应 < 3秒
- 下载不影响应用正常使用
- 安装过程用户可感知进度

#### 2.3 兼容性
- 支持 Windows 7/10/11
- 兼容不同架构（x64/ARM）
- 处理权限问题（UAC）

---

## 技术方案

### 方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **electron-updater** | 成熟稳定、与 Electron 深度集成、支持自动签名 | 需要配置服务器、学习成本 | ⭐⭐⭐⭐⭐ |
| **自研更新系统** | 完全可控、灵活定制 | 开发成本高、安全风险 | ⭐⭐⭐ |
| **第三方服务** (如 AppCenter) | 免维护、功能全面 | 依赖外部服务、可能有费用 | ⭐⭐⭐⭐ |

### 推荐方案: electron-updater

**理由:**
1. ✅ Electron 官方推荐的更新解决方案
2. ✅ 支持 Windows NSIS 安装包的自动更新
3. ✅ 内置增量更新支持
4. ✅ 完善的文档和社区支持
5. ✅ 支持 GitHub Releases 作为更新源

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     VidFlow Desktop                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────┐    ┌──────────────┐   ┌─────────────┐ │
│  │   前端 UI   │───▶│  Electron    │──▶│   Backend   │ │
│  │  更新界面   │    │  Main Process│   │  (可选辅助) │ │
│  └─────────────┘    │              │   └─────────────┘ │
│                      │  electron-   │                    │
│                      │  updater     │                    │
│                      └──────┬───────┘                    │
└─────────────────────────────┼────────────────────────────┘
                              │
                              │ HTTPS
                              ▼
                    ┌──────────────────┐
                    │   更新服务器      │
                    ├──────────────────┤
                    │ • GitHub Releases│
                    │ • 或自建服务器    │
                    │ • latest.yml     │
                    │ • 安装包文件      │
                    └──────────────────┘
```

### 组件说明

#### 1. 前端更新 UI 组件
- **位置**: `frontend/src/components/UpdateNotification.tsx`
- **职责**: 
  - 显示更新通知
  - 展示更新详情
  - 控制下载和安装流程
  - 显示进度

#### 2. Electron 主进程更新模块
- **位置**: `electron/updater.js`
- **职责**:
  - 初始化 electron-updater
  - 处理更新事件
  - 与前端通信
  - 管理下载和安装

#### 3. 后端辅助 API (可选)
- **位置**: `backend/src/api/update.py`
- **职责**:
  - 记录更新统计
  - 灰度发布控制
  - 自定义更新逻辑

#### 4. 更新服务器
- **GitHub Releases** (推荐)
  - 免费托管
  - CDN 加速
  - 版本管理便捷
  
- **自建服务器** (备选)
  - 完全可控
  - 支持私有部署
  - 可实现复杂逻辑

---

## 实现细节

### 1. 配置文件结构

#### electron-builder.json
```json
{
  "appId": "com.vidflow.desktop",
  "productName": "VidFlow",
  "publish": {
    "provider": "github",
    "owner": "your-username",
    "repo": "vidflow-desktop",
    "releaseType": "release"
  },
  "win": {
    "target": [
      {
        "target": "nsis",
        "arch": ["x64"]
      }
    ]
  },
  "nsis": {
    "oneClick": false,
    "allowToChangeInstallationDirectory": true,
    "createDesktopShortcut": true,
    "createStartMenuShortcut": true,
    "shortcutName": "VidFlow"
  }
}
```

#### latest.yml (自动生成)
```yaml
version: 1.1.0
releaseDate: 2025-11-01T00:00:00.000Z
files:
  - url: VidFlow-1.1.0-win-x64.exe
    sha512: abc123def456...
    size: 125829120
path: VidFlow-1.1.0-win-x64.exe
sha512: abc123def456...
releaseNotes: |
  ## 新功能
  - 添加自动更新功能
  - 支持 GPU 加速转码
  
  ## 改进
  - 优化下载速度
  - 修复若干已知问题
```

### 2. 更新检查流程

```
应用启动
   │
   ▼
初始化 updater
   │
   ▼
读取本地配置
   │
   ├─ 检查更新频率
   ├─ 跳过的版本列表
   └─ 更新渠道设置
   │
   ▼
检查更新（异步）
   │
   ├─ 请求 latest.yml
   ├─ 对比版本号
   └─ 验证签名
   │
   ▼
发现新版本？
   │
   ├─ 是 ──▶ 触发 'update-available' 事件
   │          │
   │          ▼
   │       显示更新通知
   │          │
   │          ├─ 立即更新 ──▶ 开始下载
   │          ├─ 稍后提醒 ──▶ 记录状态
   │          └─ 跳过版本 ──▶ 加入黑名单
   │
   └─ 否 ──▶ 继续正常运行
```

### 3. 下载和安装流程

```
用户点击"立即更新"
   │
   ▼
触发 downloadUpdate()
   │
   ▼
开始下载
   │
   ├─ 显示进度窗口
   ├─ 更新进度条
   └─ 可暂停/取消
   │
   ▼
下载完成
   │
   ├─ 验证文件完整性 (SHA512)
   └─ 验证签名
   │
   ▼
验证通过？
   │
   ├─ 是 ──▶ 提示重启安装
   │          │
   │          ├─ 立即重启 ──▶ quitAndInstall()
   │          └─ 稍后重启 ──▶ 下次启动时安装
   │
   └─ 否 ──▶ 显示错误，重新下载
```

### 4. 事件监听

#### electron-updater 核心事件

| 事件 | 触发时机 | 参数 | 处理逻辑 |
|------|---------|------|---------|
| `checking-for-update` | 开始检查更新 | - | 显示"正在检查更新..." |
| `update-available` | 发现新版本 | `info` | 显示更新通知 |
| `update-not-available` | 已是最新版本 | `info` | 静默处理或提示 |
| `download-progress` | 下载进度更新 | `progressObj` | 更新进度条 |
| `update-downloaded` | 下载完成 | `info` | 提示重启安装 |
| `error` | 发生错误 | `error` | 记录日志，显示错误 |

### 5. 版本号规范

采用 **Semantic Versioning 2.0**:
```
MAJOR.MINOR.PATCH-PRERELEASE+BUILD

例如:
- 1.0.0        - 正式版
- 1.1.0-beta.1 - 测试版
- 1.2.3        - 修复版
- 2.0.0        - 重大更新
```

**版本对比规则:**
```javascript
// electron-updater 自动处理
1.2.3 < 1.2.4   // PATCH 升级
1.2.0 < 1.3.0   // MINOR 升级  
1.9.0 < 2.0.0   // MAJOR 升级
1.0.0-beta < 1.0.0  // 预发布版本 < 正式版本
```

---

## API 设计

### Electron IPC 通信

#### 主进程 → 渲染进程

```javascript
// 通知有可用更新
mainWindow.webContents.send('update-available', {
  version: '1.1.0',
  releaseDate: '2025-11-01',
  releaseNotes: '## 新功能\n...',
  size: 125829120,
  isMandatory: false
});

// 更新下载进度
mainWindow.webContents.send('update-download-progress', {
  bytesPerSecond: 1048576,      // 1MB/s
  percent: 45.5,                 // 45.5%
  transferred: 57344000,         // 已下载字节
  total: 125829120              // 总字节
});

// 更新下载完成
mainWindow.webContents.send('update-downloaded', {
  version: '1.1.0',
  downloadTime: 120              // 下载耗时（秒）
});

// 更新错误
mainWindow.webContents.send('update-error', {
  message: '下载失败，网络连接中断',
  code: 'ERR_NETWORK'
});
```

#### 渲染进程 → 主进程

```javascript
// 手动检查更新
ipcRenderer.invoke('check-for-updates');

// 开始下载更新
ipcRenderer.invoke('download-update');

// 立即安装更新
ipcRenderer.invoke('quit-and-install');

// 跳过当前版本
ipcRenderer.invoke('skip-version', { version: '1.1.0' });

// 获取更新设置
ipcRenderer.invoke('get-update-settings');

// 更新设置
ipcRenderer.invoke('update-settings', {
  autoCheck: true,
  autoDownload: false,
  channel: 'stable'  // 'stable' | 'beta'
});
```

### 后端辅助 API (可选)

#### GET /api/v1/update/check
检查是否有可用更新（可实现灰度发布）

**请求:**
```json
{
  "current_version": "1.0.0",
  "platform": "win32",
  "arch": "x64",
  "user_id": "anonymous-or-user-id"
}
```

**响应:**
```json
{
  "has_update": true,
  "latest_version": "1.1.0",
  "download_url": "https://github.com/.../VidFlow-1.1.0.exe",
  "release_notes": "## 新功能\n...",
  "release_date": "2025-11-01T00:00:00Z",
  "file_size": 125829120,
  "is_mandatory": false,
  "minimum_version": "1.0.0",
  "rollout_percentage": 50  // 灰度发布比例
}
```

#### POST /api/v1/update/stats
记录更新统计

**请求:**
```json
{
  "from_version": "1.0.0",
  "to_version": "1.1.0",
  "status": "success",  // 'success' | 'failed' | 'skipped'
  "download_time": 120,
  "error_message": null
}
```

---

## 前端界面设计

### 1. 更新通知 Toast

**位置:** 应用右上角  
**样式:** 带图标的卡片式通知

```
┌──────────────────────────────────────────┐
│  🎉  VidFlow 1.1.0 可用                  │
├──────────────────────────────────────────┤
│  • 新增自动更新功能                       │
│  • 优化下载性能                          │
│  • 修复若干已知问题                       │
│                                           │
│  大小: 120 MB                            │
│                                           │
│  [查看详情]  [稍后提醒]  [立即更新]      │
└──────────────────────────────────────────┘
```

### 2. 更新详情弹窗

**触发:** 点击"查看详情"  
**内容:** 完整的变更日志

```
┌─────────────────────────────────────────────────┐
│  VidFlow 1.1.0 更新                             │
├─────────────────────────────────────────────────┤
│                                                  │
│  发布日期: 2025-11-01                           │
│  文件大小: 120 MB                               │
│                                                  │
│  ┌─────────────────────────────────────────┐  │
│  │ ## ✨ 新功能                             │  │
│  │ - 自动更新功能                          │  │
│  │ - GPU 加速支持                          │  │
│  │                                         │  │
│  │ ## 🔧 改进                              │  │
│  │ - 优化下载速度 30%                      │  │
│  │ - 减少内存占用                          │  │
│  │                                         │  │
│  │ ## 🐛 修复                              │  │
│  │ - 修复字幕同步问题                      │  │
│  │ - 修复偶发的崩溃问题                    │  │
│  └─────────────────────────────────────────┘  │
│                                                  │
│           [取消]  [稍后提醒]  [立即更新]        │
└─────────────────────────────────────────────────┘
```

### 3. 下载进度窗口

**类型:** Modal 弹窗  
**可操作:** 最小化到托盘

```
┌─────────────────────────────────────────────────┐
│  正在下载更新                                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  VidFlow 1.1.0                                  │
│                                                  │
│  ████████████░░░░░░░░░░░  45%                 │
│                                                  │
│  54 MB / 120 MB                                 │
│  速度: 1.2 MB/s  剩余时间: 约 1 分钟           │
│                                                  │
│              [暂停]  [取消]  [后台下载]         │
└─────────────────────────────────────────────────┘
```

### 4. 准备安装提示

**触发:** 下载完成

```
┌─────────────────────────────────────────────────┐
│  ✓ 更新已准备就绪                               │
├─────────────────────────────────────────────────┤
│                                                  │
│  VidFlow 1.1.0 已下载完成                       │
│                                                  │
│  点击"重启并更新"立即安装，或在下次启动时       │
│  自动安装更新。                                 │
│                                                  │
│              [稍后重启]  [重启并更新]           │
└─────────────────────────────────────────────────┘
```

### 5. 设置页面 - 更新选项

```
┌─────────────────────────────────────────────────┐
│  更新设置                                        │
├─────────────────────────────────────────────────┤
│                                                  │
│  [✓] 自动检查更新                               │
│      每次启动时检查新版本                       │
│                                                  │
│  [✓] 自动下载更新                               │
│      在后台自动下载，安装前会提示               │
│                                                  │
│  更新渠道:                                       │
│  ◉ 稳定版 (推荐)                                │
│  ○ 测试版 (抢先体验新功能)                      │
│                                                  │
│  当前版本: 1.0.0                                │
│                                                  │
│              [检查更新]  [查看更新历史]         │
└─────────────────────────────────────────────────┘
```

---

## 安全考虑

### 1. 传输安全

#### HTTPS 强制
```javascript
// 所有更新请求必须使用 HTTPS
autoUpdater.setFeedURL({
  provider: 'github',
  protocol: 'https',  // 强制使用 HTTPS
  owner: 'your-username',
  repo: 'vidflow-desktop'
});
```

#### 证书验证
- 验证服务器 SSL 证书
- 防止中间人攻击
- 拒绝自签名证书（生产环境）

### 2. 文件完整性验证

#### SHA-512 校验
```javascript
// electron-updater 自动验证
// latest.yml 中包含文件哈希
files:
  - url: VidFlow-1.1.0.exe
    sha512: 3a4f1c2e8b9d...  // 自动验证
```

#### 数字签名
```javascript
// Windows 代码签名
"win": {
  "certificateFile": "certificate.pfx",
  "certificatePassword": "process.env.CERTIFICATE_PASSWORD",
  "signingHashAlgorithms": ["sha256"],
  "sign": "./sign.js"  // 自定义签名脚本
}
```

### 3. 权限控制

#### UAC 提升
```javascript
// NSIS 安装程序配置
"nsis": {
  "oneClick": false,
  "perMachine": true,      // 为所有用户安装
  "allowElevation": true,  // 允许权限提升
  "runAfterFinish": true
}
```

#### 最小权限原则
- 下载过程不需要管理员权限
- 仅安装时请求 UAC
- 临时文件存储在用户目录

### 4. 防止降级攻击

```javascript
// 版本验证逻辑
function isNewerVersion(current, latest) {
  const currentParts = current.split('.').map(Number);
  const latestParts = latest.split('.').map(Number);
  
  // 确保不会降级到旧版本
  for (let i = 0; i < 3; i++) {
    if (latestParts[i] > currentParts[i]) return true;
    if (latestParts[i] < currentParts[i]) return false;
  }
  return false;
}
```

### 5. 回滚机制

#### 备份当前版本
```javascript
// 安装前备份关键文件
const backupDir = path.join(app.getPath('userData'), 'backup', currentVersion);
await fs.copy(appPath, backupDir);
```

#### 故障检测
```javascript
// 启动时检查版本
if (isFirstRunAfterUpdate()) {
  recordUpdateSuccess();
} else {
  // 连续启动失败 3 次，触发回滚
  if (getFailedStartCount() >= 3) {
    triggerRollback();
  }
}
```

---

## 测试方案

### 1. 单元测试

#### 版本对比测试
```javascript
describe('Version Comparison', () => {
  test('should detect newer version', () => {
    expect(isNewerVersion('1.0.0', '1.1.0')).toBe(true);
    expect(isNewerVersion('1.1.0', '1.0.0')).toBe(false);
    expect(isNewerVersion('1.0.0', '1.0.0')).toBe(false);
  });
  
  test('should handle pre-release versions', () => {
    expect(isNewerVersion('1.0.0-beta', '1.0.0')).toBe(true);
    expect(isNewerVersion('1.0.0-beta.1', '1.0.0-beta.2')).toBe(true);
  });
});
```

#### 配置管理测试
```javascript
describe('Update Settings', () => {
  test('should save and load settings', async () => {
    await saveUpdateSettings({ autoCheck: true });
    const settings = await loadUpdateSettings();
    expect(settings.autoCheck).toBe(true);
  });
  
  test('should handle skipped versions', async () => {
    await skipVersion('1.1.0');
    const skipped = await getSkippedVersions();
    expect(skipped).toContain('1.1.0');
  });
});
```

### 2. 集成测试

#### 更新流程测试
```javascript
describe('Update Flow Integration', () => {
  test('should complete full update cycle', async () => {
    // 1. 检查更新
    const updateInfo = await checkForUpdates();
    expect(updateInfo.hasUpdate).toBe(true);
    
    // 2. 下载更新
    const download = await downloadUpdate();
    expect(download.status).toBe('completed');
    
    // 3. 验证文件
    const verified = await verifyUpdate();
    expect(verified).toBe(true);
    
    // 4. 准备安装
    const prepared = await prepareInstallation();
    expect(prepared).toBe(true);
  });
  
  test('should handle download interruption', async () => {
    const download = downloadUpdate();
    await delay(1000);
    
    // 模拟网络中断
    simulateNetworkError();
    
    // 应该能够恢复下载
    const resumed = await resumeDownload();
    expect(resumed.status).toBe('completed');
  });
});
```

### 3. 端到端测试

#### 使用 Spectron / Playwright

```javascript
describe('Update UI Flow', () => {
  let app;
  
  beforeEach(async () => {
    app = await startApp();
  });
  
  test('should show update notification', async () => {
    // 触发更新检查
    await app.client.click('#check-update-btn');
    
    // 等待通知出现
    await app.client.waitForVisible('.update-notification', 5000);
    
    // 验证通知内容
    const text = await app.client.getText('.update-notification');
    expect(text).toContain('1.1.0');
  });
  
  test('should download and show progress', async () => {
    await app.client.click('.update-now-btn');
    
    // 验证进度窗口
    await app.client.waitForVisible('.download-progress', 2000);
    
    // 等待下载完成
    await app.client.waitForVisible('.download-complete', 60000);
  });
});
```

### 4. 手动测试清单

#### 功能测试
- [ ] 启动时自动检查更新
- [ ] 手动检查更新按钮
- [ ] 更新通知正确显示
- [ ] 变更日志格式正确
- [ ] 下载进度实时更新
- [ ] 暂停和恢复下载
- [ ] 取消下载
- [ ] 安装后版本号更新
- [ ] 跳过版本功能
- [ ] 设置项持久化

#### 边界情况测试
- [ ] 无网络连接时的处理
- [ ] 下载过程中断网
- [ ] 磁盘空间不足
- [ ] 下载文件损坏
- [ ] 签名验证失败
- [ ] 权限不足无法安装
- [ ] 已经是最新版本
- [ ] 并发检查更新

#### 性能测试
- [ ] 大文件下载（>500MB）
- [ ] 低速网络（<100KB/s）
- [ ] 多次连续更新
- [ ] 内存泄漏检查

---

## 部署流程

### 1. 版本发布流程

```
开发完成
   │
   ▼
更新版本号
   │
   ├─ package.json: "version": "1.1.0"
   ├─ CHANGELOG.md: 添加变更日志
   └─ Git Tag: v1.1.0
   │
   ▼
运行构建脚本
   │
   ├─ npm run build
   └─ 生成安装包和 latest.yml
   │
   ▼
代码签名
   │
   └─ 使用证书签名 .exe 文件
   │
   ▼
上传到发布平台
   │
   ├─ GitHub Releases
   ├─ latest.yml
   └─ VidFlow-1.1.0-win-x64.exe
   │
   ▼
发布 Release
   │
   └─ 标记为正式版本或预发布
   │
   ▼
通知用户
   │
   ├─ 自动更新推送
   └─ 社交媒体公告
```

### 2. GitHub Actions 自动化

#### .github/workflows/release.yml
```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: windows-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          npm install
          cd backend && pip install -r requirements.txt
          
      - name: Build application
        run: npm run build
        
      - name: Sign executable
        env:
          CERTIFICATE_PASSWORD: ${{ secrets.CERTIFICATE_PASSWORD }}
        run: |
          # 签名脚本
          
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            dist-output/VidFlow-*.exe
            dist-output/latest.yml
          body_path: CHANGELOG.md
          draft: false
          prerelease: ${{ contains(github.ref, 'beta') }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 3. 灰度发布策略

#### 阶段 1: 内部测试 (10%)
- 发布测试版本
- 内部团队使用
- 收集崩溃报告
- **持续时间:** 3-5 天

#### 阶段 2: Beta 测试 (25%)
- 发布 Beta 版本
- 邀请部分用户参与
- 监控关键指标
- **持续时间:** 1 周

#### 阶段 3: 分阶段推送 (50%)
- 发布正式版本
- 随机推送给 50% 用户
- 监控崩溃率和用户反馈
- **持续时间:** 3 天

#### 阶段 4: 全量发布 (100%)
- 推送给所有用户
- 持续监控
- 快速响应问题

### 4. 版本号管理

#### 分支策略
```
main (稳定版)
  │
  ├─ release/1.1.x (发布分支)
  │   └─ hotfix/1.1.1 (紧急修复)
  │
  └─ develop (开发分支)
      └─ feature/auto-update (功能分支)
```

#### 版本命名规则
- **Major**: 重大架构变更、不兼容更新
- **Minor**: 新功能、重要改进
- **Patch**: Bug 修复、小改进
- **Pre-release**: beta.1, rc.1 等

---

## 回滚策略

### 1. 自动回滚

#### 触发条件
- 连续启动失败 ≥ 3 次
- 崩溃率 > 10%（首小时）
- 关键功能失效

#### 回滚流程
```javascript
// 启动时检查
app.on('ready', async () => {
  const updateStatus = getLastUpdateStatus();
  
  if (updateStatus.failed) {
    const failCount = incrementFailCount();
    
    if (failCount >= 3) {
      // 触发回滚
      await rollbackToPreviousVersion();
      
      // 通知用户
      showRollbackNotification();
      
      // 上报问题
      reportUpdateFailure({
        fromVersion: updateStatus.oldVersion,
        toVersion: updateStatus.newVersion,
        failCount: failCount
      });
    }
  } else {
    // 更新成功，重置计数
    resetFailCount();
    markUpdateSuccessful();
  }
});
```

### 2. 手动回滚

#### 用户触发
```
设置 > 关于 > 版本历史
   │
   ▼
显示最近 3 个版本
   │
   ├─ v1.2.0 (当前)
   ├─ v1.1.0
   └─ v1.0.0
   │
   ▼
选择回滚版本
   │
   ▼
下载旧版本安装包
   │
   ▼
安装旧版本
```

### 3. 服务端回滚

#### 紧急下架
```javascript
// 修改 latest.yml
version: 1.0.0  // 回退到旧版本
files:
  - url: VidFlow-1.0.0-win-x64.exe
    sha512: previous_hash
```

#### 黑名单机制
```json
// 添加黑名单配置
{
  "blacklist": {
    "versions": ["1.1.0"],
    "reason": "Critical bug in download module",
    "recommendation": "1.0.0"
  }
}
```

### 4. 数据兼容性

#### 向后兼容
- 新版本必须能读取旧版本数据
- 数据库迁移要可逆
- 配置文件版本标记

#### 数据备份
```javascript
// 更新前备份用户数据
async function backupUserData() {
  const userDataPath = app.getPath('userData');
  const backupPath = path.join(userDataPath, 'backup', Date.now().toString());
  
  await fs.copy(
    path.join(userDataPath, 'database.db'),
    path.join(backupPath, 'database.db')
  );
  
  await fs.copy(
    path.join(userDataPath, 'config.json'),
    path.join(backupPath, 'config.json')
  );
}
```

---

## 监控和分析

### 1. 关键指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 更新成功率 | 安装成功的用户比例 | > 98% |
| 采用率 | 更新到最新版本的用户比例 | > 80% (30天) |
| 下载速度 | 平均下载速度 | > 500 KB/s |
| 安装失败率 | 安装失败的比例 | < 2% |
| 回滚率 | 需要回滚的更新比例 | < 1% |
| 跳过率 | 用户主动跳过更新的比例 | < 15% |

### 2. 日志记录

#### 更新日志示例
```json
{
  "timestamp": "2025-11-01T10:30:00Z",
  "event": "update_started",
  "user_id": "anonymous-abc123",
  "from_version": "1.0.0",
  "to_version": "1.1.0",
  "platform": "win32",
  "arch": "x64",
  "auto_triggered": true
}

{
  "timestamp": "2025-11-01T10:32:30Z",
  "event": "update_downloaded",
  "version": "1.1.0",
  "size": 125829120,
  "duration_seconds": 150,
  "average_speed_kbps": 838.86
}

{
  "timestamp": "2025-11-01T10:33:00Z",
  "event": "update_completed",
  "version": "1.1.0",
  "total_duration_seconds": 180,
  "status": "success"
}
```

### 3. 错误追踪

#### 常见错误码
| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| `ERR_NETWORK` | 网络连接失败 | 提示用户检查网络，支持重试 |
| `ERR_CHECKSUM` | 文件校验失败 | 重新下载 |
| `ERR_SIGNATURE` | 签名验证失败 | 拒绝安装，报告问题 |
| `ERR_DISK_SPACE` | 磁盘空间不足 | 提示用户清理空间 |
| `ERR_PERMISSION` | 权限不足 | 提示以管理员运行 |

---

## 常见问题 (FAQ)

### Q1: 用户可以关闭自动更新吗？
**A:** 是的，用户可以在设置中关闭自动检查和自动下载，但建议保持开启以获得最新功能和安全补丁。

### Q2: 更新会删除用户数据吗？
**A:** 不会。更新只替换应用程序文件，用户数据（下载历史、设置等）保存在单独的目录中。

### Q3: 如何处理企业用户的更新需求？
**A:** 企业用户可以：
- 禁用自动更新
- 使用组策略控制
- 自建更新服务器
- 批量部署指定版本

### Q4: 更新失败怎么办？
**A:** 系统会自动重试，如果连续失败会提示手动下载。同时保留当前版本继续使用。

### Q5: 是否支持增量更新？
**A:** electron-updater 支持增量更新，但需要额外配置。建议先实现完整更新，后续根据文件大小决定是否启用。

---

## 时间和资源估算

### 开发阶段

| 阶段 | 工作内容 | 预计时间 | 优先级 |
|------|----------|----------|--------|
| **阶段 1: 基础功能** | | | |
| 1.1 | 集成 electron-updater | 2 天 | P0 |
| 1.2 | 实现检查更新逻辑 | 1 天 | P0 |
| 1.3 | 下载和安装流程 | 2 天 | P0 |
| 1.4 | 前端更新 UI | 2 天 | P0 |
| **阶段 2: 完善功能** | | | |
| 2.1 | 更新设置页面 | 1 天 | P1 |
| 2.2 | 断点续传支持 | 1 天 | P1 |
| 2.3 | 错误处理和重试 | 1 天 | P1 |
| 2.4 | 版本跳过功能 | 0.5 天 | P1 |
| **阶段 3: 安全和稳定** | | | |
| 3.1 | 代码签名配置 | 1 天 | P0 |
| 3.2 | 回滚机制 | 2 天 | P1 |
| 3.3 | 数据备份恢复 | 1 天 | P1 |
| 3.4 | 灰度发布支持 | 1 天 | P2 |
| **阶段 4: 测试和文档** | | | |
| 4.1 | 单元测试 | 2 天 | P0 |
| 4.2 | 集成测试 | 2 天 | P0 |
| 4.3 | 用户文档 | 1 天 | P1 |
| 4.4 | 监控和日志 | 1 天 | P1 |

**总计:** 约 22 个工作日（4-5 周）

### 资源需求

- **开发人员:** 1-2 名全职开发
- **测试人员:** 1 名兼职测试
- **设计师:** 0.5 名（UI/UX 设计）
- **运维支持:** 0.5 名（发布配置）

### 基础设施

- **GitHub Releases:** 免费（或 GitHub Pro）
- **代码签名证书:** ~$300-500/年
- **CDN 加速:** 可选，~$50/月
- **监控服务:** 可选，~$30/月

---

## 总结

本文档详细规划了 VidFlow Desktop 的软件更新功能开发，包括：

### ✅ 核心优势
1. **技术成熟:** 基于 electron-updater，稳定可靠
2. **用户友好:** 简洁的 UI，清晰的流程
3. **安全可靠:** 多重验证，支持回滚
4. **灵活可控:** 支持多种更新策略

### 📦 可交付成果
- ✅ 完整的自动更新系统
- ✅ 友好的用户界面
- ✅ 完善的测试覆盖
- ✅ 详细的开发文档

### 🎯 下一步行动
1. **评审本文档**，确认技术方案
2. **准备开发环境**，配置证书和发布平台
3. **启动开发**，按阶段实施
4. **Beta 测试**，收集反馈迭代

---

**文档维护:**
- **作者:** VidFlow 开发团队
- **审核:** 待定
- **版本历史:**
  - v1.0 (2025-11-01): 初始版本

**参考资料:**
- [electron-updater 文档](https://www.electron.build/auto-update)
- [Electron 代码签名指南](https://www.electron.build/code-signing)
- [Semantic Versioning 2.0](https://semver.org/)

