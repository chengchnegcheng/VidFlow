# AI 工具管理指南

## 📋 概述

从 VidFlow 3.1.0 开始，**AI 字幕生成功能（faster-whisper）不再打包在主程序中**，而是作为**可选工具按需安装**。

### ✨ 改进优势

| 特性 | 旧版本（打包） | 新版本（按需安装） |
|------|-------------|------------------|
| **基础包大小** | ~2 GB | **~500 MB** ⭐ |
| **下载速度** | 慢 | **快** ⭐ |
| **用户选择** | 强制安装 | **按需安装** ⭐ |
| **更新灵活性** | 需重新打包 | **独立更新** ⭐ |
| **兼容性** | 可能有问题 | **更好** ⭐ |

---

## 🚀 如何使用 AI 功能

### 方法 1：应用内安装（推荐）⭐

1. **启动 VidFlow**
2. **打开设置** → **工具管理**
3. **找到"AI 字幕生成"卡片**
4. **选择版本**：
   - ✅ **CPU 版本（推荐）**：约 300 MB，兼容所有机器
   - ⚠️ GPU 版本：约 1 GB，需要 NVIDIA 显卡
5. **点击"安装"按钮**
6. **等待安装完成**（3-5 分钟）

### 方法 2：手动安装

```bash
# 1. 进入后端目录
cd backend

# 2. 激活虚拟环境
venv\Scripts\activate

# 3. 安装 CPU 版本（推荐）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install faster-whisper requests

# 或安装 GPU 版本
pip install torch torchvision torchaudio
pip install faster-whisper requests
```

---

## 📊 版本对比

### CPU 版本 ⭐ 推荐

- **下载大小**：约 300 MB
- **安装时间**：3-5 分钟
- **兼容性**：✅ 所有机器
- **性能**：中等（5分钟视频 → 8-12分钟生成）
- **推荐指数**：⭐⭐⭐

**适用场景**：
- 大多数用户
- 没有 NVIDIA 显卡
- 追求体积小、兼容性好

### GPU 版本

- **下载大小**：约 1 GB
- **安装时间**：5-10 分钟
- **兼容性**：❌ 仅 NVIDIA 显卡
- **性能**：快（5分钟视频 → 2-3分钟生成）
- **推荐指数**：⭐

**适用场景**：
- 有 NVIDIA 显卡（GTX 1060 6GB+）
- 需要处理大量视频
- 对速度要求极高

---

## 🔧 技术实现

### 后端 API

#### 1. 检查状态
```bash
GET /api/system/tools/ai/status
```

**响应示例**：
```json
{
  "installed": true,
  "faster_whisper": true,
  "torch": true,
  "version": "1.2.0",
  "torch_version": "2.7.1+cpu",
  "device": "cpu",
  "python_compatible": true
}
```

#### 2. 获取信息
```bash
GET /api/system/tools/ai/info?version=cpu
```

**响应示例**：
```json
{
  "name": "AI 字幕生成 (CPU 版本)",
  "description": "使用 faster-whisper 进行语音识别，兼容所有机器",
  "download_size": "约 300 MB",
  "install_time": "3-5 分钟",
  "compatible": "所有机器"
}
```

#### 3. 安装工具
```bash
POST /api/system/tools/ai/install?version=cpu
```

**参数**：
- `version`: "cpu" 或 "cuda"

**响应示例**：
```json
{
  "success": true,
  "message": "AI 工具安装成功 (cpu 版本)"
}
```

#### 4. 卸载工具
```bash
POST /api/system/tools/ai/uninstall
```

**响应示例**：
```json
{
  "success": true,
  "message": "AI 工具已卸载"
}
```

### 前端集成（示例）

```typescript
// 检查 AI 工具状态
const checkAIStatus = async () => {
  const response = await fetch('/api/system/tools/ai/status');
  const data = await response.json();
  return data.installed;
};

// 安装 AI 工具
const installAI = async (version: 'cpu' | 'cuda' = 'cpu') => {
  const response = await fetch(`/api/system/tools/ai/install?version=${version}`, {
    method: 'POST'
  });
  const result = await response.json();
  
  if (result.success) {
    alert('AI 工具安装成功！');
  } else {
    alert(`安装失败：${result.error}`);
  }
};

// 在字幕功能中检测
const generateSubtitle = async (videoId: string) => {
  const aiInstalled = await checkAIStatus();
  
  if (!aiInstalled) {
    // 提示用户安装
    if (confirm('AI 字幕功能未安装，是否现在安装？')) {
      await installAI('cpu');
    }
    return;
  }
  
  // 继续生成字幕...
};
```

---

## ⚠️ 注意事项

### 1. Python 版本要求

- ✅ **Python 3.8 - 3.11**：完全支持
- ❌ **Python 3.12+**：不兼容，无法安装

如果使用 Python 3.12+，请：
1. 删除 `backend\venv` 文件夹
2. 安装 Python 3.11
3. 重新运行 `SETUP.bat`

### 2. 安装失败处理

**问题：依赖包编译失败**
```
解决方案：
1. 确认 Python 版本为 3.8-3.11
2. 使用 CPU 版本（兼容性更好）
3. 检查网络连接
```

**问题：磁盘空间不足**
```
需要至少 1 GB 可用空间
建议清理系统临时文件
```

### 3. 性能优化

**CPU 版本性能调优**：
- 关闭其他占用 CPU 的程序
- 选择较小的模型（base）
- 分段处理长视频

**GPU 版本注意**：
- 确保显卡驱动最新
- 检查 CUDA 版本兼容性
- 监控显存使用

---

## 📝 常见问题

### Q1: 为什么改为按需安装？

**A:** 主要原因：
1. **减小基础包体积**：从 2 GB 降到 500 MB
2. **提高下载速度**：基础功能快速安装
3. **用户选择权**：不需要 AI 功能的用户节省空间
4. **灵活更新**：AI 组件独立更新，不影响主程序

### Q2: 安装后会影响打包大小吗？

**A:** 不会。AI 工具安装在开发环境的 `venv` 中，打包时会被排除。如果你想在打包版本中包含 AI 功能，需要修改 `backend.spec` 文件。

### Q3: 可以同时安装 CPU 和 GPU 版本吗？

**A:** 不可以。PyTorch 一次只能安装一个版本。如果需要切换：
1. 卸载当前版本
2. 安装目标版本

### Q4: 如何检查是否安装成功？

```bash
# 方法 1：通过 API
curl http://localhost:8000/api/system/tools/ai/status

# 方法 2：手动测试
cd backend
venv\Scripts\activate
python -c "import faster_whisper; print('OK')"
```

### Q5: 卸载后需要重启应用吗？

**A:** 建议重启。卸载后 Python 进程可能仍保留已加载的模块，重启可确保完全生效。

---

## 🎯 开发者指南

### 修改的文件列表

1. **backend/src/core/tool_manager.py**
   - 添加 `check_ai_tools_status()`
   - 添加 `install_ai_tools()`
   - 添加 `uninstall_ai_tools()`
   - 添加 `get_ai_tool_info()`

2. **backend/src/api/system.py**
   - 添加 `/tools/ai/status` 端点
   - 添加 `/tools/ai/info` 端点
   - 添加 `/tools/ai/install` 端点
   - 添加 `/tools/ai/uninstall` 端点

3. **backend/backend.spec**
   - 添加 `excludes` 列表
   - 排除 torch, faster_whisper 等

4. **scripts/SETUP.bat**
   - 移除 AI 工具自动安装
   - 添加按需安装提示

### 前端实现建议

在设置页面添加工具管理卡片：

```typescript
<ToolCard
  id="ai-tools"
  name="AI 字幕生成"
  description="使用 faster-whisper 进行语音识别"
  status={aiStatus}
  onInstall={() => installAI('cpu')}
  onUninstall={uninstallAI}
>
  <Select value={aiVersion} onChange={setAiVersion}>
    <option value="cpu">CPU 版本（推荐，约 300 MB）</option>
    <option value="cuda">GPU 版本（约 1 GB，需要显卡）</option>
  </Select>
</ToolCard>
```

---

## 📊 影响范围

### 对用户的影响

**正面**：
- ✅ 基础包下载更快
- ✅ 灵活选择是否安装 AI 功能
- ✅ 节省磁盘空间

**需要适应**：
- 首次使用字幕功能需要手动安装
- 需要网络连接（首次安装时）

### 对开发的影响

**优势**：
- ✅ 打包更快
- ✅ AI 组件独立测试和更新
- ✅ 更好的错误隔离

**需要注意**：
- 字幕功能需要检测 AI 工具状态
- 提供友好的安装引导
- 处理安装失败的情况

---

## 🔗 相关文档

- [PACKAGE_OPTIMIZATION.md](./PACKAGE_OPTIMIZATION.md) - 打包优化详细指南
- [scripts/BUILD_README.md](./scripts/BUILD_README.md) - 构建脚本说明
- [backend/REQUIREMENTS_README.md](./backend/REQUIREMENTS_README.md) - 依赖管理说明

---

**最后更新**：2025-10-31  
**版本**：VidFlow 3.1.0  
**作者**：VidFlow Team
