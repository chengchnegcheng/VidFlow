# VidFlow Desktop 1.0.0

> 视频下载器桌面版，采用 **Electron + Python FastAPI** 架构

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/vidflow/desktop)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## ✨ 特性

- 🎥 **多平台支持**：YouTube、Bilibili、抖音、小红书、TikTok等主流平台
- 🍪 **自动Cookie获取**：内置Selenium，一键自动登录并提取Cookie（安全便捷）
- 🤖 **AI字幕生成**：基于 faster-whisper 的高质量语音识别（可选安装）
- 🌍 **字幕翻译**：支持多语言字幕翻译
- ⚡ **高性能**：Python 后端 + Electron 前端，性能优异
- 🖥️ **跨平台**：支持 Windows、macOS、Linux
- 📦 **体积优化**：基础包仅 500 MB（AI 功能可选）

## 🆕 1.0.0 新特性

### 🍪 自动Cookie获取功能 ⭐ NEW!
- ✅ **半自动化提取**：一键启动浏览器，用户登录后自动提取Cookie
- ✅ **完全安全**：密码只在真实浏览器中输入，不经过应用
- ✅ **7大平台支持**：小红书、抖音、TikTok、B站、YouTube、Twitter、Instagram
- ✅ **内置Selenium**：安装时自动包含，开箱即用
- ✅ **UI界面配置**：无需手动操作文件，全程图形化操作

详见 [自动Cookie获取指南](Docs/AUTO_COOKIE_GUIDE.md)

### AI 工具按需安装
- ✅ **基础包体积减少 75%**：从 2 GB 降到 500 MB
- ✅ **AI 功能可选安装**：在应用内一键安装/卸载
- ✅ **支持 CPU/GPU 版本**：根据硬件灵活选择
- ✅ **统一工具管理**：FFmpeg、yt-dlp、AI 工具集中管理

详见 [AI 工具指南](Docs/AI_TOOLS_GUIDE.md)

## 🏗️ 技术栈

### 前端
- **Electron** 27 - 桌面应用框架
- **React** 18 - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 快速构建工具

### 后端
- **Python** 3.8+ - 编程语言
- **FastAPI** - 现代化 Web 框架
- **yt-dlp** - 视频下载引擎
- **Selenium** - 自动Cookie提取（内置）
- **faster-whisper** - AI 字幕生成（可选）
- **SQLite** - 数据持久化

## 🚀 快速开始

### 方式 1：使用自动化脚本（推荐）⭐

```bash
# Windows
scripts\SETUP.bat      # 一键安装所有依赖
scripts\START.bat      # 启动开发服务器

# 打包
scripts\PREPARE_PACKAGE.bat   # 准备打包
scripts\BUILD_AUTO.bat        # 自动打包
```

### 方式 2：手动安装

#### 环境要求

- Node.js >= 18.0.0
- Python 3.8-3.11（推荐 3.11）
- ⚠️ **不支持 Python 3.12+**（AI 功能限制）

#### 安装步骤

```bash
# 1. 安装 Node 依赖
npm install
cd frontend && npm install && cd ..

# 2. 设置 Python 环境
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cd ..

# 3. 启动开发
npm run dev
```

## 📦 打包应用

### 一键打包（推荐）

```bash
scripts\BUILD_AUTO.bat
```

输出：`dist-output/VidFlow Desktop Setup 1.0.0.exe` (~500 MB)

### 手动打包

```bash
# 1. 清理
scripts\CLEAN.bat

# 2. 构建前端
cd frontend && npm run build && cd ..

# 3. 打包后端
cd backend
venv\Scripts\python -m PyInstaller backend.spec --clean
cd ..

# 4. 打包 Electron
npm run build:electron
```

详见 [打包准备清单](PACKAGE_READY.md)

## 📁 项目结构

```
VidFlow-Desktop/
├── electron/          # Electron 主进程
│   ├── main.js       # 主进程入口
│   └── preload.js    # 预加载脚本
├── frontend/         # React 前端
│   ├── src/
│   └── package.json
├── backend/          # Python 后端
│   ├── src/
│   │   ├── main.py
│   │   └── api/
│   └── requirements.txt
├── scripts/          # 构建脚本
└── package.json
```

## 🔧 开发命令

```bash
npm run dev              # 启动开发模式
npm run frontend:dev     # 仅启动前端
npm run backend:dev      # 仅启动后端
npm run electron:dev     # 仅启动 Electron
npm run build            # 构建整个应用
npm run package          # 打包应用
```

## 📚 文档

### API 文档
后端启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 项目文档
- [快速开始](QUICK_START.md) - 一页式快速参考
- [打包准备](PACKAGE_READY.md) - 打包前检查清单
- [AI 工具指南](Docs/AI_TOOLS_GUIDE.md) - AI 功能完整说明
- [前端实施](Docs/FRONTEND_IMPLEMENTATION.md) - 前端开发文档
- [变更日志](Docs/CHANGELOG_AI_TOOLS.md) - 1.0.0 详细变更

## 🐛 故障排除

### Python 后端无法启动

1. 确认已创建并激活虚拟环境
2. 确认已安装所有依赖：`pip install -r requirements.txt`
3. 检查端口 8000 是否被占用

### Electron 无法连接后端

1. 确认 Python 后端已启动
2. 检查控制台是否有错误信息
3. 确认防火墙允许 localhost:8000

### FFmpeg 相关错误

确保系统已安装 FFmpeg：
- Windows: 从 https://ffmpeg.org/ 下载并添加到 PATH
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

## 📄 许可证

MIT License

## 🙏 致谢

- [Electron](https://www.electronjs.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [faster-whisper](https://github.com/guillaumekln/faster-whisper)

---

**VidFlow Team** © 2026
