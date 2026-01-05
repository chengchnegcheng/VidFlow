# VidFlow 增量更新打包指南

本文档说明如何为 VidFlow 生成和发布增量更新包。

## 概述

增量更新通过只传输版本间变化的文件，将更新下载量从 80-150MB 降低到 10-30MB（减少 70-90%）。

**技术方案**：
- 不使用 bsdiff 二进制差异（对 PyInstaller 打包的 exe 效果不佳）
- 直接打包变化的文件，排除大型依赖库
- 支持文件的新增、替换、删除操作

## 完整发布流程

```
1. 修改版本号 (VERSION.bat)
        ↓
2. 构建新版本 (BUILD_RELEASE.bat)
        ↓
3. 保存构建产物 (UPLOAD_RELEASE.bat → 选项3)
        ↓
4. 生成差异包 (GENERATE_DELTA.bat)
        ↓
5. 上传到更新服务器管理后台
```

## 详细步骤

### 步骤 1: 修改版本号

```batch
scripts\VERSION.bat
```

选择 `[2] 快速升级版本`，根据更新类型选择：
- 主版本升级 (1.0.0 → 2.0.0) - 重大更新
- 次版本升级 (1.0.0 → 1.1.0) - 新功能
- 修订版升级 (1.0.0 → 1.0.1) - Bug 修复

### 步骤 2: 构建新版本

```batch
scripts\BUILD_RELEASE.bat
```

选择 `[1] 完整构建`，等待构建完成。

构建产物位于：
- `dist-output\VidFlow-Setup-x.x.x.exe` - 安装包
- `backend\dist\VidFlow-Backend\` - 后端可执行文件
- `frontend\dist\` - 前端静态文件

### 步骤 3: 保存构建产物

```batch
scripts\UPLOAD_RELEASE.bat
```

选择 `[3] 复制到本地发布目录`

这会将构建产物复制到：
```
releases\
  └── v1.1.0\
      ├── VidFlow Setup 1.1.0.exe     # 安装包
      ├── VidFlow-Backend\            # 后端文件
      │   ├── VidFlow-Backend.exe
      │   └── _internal\
      └── frontend\
          └── dist\                   # 前端文件
              ├── index.html
              └── assets\
```

### 步骤 4: 生成差异包

```batch
scripts\GENERATE_DELTA.bat
```

输入源版本号（如 `1.0.2`），脚本会自动：
1. 扫描两个版本的文件（排除大型依赖）
2. 比较文件哈希，找出变化的文件
3. 创建差异包 ZIP 文件
4. 生成清单文件 (manifest.json)

差异包输出位置：
```
releases\
  └── deltas\
      └── delta-1.0.2-to-1.0.3-win32-x64.zip
```

### 步骤 5: 上传到更新服务器

登录更新服务器管理后台 (http://shcrystal.top:8321/admin)：

1. 进入「版本管理」上传新版本安装包
2. 进入「增量更新」上传差异包文件

## 目录结构要求

生成差异包需要以下目录结构：

```
releases\
  ├── v1.0.2\                    # 旧版本
  │   ├── VidFlow-Backend\       # 后端可执行文件
  │   │   ├── VidFlow-Backend.exe
  │   │   └── _internal\
  │   └── frontend\
  │       └── dist\              # 前端静态文件
  │           ├── index.html
  │           └── assets\
  │
  ├── v1.0.3\                    # 新版本
  │   ├── VidFlow-Backend\
  │   └── frontend\dist\
  │
  └── deltas\                    # 差异包输出目录
      └── delta-1.0.2-to-1.0.3-win32-x64.zip
```

## 差异包结构

生成的差异包 ZIP 文件包含：

```
delta-1.0.2-to-1.0.3-win32-x64.zip
├── manifest.json               # 清单文件（文件列表和哈希）
└── files/                      # 变化的文件
    ├── backend/                # 后端文件（映射到安装目录的 backend/）
    │   ├── VidFlow-Backend.exe
    │   └── _internal/
    │       └── base_library.zip
    └── frontend/dist/          # 前端文件（映射到安装目录的 frontend/dist/）
        ├── index.html
        └── assets/
            └── js/
                └── index-xxx.js
```

## 路径映射

差异包中的路径会映射到安装目录：

| 差异包路径 | 安装目录路径 |
|-----------|-------------|
| `backend/xxx` | `resources/backend/xxx` |
| `frontend/dist/xxx` | `resources/app/frontend/dist/xxx` |

## 清单文件格式

`manifest.json` 示例：

```json
{
  "version": "1.0.3",
  "source_version": "1.0.2",
  "platform": "win32",
  "arch": "x64",
  "created_at": "2026-01-04T14:26:02.332058Z",
  "files": [
    {
      "path": "backend/VidFlow-Backend.exe",
      "action": "replace",
      "target_hash": "1ec3374d6d9459286926c4a33a7e160d...",
      "target_size": 23698237,
      "source_hash": "dec057d157c4f42323f1e442848b1cec..."
    },
    {
      "path": "frontend/dist/assets/js/index-DOfn_1Ig.js",
      "action": "add",
      "target_hash": "2ad8f91fd9692218148b43d9401ef6cf...",
      "target_size": 343654,
      "source_hash": null
    },
    {
      "path": "frontend/dist/assets/js/index-DQAKwrM_.js",
      "action": "delete",
      "target_hash": null,
      "target_size": null,
      "source_hash": null
    }
  ],
  "total_size": 25486509,
  "full_package_size": 84601448,
  "file_count": 4
}
```

## 文件操作类型

| 操作 | 说明 |
|------|------|
| `add` | 新增文件 |
| `replace` | 替换已有文件 |
| `delete` | 删除文件 |

## 排除的目录

以下大型依赖目录会被自动排除（很少变化，体积巨大）：

- `playwright` - 浏览器自动化
- `selenium` - 浏览器驱动
- `pip` - Python 包管理器
- `setuptools` - Python 构建工具
- `_tcl_data`, `_tk_data`, `tcl8` - Tcl/Tk 数据
- `Pythonwin`, `win32`, `win32com` - Windows 扩展

## 注意事项

### 1. 保留历史版本

为了支持从任意旧版本升级，需要保留最近 N 个版本的构建产物：

```
releases\
  ├── v1.0.0\    # 保留
  ├── v1.0.1\    # 保留
  ├── v1.0.2\    # 保留
  └── v1.0.3\    # 当前版本
```

### 2. 差异包大小阈值

- 如果差异包大小超过完整包的 70%，系统会标记为「不推荐」
- 如果节省比例低于 20%，建议使用全量更新

### 3. 哈希算法

使用 SHA-256 计算文件哈希（比 SHA-512 更快，安全性足够）。

### 4. 测试验证

发布前务必测试：
1. 从旧版本增量更新到新版本
2. 验证更新后功能正常
3. 测试回滚功能（自动）

## 常见问题

### Q: 差异包生成失败？

检查：
1. 源版本目录是否存在（`releases\v1.0.2\`）
2. 目标版本目录是否存在（`releases\v1.0.3\`）
3. Python 虚拟环境是否正常（`backend\venv\`）

### Q: 差异包太大？

可能原因：
1. 大型依赖库发生变化（如 Python 版本升级）
2. 前端资源文件名变化（Vite 构建的 hash 文件名）

解决方案：
1. 检查是否有不必要的依赖更新
2. 考虑使用全量更新

### Q: 客户端增量更新失败？

1. 检查服务器上差异包文件是否存在
2. 检查 manifest.json 中的哈希是否正确
3. 客户端会自动回退到全量更新

### Q: 如何手动生成差异包？

```batch
cd backend
venv\Scripts\python.exe -m src.core.delta_generator 1.0.2 1.0.3 ..\releases\v1.0.2 ..\releases\v1.0.3 win32 x64
```

## 相关脚本

| 脚本 | 功能 |
|------|------|
| `VERSION.bat` | 版本号管理 |
| `BUILD_RELEASE.bat` | 构建发布版本 |
| `UPLOAD_RELEASE.bat` | 上传/保存发布版本 |
| `GENERATE_DELTA.bat` | 生成差异包 |

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/src/core/delta_generator.py` | 差异包生成器 |
| `electron/delta-updater.js` | 客户端增量更新器 |
| `electron/updater-custom.js` | 客户端更新管理器 |
