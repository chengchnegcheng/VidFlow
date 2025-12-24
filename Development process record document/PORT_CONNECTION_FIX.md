# 随机端口连接问题修复总结

## 📅 修复日期
2025年11月1日

## 🎯 问题背景

VidFlow Desktop 的后端使用**随机端口**启动（而非固定的 8000 端口），以避免端口冲突。后端启动时会：
1. 随机选择一个可用端口（如 8001, 8002, 8003...）
2. 通过 Electron IPC 将端口信息传递给前端
3. 前端需要使用这个动态端口进行所有 API 调用

## 🐛 发现的问题

多个前端模块**绕过了** `TauriIntegration` 的动态端口初始化机制，直接使用硬编码的 `localhost:8000`，导致：
- ❌ `ERR_CONNECTION_REFUSED` 错误
- ❌ 无法连接到后端
- ❌ 功能完全不可用

## 📋 修复清单

### ✅ 修复 1: SettingsContext.tsx
**问题位置**: `frontend/src/contexts/SettingsContext.tsx`

**问题代码**:
```typescript
import axios from 'axios';
const response = await axios.get('http://localhost:8000/api/v1/config');
```

**修复方案**:
```typescript
import { invoke } from '../components/TauriIntegration';
const response = await invoke('get_config');
```

**影响功能**: 设置加载和保存

---

### ✅ 修复 2: imageProxy.ts
**问题位置**: `frontend/src/utils/imageProxy.ts`

**问题代码**:
```typescript
function getApiBaseUrl(): string {
  return window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : `http://${window.location.hostname}:8000`;
}
```

**修复方案**:
```typescript
import { getApiBaseUrl } from '../components/TauriIntegration';
// 直接使用导入的函数
```

**影响功能**: B站、YouTube、抖音等视频封面图片显示（防盗链代理）

---

### ✅ 修复 3: SystemMonitor.tsx
**问题位置**: `frontend/src/components/SystemMonitor.tsx`

**问题代码**:
```typescript
// 显示服务地址
<p className="font-mono">http://localhost:8000</p>

// 打开 API 文档
onClick={() => window.open('http://localhost:8000/docs', '_blank')}

// 健康检查
onClick={() => window.open('http://localhost:8000/health', '_blank')}
```

**修复方案**:
```typescript
import { getApiBaseUrl } from './TauriIntegration';

// 显示服务地址
<p className="font-mono">{getApiBaseUrl()}</p>

// 打开 API 文档
onClick={() => window.open(`${getApiBaseUrl()}/docs`, '_blank')}

// 健康检查
onClick={() => window.open(`${getApiBaseUrl()}/health`, '_blank')}
```

**影响功能**: 系统监控界面的后端信息显示、API 文档和健康检查链接

---

### ✅ 修复 4: ToolsConfig.tsx
**问题位置**: `frontend/src/components/ToolsConfig.tsx`

**问题代码**:
```typescript
import { getApiBaseUrl } from '../utils/api';
```

**修复方案**:
```typescript
import { getApiBaseUrl } from './TauriIntegration';
```

**影响功能**: AI 工具配置和状态检查

---

### ✅ 修复 5: useAIToolsStatus.ts
**问题位置**: `frontend/src/hooks/useAIToolsStatus.ts`

**问题代码**:
```typescript
import { getApiBaseUrl } from '../utils/api';
```

**修复方案**:
```typescript
import { getApiBaseUrl } from '../components/TauriIntegration';
```

**影响功能**: AI 工具状态监控 Hook

---

## 🔧 新增功能

### 导出 `getApiBaseUrl` 函数
**位置**: `frontend/src/components/TauriIntegration.tsx`

```typescript
/**
 * 获取当前的 API Base URL（包含动态端口）
 * 用于需要直接构造 API URL 的场景（如图片代理）
 */
export function getApiBaseUrl(): string {
  return API_BASE;
}
```

**用途**: 
- 让其他模块能够获取正确的 API Base URL
- 支持需要手动构造 URL 的场景（图片代理、外部链接等）

---

## 🎯 核心原则

### ✅ 正确做法：统一使用 TauriIntegration

**方式 1: 使用 `invoke` 函数（推荐）**
```typescript
import { invoke } from '../components/TauriIntegration';

// 调用后端 API
const result = await invoke('command_name', { args });
```

**方式 2: 使用 `getApiBaseUrl` 函数**
```typescript
import { getApiBaseUrl } from '../components/TauriIntegration';

// 构造 URL
const imageUrl = `${getApiBaseUrl()}/api/v1/proxy/image?url=${encodeURIComponent(url)}`;
```

### ❌ 错误做法：直接使用硬编码或独立的 axios

```typescript
// ❌ 错误！绕过了端口初始化
import axios from 'axios';
const response = await axios.get('http://localhost:8000/api/...');

// ❌ 错误！硬编码端口
const url = 'http://localhost:8000/api/...';

// ❌ 错误！创建独立的 axios 实例
const api = axios.create({ baseURL: 'http://localhost:8000' });
```

---

## 📊 TauriIntegration 工作原理

### 端口初始化流程

```
1. 应用启动
   ↓
2. TauriIntegration.tsx 加载
   ↓
3. 调用 startPortInitialization()
   ↓
4. 通过 Electron IPC 获取后端端口
   window.electron.invoke('get-backend-port')
   ↓
5. 收到端口配置（如 8003）
   ↓
6. 更新全局变量
   API_BASE = 'http://localhost:8003'
   portInitialized = true
   ↓
7. 验证后端健康状态
   await api.get('/health')
   ↓
8. ✅ 初始化完成
```

### 请求拦截器

```typescript
api.interceptors.request.use(async (config) => {
  // 1. 检查端口是否已初始化
  if (!portInitialized && !initializationInProgress) {
    console.log('🔄 Port not initialized, waiting...');
    
    // 2. 等待初始化完成（最多 5 秒）
    for (let i = 0; i < 50; i++) {
      if (portInitialized) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  
  // 3. 使用正确的 baseURL
  if (portInitialized && backendPort) {
    config.baseURL = API_BASE;  // 动态端口
  }
  
  return config;
});
```

---

## 🧪 验证方法

### 1. 检查控制台日志

启动应用后，应该看到：
```
🚀 TauriIntegration.tsx loaded, starting port initialization...
🔄 [Attempt 1/10] Requesting backend port from Electron...
📡 Backend config received: {port: 8003, host: 'localhost', ready: true}
🔍 Verifying backend health...
✅ Backend API URL initialized and verified: http://localhost:8003
✅ Backend health check passed
✅ Port initialization completed successfully
```

### 2. 检查系统监控页面

打开系统监控，确认：
- ✅ "服务地址" 显示正确的端口（如 `http://localhost:8003`）
- ✅ "API 文档" 按钮能打开正确的 Swagger 文档
- ✅ "健康检查" 按钮能显示后端状态

### 3. 检查设置面板

打开设置面板，确认：
- ✅ 设置能够正常加载
- ✅ 修改设置后能够保存
- ✅ 控制台显示 `✅ 设置已从后端加载`

### 4. 检查图片加载

添加一个 B站/YouTube 视频，确认：
- ✅ 视频封面图片能够正常显示
- ✅ 控制台没有 `ERR_CONNECTION_REFUSED` 错误

---

## 📁 修改文件汇总

### 后端修改:
*无（此次仅修复前端连接问题）*

### 前端修改:
1. ✅ `frontend/src/contexts/SettingsContext.tsx`
   - 改用 `invoke` 函数代替直接的 axios 调用

2. ✅ `frontend/src/utils/imageProxy.ts`
   - 导入并使用 TauriIntegration 的 `getApiBaseUrl`

3. ✅ `frontend/src/components/SystemMonitor.tsx`
   - 导入并使用 `getApiBaseUrl` 显示动态端口

4. ✅ `frontend/src/components/ToolsConfig.tsx`
   - 改用 TauriIntegration 的 `getApiBaseUrl`

5. ✅ `frontend/src/hooks/useAIToolsStatus.ts`
   - 改用 TauriIntegration 的 `getApiBaseUrl`

6. ✅ `frontend/src/components/TauriIntegration.tsx`
   - 导出 `getApiBaseUrl` 函数供其他模块使用

---

## ✅ 修复完成度

- [x] 设置管理连接问题
- [x] 图片代理连接问题
- [x] 系统监控连接问题
- [x] AI 工具配置连接问题
- [x] 统一所有模块使用 TauriIntegration
- [x] 通过 linter 检查
- [x] 更新文档

---

## 🎉 结论

所有前端模块现在都**统一使用 TauriIntegration** 的动态端口机制，确保：

- ✅ 正确处理后端的随机端口
- ✅ 自动等待后端就绪
- ✅ 统一的连接管理
- ✅ 完善的错误处理
- ✅ 所有功能正常工作

**原则**: 
- 前端的**所有后端 API 调用**都必须通过 `TauriIntegration` 的 `invoke` 函数或 `getApiBaseUrl` 函数
- **禁止**直接使用硬编码的 `localhost:8000`
- **禁止**创建独立的 axios 实例绕过端口初始化

这确保了应用在任何端口配置下都能正常工作。🎊

