# 打包体积优化指南

当前打包大小：**1.98 GB** 😱  
优化目标：**500-800 MB** ✅

---

## 📊 大小分析

### 主要占用空间（估算）

| 组件 | 大小 | 必需性 |
|------|------|--------|
| **PyTorch (CUDA)** | ~800-1000 MB | ⚠️ 可优化 |
| **ctranslate2 (CUDA)** | ~200-300 MB | ⚠️ 可优化 |
| **Electron + Chromium** | ~200-300 MB | ✅ 必需 |
| **Python 运行时** | ~100-150 MB | ✅ 必需 |
| **其他依赖** | ~100-200 MB | ✅ 必需 |

**核心问题**：torch 和 ctranslate2 的 CUDA 版本太大！

---

## 🚀 优化方案

### 方案 1：使用 CPU 版本（推荐）⭐
**减少 ~600 MB**

```bash
# 1. 卸载 CUDA 版本的 torch
pip uninstall torch torchvision torchaudio

# 2. 安装 CPU 版本
pip install torch torchvision torchaudio

# 3. 重新打包
scripts\BUILD_AUTO.bat
```

**优点**：
- ✅ 大幅减小体积（约减少 600 MB）
- ✅ 兼容性更好（不需要 CUDA）
- ✅ 适合大多数用户

**缺点**：
- ❌ AI 字幕生成速度稍慢（CPU 模式）
- ❌ 有 GPU 的用户无法利用加速

**适用场景**：
- 面向普通用户发布
- 追求体积最小化

---

### 方案 2：分离 AI 功能
**减少 ~800 MB（基础包）**

创建两个版本：
- **基础版**（不含 AI）- ~500 MB
- **完整版**（含 AI）- ~1.5 GB

**实施步骤**：

#### 1. 修改 backend.spec，排除 AI 依赖

```python
# backend.spec
excludes=[
    'torch',
    'torchvision', 
    'torchaudio',
    'faster_whisper',
    'ctranslate2',
    'onnxruntime',
]
```

#### 2. AI 功能改为可选下载

```python
# 在应用设置中添加"下载 AI 功能"选项
# 首次使用字幕功能时自动下载依赖
```

**优点**：
- ✅ 基础包极小，下载快
- ✅ 用户按需下载 AI 功能
- ✅ 灵活性高

**缺点**：
- ❌ 需要修改应用逻辑
- ❌ 首次使用 AI 需要联网

---

### 方案 3：UPX 压缩（效果有限）
**减少 ~100-200 MB**

```bash
# 1. 下载 UPX
# https://github.com/upx/upx/releases

# 2. 放到 PATH 或与脚本同目录

# 3. 在 backend.spec 中启用（已启用）
upx=True  # 已经开启
```

**优点**：
- ✅ 无需改代码
- ✅ 压缩运行时文件

**缺点**：
- ❌ 效果有限（10-20% 压缩率）
- ❌ 首次启动稍慢

---

### 方案 4：按需打包（最灵活）⭐
**提供多个构建配置**

创建三个打包版本：
1. **Lite 版**（无 AI）- ~500 MB
2. **Standard 版**（CPU AI）- ~800 MB  
3. **Pro 版**（CUDA AI）- ~1.5 GB

**实施方式**：

```bash
# 创建不同的 requirements 配置
backend/
├── requirements.txt          # 基础依赖
├── requirements-ai-cpu.txt   # CPU 版 AI
├── requirements-ai-cuda.txt  # CUDA 版 AI
```

---

## 📝 推荐实施计划

### 阶段 1：快速优化（立即可用）

```bash
# 切换到 CPU 版本 torch
cd backend
venv\Scripts\activate
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio

# 重新打包
cd ..
scripts\BUILD_AUTO.bat
```

**预期结果**：1.98 GB → **~700-900 MB**

---

### 阶段 2：进一步优化（需要修改代码）

1. **AI 功能改为可选安装**
   - 修改后端检测逻辑
   - 添加"下载 AI 组件"功能
   
2. **创建多个打包配置**
   - BUILD_LITE.bat（无 AI）
   - BUILD_STANDARD.bat（CPU AI）
   - BUILD_PRO.bat（CUDA AI）

**预期结果**：
- Lite 版：**~500 MB**
- Standard 版：**~800 MB**
- Pro 版：**~1.5 GB**

---

## ⚠️ 其他可能的问题

### 检查是否误打包了不必要的文件

```bash
# 检查 electron-builder 配置
# 确保排除了这些：
"files": [
  "!**/node_modules/**/*",     # 排除 node_modules
  "!**/*.map",                  # 排除 source maps
  "!**/cache/**",               # 排除缓存
  "!**/__pycache__/**",         # 排除 Python 缓存
  "!**/venv/**"                 # 排除虚拟环境
]
```

### 检查是否包含了 Whisper 模型文件

```bash
# 模型应该在首次使用时下载，不应该打包
# 检查 backend/dist 是否包含 .bin 或 .pt 文件
```

---

## 🎯 推荐方案总结

### 对于大多数用户（推荐）
👉 **使用方案 1：CPU 版本**
- 体积：~700-900 MB
- 兼容性：最好
- 性能：AI 速度可接受

### 对于追求极致（进阶）
👉 **使用方案 2：分离 AI 功能**
- 基础包：~500 MB
- AI 功能：按需下载
- 灵活性：最高

### 对于专业用户（可选）
👉 **使用方案 4：多版本发布**
- Lite / Standard / Pro 三个版本
- 用户根据需求选择

---

## 📦 立即行动

### 快速优化（5 分钟）

```bash
# 1. 切换到 CPU 版本
cd backend
venv\Scripts\activate
pip uninstall torch -y
pip install torch torchvision torchaudio

# 2. 重新打包
cd ..
scripts\BUILD_AUTO.bat
```

### 验证结果

```bash
# 检查新打包文件大小
dir dist-output\*.exe
```

预期从 **1.98 GB** 降到 **~800 MB** 左右！

---

## 💡 参考数据

| PyTorch 版本 | 大小 | 性能 |
|-------------|------|------|
| CPU only | ~200 MB | 中等 |
| CUDA 11.8 | ~800 MB | 快 |
| CUDA 12.x | ~1000 MB | 最快 |

**结论**：除非明确需要 GPU 加速，否则使用 CPU 版本。
