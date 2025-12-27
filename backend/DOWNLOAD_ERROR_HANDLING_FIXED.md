# 下载功能错误处理修复总结

## 修复日期
2025-12-27

## 问题描述
用户报告 YouTube 下载失败时显示英文的原始 yt-dlp 错误，而不是友好的中文提示。

## 根本原因
错误处理分为三层，但每一层都有问题：

### 1. 下载器层（Downloader）
- **GenericDownloader**: 错误处理太简单，只抛出原始英文错误
- **YoutubeDownloader**: 已有完善的友好错误提示（✅ 正常）

### 2. API 层（downloads.py）
- 会覆盖下载器层的友好错误，用简化逻辑重新处理
- YouTube 错误只简单提示"需要代理"，丢失了详细的诊断信息

### 3. 下载流程
- 先用 GenericDownloader 尝试（失败抛出英文错误）
- 失败后才用 YoutubeDownloader（但 API 层已拦截错误）

## 修复内容

### 1. GenericDownloader 错误处理增强
**文件**: `backend/src/core/downloaders/generic_downloader.py`

#### get_video_info() 方法
```python
# 修复前
except Exception as e:
    logger.error(f"Error extracting video info: {e}")
    raise Exception(f"Failed to get video info: {str(e)}")

# 修复后
except Exception as e:
    error_msg = str(e)
    logger.error(f"Error extracting video info: {error_msg}")

    # 检测平台特定错误并提供友好提示
    platform = self._detect_platform(url)

    # YouTube 特殊处理
    if platform == 'youtube':
        if any(keyword in error_msg.lower() for keyword in needs_cookie_keywords):
            friendly_error = "该视频需要登录才能访问。\n\n💡 解决方法：..."
        elif 'failed to extract any player response' in error_msg.lower():
            friendly_error = "YouTube 解析失败：无法提取播放器响应。\n\n💡 可能原因：..."
        else:
            friendly_error = error_msg
    else:
        friendly_error = error_msg

    raise Exception(f"获取视频信息失败: {friendly_error}")
```

#### download_video() 方法
```python
# 同样的友好错误处理逻辑
except Exception as e:
    error_msg = str(e)
    platform = self._detect_platform(url)

    if platform == 'youtube':
        # 检测并转换为友好错误
        ...

    raise Exception(f"下载失败: {friendly_error}")
```

### 2. API 层错误处理优化
**文件**: `backend/src/api/downloads.py`

#### get_video_info 接口
```python
# 修复前
except Exception as e:
    error_msg = str(e)
    detail_msg = error_msg

    # 直接用简单逻辑覆盖下载器的错误
    if 'youtube.com' in request.url.lower():
        detail_msg = "获取 YouTube 视频信息失败。\n\n💡 提示：YouTube 在国内需要代理访问..."

# 修复后
except Exception as e:
    error_msg = str(e)

    # 如果错误已经被下载器处理过，直接使用（保留详细诊断）
    if error_msg.startswith("获取视频信息失败:") or error_msg.startswith("下载失败:"):
        raise HTTPException(status_code=400, detail=error_msg)

    # 其他错误才用 API 层的简化处理
    ...
```

#### start_download 接口
```python
# 同样优先使用下载器的友好错误
except Exception as e:
    error_msg = str(e)

    # 如果错误已经被下载器处理过，直接使用
    if error_msg.startswith("获取视频信息失败:") or error_msg.startswith("下载失败:"):
        raise HTTPException(status_code=400, detail=error_msg)
```

## 修复效果

### 修复前
```
Error getting video info: ERROR: [youtube] DVTRklHhEsU: Failed to extract any player response; please report this issue on https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using yt-dlp -U
```

### 修复后
```
获取视频信息失败: YouTube 解析失败：无法提取播放器响应。

💡 可能原因：
1. YouTube 近期更新了页面/接口
2. 网络/代理不稳定导致播放器接口请求异常
3. 需要配置 PO Token（2025 年新要求）
4. 需要配置 Cookie（部分地区/账号/视频会触发验证）

✅ 建议操作：
1. 安装 JavaScript 运行时（推荐 Deno）
2. 配置 PO Token 环境变量（YTDLP_YOUTUBE_PO_TOKEN）
3. 在「系统设置 → Cookie 管理」中配置 YouTube Cookie
4. 确认代理可用后重试
5. 如仍失败，请更新 yt-dlp 到最新版本

详细错误: [原始错误信息]
```

## 诊断工具检查结果

运行 `diagnose_youtube.py` 显示：
- ✅ yt-dlp 版本：2025.12.8（最新）
- ✅ Node.js 已安装：v25.2.1
- ✅ YouTube 连接测试成功
- ⚠️ 未配置代理（国内需要）
- ⚠️ 未配置 PO Token（建议配置）

## 相关文件

### 修改的文件
1. `backend/src/core/downloaders/generic_downloader.py` - 增强错误处理
2. `backend/src/api/downloads.py` - 优化 API 层错误处理

### 已有的完善错误处理
1. `backend/src/core/downloaders/youtube_downloader.py` - YouTube 专用下载器（已完善）
2. `backend/diagnose_youtube.py` - 诊断工具（帮助用户排查配置问题）

## 测试建议

### 1. 测试无代理情况
```python
# 国内环境测试（无代理）
url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
# 预期：显示友好的中文错误提示
```

### 2. 测试需要登录的视频
```python
# 测试会员或私有视频
url = "https://www.youtube.com/watch?v=xxxxx"
# 预期：提示需要配置 Cookie
```

### 3. 测试其他平台
```python
# 测试 Bilibili, Douyin 等
# 预期：显示平台特定的友好提示
```

## 后续优化建议

1. **添加配置向导**
   - 引导用户安装 JavaScript 运行时
   - 帮助用户配置 PO Token
   - 简化代理设置流程

2. **错误恢复机制**
   - 自动检测并提示安装缺失的依赖
   - 自动重试机制（网络临时故障）

3. **用户反馈**
   - 收集常见错误数据
   - 优化错误提示的准确性

## 注意事项

1. 重启后端服务后修复才会生效
2. 用户仍需要自行配置代理（国内访问 YouTube）
3. PO Token 是可选的，但建议配置以提高成功率
