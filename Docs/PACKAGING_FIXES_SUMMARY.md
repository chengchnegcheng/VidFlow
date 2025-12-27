# Windows 和 Mac 打包问题修复总结

## 修复日期
2025-12-27

## 修复的问题

### 🔴 严重问题

#### 1. ✅ Mac entitlements 文件缺失
**状态**: 已修复

**问题描述**:
- `electron-builder.json` 中配置了 `"entitlements": "build/entitlements.mac.plist"`
- 但项目中不存在 `build/` 目录和该文件

**修复内容**:
- 创建了 `build/entitlements.mac.plist` 文件
- 配置了必要的权限：
  - JIT 编译权限
  - 网络客户端/服务器权限
  - 文件读写权限
  - 音频输入权限

**文件位置**: `build/entitlements.mac.plist`

---

#### 2. ✅ Windows 图标路径不一致
**状态**: 已修复

**问题描述**:
- `electron-builder.json` 中配置 `"icon": "resources/icon.ico"`
- 但实际图标在 `resources/icons/icon.ico`

**修复内容**:
- 统一所有图标路径为 `resources/icons/icon.ico`
- 修改了 `electron-builder.json` 中的 Windows 和 NSIS 配置

**影响文件**: `electron-builder.json`

---

#### 3. ✅ NSIS 安装程序优化
**状态**: 已修复

**问题描述**:
- `differentialPackage: true` 可能导致更新问题

**修复内容**:
- 设置 `differentialPackage: false`

---

### 🔴 前后端连接问题

#### 4. ✅ 后端启动时序问题
**状态**: 已修复

**问题描述**:
- 前端可能在后端完全启动前就尝试连接
- 端口文件存在不代表后端已就绪

**修复内容**:
- 在 `tryReadPortFile()` 中添加健康检查
- 使用 axios 调用 `/api/v1/system/health` 验证后端状态
- 健康检查超时 3 秒

**影响文件**: `electron/main.js`

---

#### 5. ✅ backend-ready 事件丢失
**状态**: 已修复

**问题描述**:
- 渲染进程可能还未准备好接收事件
- 导致前端无法获取后端端口

**修复内容**:
- 等待页面加载完成后再发送事件
- 监听 `did-finish-load` 事件
- 支持页面加载中和加载完成两种情况

**影响文件**: `electron/main.js`

---

#### 6. ✅ IPC 返回值缺少错误状态
**状态**: 已修复

**问题描述**:
- 前端无法区分"正在启动"和"启动失败"

**修复内容**:
- 在 `get-backend-port` IPC 中添加 `error` 和 `status` 字段
- 状态包括：
  - `'starting'` - 正在启动
  - `'ready'` - 已就绪
  - `'failed'` - 启动失败
  - `'disconnected'` - 已断开

**影响文件**: `electron/main.js`

---

#### 7. ✅ 前端 API 初始化竞态条件
**状态**: 已修复

**问题描述**:
- `TauriIntegration.tsx` 和 `api.ts` 各自维护 API_BASE
- 导致状态不一致和多次初始化

**修复内容**:
- 创建统一的 `backendConfig.ts` 管理模块
- 单例模式确保只有一个配置源
- 支持配置变化监听器
- 自动处理后端事件（ready、error、disconnected）

**新增文件**: `frontend/src/utils/backendConfig.ts`
**影响文件**: `frontend/src/components/TauriIntegration.tsx`, `frontend/src/utils/api.ts`

---

#### 8. ✅ 后端进程退出处理
**状态**: 已修复

**问题描述**:
- 后端退出后前端仍在使用旧端口
- 没有通知机制

**修复内容**:
- 添加 `backend-disconnected` 事件
- 后端退出时清空端口和就绪状态
- 通知前端重新连接或显示错误

**影响文件**: `electron/main.js`

---

#### 9. ✅ 端口文件清理
**状态**: 已修复

**问题描述**:
- 旧的端口文件可能导致连接到错误的端口

**修复内容**:
- 在 `startPythonBackend()` 开始时清理旧端口文件

**影响文件**: `electron/main.js`

---

### 🔴 应用启动和托盘问题

#### 10. ✅ 应用重复启动（无单实例锁）
**状态**: 已修复

**问题描述**:
- 没有实现单实例锁定机制
- 每次点击都会启动新实例
- 导致多个进程同时运行

**修复内容**:
- 添加 `app.requestSingleInstanceLock()` 单实例锁
- 第二个实例启动时聚焦到已有窗口
- 自动恢复最小化或隐藏的窗口

**影响文件**: `electron/main.js`

---

#### 11. ✅ Windows 托盘图标不显示
**状态**: 已修复

**问题描述**:
- 托盘在后端启动成功后才创建
- 后端启动失败时托盘不会创建
- 图标路径可能不存在

**修复内容**:
- 托盘在应用启动时立即创建（不依赖后端）
- 添加详细的调试日志
- 实现备用图标机制（主图标不存在时使用 icon.ico）
- 防止重复创建托盘
- 增强错误处理和错误日志

**影响文件**: `electron/main.js`

---

## 🛠️ 新增功能

### 1. 构建验证脚本
**文件**: `scripts/validate-build.js`

**功能**:
- 检查所有必需的资源和构建产物
- 验证前后端构建产物是否存在
- 检查图标文件完整性
- 区分关键资源和可选资源

**使用方式**:
```bash
npm run validate
```

### 2. Mac 托盘图标生成工具
**文件**: `resources/icons/generate_mac_tray_template.py`

**功能**:
- 生成 macOS Template 格式的托盘图标
- 自动转换为黑白图标
- 生成标准分辨率和 Retina 分辨率两个版本

**使用方式**:
```bash
cd resources/icons
python generate_mac_tray_template.py
```

### 3. 统一的后端配置管理
**文件**: `frontend/src/utils/backendConfig.ts`

**功能**:
- 单例模式管理后端配置
- 自动初始化和重试机制
- 健康检查验证
- 配置变化监听器
- 自动处理后端事件

---

## 📁 修改的文件列表

1. `electron-builder.json` - 图标路径和 NSIS 配置
2. `electron/main.js` - 单实例锁、托盘创建、后端连接
3. `frontend/src/utils/backendConfig.ts` - 新增统一配置管理
4. `frontend/src/components/TauriIntegration.tsx` - 使用统一配置
5. `frontend/src/utils/api.ts` - 使用统一配置
6. `package.json` - 添加 validate 脚本
7. `build/entitlements.mac.plist` - 新增 Mac 权限配置
8. `scripts/validate-build.js` - 新增构建验证脚本
9. `resources/icons/generate_mac_tray_template.py` - 新增图标生成工具
10. `resources/icons/MAC_TRAY_ICON_GUIDE.md` - 新增图标指南

---

## 🎯 启动顺序优化

### 新的启动流程（已修复）:
```
1. 应用准备就绪 (app.whenReady)
   ↓
2. 移除菜单栏
   ↓
3. 创建系统托盘（立即，不依赖后端）
   ↓
4. 创建主窗口
   ↓
5. 启动后端
   ↓
6. 后端就绪后通知前端
   ↓
7. 初始化更新器
```

---

## ✅ 测试检查清单

### Windows 打包测试
- [ ] 单实例锁是否生效（多次点击只启动一个实例）
- [ ] 托盘图标是否显示
- [ ] 托盘右键菜单是否正常
- [ ] 托盘点击是否能显示/隐藏窗口
- [ ] 前后端连接是否正常
- [ ] 后端启动失败时是否有错误提示
- [ ] 应用图标是否正确显示

### Mac 打包测试
- [ ] entitlements 权限是否配置正确
- [ ] 应用是否能正常启动
- [ ] 网络请求是否被允许
- [ ] 文件读写是否正常
- [ ] 托盘图标是否适配亮/暗模式
- [ ] 前后端连接是否正常

---

## 🔧 开发环境运行

```bash
# 验证构建资源
npm run validate

# 启动开发模式
npm run dev

# 生成 Mac 托盘图标（如需要）
cd resources/icons
python generate_mac_tray_template.py
```

---

## 📦 打包命令

```bash
# Windows 打包
npm run build:win

# Mac 打包
npm run build:mac

# Linux 打包
npm run build:linux
```

---

## 🐛 已知问题

无

---

## 📝 备注

1. 所有修复已经过代码审查
2. 保持向后兼容性
3. 添加了详细的调试日志
4. 所有路径使用统一的配置
5. 错误处理更加健壮
