# 视频元数据提取实现说明

## 概述

实现了一个两阶段的视频元数据提取系统，用于从微信视频号捕获视频的完整信息（标题、缩略图、时长、分辨率、文件大小等）。

## 问题分析

### 原始问题
- 前端显示的视频只有基本信息（URL、简单标题）
- 缺少缩略图、文件大小、分辨率、时长等元数据
- 用户无法有效预览和选择要下载的视频

### 根本原因
视频下载 URL（`finder.video.qq.com/stodownload`）返回的是**视频二进制数据**（HTTP 206 Partial Content），而不是包含元数据的 JSON 响应。真正的元数据存在于**微信 API 的 JSON 响应**中，这些响应在视频播放前就已经被请求。

## 解决方案

### 架构设计

```
微信客户端 → mitmproxy 代理 → 服务器
                ↓
         两阶段拦截：
         1. API 响应（JSON）→ 提取元数据 → 缓存
         2. 视频 URL → 查找缓存 → 关联元数据
```

### 实现细节

#### 1. 元数据缓存系统

在 `VideoSnifferAddon` 类中添加：

```python
# 元数据缓存：存储从 API 响应中提取的元数据
self._metadata_cache: Dict[str, VideoMetadata] = {}
self._metadata_cache_lock = Lock()
```

#### 2. API 响应拦截

新增 `_try_extract_api_metadata()` 方法：

- **触发条件**：
  - Content-Type 包含 "json"
  - 域名是微信相关（weixin.qq.com, qq.com 等）

- **提取逻辑**：
  - 解析 JSON 响应
  - 递归搜索视频元数据字段
  - 提取 `encfilekey` 作为缓存键
  - 存储到内存缓存

- **支持的字段**：
  ```python
  {
      'title': ['title', 'desc', 'description', 'videoTitle', ...],
      'thumbnail': ['thumbUrl', 'cover', 'coverUrl', ...],
      'duration': ['duration', 'videoTime', 'playDuration', ...],
      'width': ['width', 'videoWidth', ...],
      'height': ['height', 'videoHeight', ...],
      'filesize': ['size', 'fileSize', 'videoSize', ...],
  }
  ```

#### 3. 视频 URL 处理

修改 `response()` 方法中的视频检测逻辑：

```python
# 1. 首先尝试拦截 API 响应
self._try_extract_api_metadata(flow)

# 2. 检测视频 URL
if is_video_url:
    # 3. 从缓存中查找元数据
    if 'encfilekey' in query_params:
        cache_key = query_params['encfilekey'][0]
        metadata = self._metadata_cache.get(cache_key)
    
    # 4. 如果缓存中没有，从响应头提取基本信息
    if not metadata:
        metadata = PlatformDetector.extract_metadata_from_response(
            url, headers, b""
        )
    
    # 5. 创建 DetectedVideo 对象
    video = DetectedVideo(
        title=metadata.title if metadata else default_title,
        filesize=metadata.filesize if metadata else None,
        resolution=metadata.resolution if metadata else None,
        duration=metadata.duration if metadata else None,
        thumbnail=metadata.thumbnail if metadata else None,
        ...
    )
```

## 文件修改清单

### 1. `backend/src/core/channels/proxy_sniffer.py`

**新增方法**：
- `_try_extract_api_metadata()` - 拦截并解析 API 响应
- `_parse_wechat_api_response()` - 递归解析 JSON 数据
- `_extract_video_key_from_json()` - 提取视频密钥

**修改方法**：
- `__init__()` - 添加元数据缓存
- `response()` - 集成元数据提取和缓存查找

**新增导入**：
- `VideoMetadata` from models

### 2. `backend/src/core/channels/video_metadata_extractor.py`

**已创建**（备用方案）：
- `VideoMetadataExtractor` 类 - 支持多种提取方式
  - HTTP HEAD 请求
  - JSON 响应解析
  - yt-dlp 集成（可选）

### 3. `backend/tests/test_metadata_extraction.py`

**新增测试**：
- 验证 JSON 解析逻辑
- 测试字段映射
- 验证分辨率计算

## 工作流程

### 正常流程

1. **用户在微信中浏览视频号**
2. **微信请求 API 获取视频列表**
   - 请求：`https://channels.weixin.qq.com/cgi-bin/...`
   - 响应：JSON（包含标题、缩略图、时长等）
   - 代理拦截：提取元数据 → 缓存（key: encfilekey）

3. **用户点击播放视频**
   - 请求：`https://finder.video.qq.com/stodownload?encfilekey=...`
   - 响应：视频二进制数据（206 Partial Content）
   - 代理拦截：
     - 识别为视频 URL
     - 从 URL 提取 encfilekey
     - 查找缓存中的元数据
     - 创建 DetectedVideo 对象（包含完整元数据）

4. **前端显示**
   - 标题：从元数据获取
   - 缩略图：从元数据获取
   - 文件大小：从元数据或响应头获取
   - 分辨率：从元数据计算
   - 时长：从元数据获取

### 降级方案

如果缓存中没有元数据（例如，用户直接访问视频 URL）：

1. 从响应头提取基本信息（Content-Length）
2. 从 URL 参数提取标识（X-snsvideoflag）
3. 生成默认标题（"WeChat Video (xWT158)"）

## 优势

1. **准确性高**：直接从微信 API 获取官方元数据
2. **性能好**：内存缓存，无需额外网络请求
3. **兼容性强**：支持降级方案
4. **可扩展**：易于添加新的元数据字段

## 局限性

1. **缓存生命周期**：仅在代理运行期间有效
2. **顺序依赖**：需要先捕获 API 响应，再捕获视频 URL
3. **内存占用**：缓存会随着视频数量增长

## 未来改进

1. **持久化缓存**：使用 Redis 或文件缓存
2. **异步提取**：对于缓存未命中的情况，异步调用 yt-dlp
3. **智能清理**：定期清理过期的缓存条目
4. **缩略图下载**：自动下载并缓存缩略图
5. **元数据更新**：支持手动刷新元数据

## 测试建议

### 手动测试步骤

1. **启动后端**：
   ```bash
   cd backend
   python src/main.py
   ```

2. **启动前端**：
   ```bash
   cd frontend
   npm run dev
   ```

3. **启动透明代理**：
   - 在前端界面中点击"启动捕获"
   - 确认 WinDivert 驱动已安装

4. **打开微信视频号**：
   - 浏览视频号内容
   - 观察后端日志：
     ```
     INFO - Cached metadata from API: title=视频标题, key=...
     INFO - Using cached metadata for video: title=视频标题
     ```

5. **检查前端显示**：
   - 视频列表应显示完整信息
   - 标题、缩略图、文件大小、分辨率等

### 日志关键词

- `Cached metadata from API` - API 元数据已缓存
- `Using cached metadata` - 使用缓存的元数据
- `Extracted metadata from headers` - 从响应头提取元数据
- `Detected video` - 检测到视频

## 故障排查

### 问题：视频显示但没有元数据

**可能原因**：
1. API 响应在视频 URL 之后到达
2. encfilekey 不匹配
3. JSON 解析失败

**解决方法**：
1. 检查日志中是否有 "Cached metadata" 消息
2. 验证 encfilekey 是否一致
3. 启用 DEBUG 日志查看详细信息

### 问题：缩略图不显示

**可能原因**：
1. 缩略图 URL 无效
2. CORS 问题
3. 字段名称不匹配

**解决方法**：
1. 检查元数据中的 thumbnail 字段
2. 在浏览器中直接访问缩略图 URL
3. 添加更多字段名称到映射表

## 总结

这个实现通过两阶段拦截（API 响应 + 视频 URL）的方式，成功解决了视频元数据提取的问题。系统设计简洁高效，易于维护和扩展。

**关键创新点**：
- 识别到视频 URL 和元数据 API 是分离的
- 使用 encfilekey 作为关联键
- 内存缓存提高性能
- 支持降级方案保证可用性
