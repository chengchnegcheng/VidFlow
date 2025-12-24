# 构建脚本使用指南

VidFlow Desktop 提供了三个构建脚本，适用于不同场景：

---

## 🚀 脚本选择指南

### 推荐：BUILD_AUTO.bat（智能构建）⭐
**一键构建，自动选择最佳方式**

```bash
scripts\BUILD_AUTO.bat
```

**工作原理**：
- ✅ 自动检测依赖是否完整
- ✅ 依赖缺失 → 使用完整构建（BUILD_FULL.bat）
- ✅ 依赖完整 → 使用快速构建（BUILD.bat）
- ✅ 适合所有场景，新手友好

**适用场景**：
- 🟢 不确定环境状态时
- 🟢 首次构建
- 🟢 日常开发打包
- 🟢 依赖可能有问题时

---

### BUILD.bat（快速构建）
**适合已配置好环境的日常打包**

```bash
scripts\BUILD.bat
```

**特点**：
- ⚡ 速度最快
- ✅ 检查 FFmpeg/yt-dlp 工具
- ❌ 不安装依赖（需手动运行 SETUP.bat）

**流程**：
1. 检查工具（FFmpeg/yt-dlp）
2. 清理旧文件
3. 构建前端
4. 打包后端（PyInstaller）
5. 打包 Electron

**适用场景**：
- 🟢 已运行过 SETUP.bat
- 🟢 环境依赖完整
- 🟢 快速迭代打包
- 🔴 不适合首次构建

---

### BUILD_FULL.bat（完整构建）
**首次构建或依赖损坏时使用**

```bash
scripts\BUILD_FULL.bat
```

**特点**：
- 🔧 自动检查环境（Node.js、Python、PyInstaller）
- 🔧 自动安装缺失依赖
- 🔧 详细的步骤提示
- ⏱️ 速度较慢（每次都重新安装依赖）

**流程**：
1. 检查环境（Node/Python/PyInstaller）
2. 清理旧文件
3. 安装前端依赖 + 构建前端
4. 打包后端（PyInstaller）
5. 安装 Electron 依赖 + 打包 Electron

**适用场景**：
- 🟢 首次构建
- 🟢 依赖损坏/不完整
- 🟢 长时间未构建
- 🟢 新电脑/新环境
- 🔴 不适合频繁使用（太慢）

---

## 📊 对比表格

| 特性 | BUILD_AUTO | BUILD | BUILD_FULL |
|------|-----------|-------|-----------|
| **速度** | 智能 | ⚡⚡⚡ | 🐌 慢 |
| **环境检查** | ✅ 自动 | ❌ | ✅ 详细 |
| **依赖安装** | ✅ 自动 | ❌ | ✅ 强制 |
| **工具检查** | ✅ | ✅ FFmpeg/yt-dlp | ❌ |
| **容错性** | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| **新手友好** | ⭐⭐⭐ | ⭐ | ⭐⭐ |
| **推荐度** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |

---

## 🎯 使用建议

### 场景 1：日常开发（推荐）
```bash
# 智能选择，一键搞定
scripts\BUILD_AUTO.bat
```

### 场景 2：快速迭代打包
```bash
# 前提：已运行 SETUP.bat，环境正常
scripts\BUILD.bat
```

### 场景 3：首次构建/依赖损坏
```bash
# 会自动安装所有依赖
scripts\BUILD_FULL.bat
```

### 场景 4：生产发布
```bash
# 1. 先下载工具到 backend\tools\bin\
#    - FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases
#    - yt-dlp: https://github.com/yt-dlp/yt-dlp/releases

# 2. 然后运行构建
scripts\BUILD_AUTO.bat
```

---

## ⚠️ 注意事项

### 构建前准备

1. **环境要求**
   - Node.js 18+
   - Python 3.11（推荐）
   - 已运行过 `SETUP.bat`（首次使用）

2. **磁盘空间**
   - 至少 3GB 可用空间
   - 构建输出在 `dist-output\` 目录

3. **网络要求**
   - 首次构建需要网络下载依赖
   - 后续构建可离线

### 常见问题

**Q: 构建失败怎么办？**
```bash
# 1. 清理环境
scripts\CLEAN.bat

# 2. 重新安装依赖
scripts\SETUP.bat

# 3. 使用完整构建
scripts\BUILD_FULL.bat
```

**Q: 打包后 exe 文件很大？**
- 正常，包含 Python 运行时和所有依赖
- 预计大小：200-400MB

**Q: 如何只构建前端？**
```bash
cd frontend
npm run build
```

**Q: 如何只打包后端？**
```bash
cd backend
venv\Scripts\python.exe -m PyInstaller backend.spec --clean
```

---

## 📝 输出说明

构建完成后，输出文件在：
```
dist-output/
├── VidFlow Desktop Setup x.x.x.exe    # 安装包（推荐）
├── VidFlow Desktop x.x.x.exe          # 便携版（可选）
└── ...
```

---

## 🔗 相关文档

- [SETUP.bat](./SETUP.bat) - 安装开发环境
- [START.bat](./START.bat) - 启动开发服务器
- [CLEAN.bat](./CLEAN.bat) - 清理构建文件
- [../backend/REQUIREMENTS_README.md](../backend/REQUIREMENTS_README.md) - 依赖管理说明
