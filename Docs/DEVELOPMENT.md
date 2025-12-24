# VidFlow (全能视频下载器) 开发文档

## 项目概述

VidFlow (All Video Downloader) 是一个基于 Python + FastAPI + React 技术栈开发的全能视频下载工具，支持多种视频平台的内容下载、AI字幕生成和字幕翻译功能。项目采用现代化的Web应用架构，提供了灵活的扩展性和强大的功能。

### 主要特性

- 🌐 **现代Web应用**：基于FastAPI的高性能异步Web服务
- ⚡ **高性能异步**：基于asyncio的异步处理，支持高并发
- 🐍 **Python生态**：充分利用Python丰富的AI和数据处理库
- 🔌 **RESTful API**：标准化的API接口，易于集成和扩展
- 🎬 **多平台下载**：支持YouTube、Bilibili、抖音等主流平台
- 🔊 **AI智能字幕**：基于faster-whisper的高质量语音识别
- 🌍 **字幕翻译**：支持多语言字幕翻译功能
- 💾 **数据持久化**：SQLite数据库存储任务和历史记录
- 🔄 **实时通信**：WebSocket支持实时进度更新

## 技术栈

### 后端技术
- **Python 3.8+**：后端核心语言
- **FastAPI**：现代化的Web框架，支持异步和自动API文档
- **SQLAlchemy**：强大的ORM框架
- **SQLite**：轻量级数据库
- **yt-dlp**：视频下载引擎
- **faster-whisper**：高性能AI语音识别模型
- **FFmpeg**：媒体文件处理
- **asyncio**：Python异步编程支持
- **websockets**：实时双向通信

### 前端技术
- **React 18**：前端 UI 框架
- **TypeScript**：类型安全的前端开发
- **Ant Design 5**：企业级UI组件库
- **Vite**：快速的前端构建工具
- **Zustand**：轻量级状态管理

### 主要依赖库

#### 后端依赖 (requirements.txt)
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
pydantic>=2.0.0
python-multipart>=0.0.6
yt-dlp>=2023.10.0
faster-whisper>=0.9.0
websockets>=12.0
python-dotenv>=1.0.0
aiofiles>=23.0.0
```

#### 前端依赖 (package.json)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "antd": "^5.0.0",
    "axios": "^1.6.0",
    "zustand": "^4.4.0",
    "react-router-dom": "^6.8.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "vite": "^4.4.0",
    "typescript": "^5.0.0"
  }
}

## 项目架构

### 项目结构
```
VidFlow/
├── backend/                   # Python 后端
│   ├── src/                   # 源代码
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 应用入口
│   │   ├── api/               # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── downloads.py   # 下载相关API
│   │   │   ├── subtitles.py   # 字幕相关API
│   │   │   ├── system.py      # 系统相关API
│   │   │   └── websocket.py   # WebSocket路由
│   │   ├── core/              # 核心业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── downloader.py  # 下载引擎
│   │   │   ├── downloaders/   # 分平台下载器
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_downloader.py
│   │   │   │   ├── youtube_downloader.py
│   │   │   │   ├── bilibili_downloader.py
│   │   │   │   └── ...
│   │   │   ├── subtitles.py   # 字幕处理器
│   │   │   ├── media.py       # 媒体文件处理
│   │   │   └── config.py      # 配置管理
│   │   ├── models/            # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── database.py    # 数据库配置
│   │   │   ├── download.py    # 下载任务模型
│   │   │   ├── subtitle.py    # 字幕模型
│   │   │   └── task.py        # 任务模型
│   │   └── utils/             # 工具函数
│   │       ├── __init__.py
│   │       ├── file.py        # 文件工具
│   │       ├── logger.py      # 日志工具
│   │       └── validators.py  # 验证工具
│   ├── data/                  # 数据存储
│   │   ├── downloads/         # 下载文件
│   │   └── database.db        # SQLite数据库
│   ├── requirements.txt       # Python依赖
│   └── .env                   # 环境变量
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── main.tsx           # 应用入口
│   │   ├── App.tsx            # 主应用组件
│   │   ├── components/        # React 组件
│   │   │   ├── DownloadManager.tsx
│   │   │   ├── SubtitleProcessor.tsx
│   │   │   ├── TaskManager.tsx
│   │   │   └── SystemMonitor.tsx
│   │   ├── hooks/             # React Hooks
│   │   │   ├── useApi.ts          # API调用Hook
│   │   │   ├── useDownload.ts     # 下载 Hook
│   │   │   ├── useSubtitle.ts     # 字幕 Hook
│   │   │   └── useWebSocket.ts    # WebSocket Hook
│   │   ├── utils/             # 前端工具
│   │   │   ├── api.ts             # API封装
│   │   │   ├── format.ts          # 格式化工具
│   │   │   └── constants.ts       # 常量定义
│   │   ├── types/             # TypeScript 类型
│   │   │   ├── api.ts             # API类型定义
│   │   │   ├── download.ts        # 下载类型
│   │   │   └── subtitle.ts        # 字幕类型
│   │   └── styles/            # 样式文件
│   ├── public/                # 静态资源
│   ├── package.json           # 前端依赖
│   ├── vite.config.ts         # Vite 配置
│   └── tsconfig.json          # TypeScript 配置
├── docs/                      # 文档
│   ├── API.md                 # API 文档
│   ├── DEPLOYMENT.md          # 部署指南
│   └── DEVELOPMENT.md         # 开发指南
├── docker-compose.yml         # Docker配置
├── .gitignore
└── README.md                  # 项目说明
```

### 核心模块设计

#### 1. 下载器模块 (`core/downloader.py`)

**主要类：**
- `Downloader`：主要下载器类
- `DownloadOptions`：下载选项配置
- `DownloadProgress`：下载进度跟踪
- `VideoInfo`：视频信息容器

**核心功能：**
- 多平台视频下载
- 下载进度监控
- Cookie管理
- 质量选择和格式转换
- 并发下载支持

**关键方法：**
```python
def download_video(self, url: str, options: DownloadOptions) -> Optional[str]
def get_video_info(self, url: str) -> Optional[VideoInfo]
def cancel_download(self)
```

#### 2. 字幕处理模块 (`core/subtitles.py`)

**主要类：**
- `SubtitleProcessor`：字幕处理核心
- `SubtitleEntry`：字幕条目

**核心功能：**
- AI字幕生成（基于faster-whisper）
- 字幕翻译（在线/离线）
- SRT文件解析和生成
- 字幕时间轴处理

**关键方法：**
```python
def generate_subtitles_from_audio(self, audio_path: str, language: str) -> Optional[str]
def translate_srt(self, srt_path: str, target_lang: str) -> Optional[str]
def parse_srt_file(self, srt_path: str) -> List[SubtitleEntry]
```

#### 3. 媒体处理模块 (`core/media_processor.py`)

**核心功能：**
- 音频提取
- 字幕烧录
- 格式转换
- FFmpeg集成

#### 4. 平台适配模块 (`core/platform_handler.py`)

**核心功能：**
- 平台特定处理逻辑
- Cookie获取和管理
- 登录状态维护

#### 5. UI模块 (`ui/`)

**模块化设计：**
- `MainWindow`：主窗口框架
- 各功能标签页独立实现
- 主题管理系统
- 响应式布局

### 配置管理

项目支持两种配置格式：
- `config.json`：主要配置文件
- `config.ini`：备用配置格式

**主要配置项：**
```json
{
    "version": "1.0.5",
    "download_directory": "下载目录路径",
    "whisper_model_size": "模型大小(tiny/small/medium/large)",
    "theme": "主题(light/dark/blue)",
    "max_concurrency": "最大并发数",
    "use_proxy": "是否使用代理",
    "auto_download_subs": "自动下载字幕"
}
```

## Python 开发指南

### 环境要求

- **Python**: 3.8 或更高版本
- **Node.js**: 18.0 或更高版本  
- **FFmpeg**: 最新稳定版本
- **pip**: Python 包管理器

### 环境搭建

#### 1. 安装 Python
```bash
# Windows
winget install Python.Python.3.11

# macOS
brew install python@3.11

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

#### 2. 安装 FFmpeg
```bash
# Windows (使用 Chocolatey)
choco install ffmpeg

# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt install ffmpeg
```

#### 3. 初始化项目
```bash
# 克隆项目
git clone https://github.com/your-repo/VidFlow.git
cd VidFlow

# 设置后端环境
cd backend
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install
```

### 开发模式启动

#### 1. 启动后端服务器
```bash
cd backend
# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 启动FastAPI服务器（开发模式）
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 或使用Python直接运行
python src/main.py
```

#### 2. 启动前端开发服务器
```bash
cd frontend
npm run dev
# Vite 会自动选择可用端口，并将结果写入项目根的 frontend_port.json
# Electron 主进程、npm run dev 以及 START/STOP 脚本会读取该文件，确保端口动态可用
```

#### 3. 热重载特性
- **后端**: FastAPI `--reload` 模式，Python代码修改自动重启
- **前端**: Vite HMR（热模块替换），React组件即时更新
- **数据库**: SQLAlchemy自动同步模型变更

### 生产构建

#### 后端部署
```bash
cd backend
# 使用生产级ASGI服务器
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

# 或使用Gunicorn + Uvicorn workers
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

#### 前端构建
```bash
cd frontend
npm run build
# 构建产物在 dist/ 目录
```

### Python 开发最佳实践

#### 1. 前后端通信设计

**前端 API 调用：**
```typescript
// frontend/src/utils/api.ts
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// 调用下载API
export const startDownload = async (url: string, quality: string) => {
  const response = await api.post('/api/v1/downloads/start', {
    url,
    quality,
    output_path: './downloads'
  });
  return response.data;
};

// 获取视频信息
export const getVideoInfo = async (url: string) => {
  const response = await api.post('/api/v1/downloads/info', { url });
  return response.data;
};
```

**WebSocket 实时通信：**
```typescript
// 前端WebSocket连接
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'download_progress') {
    console.log('下载进度:', data.progress);
  }
};
```

**后端 FastAPI 路由：**
```python
# backend/src/api/downloads.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..core.downloader import Downloader

router = APIRouter(prefix="/api/v1/downloads")

class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    output_path: str = "./downloads"

@router.post("/start")
async def start_download(request: DownloadRequest):
    try:
        downloader = Downloader()
        result = await downloader.download_video(
            url=request.url,
            quality=request.quality,
            output_path=request.output_path
        )
        return {"status": "success", "task_id": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2. 错误处理策略

**自定义异常类：**
```python
# backend/src/utils/exceptions.py
from fastapi import HTTPException
from typing import Any, Optional

class VidFlowException(Exception):
    """VidFlow基础异常类"""
    def __init__(self, message: str, code: str = "GENERAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class DownloadError(VidFlowException):
    """下载相关错误"""
    def __init__(self, message: str):
        super().__init__(message, "DOWNLOAD_ERROR")

class SubtitleError(VidFlowException):
    """字幕相关错误"""
    def __init__(self, message: str):
        super().__init__(message, "SUBTITLE_ERROR")

class DatabaseError(VidFlowException):
    """数据库相关错误"""
    def __init__(self, message: str):
        super().__init__(message, "DATABASE_ERROR")
```

**全局异常处理器：**
```python
# backend/src/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .utils.exceptions import VidFlowException

app = FastAPI()

@app.exception_handler(VidFlowException)
async def vidflow_exception_handler(request: Request, exc: VidFlowException):
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.code,
            "message": exc.message
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": str(exc)
        }
    )
```

#### 3. 异步编程模式

**异步任务处理：**
```python
# backend/src/core/downloader.py
import asyncio
from typing import Optional, Callable
import aiofiles

class Downloader:
    async def download_video(
        self,
        url: str,
        quality: str,
        output_path: str,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """异步下载视频"""
        # 创建异步任务
        task = asyncio.create_task(
            self._download_task(url, quality, output_path, progress_callback)
        )
        
        # 等待任务完成
        result = await task
        return result
    
    async def _download_task(
        self,
        url: str,
        quality: str,
        output_path: str,
        progress_callback: Optional[Callable]
    ) -> str:
        """内部下载任务逻辑"""
        # 模拟长时间运行的任务
        for i in range(100):
            await asyncio.sleep(0.1)
            if progress_callback:
                await progress_callback(i + 1)
        
        return f"{output_path}/video.mp4"
```

**并发任务管理：**
```python
# 并发运行多个任务
async def download_multiple_videos(urls: list[str]):
    tasks = [download_video(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

#### 4. 安全性考虑

**路径验证：**
```python
# backend/src/utils/validators.py
import os
from pathlib import Path
from typing import Union

def validate_file_path(path: Union[str, Path], base_dir: str = "./data") -> Path:
    """
    验证文件路径安全性
    
    Args:
        path: 要验证的路径
        base_dir: 允许的基本目录
        
    Raises:
        ValueError: 路径不安全
    """
    path = Path(path).resolve()
    base = Path(base_dir).resolve()
    
    # 防止路径遍历政击
    try:
        path.relative_to(base)
    except ValueError:
        raise ValueError(f"不安全的路径: {path}")
    
    return path

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除不安全字符"""
    # 移除或替换不安全字符
    unsafe_chars = '<>:"\/|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename
```

**API认证和授权：**
```python
# backend/src/api/auth.py
from fastapi import Depends, HTTPException, Header
from typing import Optional

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """验证API密钥"""
    if not x_api_key:
        return  # 开发模式可选
    
    # 在生产环境中验证API密钥
    valid_keys = ["your-secret-api-key"]
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="无效的API密钥")

# 使用
@router.post("/downloads/start", dependencies=[Depends(verify_api_key)])
async def start_download(request: DownloadRequest):
    pass
```

#### 5. 性能优化

**数据库连接池：**
```python
# backend/src/models/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    "sqlite+aiosqlite:///./data/database.db",
    echo=False,
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 最大溢出连接
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

**缓存策略：**
```python
from functools import lru_cache
from cachetools import TTLCache
import asyncio

# 内存缓存
cache = TTLCache(maxsize=100, ttl=300)  # 5分钟缓存

@lru_cache(maxsize=128)
def get_platform_info(platform: str):
    """缓存平台信息"""
    return platform_config[platform]
```

**异步优化：**
```python
# 使用异步IO操作
import aiofiles

async def read_large_file(file_path: str):
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()
    return content
```

### 添加新功能

#### 1. 新增 FastAPI 路由

**创建新的API路由：**
```python
# backend/src/api/new_feature.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/v1/feature", tags=["new_feature"])

class FeatureRequest(BaseModel):
    input: str
    options: List[str] = []

class FeatureResponse(BaseModel):
    status: str
    result: str
    task_id: Optional[str] = None

@router.post("/process", response_model=FeatureResponse)
async def process_feature(request: FeatureRequest):
    """处理新功能请求"""
    try:
        # 实现业务逻辑
        result = await process_new_feature(
            request.input,
            request.options
        )
        return FeatureResponse(
            status="success",
            result=result,
            task_id="task_123"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_feature_status(task_id: str):
    """获取任务状态"""
    # 查询任务状态
    return {"task_id": task_id, "status": "completed"}
```

**在主应用中注册API路由：**
```python
# backend/src/main.py
from fastapi import FastAPI
from .api import downloads, subtitles, system, new_feature

app = FastAPI(title="VidFlow API")

# 注册路由
app.include_router(downloads.router)
app.include_router(subtitles.router)
app.include_router(system.router)
app.include_router(new_feature.router)  # 新功能
```

#### 2. 新增 React 组件

**创建新组件：**

```typescript
// frontend/src/components/NewFeature.tsx
import React, { useState } from 'react';
import { Button, Input, message } from 'antd';
import axios from 'axios';

interface NewFeatureProps {
  onComplete?: (result: string) => void;
}

export const NewFeature: React.FC<NewFeatureProps> = ({ onComplete }) => {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/api/v1/feature/process', {
        input,
        options: ['option1', 'option2']
      });
      
      message.success('处理成功');
      onComplete?.(response.data.result);
    } catch (error: any) {
      message.error(`处理失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="输入内容"
        style={{ marginBottom: '10px' }}
      />
      <Button
        type="primary"
        loading={loading}
        onClick={handleSubmit}
      >
        处理
      </Button>
    </div>
  );
};
```

**在主应用中使用：**

```typescript
// frontend/src/App.tsx
import { NewFeature } from './components/NewFeature';

function App() {
  return (
    <div>
      {/* 其他组件 */}
      <NewFeature onComplete={(result) => console.log(result)} />
    </div>
  );
}
```

#### 3. 新增数据库模型

**定义SQLAlchemy模型：**

```python
# backend/src/models/new_model.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime
from typing import Optional

class NewModel(Base):
    __tablename__ = "new_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    @classmethod
    async def create(cls, session, name: str) -> "NewModel":
        """创建新记录"""
        new_record = cls(name=name, status="pending")
        session.add(new_record)
        await session.commit()
        await session.refresh(new_record)
        return new_record
    
    @classmethod
    async def find_by_id(cls, session, record_id: int) -> Optional["NewModel"]:
        """通过ID查找记录"""
        from sqlalchemy import select
        result = await session.execute(
            select(cls).where(cls.id == record_id)
        )
        return result.scalar_one_or_none()
```

**数据库迁移脚本：**

```python
# backend/src/models/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text

Base = declarative_base()

async def init_database():
    """初始化数据库表"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///./data/database.db",
        echo=True
    )
    
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建索引
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_new_models_status "
            "ON new_models(status)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_new_models_created_at "
            "ON new_models(created_at)"
        ))
```

### 调试和测试

#### 1. 开发者工具

**FastAPI 自动文档：**
```bash
# 访问自动生成的API文档
http://localhost:8000/docs  # Swagger UI
http://localhost:8000/redoc  # ReDoc
```

**前端调试：**
- 浏览器开发者工具 (F12)
- React DevTools 扩展
- Vite 热模块更新 (HMR)

#### 2. 日志系统

**Python 后端日志：**
```python
# backend/src/utils/logger.py
import logging
from pathlib import Path

def setup_logger(name: str = "vidflow"):
    """\u914d\u7f6e\u65e5\u5fd7\u7cfb\u7edf"""
    # 创建日志目录
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    
    # 配置日志格式
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "vidflow.log"),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(name)

# 使用示例
logger = setup_logger()
logger.info(f"下载开始: {url}")
logger.error(f"下载失败: {error}")
logger.debug(f"调试信息: {data}")
```

**前端日志：**
```typescript
// frontend/src/utils/logger.ts
export const logger = {
  debug: (message: string, ...args: any[]) => {
    if (import.meta.env.DEV) {
      console.debug(`[DEBUG] ${message}`, ...args);
    }
  },
  info: (message: string, ...args: any[]) => {
    console.info(`[INFO] ${message}`, ...args);
  },
  error: (message: string, error?: Error) => {
    console.error(`[ERROR] ${message}`, error);
  },
  warn: (message: string, ...args: any[]) => {
    console.warn(`[WARN] ${message}`, ...args);
  }
};
```

#### 3. 测试策略

**Python 单元测试：**
```python
# backend/tests/test_downloader.py
import pytest
from src.core.downloader import Downloader
from src.utils.validators import validate_file_path, sanitize_filename

@pytest.mark.asyncio
async def test_video_info_extraction():
    """测试视频信息提取"""
    downloader = Downloader()
    result = await downloader.get_video_info("https://test.com/video")
    
    assert result is not None
    assert result.get('title')
    assert result.get('duration') > 0

def test_url_validation():
    """测试URL验证"""
    from src.utils.validators import is_valid_url
    
    assert is_valid_url("https://youtube.com/watch?v=test")
    assert not is_valid_url("invalid-url")

def test_filename_sanitization():
    """测试文件名清理"""
    assert sanitize_filename("test<file>.mp4") == "test_file_.mp4"
    assert sanitize_filename("normal_file.mp4") == "normal_file.mp4"

# 运行测试： pytest tests/
```

**FastAPI 集成测试：**
```python
# backend/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_get_video_info():
    """测试获取视频信息API"""
    response = client.post(
        "/api/v1/downloads/info",
        json={"url": "https://test.com/video"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "title" in data

def test_start_download():
    """测试开始下载API"""
    response = client.post(
        "/api/v1/downloads/start",
        json={
            "url": "https://test.com/video",
            "quality": "best"
        }
    )
    assert response.status_code == 200
    assert response.json().get("status") == "success"
```

**前端测试：**
```typescript
// frontend/src/components/__tests__/DownloadManager.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DownloadManager } from '../DownloadManager';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

test('下载管理器渲染', () => {
  render(<DownloadManager />);
  
  const input = screen.getByPlaceholderText('输入视频链接');
  const button = screen.getByText('开始下载');
  
  expect(input).toBeInTheDocument();
  expect(button).toBeInTheDocument();
});

test('下载功能', async () => {
  // Mock axios
  mockedAxios.post.mockResolvedValue({
    data: { status: 'success', task_id: '123' }
  });
  
  render(<DownloadManager />);
  
  const input = screen.getByPlaceholderText('输入视频链接');
  const button = screen.getByText('开始下载');
  
  fireEvent.change(input, { target: { value: 'https://test.com/video' } });
  fireEvent.click(button);
  
  await waitFor(() => {
    expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/v1/downloads/start',
      expect.objectContaining({ url: 'https://test.com/video' })
    );
  });
});

// 运行测试： npm test
```

#### 4. 性能分析

**后端性能测试：**
```python
# backend/tests/test_performance.py
import pytest
import time
from src.core.downloader import Downloader

@pytest.mark.asyncio
async def test_download_performance():
    """测试下载性能"""
    downloader = Downloader()
    start_time = time.time()
    
    await downloader.download_video(
        url="https://test.com/video",
        quality="best",
        output_path="./downloads"
    )
    
    elapsed_time = time.time() - start_time
    assert elapsed_time < 60  # 应在60秒内完成

# 使用locust进行负载测试
from locust import HttpUser, task, between

class VidFlowUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def get_video_info(self):
        self.client.post("/api/v1/downloads/info", 
                        json={"url": "https://test.com/video"})
```

**前端构建分析：**
```bash
# 构建并分析包大小
cd frontend
npm run build
npm run preview

# 使用rollup-plugin-visualizer分析
npm install --save-dev rollup-plugin-visualizer
# 在vite.config.ts中添加插件
```

### 性能优化

#### 1. 下载性能
- 使用适当的并发数量
- 实现下载队列管理
- 支持断点续传

#### 2. AI模型优化
- 模型缓存机制
- 按需加载模型
- GPU加速支持

#### 3. 内存管理
- 及时释放大文件引用
- 流式处理大型媒体文件
- 垃圾回收优化

### 部署和分发

#### 1. Docker 部署 (推荐)

**Dockerfile：**
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml：**
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/data:/app/data
      - ./backend/logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

**启动：**
```bash
docker-compose up -d
```

#### 2. 传统部署

**使用Systemd服务 (Linux)：**
```ini
# /etc/systemd/system/vidflow.service
[Unit]
Description=VidFlow Backend Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/vidflow/backend
Environment="PATH=/opt/vidflow/backend/venv/bin"
ExecStart=/opt/vidflow/backend/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动服务：**
```bash
sudo systemctl enable vidflow
sudo systemctl start vidflow
sudo systemctl status vidflow
```

#### 3. Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /var/www/vidflow/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 4. 环境变量配置

```bash
# backend/.env
DATABASE_URL=sqlite:///./data/database.db
LOG_LEVEL=INFO
MAX_CONCURRENT_DOWNLOADS=3
DOWNLOAD_PATH=./data/downloads
WHISPER_MODEL_SIZE=base
```

#### 5. 依赖管理
```bash
# 生成依赖文件
pip freeze > requirements.txt

# 使用固定版本，避免依赖冲突
pip install -r requirements.txt

# 定期检查更新
pip list --outdated
```

#### 6. 发布流程
1. **版本管理**：更新 `__version__` 和 `CHANGELOG.md`
2. **测试**：运行全部测试套件
3. **构建**：构建前后端产物
4. **部署**：使用CI/CD自动部署
5. **监控**：检查服务状态和日志

## 故障排除

### 常见问题

#### 1. 模型下载失败
**现象：** faster-whisper模型下载超时
**解决方案：**
- 检查网络连接
- 配置代理设置
- 使用本地模型文件

#### 2. 视频下载失败
**现象：** 特定网站视频无法下载
**解决方案：**
- 更新yt-dlp版本
- 检查Cookie有效性
- 验证URL格式

#### 3. 字幕生成错误
**现象：** 音频转录失败
**解决方案：**
- 检查音频文件格式
- 调整模型大小
- 验证FFmpeg安装

#### 4. API连接问题
**现象：** 前端无法连接后端
**解决方案：**
- 检查后端服务是否启动
- 验证CORS配置
- 检查网络防火墙设置

### 调试技巧

1. **启用详细日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **使用开发者工具**
   - FastAPI `/docs` 自动API文档
   - Python Debugger (pdb, ipdb)
   - 浏览器DevTools进行网络调试

3. **性能分析**
   ```python
   import cProfile
   import pstats
   
   profiler = cProfile.Profile()
   profiler.enable()
   # 代码执行
   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(10)
   ```

4. **异步调试**
   ```python
   import asyncio
   
   # 启用asyncio调试模式
   asyncio.run(main(), debug=True)
   ```

## 贡献指南

### 代码规范

#### 1. Python代码风格
- 遵循PEP 8规范
- 使用类型提示
- 编写文档字符串

#### 2. 命名约定
- 类名：PascalCase
- 函数名：snake_case
- 常量：UPPER_CASE
- 私有方法：_private_method

#### 3. 注释规范
```python
def download_video(self, url: str, options: DownloadOptions) -> Optional[str]:
    """
    下载指定URL的视频
    
    Args:
        url: 视频URL
        options: 下载选项配置
        
    Returns:
        下载的文件路径，失败时返回None
        
    Raises:
        ValueError: 当URL格式无效时
        ConnectionError: 当网络连接失败时
    """
    pass
```

### 提交流程

1. **Fork项目**
2. **创建功能分支**
   ```bash
   git checkout -b feature/new-feature
   ```
3. **编写代码和测试**
4. **提交变更**
   ```bash
   git commit -m "feat: 添加新功能描述"
   ```
5. **推送分支**
   ```bash
   git push origin feature/new-feature
   ```
6. **创建Pull Request**

### 提交信息规范
```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
test: 测试相关
chore: 构建工具或辅助工具的变动
```

## 路线图

### 已完成功能 (v1.0.5)
- ✅ 基础视频下载功能
- ✅ AI字幕生成
- ✅ 字幕翻译
- ✅ 字幕烧录
- ✅ 主题系统
- ✅ 浏览器登录集成

### 计划功能

#### v1.1.0
- 🔄 批量下载管理
- 🔄 下载队列优化
- 🔄 更多视频平台支持
- 🔄 插件系统框架

#### v1.2.0
- 📋 视频播放器集成
- 📋 字幕编辑器
- 📋 下载历史管理
- 📋 云同步功能

#### v2.0.0
- 📋 Web版本开发
- 📋 移动端支持
- 📋 API服务提供
- 📋 企业版功能

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

- 项目地址：[GitHub Repository]
- 问题反馈：[Issues]
- 讨论交流：[Discussions]

---

**注意：** 本文档会随着项目发展持续更新，请关注最新版本。

**技术栈状态**: ✅ **Python + FastAPI 后端架构**

### 主要特性

- 支持多平台视频下载（YouTube、Bilibili、抖音等）
- AI字幕生成（基于Whisper）
- 字幕翻译功能
- 实时下载进度显示
- 任务管理和历史记录
- 系统监控和配置管理

## 技术栈

### 后端
- **框架**: FastAPI (Python)
- **数据库**: SQLite + SQLAlchemy ORM
- **下载核心**: yt-dlp
- **AI模型**: faster-whisper
- **异步任务**: asyncio
- **WebSocket**: 实时通信

### 前端
- **框架**: React 18 + TypeScript
- **UI组件**: Ant Design 5
- **构建工具**: Vite
- **状态管理**: React Hooks
- **WebSocket**: 实时更新

## 下载器架构

### 模块化设计

项目采用模块化的下载器架构，支持灵活扩展：

```
backend/src/core/downloaders/
├── __init__.py
├── base_downloader.py          # 基础下载器抽象类
├── downloader_factory.py       # 下载器工厂
├── youtube_downloader.py       # YouTube专用下载器
├── bilibili_downloader.py      # Bilibili专用下载器
├── douyin_downloader.py        # 抖音专用下载器
├── weixin_downloader.py        # 微信视频号下载器
├── xiaohongshu_downloader.py   # 小红书下载器
├── qq_downloader.py            # 腾讯视频下载器
├── youku_downloader.py         # 优酷下载器
├── iqiyi_downloader.py         # 爱奇艺下载器
└── generic_downloader.py       # 通用下载器（后备方案）
```

### 下载器特性

1. **智能平台检测**: 自动识别URL对应的平台
2. **专用优化**: 每个平台都有专门的下载器实现
3. **通用后备**: 对于未识别的平台使用通用下载器
4. **统一接口**: 所有下载器实现相同的接口
5. **向后兼容**: 保持与原有API的完全兼容

### 添加新平台支持

1. 创建新的下载器文件：
```python
# backend/src/core/downloaders/newplatform_downloader.py
from .base_downloader import BaseDownloader

class NewPlatformDownloader(BaseDownloader):
    """新平台下载器"""
    
    PLATFORM_NAME = "newplatform"
    SUPPORTED_DOMAINS = ["newplatform.com", "www.newplatform.com"]
    
    async def download(self, url: str, options: DownloadOptions, 
                      progress_callback=None, task_id: str = None) -> dict:
        # 实现下载逻辑
        pass
```

2. 在工厂中注册：
```python
# backend/src/core/downloaders/downloader_factory.py
from .newplatform_downloader import NewPlatformDownloader

# 添加到下载器列表
self._downloaders = [
    # ... 其他下载器
    NewPlatformDownloader(),
]
```

## 项目结构

```
VidFlow/
├── backend/                    # 后端代码
│   ├── src/                   # 源代码
│   │   ├── api/              # API路由
│   │   ├── core/             # 核心功能
│   │   │   ├── downloaders/  # 下载器模块
│   │   │   ├── downloader.py # 主下载器
│   │   │   └── ...
│   │   ├── models/           # 数据模型
│   │   └── utils/            # 工具函数
│   ├── data/                 # 数据存储
│   └── main.py              # 入口文件
├── frontend/                  # 前端代码
│   ├── src/
│   │   ├── components/       # React组件
│   │   ├── hooks/           # 自定义Hooks
│   │   └── App.tsx          # 主应用
│   └── package.json
└── docker-compose.yml        # Docker配置
```

## 前端更新说明

### 平台信息展示

前端已更新以充分利用后端的模块化下载器架构：

1. **下载页面**
   - 视频信息展示包含平台标识
   - 下载任务列表显示平台标签
   - 使用图标和颜色区分不同平台

2. **历史页面**
   - 任务列表显示平台信息
   - 支持按平台筛选历史记录
   - 平台标签可视化展示

3. **系统页面**
   - 支持平台列表使用标签展示
   - 直观显示所有支持的平台

### 平台标识配置

```typescript
const platformConfig = {
  youtube: { icon: <YoutubeOutlined />, color: 'red', name: 'YouTube' },
  bilibili: { icon: <PlayCircleOutlined />, color: 'pink', name: 'Bilibili' },
  douyin: { icon: <PlayCircleOutlined />, color: 'black', name: '抖音' },
  // ... 其他平台配置
};
```

## API接口

### 下载相关

- `POST /api/v1/downloads/info` - 获取视频信息
- `POST /api/v1/downloads/start` - 开始下载任务
- `GET /api/v1/downloads/tasks` - 获取任务列表
- `DELETE /api/v1/downloads/tasks/{task_id}` - 删除任务

### 系统相关

- `GET /api/v1/system/info` - 获取系统信息
- `GET /api/v1/system/settings` - 获取系统设置
- `PUT /api/v1/system/settings` - 更新系统设置

## 开发指南

### 环境准备

1. **后端环境**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **前端环境**
   ```bash
   cd frontend
   npm install
   ```

### 启动开发服务器

1. **启动后端**
   ```bash
   cd backend
   python main.py
   ```

2. **启动前端**
   ```bash
   cd frontend
   npm run dev
   ```

### 数据库迁移

项目使用SQLAlchemy自动管理数据库结构，首次运行会自动创建所需表。

### WebSocket通信

项目使用WebSocket实现实时进度更新：

```python
# 后端发送进度
await websocket_manager.send_message({
    "type": "download_progress",
    "task_id": task_id,
    "progress": progress,
    "title": title
})
```

```typescript
// 前端接收进度
const { lastMessage } = useWebSocket({
    url: 'ws://localhost:8000/ws',
    onMessage: (data) => {
        // 处理进度更新
    }
});
```

## 部署说明

### Docker部署

```bash
docker-compose up -d
```

### 手动部署

1. 配置环境变量
2. 安装依赖
3. 配置反向代理（nginx）
4. 启动服务

## 注意事项

1. **Cookie管理**: 某些平台需要登录Cookie才能下载高质量视频
2. **速率限制**: 避免频繁请求导致IP被封
3. **存储空间**: 确保有足够的磁盘空间存储下载文件
4. **性能优化**: AI字幕生成需要较高的CPU/GPU资源

---

## 🚀 VidFlow Tauri 版本优势总结

### 性能革命
- **启动速度**: 从 3-5 秒降低到 0.3-1 秒，**提升 10 倍**
- **内存占用**: 从 200-500MB 降低到 30-80MB，**减少 85%**
- **应用体积**: 从 100-300MB 降低到 8-25MB，**缩小 90%**
- **执行效率**: Rust 编译优化带来 **3-10 倍** 性能提升

### 安全可靠
- **内存安全**: Rust 所有权系统杜绝内存泄漏和悬挂指针
- **类型安全**: 编译时类型检查，运行时错误大幅减少
- **沙箱隔离**: Tauri 安全沙箱保护系统资源
- **权限控制**: 细粒度 API 权限管理

### 开发体验
- **现代工具链**: Cargo + npm 双工具链优势互补
- **热重载**: 前后端代码修改即时生效
- **类型提示**: Rust + TypeScript 全栈类型安全
- **丰富生态**: Rust 和 React 生态系统完美结合

### 部署便利
- **单文件分发**: 无需复杂的运行时环境
- **跨平台一致**: Windows/macOS/Linux 统一体验
- **自动更新**: 内置更新机制，支持增量更新
- **原生集成**: 深度系统集成，支持通知和系统托盘

### 面向未来
- **WebAssembly**: 未来可扩展到浏览器环境
- **移动端**: Tauri Mobile 即将支持移动平台
- **云原生**: 容器化部署和微服务架构
- **AI 集成**: Rust AI 生态快速发展

**VidFlow 选择 Tauri 不仅是技术升级，更是面向未来的战略选择。**

---

**注意：** 本文档会随着项目发展持续更新，请关注最新版本。

**Tauri 版本状态**: 🚀 **架构设计完成，开发就绪**
统一API架构：确保所有模块都有一致的记录管理接口