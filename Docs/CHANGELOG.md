# VidFlow Desktop 更新日志

## [v1.0.1] - 2025-10-26

### ✨ 新增功能

#### 系统集成 ⭐
- **系统托盘功能** - Windows 系统托盘完整实现
  - 托盘图标显示应用状态
  - 单击/双击托盘图标显示/隐藏窗口
  - 右键菜单（显示/隐藏/关于/退出）
  - 关闭窗口最小化到托盘（不退出应用）
  - 首次最小化气泡提示
  - Windows 优化的交互体验

#### Python 版本管理
- **优先使用 Python 3.11** - SETUP.bat 自动检测和使用 3.11
- **版本智能检测** - 优先 3.11，降级到默认版本
- **REBUILD_VENV.bat** - 一键重建虚拟环境脚本
- **完整文档** - 新增 PYTHON_VERSION_GUIDE.md

#### 依赖优化
- **faster-whisper 改为可选** - 不影响核心功能
- **requirements-optional.txt** - 可选依赖独立管理
- **INSTALL_WHISPER.md** - 详细的字幕功能安装指南

### 🔧 技术改进

#### 前端
- 修改 `ToolConfig.tsx` - 添加"自动安装"和"查看说明"按钮
- 改进 `handleOpenWebsite` - 支持 Electron 环境打开外部链接
- 优化安装提示和错误处理

#### 后端
- 修复 `tool_manager.py` - Unicode 编码错误（✓ → [OK]）
- 优化日志输出，兼容 Windows GBK 编码
- 改进错误提示信息

#### Electron
- 新增 `Tray` 和 `Menu` API 集成
- 实现完整的托盘生命周期管理
- 优化窗口关闭行为（最小化到托盘）
- 改进应用退出流程

#### 脚本优化
- 修改 `SETUP.bat` - Python 3.11 优先级检测
- 新增 `REBUILD_VENV.bat` - 虚拟环境重建工具
- 改进错误提示和用户引导

### 📁 新增文件

```
electron/main.js (修改)                       # 系统托盘实现
backend/requirements-optional.txt             # 可选依赖
backend/INSTALL_WHISPER.md                    # faster-whisper 安装指南
REBUILD_VENV.bat                              # 虚拟环境重建脚本
PYTHON_VERSION_GUIDE.md                       # Python 版本使用指南
TRAY_FEATURE.md                               # 托盘功能说明文档
WINDOWS_INTEGRATION_STATUS.md (更新)         # Windows 集成状态
```

### 🐛 修复

- **修复 Unicode 编码错误** - tool_manager.py 日志输出在 Windows GBK 环境下的崩溃
- **修复托盘退出逻辑** - 正确处理 before-quit 和 quit 事件
- **修复窗口关闭行为** - 区分关闭窗口和退出应用
- **修复 Python 版本兼容性** - 明确 3.8-3.11 支持范围

### 📝 文档

- 新增 `TRAY_FEATURE.md` - 系统托盘功能完整说明
- 新增 `PYTHON_VERSION_GUIDE.md` - Python 版本管理指南
- 新增 `INSTALL_WHISPER.md` - AI 字幕功能安装文档
- 更新 `WINDOWS_INTEGRATION_STATUS.md` - 95% → 98% 完成度

### 🔄 改进

#### 用户体验
- ✅ 应用可后台运行（托盘模式）
- ✅ 快速访问应用（托盘图标）
- ✅ 符合 Windows 应用习惯
- ✅ 明确的 Python 版本要求提示
- ✅ 可选功能清晰标注

#### 开发体验
- ✅ Python 3.11 自动检测和使用
- ✅ 一键重建虚拟环境
- ✅ 可选依赖独立管理
- ✅ 详细的版本兼容性文档

#### 稳定性
- ✅ 修复 Windows 编码问题
- ✅ 改进错误处理和提示
- ✅ 优化应用生命周期管理

---

## 📊 本次更新统计 (v1.0.1)

| 指标 | 数量 |
|------|------|
| 新增文件 | 4 |
| 修改文件 | 6 |
| 新增代码行 | ~500 |
| 删除代码行 | ~20 |
| 新增功能 | 6 |
| 修复Bug | 4 |
| 文档更新 | 4 |

---

## 🚀 升级指南 (v1.0.0 → v1.0.1)

### 推荐步骤

1. **（可选）安装 Python 3.11**
   ```batch
   # 下载: https://www.python.org/downloads/release/python-3119/
   # 安装时勾选 "Add to PATH" 和 "py launcher"
   ```

2. **（可选）重建虚拟环境**
   ```batch
   .\REBUILD_VENV.bat
   # 或手动操作，参考 PYTHON_VERSION_GUIDE.md
   ```

3. **更新代码**
   ```batch
   git pull origin main
   ```

4. **重装依赖**（如果不重建虚拟环境）
   ```batch
   cd backend
   venv\Scripts\activate
   pip install -r requirements.txt
   cd ..
   ```

5. **启动应用**
   ```batch
   .\START.bat
   ```

6. **验证新功能**
   - 检查系统托盘图标
   - 测试托盘菜单和交互
   - 查看工具配置页面的新按钮

### 注意事项
- ⚠️ Python 3.14 用户：AI 字幕功能不可用，建议安装 3.11
- ✅ Python 3.8-3.11 用户：无需任何操作
- ✅ 现有数据和配置不受影响

---

## ⚠️ 已知问题 (v1.0.1)

### 待解决
1. **图标文件未生成** - 需要手动生成 icon.png 和 icon.ico 用于打包
2. **自动字幕未完整实现** - 功能框架已就绪，需集成 API

### 限制
1. **Python 3.12+ 不支持 faster-whisper** - 需要等待 ctranslate2 更新
2. **托盘功能 Windows 优化** - macOS/Linux 行为可能不同

---

## 🎯 下一版本计划 (v1.1.0)

### 计划功能
- [ ] 完整实现自动字幕功能
- [ ] 图标文件生成和打包
- [ ] WebSocket 实时进度推送
- [ ] 断点续传支持
- [ ] 托盘进度显示

### 优化方向
- [ ] 托盘菜单动态状态更新
- [ ] Python 多版本自动切换
- [ ] 安装脚本智能化
- [ ] 更多平台系统集成

---

## [Unreleased] - 2025-10-25

### ✨ 新增功能

#### 核心功能
- **下载路径自定义**: 支持用户自定义下载保存路径，设置立即生效
- **智能队列管理**: 实现并发下载控制，可配置最大并发数（默认3个）
- **桌面通知**: 任务完成/失败时显示系统通知，点击通知聚焦窗口
- **自动字幕钩子**: 预留下载完成后自动生成字幕的接口

#### UI/UX改进
- **全局设置系统**: 创建`SettingsContext`，设置实时生效
- **主题切换**: 支持亮色/暗色/跟随系统，立即生效
- **默认值应用**: 下载质量和格式自动使用用户偏好
- **文件夹打开优化**: 智能路径处理，详细错误提示

#### 开发体验
- **TypeScript类型完善**: 添加Electron API完整类型定义
- **图标资源系统**: 提供SVG源文件和生成脚本
- **测试清单**: 详细的功能测试文档
- **代码质量**: 清理未使用的导入，修复Lint警告

### 🔧 技术实现

#### 后端
- 新增 `download_queue.py` - 完整的队列管理器
  - 并发控制
  - 任务优先级
  - 自动队列处理
- 修改 `downloads.py` - 集成队列和钩子系统
- 优化 `download.py` model - 智能`file_path`构建

#### 前端
- 新增 `SettingsContext.tsx` - 全局设置管理
- 修改 `TaskManager.tsx` - 任务状态监控和通知
- 修改 `DownloadManager.tsx` - 使用全局设置
- 完善 `electron.d.ts` - 类型定义

#### Electron
- `main.js` - 添加Notification API
- `preload.js` - 暴露showNotification方法

### 📁 新增文件

```
backend/src/core/download_queue.py         # 队列管理器
frontend/src/contexts/SettingsContext.tsx  # 设置上下文
resources/icons/icon.svg                   # 应用图标源文件
resources/icons/GENERATE_ICONS.bat         # 图标生成脚本
resources/ICON_GUIDE.md                    # 图标指南
TESTING_CHECKLIST.md                       # 测试清单
CHANGELOG.md                               # 本文件
```

### 🐛 修复

- 修复 `START.bat` Python模块导入错误
- 修复 `STOP.bat` 未停止Electron进程
- 修复 `TaskManager` 字段访问undefined错误
- 修复 `TauriIntegration` API调用错误处理
- 修复 `DownloadTask` 接口类型不匹配

### 📝 文档

- 更新 `ICON_GUIDE.md` - 详细的图标创建指南
- 新增 `TESTING_CHECKLIST.md` - 完整的测试清单
- 更新 `STOP.bat` - 添加Electron和Node进程停止

### 🔄 改进

#### 性能优化
- 队列管理减少并发压力
- 异步任务处理不阻塞UI
- 设置localStorage缓存

#### 用户体验
- 设置保存有明确反馈
- 主题切换立即生效
- 错误提示更加详细
- 文件路径智能处理

#### 代码质量
- 清理未使用的导入
- 统一错误处理模式
- 添加详细的注释
- 类型安全提升

---

## 📊 本次更新统计

| 指标 | 数量 |
|------|------|
| 新增文件 | 7 |
| 修改文件 | 12 |
| 新增代码行 | ~800 |
| 删除代码行 | ~50 |
| 新增功能 | 5 |
| 修复Bug | 6 |
| 文档更新 | 4 |

---

## 🚀 升级指南

### 从旧版本升级

1. **备份数据**
   ```batch
   # 备份数据库和下载历史
   copy backend\data\*.db backup\
   ```

2. **更新代码**
   ```batch
   git pull origin main
   ```

3. **安装新依赖**
   ```batch
   # Python依赖（无新增）
   cd backend
   pip install -r requirements.txt
   
   # Node依赖（无新增）
   cd frontend
   npm install
   ```

4. **重启服务**
   ```batch
   .\STOP.bat
   .\START.bat
   ```

5. **验证功能**
   - 参考 `TESTING_CHECKLIST.md` 进行测试

---

## ⚠️ 已知问题

### 待解决
1. **自动字幕未完整实现** - 仅添加了钩子，需要完整的字幕API调用
2. **图标需要生成** - 运行 `resources/icons/GENERATE_ICONS.bat` 生成
3. **并发数需重启生效** - 动态更新需要后续实现

### 限制
1. **Windows专属功能** - 通知和文件操作针对Windows优化
2. **Python环境依赖** - 需要虚拟环境正确配置
3. **外部工具依赖** - yt-dlp、FFmpeg需要单独安装

---

## 🎯 下一版本计划 (v1.1.0)

### 计划功能
- [ ] 完整实现自动字幕功能
- [ ] WebSocket实时进度推送
- [ ] 断点续传支持
- [ ] 下载历史统计图表
- [ ] 批量任务管理
- [ ] 代理服务器支持

### 优化方向
- [ ] 队列性能优化
- [ ] 数据库查询优化
- [ ] UI响应速度提升
- [ ] 内存使用优化

---

## 📮 反馈

如有问题或建议，请：
- 提交 Issue
- 发送邮件
- 参与讨论

---

**版本**: v1.0.0
**发布日期**: 2025-10-25
**贡献者**: VidFlow Team

---

## 版本历史

### v1.0.0 (2025-10-25)
- 初始发布
- 完整的下载功能
- 队列管理系统
- 桌面通知集成
- 主题切换支持

---

**感谢使用 VidFlow Desktop！** 🎉
