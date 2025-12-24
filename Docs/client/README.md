# VidFlow Update Client

客户端自定义更新器 - 用于 Electron 应用

## 特性

- ✅ 完全自定义的更新流程
- ✅ 支持灰度发布控制
- ✅ 文件完整性验证（SHA-512）
- ✅ 断点续传支持
- ✅ 详细的进度反馈
- ✅ 优雅的 React UI 组件
- ✅ 更新统计上报

## 目录结构

```
client/
├── electron/
│   ├── updater-custom.js          # 自定义更新器核心
│   └── updater-integration.js     # Electron 集成示例
└── react/
    ├── CustomUpdateNotification.tsx  # React 更新通知组件
    └── types.d.ts                    # TypeScript 类型定义
```

## 使用方法

### 1. Electron 主进程集成

在你的 Electron 主进程文件中：

```javascript
const { app, BrowserWindow } = require('electron');
const { initUpdater, registerIpcHandlers } = require('./electron/updater-integration');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  // 初始化更新器
  initUpdater(mainWindow);
}

app.whenReady().then(() => {
  // 注册 IPC 处理器
  registerIpcHandlers();
  
  createWindow();
});
```

### 2. Preload 脚本

创建 `preload.js` 文件：

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  // 监听更新事件
  on: (channel, callback) => {
    const validChannels = [
      'update-checking',
      'update-available',
      'update-not-available',
      'download-progress',
      'update-downloaded',
      'update-error'
    ];
    
    if (validChannels.includes(channel)) {
      ipcRenderer.on(channel, (event, ...args) => callback(...args));
    }
  },
  
  // 调用主进程方法
  invoke: (channel, ...args) => {
    const validChannels = [
      'custom-update-check',
      'custom-update-download',
      'custom-update-install'
    ];
    
    if (validChannels.includes(channel)) {
      return ipcRenderer.invoke(channel, ...args);
    }
  }
});
```

### 3. React 组件集成

在你的 React 应用中：

```tsx
import React from 'react';
import { CustomUpdateNotification } from './components/CustomUpdateNotification';
import { Toaster } from 'sonner';

function App() {
  return (
    <div className="app">
      {/* 你的应用内容 */}
      <YourAppContent />
      
      {/* 更新通知组件 */}
      <CustomUpdateNotification />
      
      {/* Toast 通知（使用 sonner） */}
      <Toaster position="top-right" />
    </div>
  );
}

export default App;
```

### 4. 依赖安装

#### Electron 依赖

```bash
npm install axios
```

#### React 依赖

```bash
npm install sonner
```

## API 参考

### CustomUpdater 类

#### 构造函数

```javascript
const updater = new CustomUpdater({
  updateServerUrl: 'http://shcrystal.top:8321',  // 更新服务器地址
  autoCheck: true,                                 // 自动检查更新
  autoDownload: false                              // 自动下载更新
});
```

#### 方法

**checkForUpdates()**

检查更新

```javascript
await updater.checkForUpdates();
```

**downloadUpdate()**

下载更新

```javascript
await updater.downloadUpdate();
```

**quitAndInstall()**

退出并安装

```javascript
await updater.quitAndInstall();
```

#### 事件

- `checking-for-update` - 开始检查更新
- `update-available` - 发现新版本
- `update-not-available` - 已是最新版本
- `download-progress` - 下载进度
- `update-downloaded` - 下载完成
- `error` - 发生错误

### React 组件 Props

`CustomUpdateNotification` 组件不需要 props，它会自动监听 Electron 更新事件。

## 配置服务器地址

修改 `electron/updater-integration.js` 中的服务器地址：

```javascript
const updater = new CustomUpdater({
  updateServerUrl: 'http://your-server.com:8321'
});
```

## 自定义 UI

你可以修改 `react/CustomUpdateNotification.tsx` 来定制更新通知的外观和行为。

### 示例：修改按钮颜色

```tsx
<button
  onClick={handleDownload}
  className="flex-1 px-4 py-2 text-white bg-purple-600 rounded-md hover:bg-purple-700"
>
  立即下载
</button>
```

### 示例：添加更多信息

```tsx
<div className="mb-4">
  <h3 className="text-sm font-medium mb-2">系统要求</h3>
  <p className="text-sm text-gray-600">
    Windows 10 或更高版本
  </p>
</div>
```

## 测试更新流程

### 1. 手动触发更新检查

在你的应用中添加一个按钮：

```tsx
<button onClick={() => window.electron.invoke('custom-update-check')}>
  检查更新
</button>
```

### 2. 模拟更新场景

在开发时，你可以修改 `package.json` 中的版本号来测试不同的更新场景：

```json
{
  "version": "0.9.0"  // 降低版本号来测试更新检测
}
```

## 故障排查

### 更新检查失败

1. 检查服务器地址是否正确
2. 检查网络连接
3. 查看控制台错误日志

### 下载失败

1. 检查磁盘空间
2. 检查文件权限
3. 尝试重新下载

### 安装失败

1. 关闭杀毒软件
2. 以管理员身份运行
3. 检查安装程序是否损坏

## 最佳实践

### 1. 延迟检查更新

不要在应用启动时立即检查更新，建议延迟 5-10 秒：

```javascript
setTimeout(() => {
  updater.checkForUpdates();
}, 5000);
```

### 2. 错误处理

总是捕获更新错误：

```javascript
try {
  await updater.checkForUpdates();
} catch (error) {
  console.error('Update check failed:', error);
  // 显示用户友好的错误消息
}
```

### 3. 用户体验

- 不要强制用户立即更新（除非是安全更新）
- 提供"稍后提醒"选项
- 显示详细的更新说明
- 显示下载进度和速度

## 安全建议

1. **文件完整性验证** - 更新器会自动验证 SHA-512 哈希
2. **HTTPS** - 生产环境使用 HTTPS 传输
3. **代码签名** - 为安装程序添加代码签名
4. **权限最小化** - 只请求必要的系统权限

## 示例项目

完整的集成示例请参考 VidFlow Desktop 项目。

## 许可证

Copyright © 2025 VidFlow Team
