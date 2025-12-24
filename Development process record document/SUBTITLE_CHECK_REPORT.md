# 字幕生成与烧录功能检查报告

**检查日期**: 2025-11-01  
**检查范围**: 字幕生成 + 字幕烧录

---

## 📋 功能概览

### 1. 字幕生成功能
- **前端**: `frontend/src/components/SubtitleProcessor.tsx`
- **后端API**: `backend/src/api/subtitle.py`
- **核心处理**: `backend/src/core/subtitle_processor.py`
- **数据模型**: `backend/src/models/subtitle.py`

**功能特性**：
- AI 字幕生成（基于 faster-whisper）
- 多语言支持（自动检测/手动选择）
- 多模型选择（tiny/base/small/medium/large）
- 字幕翻译（多目标语言）
- 任务队列管理
- WebSocket 实时进度

### 2. 字幕烧录功能
- **前端**: `frontend/src/components/BurnSubtitle.tsx`
- **后端API**: `backend/src/api/subtitle.py`
- **核心工具**: FFmpeg

**功能特性**：
- 字幕永久嵌入视频
- 支持多种字幕格式（SRT/VTT/ASS/SSA）
- 任务队列管理
- WebSocket 实时进度

---

## ⚠️ 发现的问题

### 问题1：前端文件选择功能依赖electron API 🔴

#### 问题位置
`frontend/src/components/SubtitleProcessor.tsx:94-116`

```tsx
const handleSelectFile = async () => {
  try {
    // 检查是否在 Electron 环境
    if (window.electron && window.electron.isElectron) {
      const filePath = await window.electron.selectVideoFile(); // ❌ 依赖 electron API
      if (filePath) {
        setSelectedFile(filePath);
        toast.success('文件已选择');
      }
    } else {
      // 浏览器环境降级
      toast.info('选择文件', {
        description: '浏览器环境不支持文件选择，请使用 Electron 版本'
      });
    }
  } catch (error) {
    toast.error('选择文件失败');
  }
};
```

#### 问题分析
1. **TypeScript错误**：`window.electron` 未定义类型
2. **API不统一**：使用 `window.electron.selectVideoFile()`，而不是标准的 `invoke` API
3. **功能缺失**：`window.electron.selectVideoFile` 可能未在 `electron/preload.js` 中实现

#### 影响
- 可能导致文件选择功能完全不工作
- TypeScript 编译错误

#### 建议修复
使用统一的 `invoke('select_file')` API：

```tsx
const handleSelectFile = async () => {
  try {
    const result = await invoke('select_file', {
      filters: [
        { name: '视频文件', extensions: ['mp4', 'mkv', 'avi', 'mov', 'flv', 'wmv', 'webm'] }
      ]
    });
    if (result) {
      setSelectedFile(result);
      toast.success('文件已选择', {
        description: result.split(/[/\\]/).pop()
      });
    }
  } catch (error) {
    toast.error('选择文件失败', {
      description: error instanceof Error ? error.message : '未知错误'
    });
  }
};
```

---

### 问题2："下载字幕"和"重试"按钮无功能实现 🟡

#### 问题位置
`frontend/src/components/SubtitleProcessor.tsx:437-446`

```tsx
{task.status === 'completed' && (
  <>
    <Button size="sm" variant="outline">
      <Download className="size-4 mr-2" />
      下载字幕  {/* ❌ 无 onClick */}
    </Button>
  </>
)}
{task.status === 'failed' && (
  <Button size="sm" variant="outline">
    <Play className="size-4 mr-2" />
    重试  {/* ❌ 无 onClick */}
  </Button>
)}
```

#### 问题分析
- "下载字幕"按钮没有 `onClick` 处理函数
- "重试"按钮没有 `onClick` 处理函数
- 按钮可点击但无任何反应

#### 影响
- 用户体验差：按钮看起来可用但点击无效
- 功能不完整

#### 建议修复
```tsx
// 添加处理函数
const handleDownloadSubtitle = async (outputFiles: string[]) => {
  // 打开字幕文件所在文件夹
  if (outputFiles.length > 0) {
    const folderPath = outputFiles[0].split(/[\\/]/).slice(0, -1).join('\\');
    await invoke('open_folder', { path: folderPath });
  }
};

const handleRetryTask = async (task: SubtitleTask) => {
  try {
    await invoke('generate_subtitle', {
      video_path: task.video_path,
      video_title: task.video_title,
      source_language: task.source_language,
      target_languages: task.target_languages,
      model: task.model,
      formats: ['srt', 'vtt']
    });
    toast.success('任务已重新创建');
    await fetchTasks();
  } catch (error) {
    toast.error('重试失败');
  }
};

// 按钮添加 onClick
<Button 
  size="sm" 
  variant="outline"
  onClick={() => handleDownloadSubtitle(task.output_files)}
>
  <Download className="size-4 mr-2" />
  下载字幕
</Button>

<Button 
  size="sm" 
  variant="outline"
  onClick={() => handleRetryTask(task)}
>
  <Play className="size-4 mr-2" />
  重试
</Button>
```

---

### 问题3：烧录字幕组件中的"重试"按钮无功能 🟡

#### 问题位置
`frontend/src/components/BurnSubtitle.tsx:407-411`

```tsx
{task.status === 'failed' && (
  <Button size="sm" variant="outline">
    <Play className="size-4 mr-2" />
    重试  {/* ❌ 无 onClick */}
  </Button>
)}
```

#### 建议修复
```tsx
const handleRetryBurnTask = async (task: BurnSubtitleTask) => {
  try {
    await invoke('create_burn_subtitle_task', {
      video_path: task.video_path,
      subtitle_path: task.subtitle_path,
      output_path: task.output_path,
      video_title: task.video_title
    });
    toast.success('任务已重新创建');
    await fetchTasks();
  } catch (error) {
    toast.error('重试失败');
  }
};

<Button 
  size="sm" 
  variant="outline"
  onClick={() => handleRetryBurnTask(task)}
>
  <Play className="size-4 mr-2" />
  重试
</Button>
```

---

### 问题4：字幕路径转义可能在Windows下有问题 🟡

#### 问题位置
`backend/src/api/subtitle.py:276` 和 `420`

```python
# 构建 FFmpeg 命令
subtitle_path_escaped = str(subtitle_file).replace('\\', '/').replace(':', '\\:')

cmd = [
    ffmpeg_path,
    '-i', str(video_file),
    '-vf', f"subtitles='{subtitle_path_escaped}'",  # ⚠️ 可能有问题
    '-c:a', 'copy',
    '-y',
    output_path
]
```

#### 问题分析
1. Windows路径转义规则复杂
2. 反斜杠 `\` 转为正斜杠 `/` 可能导致问题
3. 冒号 `:` 转义可能不够（如 `C:\path`）

#### 实际问题
Windows路径 `C:\Users\test\video.srt` 会被转换为：
```
C\\:/Users/test/video.srt
```
这可能导致FFmpeg无法找到文件。

#### 建议修复
使用更可靠的路径转义方法：

```python
import re

def escape_ffmpeg_path(path: str) -> str:
    """转义FFmpeg subtitles filter的路径"""
    # Windows: 将反斜杠替换为双反斜杠
    # 冒号不需要转义（在Windows盘符中）
    if os.name == 'nt':  # Windows
        # 使用原始路径，只转义单引号
        path = str(path).replace("'", "'\\''")
        return path
    else:  # Linux/Mac
        # 替换特殊字符
        path = str(path).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")
        return path

# 使用
subtitle_path_escaped = escape_ffmpeg_path(subtitle_file)

cmd = [
    ffmpeg_path,
    '-i', str(video_file),
    '-vf', f"subtitles='{subtitle_path_escaped}'",
    '-c:a', 'copy',
    '-y',
    output_path
]
```

**或者更简单的方法（推荐）**：

```python
# 使用 subtitles 过滤器的文件名参数（更安全）
cmd = [
    str(ffmpeg_path),
    '-i', str(video_file),
    '-vf', f"subtitles={str(subtitle_file).replace('\\', '/')}",  # 简单转换
    '-c:a', 'copy',
    '-y',
    output_path
]
```

---

### 问题5：后端subprocess调用缺少路径类型转换 ⚠️

#### 问题位置
`backend/src/api/subtitle.py:278-285`

```python
cmd = [
    ffmpeg_path,  # ⚠️ 可能是 Path 对象
    '-i', str(video_file),
    '-vf', f"subtitles='{subtitle_path_escaped}'",
    '-c:a', 'copy',
    '-y',
    output_path
]

result = subprocess.run(cmd, ...)  # ❌ subprocess需要字符串
```

#### 问题分析
- `ffmpeg_path` 来自 `tool_manager.get_ffmpeg_path()`，返回 `Path` 对象
- `subprocess.run()` 需要字符串列表，而非 `Path` 对象
- 在某些Python版本可能工作，但不规范

#### 建议修复
```python
cmd = [
    str(ffmpeg_path),  # ✅ 显式转换为字符串
    '-i', str(video_file),
    '-vf', f"subtitles='{subtitle_path_escaped}'",
    '-c:a', 'copy',
    '-y',
    str(output_path)  # ✅ 也转换输出路径
]
```

---

### 问题6：字幕处理器缺少进度回调机制 ⚠️

#### 问题位置
`backend/src/core/subtitle_processor.py:385-430`

#### 问题描述
`SubtitleProcessor.process_video()` 方法没有进度回调参数，导致：
- 无法实时更新任务进度
- WebSocket 无法推送进度
- 用户只能看到"处理中"状态，没有百分比

#### 当前代码
```python
async def process_video(
    self,
    video_path: str,
    output_dir: str,
    source_language: str = "auto",
    target_languages: List[str] = None,
    model_name: str = "base",
    formats: List[str] = None
) -> Dict:
    # ❌ 没有 progress_callback 参数
    # ❌ 没有调用进度回调
    ...
```

#### 建议修复
```python
async def process_video(
    self,
    video_path: str,
    output_dir: str,
    source_language: str = "auto",
    target_languages: List[str] = None,
    model_name: str = "base",
    formats: List[str] = None,
    progress_callback: Optional[Callable] = None  # ✅ 添加进度回调
) -> Dict:
    """完整的视频字幕处理流程"""
    try:
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if formats is None:
            formats = ["srt"]
        if target_languages is None:
            target_languages = []
        
        # 1. 提取音频 (10%)
        if progress_callback:
            await progress_callback(10, "提取音频中...")
        audio_path = output_dir / f"{video_path.stem}_audio.wav"
        await self.extract_audio(str(video_path), str(audio_path))
        
        # 2. 初始化模型 (20%)
        if progress_callback:
            await progress_callback(20, "加载模型中...")
        if not self.model or self.model_name != model_name:
            await self.initialize_model(model_name)
        
        # 3. 转录 (20-80%)
        if progress_callback:
            await progress_callback(30, "AI识别中...")
        result = await self.transcribe(
            str(audio_path),
            language=source_language
        )
        
        if progress_callback:
            await progress_callback(80, "生成字幕文件...")
        
        # 4. 生成字幕文件
        # ...
        
        # 5. 翻译（如果需要）
        if target_languages:
            if progress_callback:
                await progress_callback(90, "翻译字幕中...")
            # ...
        
        if progress_callback:
            await progress_callback(100, "完成")
        
        return result
    except Exception as e:
        logger.error(f"Process video failed: {e}")
        raise
```

**并在 API 中使用**：

```python
async def process_subtitle_task(task_id: str, request: SubtitleGenerateRequest):
    """后台处理字幕任务"""
    from src.models.database import AsyncSessionLocal
    from src.core.subtitle_processor import get_subtitle_processor
    from src.api.websocket import get_connection_manager
    
    # 进度回调函数
    async def update_progress(progress: float, message: str):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SubtitleTaskModel).where(SubtitleTaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task.progress = progress
                task.status = "processing" if progress < 100 else "completed"
                await db.commit()
                
                # WebSocket 通知
                ws_manager = get_connection_manager()
                await ws_manager.broadcast({
                    "type": "subtitle_task_update",
                    "data": task.to_dict()
                })
    
    try:
        # 处理视频（带进度回调）
        processor = get_subtitle_processor()
        result_data = await processor.process_video(
            video_path=request.video_path,
            output_dir=str(output_dir),
            source_language=request.source_language,
            target_languages=request.target_languages,
            model_name=request.model,
            formats=request.formats,
            progress_callback=update_progress  # ✅ 传入进度回调
        )
        # ...
    except Exception as e:
        # ...
```

---

### 问题7：音频提取使用阻塞式调用 ⚠️

#### 问题位置
`backend/src/core/subtitle_processor.py:65-88`

```python
async def extract_audio(self, video_path: str, audio_path: str):
    """从视频中提取音频"""
    import subprocess
    
    ffmpeg_path = self.tool_manager.get_ffmpeg_path()
    if not ffmpeg_path:
        raise Exception("FFmpeg not found")
    
    cmd = [
        str(ffmpeg_path),
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        audio_path
    ]
    
    result = subprocess.run(cmd, ...)  # ❌ 阻塞调用
```

#### 问题分析
- 使用 `subprocess.run()` 是同步阻塞的
- 在 `async` 函数中应使用异步版本
- 可能阻塞事件循环

#### 建议修复
```python
async def extract_audio(self, video_path: str, audio_path: str):
    """从视频中提取音频"""
    import asyncio
    
    ffmpeg_path = self.tool_manager.get_ffmpeg_path()
    if not ffmpeg_path:
        raise Exception("FFmpeg not found")
    
    cmd = [
        str(ffmpeg_path),
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        audio_path
    ]
    
    # ✅ 使用异步 subprocess
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode('utf-8', errors='ignore') if stderr else 'Unknown error'
        logger.error(f"FFmpeg error: {error_msg}")
        raise Exception(f"Failed to extract audio: {error_msg}")
    
    logger.info(f"Audio extracted: {audio_path}")
```

---

## 📊 问题总结

| 优先级 | 问题 | 影响 | 修复难度 |
|--------|------|------|----------|
| 🔴 高 | 文件选择功能依赖electron API | 功能完全不可用 | 低 |
| 🟡 中 | "下载字幕"和"重试"按钮无功能 | 用户体验差 | 低 |
| 🟡 中 | 烧录字幕"重试"按钮无功能 | 用户体验差 | 低 |
| 🟡 中 | Windows路径转义可能失败 | 烧录功能可能失败 | 中 |
| ⚠️ 低 | subprocess缺少类型转换 | 代码不规范，潜在风险 | 低 |
| ⚠️ 低 | 缺少进度回调机制 | 无法显示实时进度 | 中 |
| ⚠️ 低 | 音频提取使用阻塞调用 | 可能阻塞事件循环 | 低 |

---

## ✅ 正常功能

### 1. 基础架构 ✓
- ✅ 数据库模型完整（SubtitleTask, BurnSubtitleTask）
- ✅ API路由定义完整
- ✅ 前端UI设计良好
- ✅ 任务队列机制
- ✅ WebSocket通知机制

### 2. API完整性 ✓
- ✅ `POST /api/v1/subtitle/generate` - 创建字幕任务
- ✅ `GET /api/v1/subtitle/tasks` - 获取任务列表
- ✅ `DELETE /api/v1/subtitle/tasks/{task_id}` - 删除任务
- ✅ `POST /api/v1/subtitle/burn-subtitle` - 烧录字幕（同步）
- ✅ `POST /api/v1/subtitle/burn-subtitle-task` - 创建烧录任务（异步）
- ✅ `GET /api/v1/subtitle/burn-subtitle-tasks` - 获取烧录任务
- ✅ `DELETE /api/v1/subtitle/burn-subtitle-tasks/{task_id}` - 删除烧录任务

### 3. TauriIntegration映射 ✓
- ✅ `generate_subtitle` → `/api/v1/subtitle/generate`
- ✅ `get_subtitle_tasks` → `/api/v1/subtitle/tasks`
- ✅ `delete_subtitle_task` → `/api/v1/subtitle/tasks/{id}`
- ✅ `burn_subtitle` → `/api/v1/subtitle/burn-subtitle`
- ✅ `create_burn_subtitle_task` → `/api/v1/subtitle/burn-subtitle-task`
- ✅ `get_burn_subtitle_tasks` → `/api/v1/subtitle/burn-subtitle-tasks`
- ✅ `delete_burn_subtitle_task` → `/api/v1/subtitle/burn-subtitle-tasks/{id}`
- ✅ `select_file` → `/api/v1/system/select-file`
- ✅ `save_file` → `/api/v1/system/save-file`
- ✅ `open_folder` → `/api/v1/system/open-folder`

---

## 🎯 修复优先级建议

### 立即修复（高优先级）
1. ✅ **文件选择功能** - 替换为统一的 `invoke` API
2. ✅ **Windows路径转义** - 修复FFmpeg路径问题

### 可选修复（中优先级）
3. ✅ **按钮功能** - 实现"下载字幕"和"重试"功能
4. ✅ **进度回调** - 添加实时进度更新

### 优化建议（低优先级）
5. ⚠️ **异步subprocess** - 使用 `asyncio.create_subprocess_exec`
6. ⚠️ **类型转换** - 显式转换 Path 为 str

---

## 📝 总体评价

**字幕生成与烧录功能架构完整，核心逻辑正常** ⭐⭐⭐⭐

- ✅ 架构设计：完整的任务队列系统
- ✅ API设计：RESTful，职责清晰
- ✅ 前端UI：设计美观，交互友好
- ⚠️ 实现细节：存在一些小问题
- 🔴 文件选择：需要紧急修复

**建议**：
1. 优先修复文件选择功能（影响最大）
2. 修复Windows路径转义（烧录可能失败）
3. 实现缺失的按钮功能（提升用户体验）
4. 添加进度回调（提升用户体验）

---

**检查人员**: AI Assistant  
**检查日期**: 2025-11-01  
**检查状态**: ✅ 完成  
**总体结论**: **架构良好，需修复7个问题**




