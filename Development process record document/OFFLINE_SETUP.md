# 🔌 VidFlow 离线安装指南

## 为什么需要离线安装？

开发团队或企业环境中，可能需要：
- ✅ 无网络环境下安装
- ✅ 多台机器快速部署
- ✅ 节省下载时间
- ✅ 版本一致性

---

## 📦 离线安装方案

### 方案概述

**可以离线集成的组件：**

| 组件 | 类型 | 集成方式 | 体积 | 难度 |
|------|------|---------|------|------|
| **FFmpeg** | 二进制文件 | 直接放置 `backend/tools/bin/` | ~100MB | ⭐ 简单 |
| **yt-dlp** | 二进制文件 | 直接放置 `backend/tools/bin/` | ~10MB | ⭐ 简单 |
| **faster-whisper** | Python 包 | 缓存 wheel 文件 | ~500MB | ⭐⭐ 中等 |
| **Node 依赖** | npm 包 | npm cache | ~200MB | ⭐⭐⭐ 复杂 |

---

## 🎯 完整离线部署流程

### 第一步：准备环境（联网机器）

#### 1. 克隆项目并首次安装
```bash
git clone <repo-url>
cd VidFlow-Desktop
scripts\SETUP.bat
```

#### 2. 缓存 Python 依赖
```bash
cd scripts
CACHE_WHEELS.bat
```

这会下载所有 Python 依赖到 `cache/wheels/` 目录（~500MB）

#### 3. 下载二进制工具
```bash
# 手动下载到 backend/tools/bin/
# FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases
# yt-dlp: https://github.com/yt-dlp/yt-dlp/releases
```

#### 4. 打包整个项目
```bash
# 方式 A: 提交到 Git（如果仓库允许大文件）
git add cache/wheels backend/tools/bin
git commit -m "Add offline dependencies"

# 方式 B: 打包成压缩包
# 压缩整个 VidFlow-Desktop/ 目录
```

---

### 第二步：离线部署（无网络机器）

#### 1. 解压项目到目标机器

#### 2. 安装 Node.js 和 Python
- Node.js 18+ (使用离线安装包)
- Python 3.11 (使用离线安装包)

#### 3. 运行离线安装
```bash
cd VidFlow-Desktop/scripts
SETUP.bat
```

**SETUP.bat 会自动检测：**
```
[INFO] Installing faster-whisper...
[INFO] Found cached wheels, installing offline... ✅
(使用 cache/wheels/ 离线安装，无需联网)
```

---

## 📁 目录结构

### 完整的离线包结构：

```
VidFlow-Desktop/
├── backend/
│   ├── tools/
│   │   └── bin/
│   │       ├── ffmpeg.exe        ← 预下载 (100MB)
│   │       └── yt-dlp.exe        ← 预下载 (10MB)
│   ├── requirements-minimal.txt
│   └── requirements-optional.txt
│
├── cache/
│   └── wheels/                   ← Python 离线包 (500MB)
│       ├── faster_whisper-1.2.0-py3-none-any.whl
│       ├── torch-2.0.0+cu118-cp311-win_amd64.whl
│       └── ... (其他依赖)
│
├── frontend/
│   └── node_modules/              ← npm 依赖 (可选缓存)
│
└── scripts/
    ├── SETUP.bat                  ← 支持离线安装
    └── CACHE_WHEELS.bat           ← 缓存工具
```

---

## ⚡ 快速部署命令

### 准备离线包（联网环境）
```bash
# 1. 首次完整安装
scripts\SETUP.bat

# 2. 缓存 Python 依赖
scripts\CACHE_WHEELS.bat

# 3. 下载工具
# 手动下载 ffmpeg.exe 和 yt-dlp.exe 到 backend\tools\bin\

# 4. 打包项目
# 压缩整个目录或提交到 Git
```

### 部署到离线机器
```bash
# 1. 解压项目

# 2. 确保已安装 Node.js 18+ 和 Python 3.11

# 3. 运行安装
scripts\SETUP.bat

# 4. 启动应用
scripts\START.bat
```

---

## 🔍 技术细节

### Python 离线安装原理

**在线安装：**
```bash
pip install faster-whisper
# 从 PyPI 下载 (~500MB)
```

**离线安装：**
```bash
# CACHE_WHEELS.bat 执行：
pip download -r requirements-optional.txt -d cache/wheels

# SETUP.bat 检测到缓存后执行：
pip install --no-index --find-links=cache/wheels -r requirements-optional.txt
# 从本地 cache/wheels/ 安装 (无需联网)
```

### 为什么不直接打包 venv？

| 方式 | 优点 | 缺点 |
|------|------|------|
| **打包 venv** | 最简单 | ❌ 体积巨大 (1-2GB)<br>❌ 平台相关<br>❌ 不灵活 |
| **缓存 wheels** | ✅ 体积小 (~500MB)<br>✅ 跨平台<br>✅ 灵活 | 需要额外步骤 |

---

## 📊 体积对比

| 方式 | 总大小 | 说明 |
|------|--------|------|
| **最小化** | ~50MB | 不包含工具，首次使用下载 |
| **集成二进制工具** | ~150MB | 包含 FFmpeg + yt-dlp |
| **完全离线包** | ~650MB | 包含所有依赖 + 工具 |
| **打包 venv（不推荐）** | ~2GB | 包含整个虚拟环境 |

---

## ✅ 验证离线安装

运行 SETUP.bat 后，检查输出：

### 成功标志：
```
[INFO] Installing faster-whisper...
[INFO] Found cached wheels, installing offline... ✅
(安装过程中不会有网络请求)
[OK] faster-whisper installed successfully
```

### 验证工具：
```
backend\tools\bin\ffmpeg.exe -version     ✅
backend\tools\bin\yt-dlp.exe --version    ✅
```

---

## 🎉 总结

**是的，faster-whisper 可以像 FFmpeg/yt-dlp 一样预先集成！**

**区别在于：**
- **FFmpeg/yt-dlp** - 直接放文件 (.exe)
- **faster-whisper** - 缓存安装包 (.whl)

**现在的流程：**
1. ✅ 运行 `CACHE_WHEELS.bat` 下载依赖
2. ✅ 将 `cache/wheels/` 目录包含在分发包中
3. ✅ `SETUP.bat` 自动检测并离线安装
4. ✅ 完全离线部署

**优势：**
- ✅ 完全离线安装
- ✅ 快速部署（秒级安装）
- ✅ 版本一致性
- ✅ 节省带宽
