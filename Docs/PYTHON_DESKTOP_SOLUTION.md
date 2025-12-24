# VidFlow Python 桌面版技术方案

## 📋 方案概述

VidFlow 桌面版采用 **Electron + Python FastAPI** 混合架构，结合了现代Web技术的灵活性和Python生态的强大功能。

### 核心理念

- **前端**：Electron + React + TypeScript - 提供现代化的桌面UI体验
- **后端**：Python + FastAPI - 利用丰富的视频处理和AI生态
- **通信**：REST API + WebSocket - 前后端解耦，易于维护
- **打包**：一键打包成独立的桌面应用

---

## 🏗️ 整体架构

```
┌─────────────────────────────────────────┐
│         VidFlow Desktop App              │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │   Electron Main Process            │ │
│  │   • 窗口管理                        │ │
│  │   • 启动 Python 后端               │ │
│  │   • 系统托盘和菜单                  │ │
│  └────────────────────────────────────┘ │
│              │                           │
│              ▼                           │
│  ┌────────────────────────────────────┐ │
│  │   React UI (Renderer Process)     │ │
│  │   • 下载管理界面                   │ │
│  │   • 字幕处理界面                   │ │
│  │   • 系统监控界面                   │ │
│  └────────────────────────────────────┘ │
│              │                           │
│      REST API / WebSocket               │
│              ▼                           │
│  ┌────────────────────────────────────┐ │
│  │   Python FastAPI Backend          │ │
│  │   • yt-dlp 视频下载               │ │
│  │   • faster-whisper AI字幕         │ │
│  │   • SQLite 数据持久化             │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## 📂 项目结构

```
VidFlow-Desktop/
├── electron/                    # Electron 主进程
│   ├── main.js                 # 主进程入口
│   ├── preload.js              # 预加载脚本
│   └── python-backend.js       # Python后端管理
│
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── components/         # UI组件
│   │   ├── hooks/             # 自定义Hooks
│   │   ├── utils/             # 工具函数
│   │   └── App.tsx            # 主应用
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                     # Python 后端
│   ├── src/
│   │   ├── main.py            # FastAPI入口
│   │   ├── api/               # API路由
│   │   ├── core/              # 核心业务
│   │   │   └── downloaders/   # 各平台下载器
│   │   ├── models/            # 数据模型
│   │   └── utils/             # 工具函数
│   ├── requirements.txt
│   └── .env
│
├── scripts/                     # 构建脚本
│   ├── build-backend.js        # 打包Python
│   ├── package.js              # 打包整个应用
│   └── dev.js                  # 开发模式
│
├── resources/                   # 应用资源
│   └── icons/                  # 应用图标
│
├── package.json                # 项目配置
└── electron-builder.json       # 打包配置
```

---

## 🔧 技术栈

### 前端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| Electron | ^27.0.0 | 桌面应用框架 |
| React | ^18.2.0 | UI框架 |
| TypeScript | ^5.0.0 | 类型安全 |
| Vite | ^5.0.0 | 构建工具 |
| Tailwind CSS | ^3.3.0 | CSS框架 |
| Axios | ^1.6.0 | HTTP客户端 |
| Zustand | ^4.4.0 | 状态管理 |

### 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.8+ | 编程语言 |
| FastAPI | ^0.104.0 | Web框架 |
| Uvicorn | ^0.24.0 | ASGI服务器 |
| SQLAlchemy | ^2.0.0 | ORM框架 |
| yt-dlp | ^2023.10.0 | 视频下载 |
| faster-whisper | ^0.9.0 | AI字幕 |
| websockets | ^12.0 | 实时通信 |

---

## 🚀 快速开始

### 环境要求

- Node.js >= 18.0.0
- Python >= 3.8
- FFmpeg（系统安装）

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd VidFlow-Desktop

# 2. 安装前端依赖
npm install

# 3. 安装Python依赖
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 4. 启动开发模式
npm run dev
```

### 开发命令

```bash
# 开发模式（自动启动Python后端 + Electron）
npm run dev

# 仅启动Python后端
npm run backend:dev

# 仅启动Electron
npm run electron:dev

# 构建Python后端
npm run build:backend

# 打包完整应用
npm run build
```

---

## 🔌 前后端通信

### API通信示例

**前端调用**：
```typescript
// frontend/src/utils/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
});

export const downloadVideo = async (url: string) => {
  const response = await api.post('/api/v1/downloads/start', { url });
  return response.data;
};
```

**后端路由**：
```python
# backend/src/api/downloads.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/downloads")

class DownloadRequest(BaseModel):
    url: str

@router.post("/start")
async def start_download(request: DownloadRequest):
    # 实现下载逻辑
    return {"status": "success", "task_id": "123"}
```

### WebSocket实时更新

**后端**：
```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # 发送进度更新
    await websocket.send_json({
        "type": "download_progress",
        "progress": 50
    })
```

**前端**：
```typescript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress:', data.progress);
};
```

---

## 📦 打包和分发

### 打包流程

```bash
# 1. 打包Python后端（使用PyInstaller）
npm run build:backend
# 输出: backend/dist/main.exe

# 2. 打包Electron应用（包含前端和后端）
npm run build
# 输出: release/VidFlow-Setup.exe (Windows)
#      release/VidFlow.dmg (macOS)
#      release/VidFlow.AppImage (Linux)
```

### Electron Builder配置

```json
{
  "appId": "com.vidflow.desktop",
  "productName": "VidFlow",
  "directories": {
    "output": "release"
  },
  "files": [
    "electron/**/*",
    "frontend/dist/**/*",
    "backend/dist/**/*"
  ],
  "win": {
    "target": ["nsis"],
    "icon": "resources/icons/icon.ico"
  },
  "mac": {
    "target": ["dmg"],
    "icon": "resources/icons/icon.icns"
  }
}
```

---

## 🔐 安全性

### 进程隔离

```javascript
// electron/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
});
```

### 内容安全策略

```html
<meta 
  http-equiv="Content-Security-Policy" 
  content="default-src 'self'; 
           connect-src 'self' http://localhost:8000;"
>
```

---

## 🎯 性能优化

### Python后端优化

```python
# 异步I/O
import asyncio

async def download_video(url: str):
    # 异步下载避免阻塞
    await asyncio.sleep(1)

# 数据库连接池
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "sqlite+aiosqlite:///./data/database.db",
    pool_size=10
)

# 缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def get_config(key: str):
    return config[key]
```

### Electron优化

```javascript
// 延迟加载窗口
let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    show: false,  // 初始隐藏
  });
  
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();  // 准备好后显示
  });
}
```

---

## 🔄 与Tauri方案对比

| 特性 | Electron + Python | Tauri + Rust |
|------|-------------------|--------------|
| 学习曲线 | ✅ 低 | ❌ 高 |
| 开发速度 | ✅ 快 | ⚠️ 中 |
| Python生态 | ✅ 原生 | ❌ 需集成 |
| 包体积 | ❌ 大(~100MB) | ✅ 小(~20MB) |
| 内存占用 | ⚠️ 中(80-150MB) | ✅ 低(30-80MB) |
| 性能 | ⚠️ 良好 | ✅ 优秀 |
| 社区生态 | ✅ 巨大 | ⚠️ 成长中 |

---

## 📚 参考资源

### 官方文档
- [Electron 文档](https://www.electronjs.org/docs)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [faster-whisper](https://github.com/guillaumekln/faster-whisper)

### 示例项目
- [Electron + Python 示例](https://github.com/fyears/electron-python-example)
- [FastAPI 最佳实践](https://github.com/zhanymkanov/fastapi-best-practices)

---

**文档版本**: v1.0  
**最后更新**: 2024-10-23  
**维护者**: VidFlow Team
