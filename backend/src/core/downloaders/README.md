# 视频下载器模块

## 架构说明

VidFlow 采用模块化的下载器架构，支持针对不同平台进行专门优化。

### 目录结构

```
downloaders/
├── __init__.py                 # 模块入口
├── base_downloader.py          # 基础下载器抽象类
├── downloader_factory.py       # 下载器工厂
├── cache_manager.py            # 视频信息缓存管理器
├── youtube_downloader.py       # YouTube专用下载器
├── bilibili_downloader.py      # Bilibili专用下载器
├── douyin_downloader.py        # 抖音/TikTok专用下载器 ✨ 新增
├── generic_downloader.py       # 通用下载器（后备方案）
└── README.md                   # 本文档
```

## ✨ 最新更新

### v3.1.0 (2025-11)
- ✅ **抖音/TikTok专用下载器** - 支持短链接解析、反爬虫优化
- ✅ **视频信息缓存** - 24小时缓存，大幅提升性能
- ✅ **文件名清理** - 自动移除非法字符，支持长文件名截断
- ✅ **断点续传支持** - yt-dlp内置功能，自动恢复中断的下载

## 如何添加新平台支持

### 1. 创建新的下载器类

在 `downloaders/` 目录下创建新文件，例如 `douyin_downloader.py`:

```python
"""
抖音专用下载器
"""
from .base_downloader import BaseDownloader
import asyncio
import logging

logger = logging.getLogger(__name__)


class DouyinDownloader(BaseDownloader):
    """抖音专用下载器"""
    
    def __init__(self, output_dir: str = "./data/downloads"):
        super().__init__(output_dir)
        self.platform_name = "douyin"
    
    @staticmethod
    def supports_url(url: str) -> bool:
        """检查是否支持该URL"""
        url_lower = url.lower()
        return 'douyin.com' in url_lower or 'tiktok.com' in url_lower
    
    async def get_video_info(self, url: str):
        """获取视频信息"""
        # 实现抖音特定的信息提取逻辑
        pass
    
    async def download_video(self, url: str, **kwargs):
        """下载视频"""
        # 实现抖音特定的下载逻辑
        pass
```

### 2. 注册新下载器

在 `downloader_factory.py` 中注册：

```python
from .douyin_downloader import DouyinDownloader

class DownloaderFactory:
    _downloaders = [
        YoutubeDownloader,
        BilibiliDownloader,
        DouyinDownloader,  # 添加新下载器
        # ...
    ]
```

### 3. 更新 `__init__.py`

```python
from .douyin_downloader import DouyinDownloader

__all__ = [
    'BaseDownloader',
    'DownloaderFactory',
    'YoutubeDownloader',
    'BilibiliDownloader',
    'DouyinDownloader',  # 导出新下载器
    'GenericDownloader',
]
```

## 平台特定优化建议

### YouTube
- 使用多个客户端尝试（android, web）
- 启用并发分片下载
- 合理设置重试次数

### Bilibili
- 添加 Referer 头
- 支持多P视频下载
- 考虑添加 Cookie 支持以下载高清视频

### 国内平台（抖音、快手等）
- 设置合适的 User-Agent
- 可能需要处理短链接重定向
- 注意反爬虫机制

### 其他平台
- 参考 yt-dlp 的支持情况
- 根据需要自定义 HTTP 头
- 处理特殊的认证机制

## 工作流程

1. 用户提交下载链接
2. `DownloaderFactory` 检测平台类型
3. 遍历已注册的下载器，找到支持该URL的下载器
4. 如果没有专用下载器，使用 `GenericDownloader`
5. 调用下载器的方法执行任务

## 测试建议

每个新增的下载器应该测试：

- ✅ URL 识别准确性
- ✅ 视频信息提取
- ✅ 不同画质下载
- ✅ 进度回调
- ✅ 错误处理
- ✅ 特殊情况（多P、播放列表等）

## 支持的平台

### 专用下载器（优化支持）
| 平台 | 状态 | 特性 |
|------|------|------|
| YouTube | ✅ | 多客户端、并发分片、4K支持 |
| Bilibili | ✅ | Referer头、多P视频、Cookie登录 |
| 抖音/TikTok | ✅ | 短链接解析、无水印、反爬虫 |

### 通用支持（通过yt-dlp）
支持 **1000+ 网站**，包括但不限于：
- 国内：微信视频号、快手、小红书、腾讯视频、优酷、爱奇艺
- 国外：Twitter/X、Instagram、Facebook、Vimeo、Dailymotion
- 更多平台请参考 [yt-dlp支持列表](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

## 性能优化 ⚡

### 已实现
- ✅ 异步 I/O（asyncio + await）
- ✅ 并发分片下载（yt-dlp内置）
- ✅ 断点续传（自动恢复）
- ✅ **视频信息缓存**（24小时，减少90%重复请求）
- ✅ 连接池复用（yt-dlp内置）
- ✅ 内存+文件双层缓存

### 缓存性能
```python
# 使用缓存前
获取视频信息：2-5秒
重复获取：2-5秒

# 使用缓存后
首次获取：2-5秒
重复获取：< 10ms（内存缓存）或 < 50ms（文件缓存）
性能提升：200-500倍
```

## 注意事项

1. **遵守平台规则**: 不要绕过付费内容保护
2. **尊重版权**: 仅供个人学习使用
3. **控制并发**: 避免对平台造成过大压力
4. **用户隐私**: 不收集或传输用户信息
5. **错误处理**: 提供友好的错误提示
