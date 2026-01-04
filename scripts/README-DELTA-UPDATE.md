# VidFlow 增量更新打包指南

本文档说明如何为 VidFlow 生成和发布增量更新包。

## 概述

增量更新通过只传输版本间的差异数据，将更新下载量从 100-150MB 降低到 10-30MB（减少 70-90%）。

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
5. 上传到更新服务器
        ↓
6. 在服务器注册版本信息
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
      ├── VidFlow-Setup-1.1.0.exe    # 安装包
      ├── VidFlow-Backend\            # 后端文件
      └── frontend\dist\              # 前端文件
```

### 步骤 4: 生成差异包

```batch
scripts\GENERATE_DELTA.bat
```

输入源版本号（如 `1.0.0`），脚本会自动：
1. 比较两个版本的文件差异
2. 生成二进制补丁文件
3. 创建差异包 ZIP 文件
4. 生成清单文件 (manifest.json)

差异包输出位置：
```
releases\
  └── deltas\
      └── delta-1.0.0-to-1.1.0-win-x64.zip
```

### 步骤 5: 上传到更新服务器

将以下文件上传到更新服务器：

```bash
# 上传完整安装包
scp releases/v1.1.0/VidFlow-Setup-1.1.0.exe user@shcrystal.top:/path/to/releases/v1.1.0/

# 上传差异包
scp releases/deltas/delta-1.0.0-to-1.1.0-win-x64.zip user@shcrystal.top:/path/to/releases/deltas/
```

### 步骤 6: 在服务器注册版本

登录更新服务器管理后台 (http://shcrystal.top:8321/admin)：

1. 上传新版本信息
2. 注册差异包信息

或使用 API：

```bash
# 注册新版本
curl -X POST http://shcrystal.top:8321/api/v1/admin/versions/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@releases/v1.1.0/VidFlow-Setup-1.1.0.exe" \
  -F "version=1.1.0" \
  -F "channel=stable" \
  -F "release_notes=更新说明"
```

## 目录结构要求

生成差异包需要以下目录结构：

```
releases\
  ├── v1.0.0\                    # 旧版本
  │   ├── VidFlow-Backend\       # 后端可执行文件
  │   │   ├── VidFlow-Backend.exe
  │   │   └── ...
  │   └── frontend\dist\         # 前端静态文件
  │       ├── index.html
  │       └── assets\
  │
  ├── v1.1.0\                    # 新版本
  │   ├── VidFlow-Backend\
  │   └── frontend\dist\
  │
  └── deltas\                    # 差异包输出目录
      └── delta-1.0.0-to-1.1.0-win-x64.zip
```

## 差异包结构

生成的差异包 ZIP 文件包含：

```
delta-1.0.0-to-1.1.0-win-x64.zip
├── manifest.json           # 清单文件（文件列表和哈希）
├── patches/                # 补丁文件目录
│   ├── app.asar.patch     # 二进制差异文件
│   └── VidFlow-Backend.exe.patch
├── new/                    # 新增文件目录
│   └── new_feature.dll
└── checksum.sha512        # 整包校验和
```

## 清单文件格式

`manifest.json` 示例：

```json
{
  "version": "1.1.0",
  "source_version": "1.0.0",
  "platform": "win32",
  "arch": "x64",
  "created_at": "2026-01-04T10:00:00Z",
  "files": [
    {
      "path": "VidFlow-Backend/VidFlow-Backend.exe",
      "action": "patch",
      "source_hash": "abc123...",
      "target_hash": "def456...",
      "patch_file": "VidFlow-Backend.exe.patch",
      "patch_size": 1048576
    },
    {
      "path": "frontend/dist/assets/index.js",
      "action": "replace",
      "target_hash": "ghi789...",
      "target_size": 500000
    },
    {
      "path": "old_file.dll",
      "action": "delete"
    }
  ],
  "total_patch_size": 15728640,
  "full_package_size": 157286400
}
```

## 文件操作类型

| 操作 | 说明 |
|------|------|
| `patch` | 使用二进制差异补丁更新文件 |
| `replace` | 完整替换文件（差异太大时） |
| `add` | 新增文件 |
| `delete` | 删除文件 |

## 注意事项

### 1. 保留历史版本

为了支持从任意旧版本升级，需要保留最近 N 个版本的构建产物：

```
releases\
  ├── v1.0.0\    # 保留
  ├── v1.0.1\    # 保留
  ├── v1.1.0\    # 保留
  └── v1.2.0\    # 当前版本
```

### 2. 差异包大小阈值

如果差异包大小超过完整包的 80%，系统会自动推荐全量更新。

### 3. 版本跨度限制

如果用户版本落后超过 5 个版本，建议使用全量更新而非链式增量更新。

### 4. 测试验证

发布前务必测试：
1. 从旧版本增量更新到新版本
2. 验证更新后功能正常
3. 测试回滚功能

## 常见问题

### Q: 差异包生成失败？

检查：
1. 源版本目录是否存在
2. Python 虚拟环境是否正常
3. 是否安装了 bsdiff 依赖

### Q: 客户端无法下载差异包？

检查：
1. 服务器上差异包文件是否存在
2. 数据库中是否注册了差异包信息
3. 文件权限是否正确

### Q: 增量更新后程序异常？

1. 检查清单文件中的哈希是否正确
2. 尝试回滚到旧版本
3. 使用全量更新重新安装

## 相关脚本

| 脚本 | 功能 |
|------|------|
| `VERSION.bat` | 版本号管理 |
| `BUILD_RELEASE.bat` | 构建发布版本 |
| `UPLOAD_RELEASE.bat` | 上传/保存发布版本 |
| `GENERATE_DELTA.bat` | 生成差异包 |

## 相关文档

- [增量更新设计文档](../.kiro/specs/incremental-update/design.md)
- [更新服务器部署](../VidFlow%20Service%20Update/server/scripts/README_DEPLOY.txt)
