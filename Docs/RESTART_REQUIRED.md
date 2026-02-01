# ⚠️ 需要重启应用以应用元数据提取功能

## 问题诊断

通过查看日志文件，我发现：

**当前运行的是旧代码**，新的元数据提取功能还没有生效。

日志中只有：
```
Matched channels video URL
Matched video content type: video/mp4
Detected video: WeChat Video (xWT156)
```

**缺少新功能的日志**：
- ❌ 没有 "Cached metadata from API"（API 元数据已缓存）
- ❌ 没有 "Using cached metadata"（使用缓存的元数据）
- ❌ 没有 "Extracted metadata from headers"（从响应头提取元数据）

## 解决方案

### 步骤 1：停止应用

双击运行：
```
scripts\STOP.bat
```

或者在命令行中：
```cmd
cd scripts
STOP.bat
```

### 步骤 2：重新启动应用

双击运行：
```
scripts\START.bat
```

或者在命令行中：
```cmd
cd scripts
START.bat
```

### 步骤 3：验证新功能

1. **启动捕获**：在前端界面点击"启动捕获"
2. **浏览视频号**：在微信中浏览视频号内容
3. **查看日志**：观察后端日志窗口，应该看到：
   ```
   INFO - Cached metadata from API: title=视频标题, key=...
   INFO - Using cached metadata for video: title=视频标题
   ```
4. **检查前端**：视频列表应该显示：
   - ✅ 视频标题（真实标题，不是 "WeChat Video (xWT156)"）
   - ✅ 缩略图（如果 API 返回了）
   - ✅ 文件大小
   - ✅ 分辨率
   - ✅ 时长

## 新功能说明

### 元数据提取系统

我们实现了一个两阶段的元数据提取系统：

#### 阶段 1：拦截 API 响应
- 自动拦截微信 API 的 JSON 响应
- 提取视频元数据（标题、缩略图、时长、分辨率、文件大小）
- 使用 `encfilekey` 作为键存入内存缓存

#### 阶段 2：关联视频 URL
- 检测到视频 URL 时，从 URL 提取 `encfilekey`
- 查找缓存中的元数据
- 创建包含完整信息的视频对象

### 支持的元数据字段

- **标题**：title, desc, description, videoTitle
- **缩略图**：thumbUrl, cover, coverUrl
- **时长**：duration, videoTime, playDuration
- **分辨率**：自动从 width/height 计算（1080p, 720p 等）
- **文件大小**：size, fileSize, videoSize

### 降级方案

如果缓存中没有元数据（例如，直接访问视频 URL）：
1. 从响应头提取基本信息（Content-Length）
2. 从 URL 参数提取标识（X-snsvideoflag）
3. 生成默认标题（"WeChat Video (xWT156)"）

## 故障排查

### 如果重启后仍然没有元数据

1. **检查日志**：
   - 打开后端日志窗口
   - 查找 "Cached metadata" 或 "Using cached metadata"
   - 如果没有，说明微信 API 响应没有被拦截

2. **可能的原因**：
   - 微信 API 响应在视频 URL 之前到达（正常情况）
   - 微信 API 响应格式变化
   - `encfilekey` 不匹配

3. **调试步骤**：
   - 在微信中**先浏览视频列表**（触发 API 请求）
   - **然后点击播放视频**（触发视频 URL 请求）
   - 这样可以确保 API 响应先被缓存

### 如果缩略图不显示

1. **检查元数据**：查看日志中的 thumbnail 字段
2. **测试 URL**：在浏览器中直接访问缩略图 URL
3. **CORS 问题**：可能需要配置 CORS 代理

## 技术细节

详细的实现说明请查看：
- `backend/VIDEO_METADATA_IMPLEMENTATION.md` - 完整的技术文档
- `backend/src/core/channels/proxy_sniffer.py` - 主要实现代码
- `backend/src/core/channels/video_metadata_extractor.py` - 元数据提取器

## 总结

**重启应用后，前端应该能够显示完整的视频信息，包括标题、缩略图、文件大小、分辨率和时长。**

如果还有问题，请查看后端日志并提供详细信息。
