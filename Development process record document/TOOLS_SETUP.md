# 🔧 VidFlow 工具集成指南

## 📦 核心工具

VidFlow 需要以下工具来实现完整功能：

| 工具 | 用途 | 必需 | 大小 |
|------|------|------|------|
| **FFmpeg** | 视频处理 | ✅ 是 | ~80-120 MB |
| **yt-dlp** | 视频下载 | ✅ 是 | ~10 MB |

---

## 🎯 集成方式

### 方式 1：预集成到项目中（推荐用于分发）

**优点：**
- ✅ 用户开箱即用
- ✅ 离线可用
- ✅ 无需首次下载等待

**步骤：**

1. **下载工具**

   **FFmpeg:**
   - Windows: https://github.com/BtbN/FFmpeg-Builds/releases
   - 下载 `ffmpeg-master-latest-win64-gpl.zip`
   - 解压后找到 `ffmpeg.exe`

   **yt-dlp:**
   - Windows: https://github.com/yt-dlp/yt-dlp/releases
   - 下载 `yt-dlp.exe`

2. **放置到项目目录**

   ```
   VidFlow-Desktop/
   └── backend/
       └── tools/
           └── bin/
               ├── ffmpeg.exe     ← 放这里
               └── yt-dlp.exe     ← 放这里
   ```

   或者（打包时使用）：

   ```
   VidFlow-Desktop/
   └── resources/
       └── tools/
           └── bin/
               ├── ffmpeg.exe     ← 放这里
               └── yt-dlp.exe     ← 放这里
   ```

3. **验证**

   重启应用，工具会自动被检测到。

---

### 方式 2：自动下载（适用于开发环境）

**优点：**
- ✅ 项目体积小
- ✅ 始终使用最新版本

**缺点：**
- ⚠️ 首次使用需要等待下载
- ⚠️ 需要网络连接

**步骤：**

无需任何操作，首次使用视频下载功能时会自动下载。

下载位置：`backend/tools/bin/`

---

### 方式 3：使用系统安装的版本

**前提：**
- 系统已安装 FFmpeg（在 PATH 中）
- 系统已安装 yt-dlp（在 PATH 中）

**检测优先级：**
1. `resources/tools/bin/` (最高优先级)
2. `backend/tools/bin/`
3. 系统 PATH
4. 自动下载（最后）

---

## 📊 开发者建议

### 开发环境

```bash
# 克隆项目
git clone xxx

# 运行 SETUP.bat
cd scripts
SETUP.bat

# 首次使用时会自动下载工具
# 或手动下载放到 backend/tools/bin/
```

### 打包分发

```bash
# 1. 下载工具到 resources/tools/bin/
# 2. 打包时会自动包含
# 3. 用户无需下载
```

### Git 管理

**选项 A：提交到 Git（推荐）**
```gitignore
# 不在 .gitignore 中排除
# backend/tools/bin/ffmpeg.exe
# backend/tools/bin/yt-dlp.exe
```

**优点：** 团队成员克隆即可用
**缺点：** 仓库体积增加 ~100MB

**选项 B：不提交到 Git**
```gitignore
# .gitignore 中添加
backend/tools/bin/
```

**优点：** 仓库体积小
**缺点：** 每个开发者需要自行下载

---

## 🔍 检查工具状态

启动应用后，打开 **设置面板 → 工具管理**，可以看到：

```
✓ FFmpeg
  版本: 6.0
  路径: backend\tools\bin\ffmpeg.exe
  
✓ yt-dlp
  版本: 2024.10.22
  路径: backend\tools\bin\yt-dlp.exe
```

---

## 🚀 快速开始

**最简单的方式：**

1. 运行 `scripts\SETUP.bat`
2. 首次下载视频时自动下载工具
3. 完成！

**离线分发：**

1. 手动下载 FFmpeg 和 yt-dlp
2. 放到 `backend\tools\bin\`
3. 打包或分发项目
4. 用户开箱即用

---

## ❓ 常见问题

**Q: 工具会占用多少空间？**
A: FFmpeg ~100MB, yt-dlp ~10MB, 总共约 110MB

**Q: 可以使用系统安装的 FFmpeg 吗？**
A: 可以，但项目内置的优先级更高

**Q: 如何更新工具？**
A: 删除旧文件，下载新版本放到同一位置

**Q: 打包后工具在哪里？**
A: `resources/tools/bin/` (会被 PyInstaller 包含)
