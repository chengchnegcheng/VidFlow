# VidFlow 脚本与打包说明

本文档只保留当前仍在维护和推荐使用的脚本，并给出 Windows 打包、归档和增量更新的实际流程。

## 当前保留的脚本

### Windows 开发

| 脚本 | 用途 |
| --- | --- |
| `SETUP.bat` | 初始化 Node/Python 环境并创建 `backend\venv` |
| `START.bat` | 启动后端、前端和 Electron 开发环境 |
| `STOP.bat` | 停止开发环境相关进程 |
| `START_ELECTRON_DEV.bat` | 由 `START.bat` 调用，单独启动 Electron |

### Windows 打包与发布

| 脚本 | 用途 |
| --- | --- |
| `BUILD_OPTIMIZED.bat` | 推荐的 Windows 发布构建脚本 |
| `BUILD_RELEASE.bat` | 交互式构建菜单，可只构建某一部分 |
| `UPLOAD_RELEASE.bat` | 生成发布 JSON，或把当前构建同步到 `releases\` |
| `VERSION.bat` | 版本号管理 |
| `GENERATE_DELTA.bat` | 从已有历史版本生成增量更新包 |
| `BUILD_AND_GENERATE_DELTA.bat` | 一键执行“构建当前版本 -> 归档 -> 生成增量包” |

### Node 辅助脚本

| 脚本 | 用途 |
| --- | --- |
| `build-backend.js` | `npm run build:backend` 使用的后端打包入口 |
| `archive-release.js` | 归档当前构建产物到 `releases\vX.Y.Z\` |
| `generate-delta.js` | 增量包命令行入口 |
| `build-and-generate-delta.js` | 一键串联构建、归档、差分生成 |
| `generate-tray-icons.js` | 生成托盘图标资源 |

### macOS

| 脚本 | 用途 |
| --- | --- |
| `setup-mac.sh` | macOS 环境初始化 |
| `dev-mac.sh` | macOS 开发模式 |
| `build-mac.sh` | macOS 构建脚本 |
| `README-macOS.md` | macOS 使用说明 |

## 已清理的历史脚本

下列脚本没有被当前 `package.json`、主流程脚本或运行入口引用，且功能已被现有命令覆盖，因此已移除：

- `dev.js`
- `validate-build.js`
- `CLEAN_CACHE.bat`

## Windows 打包流程

### 1. 首次环境准备

```bat
scripts\SETUP.bat
```

完成后应至少具备以下环境：

- 根目录 `node_modules`
- `frontend\node_modules`
- `backend\venv`

### 2. 构建当前版本

推荐直接运行：

```bat
scripts\BUILD_OPTIMIZED.bat
```

或使用 npm：

```bash
npm run build
```

构建完成后，主要产物位于：

- `dist-output\VidFlow Setup x.y.z.exe`
- `backend\dist\VidFlow-Backend\`
- `frontend\dist\`

### 3. 归档发布快照

如果需要为后续增量更新保留一个完整版本快照，执行：

```bash
npm run release:archive
```

或使用：

```bat
scripts\UPLOAD_RELEASE.bat
```

然后选择：

- `[3] Sync to local releases directory`

归档完成后会生成：

```text
releases\
  v1.0.0\
    VidFlow Setup 1.0.0.exe
    VidFlow-Backend\
    frontend\dist\
```

说明：

- 归档脚本会先重建 `releases\v当前版本\`
- 这样可以避免同版本重复归档时残留旧文件，影响 delta 对比结果

### 4. 生成发布信息

如果只需要生成安装包元数据 JSON：

```bat
scripts\UPLOAD_RELEASE.bat
```

然后选择：

- `[2] Generate release metadata JSON`

输出文件位于：

- `dist-output\release-x.y.z.json`

### 5. 生成增量更新包

前提：

- 已有旧版本快照，例如 `releases\v0.9.0\`
- 已归档当前版本快照，例如 `releases\v1.0.0\`

可以先查看可用旧版本：

```bash
npm run delta:list
```

再生成差异包：

```bash
npm run delta -- 0.9.0
```

或使用批处理：

```bat
scripts\GENERATE_DELTA.bat
```

生成后的文件位于：

- `releases\deltas\delta-0.9.0-to-1.0.0-win32-x64.zip`

### 6. 一键构建并生成增量包

如果你想从当前源码直接走到差异包，可以使用：

```bat
scripts\BUILD_AND_GENERATE_DELTA.bat --source=0.9.0
```

或：

```bash
npm run delta:build -- --source=0.9.0
```

流程会自动执行：

1. 构建当前版本
2. 归档当前构建产物
3. 根据 `--source` 指定的旧版本生成 delta 包

如果缺少旧版本目录，例如 `releases\v0.9.0\`，脚本会直接提示并停止。

## 推荐发布流程

### 仅发布全量安装包

1. `scripts\VERSION.bat`
2. `scripts\BUILD_OPTIMIZED.bat`
3. `scripts\UPLOAD_RELEASE.bat` 选择 `[2]` 或 `[3]`

### 发布全量包并保留增量更新能力

1. `scripts\VERSION.bat`
2. `scripts\BUILD_OPTIMIZED.bat`
3. `npm run release:archive`
4. `npm run delta -- 旧版本号`

### 从已有构建产物补做 delta

1. 确认 `releases\v旧版本\` 存在
2. 确认 `releases\v当前版本\` 已通过 `release:archive` 归档
3. 执行 `npm run delta -- 旧版本号`

## 常用命令速查

```bash
npm run build
npm run release:archive
npm run delta:list
npm run delta -- 0.9.0
npm run delta:build -- --source=0.9.0
```

## 相关文档

- [增量更新说明](README-DELTA-UPDATE.md)
- [macOS 脚本说明](README-macOS.md)
