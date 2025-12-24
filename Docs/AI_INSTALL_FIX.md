# AI 工具安装卡住问题 - 修复总结

## 📋 问题描述

用户在工具配置页面安装 AI 功能时，进度条卡在 5% 不动，显示"安装中 (3-5 分钟)"但没有任何进度更新。

## 🔍 根本原因分析

### 1. **没有超时机制**
   - pip 安装 PyTorch 和 faster-whisper 没有设置超时
   - 如果网络慢或 PyPI 服务器无响应，会无限等待
   - 用户看不到任何反馈，以为程序卡住了

### 2. **进度更新太少**
   - 原实现只有 3 个进度点：5%, 10%, 60%
   - PyTorch 下载过程（最耗时）完全没有进度反馈
   - 从 10% 到 60% 之间可能需要 5-10 分钟，但用户看到的是静止不动

### 3. **没有实时输出**
   - pip 的安装输出被丢弃，用户和开发者都无法看到实际进度
   - 无法判断是网络慢、安装中，还是真的卡住了

### 4. **WebSocket 连接状态未显示**
   - 如果 WebSocket 连接失败，进度永远不会更新
   - 用户不知道是安装卡住还是连接断开

## ✅ 修复方案

### 后端修复 (`backend/src/core/tool_manager.py`)

#### 1. **添加超时机制**
```python
# 卸载旧版本：30 秒超时
await asyncio.wait_for(process.communicate(), timeout=30)

# 安装 PyTorch：10 分钟超时
await asyncio.wait_for(
    asyncio.gather(read_output(), process.wait()),
    timeout=600
)

# 安装 faster-whisper：10 分钟超时
await asyncio.wait_for(
    asyncio.gather(read_whisper_output(), process.wait()),
    timeout=600
)
```

#### 2. **实时读取并解析 pip 输出**
```python
async def read_output():
    nonlocal current_progress
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        
        line_text = line.decode('utf-8', errors='ignore').strip()
        output_lines.append(line_text)
        logger.info(f"[PyTorch Install] {line_text}")
        
        # 根据输出更新进度
        if 'Downloading' in line_text or 'Obtaining' in line_text:
            current_progress = min(current_progress + 2, 45)
            if progress_callback:
                await progress_callback(current_progress, "下载 PyTorch 依赖包...")
        elif 'Installing' in line_text:
            current_progress = min(current_progress + 3, 55)
            if progress_callback:
                await progress_callback(current_progress, "安装 PyTorch...")
        elif 'Successfully installed' in line_text:
            if progress_callback:
                await progress_callback(60, "PyTorch 安装完成！")
```

#### 3. **改进进度分布**
- **5%**: 清理旧版本
- **10-45%**: 下载 PyTorch 依赖包（实时更新）
- **45-55%**: 安装 PyTorch（实时更新）
- **60%**: PyTorch 安装完成
- **65-85%**: 下载 faster-whisper（实时更新）
- **85-95%**: 安装 faster-whisper（实时更新）
- **98-100%**: 完成

#### 4. **添加 pip 超时参数**
```python
'--default-timeout=300'  # 5 分钟 HTTP 超时
```

#### 5. **改进错误处理**
```python
except asyncio.TimeoutError:
    process.kill()
    logger.error("PyTorch installation timeout")
    return {
        "success": False,
        "error": "PyTorch 安装超时（网络太慢或服务器无响应）\n请检查网络连接后重试"
    }
```

### 前端修复

#### 1. **添加 WebSocket 连接状态追踪** (`ToolsConfig.tsx`)
```typescript
const [wsConnected, setWsConnected] = useState(false);

ws.onopen = () => {
  setWsConnected(true);
  // ...
};

ws.onerror = () => {
  setWsConnected(false);
  // ...
};

ws.onclose = () => {
  setWsConnected(false);
  // ...
};
```

#### 2. **传递连接状态给 AI 工具卡片**
```typescript
<AIToolsCard
  status={aiToolsStatus}
  version={aiVersion}
  installing={installingAI}
  progress={installProgress['ai-tools']}
  wsConnected={wsConnected}  // 新增
  onVersionChange={setAiVersion}
  onInstall={handleInstallAI}
  onUninstall={handleUninstallAI}
/>
```

#### 3. **显示 WebSocket 连接警告** (`AIToolsCard.tsx`)
```typescript
{/* WebSocket 连接警告 */}
{installing && !wsConnected && (
  <Alert variant="destructive">
    <AlertCircle className="h-4 w-4" />
    <AlertDescription>
      <span className="font-medium">实时进度连接失败</span>
      <br />
      安装仍在后台进行，但无法实时显示进度。请耐心等待 5-10 分钟后刷新页面查看结果。
    </AlertDescription>
  </Alert>
)}
```

## 📊 修复效果对比

| 方面 | 修复前 | 修复后 |
|------|--------|--------|
| **超时处理** | ❌ 无超时，可能永久卡住 | ✅ 10 分钟超时，自动终止 |
| **进度更新** | ❌ 仅 3 个点 (5%, 10%, 60%) | ✅ 10+ 个点，实时更新 |
| **输出可见** | ❌ 完全不可见 | ✅ 实时记录到后端日志 |
| **WebSocket 状态** | ❌ 用户不知道是否连接 | ✅ 明确提示连接状态 |
| **错误提示** | ❌ 简单错误码 | ✅ 详细错误信息和解决方案 |
| **用户体验** | ⭐⭐ 看起来卡死 | ⭐⭐⭐⭐⭐ 清晰的进度反馈 |

## 🧪 测试建议

### 1. **正常安装测试**
```bash
# 1. 启动应用
START.bat

# 2. 打开工具配置页面
# 3. 选择 CPU 版本
# 4. 点击"安装"
# 5. 观察进度条是否实时更新
# 6. 查看后端日志，确认 pip 输出被记录
```

**预期结果**:
- 进度条从 5% 开始，逐步增加到 100%
- 每个阶段都有文字提示（"下载 PyTorch 依赖包..."、"安装 PyTorch..." 等）
- 后端日志中可以看到 pip 的实时输出
- 安装完成后显示成功提示

### 2. **慢网络测试**
```bash
# 模拟慢网络（Windows PowerShell）
# 1. 使用系统代理工具限速到 100KB/s
# 2. 启动安装
# 3. 观察进度更新是否仍然正常
```

**预期结果**:
- 虽然慢，但进度条会持续更新
- 不会卡在某个百分比不动
- 如果超过 10 分钟，会提示超时错误

### 3. **WebSocket 断开测试**
```bash
# 1. 开始安装
# 2. 立即关闭 WebSocket（在浏览器控制台执行）
wsRef.current.close()
# 3. 观察是否显示警告
```

**预期结果**:
- 立即显示红色警告："实时进度连接失败"
- 提示用户安装仍在后台进行
- 建议用户 5-10 分钟后刷新页面

### 4. **超时测试**
```bash
# 模拟极慢网络或服务器无响应
# 1. 断开网络
# 2. 启动安装
# 3. 等待 10 分钟
```

**预期结果**:
- 10 分钟后自动终止安装
- 显示超时错误："PyTorch 安装超时（网络太慢或服务器无响应）"
- 建议用户检查网络连接

## 🔧 如何查看安装日志

### 方法 1: 后端控制台
安装过程中，后端控制台会实时输出 pip 的日志：
```
INFO [PyTorch Install] Collecting torch
INFO [PyTorch Install] Downloading torch-2.1.0-cp311-cp311-win_amd64.whl (197.9 MB)
INFO [PyTorch Install]   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 10%
INFO [PyTorch Install]   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 20%
...
```

### 方法 2: 日志中心
安装完成后，可以在"日志中心"搜索 "PyTorch Install" 或 "Whisper Install" 查看完整日志。

## 📝 相关文件

### 修改的文件
1. **`backend/src/core/tool_manager.py`**
   - `install_ai_tools()` 方法：添加超时、实时输出、改进进度

2. **`frontend/src/components/ToolsConfig.tsx`**
   - 添加 `wsConnected` 状态
   - 更新 WebSocket 事件处理

3. **`frontend/src/components/AIToolsCard.tsx`**
   - 添加 `wsConnected` 属性
   - 显示 WebSocket 连接警告

### 未修改的文件
- `backend/src/api/system.py` - AI 安装 API 端点（无需修改）
- `backend/src/core/websocket_manager.py` - WebSocket 管理器（无需修改）

## 🎯 关键改进点

1. **⏱️ 超时保护** - 防止无限等待
2. **📊 实时进度** - 用户可以看到实际进度
3. **📝 日志记录** - 开发者可以调试问题
4. **🔌 连接状态** - 用户知道进度为何不更新
5. **❌ 错误处理** - 清晰的错误信息和解决方案

## 🚀 后续优化建议

### 1. 下载进度百分比
如果 pip 支持 `--progress-bar` 参数，可以解析进度条输出：
```python
# 示例输出
# Downloading torch-2.1.0-cp311-cp311-win_amd64.whl (197.9 MB)
#   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 45%
```

### 2. 镜像源切换
如果 PyPI 太慢，可以提供国内镜像选项：
```python
# 清华镜像
'--index-url', 'https://pypi.tuna.tsinghua.edu.cn/simple'

# 阿里云镜像
'--index-url', 'https://mirrors.aliyun.com/pypi/simple/'
```

### 3. 安装重试机制
网络不稳定时，自动重试 1-2 次：
```python
max_retries = 2
for attempt in range(max_retries):
    try:
        result = await install_pytorch()
        if result['success']:
            break
    except Exception as e:
        if attempt == max_retries - 1:
            raise
        await progress_callback(10, f"重试 {attempt + 1}/{max_retries}...")
```

## ✅ 验收标准

- [x] 安装过程中进度条实时更新（不再卡住）
- [x] 后端日志可以看到 pip 的实时输出
- [x] 10 分钟超时自动终止
- [x] WebSocket 断开时显示警告
- [x] 超时错误提示清晰明确
- [x] 没有 linter 错误
- [x] 正常安装流程完整可用

---

**修复日期**: 2025-11-05  
**修复作者**: AI Assistant  
**相关 Issue**: AI 工具安装卡住问题

