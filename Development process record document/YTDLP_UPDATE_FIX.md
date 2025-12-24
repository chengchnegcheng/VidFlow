# yt-dlp 更新功能修复

**修复日期**: 2025-11-01  
**问题类型**: 功能逻辑错误 + 新功能添加

---

## 🎯 核心问题

### yt-dlp 与 FFmpeg 的区别

| 特性 | FFmpeg | yt-dlp |
|------|--------|--------|
| **用途** | 视频处理工具 | 视频下载引擎 |
| **更新频率** | 几个月一次 | **几乎每周** |
| **版本重要性** | 低（功能稳定） | **高（修复网站支持）** |
| **用户需求** | 不需要频繁更新 | **经常需要更新** |
| **是否需要更新功能** | ❌ 否 | ✅ **是** |

### 问题分析

**原问题**：
1. 内置工具优先级设计不合理
2. 即使用户"更新"yt-dlp，系统还是使用旧的内置版本
3. 用户无法真正更新 yt-dlp

**原始优先级逻辑**：

```python
# backend/src/core/tool_manager.py:162-173

async def setup_ytdlp(self) -> Path:
    """设置 yt-dlp - 优先使用打包内置版本"""
    
    # ❌ 问题：内置版本优先级最高
    # 1. 检查打包的内置版本（最高优先级）
    bundled_path = BUNDLED_BIN_DIR / exe_name
    if bundled_path.exists():
        return bundled_path  # 总是返回旧的内置版本
    
    # 2. 检查已下载的版本（用户更新的）
    builtin_path = BIN_DIR / exe_name
    if builtin_path.exists():
        return builtin_path  # 这行代码永远不会执行！
```

**导致的问题**：
```
用户点击"检查更新"
    ↓
下载最新版本到 backend/tools/bin/
    ↓
setup_ytdlp() 被调用
    ↓
返回内置版本（旧版本）
    ↓
❌ 更新失败！用户还是使用旧版本
```

---

## ✅ 解决方案

### 设计决策

**核心原则**：
- ✅ **FFmpeg 不需要更新**：稳定工具，版本随应用更新
- ✅ **yt-dlp 需要频繁更新**：特殊处理，支持用户更新
- ✅ **下载版本优先于内置版本**：用户主动更新的版本优先级更高
- ✅ **提供恢复默认功能**：允许用户回退到内置版本

### 修复实现

#### 1. 后端：调整 yt-dlp 优先级

**文件**: `backend/src/core/tool_manager.py:162-183`

**修复前**：
```python
async def setup_ytdlp(self) -> Path:
    """设置 yt-dlp - 优先使用打包内置版本"""
    exe_name = "yt-dlp.exe" if self.system == "Windows" else "yt-dlp"
    
    # ❌ 1. 检查打包的内置版本（最高优先级）
    bundled_path = BUNDLED_BIN_DIR / exe_name
    if bundled_path.exists():
        return bundled_path
    
    # 2. 检查已下载的版本
    builtin_path = BIN_DIR / exe_name
    if builtin_path.exists():
        return builtin_path
```

**修复后**：
```python
async def setup_ytdlp(self) -> Path:
    """设置 yt-dlp - 优先使用用户下载的版本（支持更新）"""
    exe_name = "yt-dlp.exe" if self.system == "Windows" else "yt-dlp"
    
    # ✅ 1. 检查已下载的版本（最高优先级 - 用户主动更新的）
    builtin_path = BIN_DIR / exe_name
    if builtin_path.exists():
        logger.info(f"Using downloaded yt-dlp: {builtin_path}")
        return builtin_path
    
    # 2. 检查打包的内置版本（备用版本）
    bundled_path = BUNDLED_BIN_DIR / exe_name
    if bundled_path.exists():
        logger.info(f"[OK] Using bundled yt-dlp: {bundled_path}")
        return bundled_path
```

**关键变化**：
- 📝 交换优先级顺序
- 📝 下载版本优先于内置版本
- 📝 更新注释说明设计意图

#### 2. 后端：添加"恢复默认"API

**文件**: `backend/src/api/system.py:484-514`

**新增 API**：
```python
@router.delete("/tools/ytdlp/downloaded")
async def reset_ytdlp_to_bundled():
    """恢复 yt-dlp 到内置版本（删除下载的版本）"""
    try:
        from pathlib import Path
        import platform
        
        # 确定下载文件的路径
        system = platform.system()
        exe_name = "yt-dlp.exe" if system == "Windows" else "yt-dlp"
        
        # 获取工具目录
        base_dir = Path(__file__).parent.parent.parent
        bin_dir = base_dir / "tools" / "bin"
        downloaded_path = bin_dir / exe_name
        
        if downloaded_path.exists():
            downloaded_path.unlink()  # 删除文件
            logger.info(f"Deleted downloaded yt-dlp: {downloaded_path}")
            return {
                "success": True,
                "message": "已恢复到内置版本"
            }
        else:
            return {
                "success": True,
                "message": "当前使用的就是内置版本"
            }
    except Exception as e:
        logger.error(f"Failed to reset yt-dlp: {e}")
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")
```

**功能**：
- ✅ 删除用户下载的 yt-dlp
- ✅ 恢复使用内置版本
- ✅ 提供清晰的反馈消息

#### 3. 前端：区分 FFmpeg 和 yt-dlp

**文件**: `frontend/src/components/ToolsConfig.tsx:597-634`

**修复前**：
```tsx
{/* 内置工具：不显示操作按钮（版本随应用更新） */}
{tool.bundled && (
  <p className="text-sm text-muted-foreground py-2">
    内置工具版本随应用更新而更新
  </p>
)}
```

**修复后**：
```tsx
{/* FFmpeg 内置工具：不显示操作按钮 */}
{tool.bundled && tool.id === 'ffmpeg' && (
  <p className="text-sm text-muted-foreground py-2">
    内置工具版本随应用更新而更新
  </p>
)}

{/* yt-dlp 内置工具：显示更新和恢复按钮（支持频繁更新） */}
{tool.bundled && tool.id === 'ytdlp' && (
  <>
    <Button
      onClick={onInstall}
      disabled={installing}
      variant="outline"
      className="flex-1"
    >
      {installing ? (
        <>
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          更新中...
        </>
      ) : (
        <>
          <RefreshCw className="w-4 h-4 mr-2" />
          检查更新
        </>
      )}
    </Button>
    <Button
      onClick={onReset}
      disabled={installing}
      variant="ghost"
      size="sm"
      className="text-muted-foreground hover:text-foreground"
    >
      恢复默认
    </Button>
  </>
)}
```

**关键变化**：
- ✅ FFmpeg：只显示说明文字，无操作按钮
- ✅ yt-dlp：显示"检查更新"和"恢复默认"两个按钮
- ✅ 清晰区分不同工具的处理方式

#### 4. 前端：添加恢复默认处理函数

**文件**: `frontend/src/components/ToolsConfig.tsx:267-284`

**新增函数**：
```typescript
// 恢复 yt-dlp 到内置版本
const handleReset = async (toolId: string, toolName: string) => {
  if (toolId !== 'ytdlp') {
    toast.error('仅支持恢复 yt-dlp');
    return;
  }

  try {
    const result = await invoke('reset_ytdlp');
    toast.success(result.message || '恢复成功');
    await fetchToolsStatus(); // 刷新状态
  } catch (error) {
    console.error('Reset failed:', error);
    toast.error('恢复失败', {
      description: error instanceof Error ? error.message : '未知错误'
    });
  }
};
```

**功能**：
- ✅ 调用后端 API 删除下载的版本
- ✅ 显示用户友好的提示信息
- ✅ 刷新工具状态显示

#### 5. 前端：添加 API 调用

**文件**: `frontend/src/components/TauriIntegration.tsx:854-862`

**新增命令**：
```typescript
// 恢复 yt-dlp 到内置版本
'reset_ytdlp': async () => {
  try {
    const res = await api.delete('/api/v1/system/tools/ytdlp/downloaded');
    return res.data;
  } catch (error: any) {
    throw new Error(error.response?.data?.detail || '恢复失败');
  }
},
```

---

## 📊 修复前后对比

### 修复前

| 场景 | 行为 | 问题 |
|------|------|------|
| FFmpeg（内置） | 显示"内置工具版本随应用更新而更新" | ✅ 正确 |
| yt-dlp（内置） | 显示"内置工具版本随应用更新而更新" | ❌ 不符合需求 |
| 点击"检查更新" | 下载新版本 | ❌ 但还是使用旧版本 |
| 更新后 | 系统优先使用内置版本 | ❌ 更新无效 |

### 修复后

| 场景 | 行为 | 效果 |
|------|------|------|
| FFmpeg（内置） | 显示说明文字，无按钮 | ✅ 不需要更新 |
| yt-dlp（内置） | 显示"检查更新"和"恢复默认"按钮 | ✅ 支持更新 |
| 点击"检查更新" | 下载最新版本 | ✅ 真正使用新版本 |
| 更新后 | 系统优先使用下载版本 | ✅ 更新生效 |
| 点击"恢复默认" | 删除下载版本 | ✅ 回退到内置版本 |

---

## 🎨 UI 展示

### FFmpeg（不需要更新）

```
┌─────────────────────────────────────┐
│ FFmpeg                    [内置]    │
│ 版本：N-121567-g00c23bafb0          │
│ 视频处理工具                        │
│                                     │
│ 内置工具版本随应用更新而更新        │
│ ← 说明文字，无操作按钮              │
└─────────────────────────────────────┘
```

### yt-dlp（支持更新）

```
┌─────────────────────────────────────┐
│ yt-dlp                    [内置]    │
│ 版本：2024.10.07                    │
│ 视频下载引擎                        │
│                                     │
│ [🔄 检查更新]  [恢复默认]          │
│  ↑ 下载最新    ↑ 回退到             │
│     版本          内置版本           │
└─────────────────────────────────────┘
```

---

## 🔄 工作流程

### 正常使用内置版本

```
应用启动
    ↓
setup_ytdlp() 被调用
    ↓
检查 backend/tools/bin/yt-dlp.exe  (不存在)
    ↓
检查 resources/tools/bin/yt-dlp.exe  (存在)
    ↓
✅ 使用内置版本
```

### 用户更新 yt-dlp

```
用户点击"检查更新"
    ↓
调用 /api/v1/system/tools/install/ytdlp
    ↓
下载最新版本到 backend/tools/bin/yt-dlp.exe
    ↓
setup_ytdlp() 被调用
    ↓
检查 backend/tools/bin/yt-dlp.exe  (存在！)
    ↓
✅ 使用下载的最新版本
```

### 用户恢复默认

```
用户点击"恢复默认"
    ↓
调用 /api/v1/system/tools/ytdlp/downloaded (DELETE)
    ↓
删除 backend/tools/bin/yt-dlp.exe
    ↓
setup_ytdlp() 被调用
    ↓
检查 backend/tools/bin/yt-dlp.exe  (不存在)
    ↓
检查 resources/tools/bin/yt-dlp.exe  (存在)
    ↓
✅ 使用内置版本
```

---

## 🧪 测试验证

### 场景1：查看 FFmpeg

```
步骤：
1. 打开"系统设置" > "工具配置"
2. 查看 FFmpeg 卡片

预期结果：
✅ 显示 [内置] 蓝色徽章
✅ 显示版本号
✅ 显示说明文字："内置工具版本随应用更新而更新"
✅ 不显示任何操作按钮
```

### 场景2：查看 yt-dlp

```
步骤：
1. 查看 yt-dlp 卡片

预期结果：
✅ 显示 [内置] 蓝色徽章
✅ 显示版本号
✅ 显示"检查更新"按钮
✅ 显示"恢复默认"按钮
```

### 场景3：更新 yt-dlp

```
步骤：
1. 点击 yt-dlp 的"检查更新"按钮
2. 等待下载完成
3. 重启应用（或重新获取视频信息）

预期结果：
✅ 显示下载进度
✅ 提示"yt-dlp 安装成功"
✅ 系统使用新下载的版本
✅ 版本号可能变化（如果有新版本）
```

### 场景4：恢复默认版本

```
步骤：
1. 更新 yt-dlp 后
2. 点击"恢复默认"按钮
3. 等待操作完成

预期结果：
✅ 提示"已恢复到内置版本"
✅ 系统使用内置版本
✅ 版本号恢复到原来的内置版本
```

---

## 📁 修改文件清单

| 文件 | 修改内容 | 行数变化 |
|------|----------|----------|
| `backend/src/core/tool_manager.py` | 调整 yt-dlp 优先级逻辑 | ~0 |
| `backend/src/api/system.py` | 添加恢复默认 API | +32 |
| `frontend/src/components/ToolsConfig.tsx` | 区分 FFmpeg 和 yt-dlp UI，添加恢复默认按钮和处理函数 | +35 |
| `frontend/src/components/TauriIntegration.tsx` | 添加 reset_ytdlp 命令 | +9 |

**净变化**: +76 行

---

## 💡 设计考虑

### 为什么不让 FFmpeg 也支持更新？

1. **稳定性**
   - FFmpeg 功能非常稳定
   - 新版本主要是性能优化和边缘特性
   - 对普通用户影响很小

2. **兼容性风险**
   - 应用是针对特定 FFmpeg 版本测试的
   - 随意更新可能导致兼容性问题
   - 字幕烧录等功能可能受影响

3. **用户体验**
   - FFmpeg 更新频率低（几个月一次）
   - 用户很少需要最新版本
   - 随应用更新更合理

### 为什么 yt-dlp 需要频繁更新？

1. **网站变化频繁**
   - 抖音、B站等网站经常调整防爬虫机制
   - yt-dlp 需要快速跟进修复
   - 几乎每周都有新版本

2. **功能性影响大**
   - yt-dlp 版本过旧可能导致某些网站无法下载
   - 直接影响核心功能
   - 用户强烈需要更新

3. **更新风险低**
   - yt-dlp 是独立工具
   - 更新不会影响其他组件
   - 出问题可以轻松回退

---

## 🔧 未来改进建议

### 1. 自动更新提醒

**建议**：当检测到 yt-dlp 有新版本时，自动提示用户

**实现**：
```typescript
// 检查更新
const checkYtdlpUpdate = async () => {
  const currentVersion = await getCurrentVersion();
  const latestVersion = await getLatestVersion();
  
  if (currentVersion !== latestVersion) {
    toast.info('yt-dlp 有新版本可用', {
      description: `当前：${currentVersion}，最新：${latestVersion}`,
      action: {
        label: '立即更新',
        onClick: () => handleInstall('ytdlp', 'yt-dlp')
      }
    });
  }
};
```

### 2. 版本比较显示

**建议**：在 UI 上显示当前使用的是内置版本还是下载版本

**实现**：
```tsx
<Badge variant={isUsingDownloadedVersion ? "default" : "secondary"}>
  {isUsingDownloadedVersion ? "使用下载版本" : "使用内置版本"}
</Badge>
```

### 3. 更新日志显示

**建议**：更新后显示版本更新日志

**实现**：
```typescript
const showChangelog = (oldVersion: string, newVersion: string) => {
  // 从 GitHub API 获取更新日志
  const changelog = await fetchChangelog(oldVersion, newVersion);
  
  toast.success('更新成功', {
    description: changelog
  });
};
```

---

## ✅ 修复效果总结

### 问题解决
- ✅ yt-dlp 更新功能真正可用
- ✅ 下载的新版本会被优先使用
- ✅ 提供恢复默认版本的功能
- ✅ FFmpeg 保持稳定，不允许更新

### 用户体验
- ✨ 清晰区分不同工具的处理方式
- ✨ 提供灵活的更新和回退机制
- ✨ 用户友好的提示信息
- ✨ 符合工具特性的设计决策

### 代码质量
- 🏗️ 逻辑清晰，易于理解
- 🎨 UI 简洁，操作直观
- 🔧 易于维护和扩展
- 📖 注释完善，文档详细

---

## 📝 经验总结

### 设计原则

1. **工具特性决定功能**
   - 不同工具有不同的更新需求
   - 不能"一刀切"的处理方式
   - 根据实际使用场景设计功能

2. **优先级要合理**
   - 用户主动操作的优先级应该更高
   - 下载的版本应该优先于内置版本
   - 提供回退机制保证灵活性

3. **用户期望要考虑**
   - yt-dlp 用户期望能频繁更新
   - FFmpeg 用户不需要频繁关注版本
   - 功能设计要符合用户心智模型

### 类似问题排查

遇到"更新不生效"问题时：

1. **检查优先级逻辑**
   - 哪个版本优先级最高？
   - 更新的版本会被使用吗？
   - 优先级顺序是否合理？

2. **检查路径和文件**
   - 文件下载到哪里？
   - 系统从哪里读取？
   - 路径是否一致？

3. **检查用户需求**
   - 用户真的需要这个更新功能吗？
   - 更新频率是多少？
   - 更新的影响有多大？

---

**修复人员**: AI Assistant  
**修复日期**: 2025-11-01  
**修复状态**: ✅ 已完成并验证  
**用户反馈**: 符合 yt-dlp 的特殊需求




