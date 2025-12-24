# 前端 AI 工具管理 - 实施完成

**实施日期**：2025-10-31  
**版本**：VidFlow 3.1.0

---

## ✅ 已完成的前端组件

### 1. AI 工具卡片组件 (`AIToolsCard.tsx`)

**功能**：
- ✅ 显示 AI 工具安装状态
- ✅ 版本选择（CPU / GPU）
- ✅ 一键安装/卸载
- ✅ Python 兼容性检查
- ✅ 实时状态更新

**使用示例**：
```tsx
import { AIToolsCard } from './components/AIToolsCard';

<AIToolsCard
  status={aiToolsStatus}
  version={aiVersion}
  installing={installingAI}
  onVersionChange={setAiVersion}
  onInstall={handleInstallAI}
  onUninstall={handleUninstallAI}
/>
```

---

### 2. 工具配置页面扩展 (`ToolsConfig.tsx`)

**新增功能**：
- ✅ AI 工具状态管理
- ✅ 安装/卸载 API 调用
- ✅ 刷新按钮包含 AI 状态
- ✅ WebSocket 进度显示（已有）

**修改内容**：
```tsx
// 新增状态
const [aiToolsStatus, setAiToolsStatus] = useState<...>();
const [aiVersion, setAiVersion] = useState<'cpu' | 'cuda'>('cpu');
const [installingAI, setInstallingAI] = useState(false);

// 新增方法
const fetchAIToolsStatus = async () => { ... }
const handleInstallAI = async () => { ... }
const handleUninstallAI = async () => { ... }
```

---

### 3. AI 状态检测 Hook (`useAIToolsStatus.ts`)

**功能**：
- ✅ 自动获取 AI 工具状态
- ✅ 错误处理
- ✅ 手动刷新功能

**使用示例**：
```tsx
import { useAIToolsStatus } from '../hooks/useAIToolsStatus';

function MyComponent() {
  const { status, loading, error, refresh } = useAIToolsStatus();
  
  if (status?.installed) {
    // AI 工具已安装
  }
}
```

---

### 4. AI 安装提示对话框 (`AIToolsPrompt.tsx`)

**功能**：
- ✅ 友好的提示界面
- ✅ 三个操作选项：
  - 稍后安装
  - 前往设置
  - 立即安装（CPU）

**使用示例**：
```tsx
import { AIToolsPrompt } from './components/AIToolsPrompt';

<AIToolsPrompt
  open={showPrompt}
  onOpenChange={setShowPrompt}
  onInstall={handleQuickInstall}
  onGoToSettings={() => navigate('/settings?tab=tools')}
/>
```

---

## 🔧 集成到字幕功能

### 在 SubtitleProcessor.tsx 中添加检测

```tsx
import { useAIToolsStatus } from '../hooks/useAIToolsStatus';
import { AIToolsPrompt } from './AIToolsPrompt';
import { useState } from 'react';

function SubtitleProcessor() {
  const { status: aiStatus } = useAIToolsStatus();
  const [showAIPrompt, setShowAIPrompt] = useState(false);

  const handleGenerateSubtitle = async () => {
    // 检查 AI 工具是否已安装
    if (!aiStatus?.installed) {
      setShowAIPrompt(true);
      return;
    }
    
    // 继续生成字幕...
    await invoke('generate_subtitle', { ... });
  };

  return (
    <>
      <Button onClick={handleGenerateSubtitle}>
        生成字幕
      </Button>
      
      <AIToolsPrompt
        open={showAIPrompt}
        onOpenChange={setShowAIPrompt}
        onInstall={() => {
          // 调用快速安装 API
          fetch('/api/v1/system/tools/ai/install?version=cpu', {
            method: 'POST'
          });
        }}
        onGoToSettings={() => {
          // 跳转到设置页
        }}
      />
    </>
  );
}
```

---

## 📁 新增文件清单

```
frontend/src/
├── components/
│   ├── AIToolsCard.tsx              ← 新增：AI 工具卡片
│   ├── AIToolsPrompt.tsx            ← 新增：安装提示对话框
│   └── ToolsConfig.tsx              ← 已修改：集成 AI 管理
└── hooks/
    └── useAIToolsStatus.ts          ← 新增：AI 状态 Hook
```

---

## 🎨 UI 效果

### 工具配置页面

```
┌─────────────────────────────────────────┐
│ 工具配置              [刷新状态]        │
├─────────────────────────────────────────┤
│                                          │
│ 外部工具                                 │
│ ┌────────────────────────────────┐     │
│ │ ✓ FFmpeg [内置] [已安装]       │     │
│ │ 视频处理工具                    │     │
│ └────────────────────────────────┘     │
│                                          │
│ AI 功能                                  │
│ ┌────────────────────────────────┐     │
│ │ ℹ AI 字幕生成 [未安装]         │     │
│ │ 使用 faster-whisper 进行语音识别│     │
│ │                                 │     │
│ │ 选择版本：                      │     │
│ │ [CPU 版本 ⭐]  [GPU 版本]      │     │
│ │  约 300 MB      约 1 GB         │     │
│ │                                 │     │
│ │ ℹ 可选组件                      │     │
│ │ AI 字幕生成功能需要安装...      │     │
│ │                                 │     │
│ │        [安装 CPU 版本]          │     │
│ └────────────────────────────────┘     │
└─────────────────────────────────────────┘
```

### 安装提示对话框

```
┌──────────────────────────────────────────┐
│ ⚠ AI 字幕功能未安装                      │
├──────────────────────────────────────────┤
│ 生成字幕需要安装 faster-whisper AI 组件   │
│                                           │
│ ╔════════════════════════════════════╗   │
│ ║ AI 组件说明                        ║   │
│ ║ • CPU 版本（推荐）：约 300 MB      ║   │
│ ║ • GPU 版本：约 1 GB               ║   │
│ ║ 💡 推荐使用 CPU 版本              ║   │
│ ╚════════════════════════════════════╝   │
│                                           │
│ 您可以前往 设置 → 工具配置 进行安装       │
│                                           │
│  [稍后安装]  [前往设置]  [立即安装(CPU)]│
└──────────────────────────────────────────┘
```

---

## 🔌 API 调用示例

### 检查状态
```typescript
const response = await fetch('/api/v1/system/tools/ai/status');
const data = await response.json();
// { installed: false, faster_whisper: false, ... }
```

### 安装 AI 工具
```typescript
const response = await fetch(
  '/api/v1/system/tools/ai/install?version=cpu',
  { method: 'POST' }
);
const result = await response.json();
// { success: true, message: "AI 工具安装成功 (cpu 版本)" }
```

### 卸载 AI 工具
```typescript
const response = await fetch(
  '/api/v1/system/tools/ai/uninstall',
  { method: 'POST' }
);
const result = await response.json();
// { success: true, message: "AI 工具已卸载" }
```

---

## 🎯 使用流程

### 场景 1：用户首次使用 AI 字幕

1. 用户点击"生成字幕"
2. 检测到 AI 工具未安装
3. 显示 `AIToolsPrompt` 对话框
4. 用户选择：
   - **稍后安装** → 取消操作
   - **前往设置** → 跳转到工具配置页
   - **立即安装** → 开始安装 CPU 版本

### 场景 2：用户在设置中管理 AI 工具

1. 打开设置 → 工具配置
2. 看到 AI 字幕生成卡片
3. 选择版本（CPU / GPU）
4. 点击"安装"按钮
5. 等待安装完成（显示进度）
6. 安装成功，显示"已安装"状态

### 场景 3：用户卸载 AI 工具

1. 打开设置 → 工具配置
2. 看到 AI 工具"已安装"
3. 点击"卸载 AI 工具"按钮
4. 确认卸载
5. 卸载完成

---

## ✨ 特性亮点

1. **版本选择**
   - CPU 版本标记 ⭐ 推荐
   - 显示下载大小
   - 清晰的兼容性说明

2. **状态反馈**
   - 实时状态显示
   - 安装进度（通过 WebSocket）
   - 错误提示和解决建议

3. **Python 兼容性检查**
   - 自动检测 Python 版本
   - 不兼容时禁用安装按钮
   - 显示详细错误信息

4. **友好提示**
   - 未安装时不强制安装
   - 提供多个操作选项
   - 说明清晰，用户体验好

---

## 🧪 测试清单

### 工具配置页面

- [ ] 页面加载时正确显示 AI 工具状态
- [ ] 未安装时显示版本选择按钮
- [ ] 点击"安装"按钮触发安装
- [ ] 安装过程中显示进度（如果后端支持 WebSocket）
- [ ] 安装成功后状态变为"已安装"
- [ ] 已安装时显示"卸载"按钮
- [ ] 点击"卸载"按钮触发确认对话框
- [ ] 确认后成功卸载

### 字幕功能集成

- [ ] AI 未安装时显示提示对话框
- [ ] "稍后安装"按钮关闭对话框
- [ ] "前往设置"按钮跳转到工具配置
- [ ] "立即安装"按钮触发 CPU 版本安装
- [ ] AI 已安装时可正常生成字幕

### API 通信

- [ ] GET `/api/v1/system/tools/ai/status` 返回正确状态
- [ ] POST `/api/v1/system/tools/ai/install` 成功安装
- [ ] POST `/api/v1/system/tools/ai/uninstall` 成功卸载
- [ ] 错误情况下显示友好错误信息

---

## 📝 后续优化建议

1. **安装进度优化**
   - 添加更详细的进度百分比
   - 显示当前安装步骤（下载 PyTorch、安装 faster-whisper）
   - 添加取消安装功能

2. **离线安装支持**
   - 检测离线 wheel 文件
   - 提供离线安装选项
   - 显示离线包下载链接

3. **性能监控**
   - 显示 AI 推理速度
   - CPU vs GPU 性能对比
   - 内存使用情况

4. **高级设置**
   - 选择 Whisper 模型大小（tiny/base/small/medium）
   - 自定义模型缓存路径
   - 语言优化设置

---

## 🔗 相关文档

- [AI_TOOLS_GUIDE.md](./AI_TOOLS_GUIDE.md) - AI 工具完整使用指南
- [CHANGELOG_AI_TOOLS.md](./CHANGELOG_AI_TOOLS.md) - 后端实施总结
- [Backend API 文档](./AI_TOOLS_GUIDE.md#后端-api) - API 端点说明

---

**前端实施状态**：✅ 完成  
**可开始测试**：是  
**准备合并**：建议先测试后合并
