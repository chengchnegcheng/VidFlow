"""
智能下载管理器
实现自动回退策略：默认使用通用下载器，认证错误时回退到专用下载器
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .downloader_factory import DownloaderFactory
from .error_classifier import is_auth_required_error, is_non_retryable_error, classify_error, get_platform_extractor_issue
from .cookie_manager import (
    get_cookie_path_for_platform,
    has_cookie_for_platform,
    create_friendly_cookie_error,
    get_platform_display_name,
)
from .proxy_config import get_proxy_url, disable_proxy_temporarily, enable_proxy

logger = logging.getLogger(__name__)


def is_bot_detection_error(error_msg: str) -> bool:
    """
    检查是否是 bot 检测错误（可能由代理导致）
    
    Args:
        error_msg: 错误信息
        
    Returns:
        是否是 bot 检测错误
    """
    bot_keywords = [
        "sign in to confirm you're not a bot",
        "confirm you're not a bot",
        "sign in to confirm",
        "please sign in",
        "http error 403",
        # 中文关键词（YouTube 专用下载器返回的友好错误信息）
        "检测到机器人",
        "机器人行为",
        "需要验证身份",
        "po token",
    ]
    error_lower = error_msg.lower()
    return any(keyword in error_lower for keyword in bot_keywords)


def is_ssl_proxy_error(error_msg: str) -> bool:
    """
    检查是否是代理导致的 SSL 错误
    
    Args:
        error_msg: 错误信息
        
    Returns:
        是否是 SSL 代理错误
    """
    ssl_keywords = [
        "ssl: unexpected_eof_while_reading",
        "eof occurred in violation of protocol",
        "ssl: certificate_verify_failed",
        "ssl handshake",
        "connection reset by peer",
        "connection aborted",
    ]
    error_lower = error_msg.lower()
    return any(keyword in error_lower for keyword in ssl_keywords)


class SmartDownloadManager:
    """
    智能下载管理器
    
    实现自动回退策略：
    1. 默认使用通用下载器（无 Cookie）
    2. 认证错误时自动回退到专用下载器（带 Cookie）
    3. 非认证错误直接报错，不浪费时间重试
    """
    
    # 优先使用专用下载器的平台（这些平台的 yt-dlp 提取器不稳定或需要特殊处理）
    PREFER_SPECIALIZED_PLATFORMS = ['iqiyi', 'douyin', 'tiktok']
    
    def __init__(self, output_dir: str = None):
        # 如果没有指定输出目录，使用系统默认下载路径
        if output_dir is None:
            from src.core.config_manager import get_default_download_path
            output_dir = get_default_download_path()
        self.output_dir = output_dir
    
    async def get_info_with_fallback(self, url: str) -> Dict[str, Any]:
        """
        获取视频信息，支持智能回退
        
        Args:
            url: 视频链接
            
        Returns:
            视频信息字典，包含额外字段：
            - downloader_used: 使用的下载器名称
            - fallback_used: 是否使用了回退
            - fallback_reason: 回退原因（如果有）
        """
        platform = DownloaderFactory.detect_platform(url)
        logger.info(f"[SmartDownload] Getting info for URL: {url}, platform: {platform}")
        
        # 检查是否有系统代理（用于后续的无代理重试）
        current_proxy = get_proxy_url()
        
        # 🔥 优先使用专用下载器的情况：
        # 1. 用户已配置该平台的 Cookie
        # 2. 该平台在 PREFER_SPECIALIZED_PLATFORMS 列表中（yt-dlp 提取器不稳定）
        use_specialized_first = has_cookie_for_platform(platform) or platform in self.PREFER_SPECIALIZED_PLATFORMS
        
        if use_specialized_first:
            reason = "Cookie configured" if has_cookie_for_platform(platform) else "platform prefers specialized"
            logger.info(f"[SmartDownload] Using specialized downloader first for {platform} ({reason})")
            specialized = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
            try:
                result = await specialized.get_video_info(url)
                result['downloader_used'] = specialized.platform_name
                result['fallback_used'] = False
                result['fallback_reason'] = None
                logger.info(f"[SmartDownload] Specialized downloader succeeded")
                return result
            except Exception as e:
                logger.warning(f"[SmartDownload] Specialized downloader failed: {str(e)[:200]}, falling back to generic...")
                # 专用下载器失败，继续尝试通用下载器
        
        # YouTube 特殊处理：代理更容易触发 bot 检测，优先尝试直连
        # 对于其他平台（如国内平台），保持原有逻辑
        youtube_no_proxy_first = platform == 'youtube' and current_proxy
        
        if youtube_no_proxy_first:
            logger.info(f"[SmartDownload] YouTube detected with proxy, trying direct connection first...")
            try:
                disable_proxy_temporarily()
                generic_no_proxy = DownloaderFactory.get_generic_downloader(self.output_dir)
                result = await generic_no_proxy.get_video_info(url)
                enable_proxy()
                
                result['downloader_used'] = 'generic_no_proxy'
                result['fallback_used'] = False
                result['fallback_reason'] = None
                logger.info(f"[SmartDownload] YouTube direct connection succeeded")
                return result
            except Exception as e:
                enable_proxy()
                logger.warning(f"[SmartDownload] YouTube direct connection failed: {str(e)[:200]}, will try with proxy...")
        
        # Step 1: 尝试通用下载器（无 Cookie）
        generic = DownloaderFactory.get_generic_downloader(self.output_dir)
        generic_error = None
        
        try:
            logger.info(f"[SmartDownload] Trying GenericDownloader (no cookie)...")
            result = await generic.get_video_info(url)
            
            # 成功，添加元信息
            result['downloader_used'] = 'generic'
            result['fallback_used'] = False
            result['fallback_reason'] = None
            logger.info(f"[SmartDownload] GenericDownloader succeeded")
            return result
            
        except Exception as e:
            generic_error = e
            logger.warning(f"[SmartDownload] GenericDownloader failed: {str(e)[:200]}")
        
        # Step 1.5: 如果是 bot 检测错误或 SSL 错误且有代理，尝试不使用代理重试
        # （对于 YouTube，如果上面已经尝试过直连，这里跳过）
        error_msg = str(generic_error)
        should_retry_without_proxy = (
            current_proxy and 
            not youtube_no_proxy_first and  # YouTube 已经在上面尝试过直连了
            (is_bot_detection_error(error_msg) or is_ssl_proxy_error(error_msg))
        )
        
        if should_retry_without_proxy:
            retry_reason = "Bot detection" if is_bot_detection_error(error_msg) else "SSL error"
            logger.info(f"[SmartDownload] {retry_reason} with proxy ({current_proxy}), trying without proxy...")
            try:
                # 临时禁用代理
                disable_proxy_temporarily()
                
                # 创建新的下载器实例（不使用代理）
                generic_no_proxy = DownloaderFactory.get_generic_downloader(self.output_dir)
                result = await generic_no_proxy.get_video_info(url)
                
                # 恢复代理
                enable_proxy()
                
                # 成功，添加元信息
                result['downloader_used'] = 'generic_no_proxy'
                result['fallback_used'] = True
                result['fallback_reason'] = f'{retry_reason} bypassed by disabling proxy'
                logger.info(f"[SmartDownload] GenericDownloader succeeded without proxy")
                return result
                
            except Exception as e2:
                # 恢复代理
                enable_proxy()
                logger.warning(f"[SmartDownload] GenericDownloader without proxy also failed: {str(e2)[:200]}")
                # 继续使用原来的错误进行后续处理
        
        # Step 2: 判断是否需要回退
        error_type = classify_error(error_msg, platform)
        
        if error_type == 'non_retryable':
            # 不可重试错误，直接报错
            logger.info(f"[SmartDownload] Non-retryable error, not falling back")
            raise generic_error
        
        if error_type != 'auth_required':
            # 未知错误，尝试回退（可能是网络问题等）
            logger.info(f"[SmartDownload] Unknown error type, attempting fallback anyway")
        
        # Step 3: 先尝试专用下载器（即使没有 Cookie，专用下载器可能有更好的处理逻辑）
        # 例如 YouTube 专用下载器有 player_client 回退机制
        specialized = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
        specialized_error = None
        
        try:
            logger.info(f"[SmartDownload] Trying {specialized.platform_name} downloader...")
            result = await specialized.get_video_info(url)
            
            # 成功，添加元信息
            result['downloader_used'] = specialized.platform_name
            result['fallback_used'] = True
            result['fallback_reason'] = error_msg[:200]  # 截断过长的错误信息
            logger.info(f"[SmartDownload] Specialized downloader succeeded after fallback")
            return result
            
        except Exception as e:
            specialized_error = e
            logger.warning(f"[SmartDownload] Specialized downloader also failed: {str(e)[:200]}")
        
        # Step 3.5: 如果专用下载器也遇到 SSL 错误或 bot 检测错误，尝试禁用代理重试
        specialized_error_msg = str(specialized_error)
        should_retry_specialized_without_proxy = current_proxy and (is_ssl_proxy_error(specialized_error_msg) or is_bot_detection_error(specialized_error_msg))
        
        if should_retry_specialized_without_proxy:
            retry_reason = "Bot detection" if is_bot_detection_error(specialized_error_msg) else "SSL error"
            logger.info(f"[SmartDownload] {retry_reason} in specialized downloader, trying without proxy...")
            try:
                disable_proxy_temporarily()
                
                # 重新创建专用下载器（不使用代理）
                specialized_no_proxy = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
                result = await specialized_no_proxy.get_video_info(url)
                
                enable_proxy()
                
                result['downloader_used'] = f'{specialized.platform_name}_no_proxy'
                result['fallback_used'] = True
                result['fallback_reason'] = 'SSL error bypassed by disabling proxy'
                logger.info(f"[SmartDownload] Specialized downloader succeeded without proxy")
                return result
                
            except Exception as e3:
                enable_proxy()
                logger.warning(f"[SmartDownload] Specialized downloader without proxy also failed: {str(e3)[:200]}")
                # 使用原来的错误继续
        
        # Step 4: 专用下载器也失败，检查是否需要 Cookie
        
        # 如果是认证错误且没有配置 Cookie，提示用户配置
        if error_type == 'auth_required' or classify_error(specialized_error_msg, platform) == 'auth_required':
            if not has_cookie_for_platform(platform):
                friendly_error = create_friendly_cookie_error(platform, specialized_error_msg)
                logger.info(f"[SmartDownload] Cookie not configured for {platform}, auth required")
                raise Exception(friendly_error)
        
        # 返回综合错误
        logger.error(f"[SmartDownload] All downloaders failed")
        raise Exception(
            f"下载失败。\n\n"
            f"🔹 通用下载器错误:\n{str(generic_error)[:300]}\n\n"
            f"🔹 专用下载器错误:\n{str(specialized_error)[:300]}"
        )
    
    async def download_with_fallback(
        self,
        url: str,
        quality: str = "best",
        output_path: Optional[str] = None,
        format_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        下载视频，支持智能回退
        
        Args:
            url: 视频链接
            quality: 画质选择
            output_path: 输出路径
            format_id: 格式ID
            progress_callback: 进度回调
            task_id: 任务ID
            **kwargs: 其他参数
            
        Returns:
            下载结果字典，包含额外字段：
            - downloader_used: 使用的下载器名称
            - fallback_used: 是否使用了回退
            - fallback_reason: 回退原因（如果有）
        """
        platform = DownloaderFactory.detect_platform(url)
        logger.info(f"[SmartDownload] Downloading URL: {url}, platform: {platform}, quality: {quality}")
        
        # 检查是否有系统代理（用于后续的无代理重试）
        current_proxy = get_proxy_url()
        
        # 🔥 优先使用专用下载器的情况：
        # 1. 用户已配置该平台的 Cookie
        # 2. 该平台在 PREFER_SPECIALIZED_PLATFORMS 列表中（yt-dlp 提取器不稳定）
        use_specialized_first = has_cookie_for_platform(platform) or platform in self.PREFER_SPECIALIZED_PLATFORMS
        
        if use_specialized_first:
            reason = "Cookie configured" if has_cookie_for_platform(platform) else "platform prefers specialized"
            logger.info(f"[SmartDownload] Using specialized downloader first for {platform} ({reason})")
            specialized = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
            
            # 通知用户正在使用专用下载器
            if progress_callback and task_id:
                platform_name = get_platform_display_name(platform)
                await progress_callback({
                    'task_id': task_id,
                    'status': 'info',
                    'message': f'使用 {platform_name} 专用下载器...'
                })
            
            try:
                result = await specialized.download_video(
                    url=url,
                    quality=quality,
                    output_path=output_path,
                    format_id=format_id,
                    progress_callback=progress_callback,
                    task_id=task_id,
                    **kwargs
                )
                result['downloader_used'] = specialized.platform_name
                result['fallback_used'] = False
                result['fallback_reason'] = None
                logger.info(f"[SmartDownload] Specialized downloader download succeeded")
                return result
            except Exception as e:
                logger.warning(f"[SmartDownload] Specialized downloader failed: {str(e)[:200]}, falling back to generic...")
                # 专用下载器失败，继续尝试通用下载器
        
        # YouTube 特殊处理：代理更容易触发 bot 检测，优先尝试直连
        youtube_no_proxy_first = platform == 'youtube' and current_proxy
        
        if youtube_no_proxy_first:
            logger.info(f"[SmartDownload] YouTube detected with proxy, trying direct download first...")
            try:
                disable_proxy_temporarily()
                generic_no_proxy = DownloaderFactory.get_generic_downloader(self.output_dir)
                result = await generic_no_proxy.download_video(
                    url=url,
                    quality=quality,
                    output_path=output_path,
                    format_id=format_id,
                    progress_callback=progress_callback,
                    task_id=task_id,
                    **kwargs
                )
                enable_proxy()
                
                result['downloader_used'] = 'generic_no_proxy'
                result['fallback_used'] = False
                result['fallback_reason'] = None
                logger.info(f"[SmartDownload] YouTube direct download succeeded")
                return result
            except Exception as e:
                enable_proxy()
                logger.warning(f"[SmartDownload] YouTube direct download failed: {str(e)[:200]}, will try with proxy...")
        
        # Step 1: 尝试通用下载器（无 Cookie）
        generic = DownloaderFactory.get_generic_downloader(self.output_dir)
        generic_error = None
        
        try:
            logger.info(f"[SmartDownload] Trying GenericDownloader (no cookie)...")
            result = await generic.download_video(
                url=url,
                quality=quality,
                output_path=output_path,
                format_id=format_id,
                progress_callback=progress_callback,
                task_id=task_id,
                **kwargs
            )
            
            # 成功，添加元信息
            result['downloader_used'] = 'generic'
            result['fallback_used'] = False
            result['fallback_reason'] = None
            logger.info(f"[SmartDownload] GenericDownloader download succeeded")
            return result
            
        except Exception as e:
            generic_error = e
            logger.warning(f"[SmartDownload] GenericDownloader download failed: {str(e)[:200]}")
        
        # Step 1.5: 如果是 bot 检测错误或 SSL 错误且有代理，尝试不使用代理重试
        # （对于 YouTube，如果上面已经尝试过直连，这里跳过）
        error_msg = str(generic_error)
        should_retry_without_proxy = (
            current_proxy and 
            not youtube_no_proxy_first and
            (is_bot_detection_error(error_msg) or is_ssl_proxy_error(error_msg))
        )
        
        if should_retry_without_proxy:
            retry_reason = "Bot detection" if is_bot_detection_error(error_msg) else "SSL error"
            logger.info(f"[SmartDownload] {retry_reason} with proxy ({current_proxy}), trying download without proxy...")
            try:
                # 临时禁用代理
                disable_proxy_temporarily()
                
                # 创建新的下载器实例（不使用代理）
                generic_no_proxy = DownloaderFactory.get_generic_downloader(self.output_dir)
                result = await generic_no_proxy.download_video(
                    url=url,
                    quality=quality,
                    output_path=output_path,
                    format_id=format_id,
                    progress_callback=progress_callback,
                    task_id=task_id,
                    **kwargs
                )
                
                # 恢复代理
                enable_proxy()
                
                # 成功，添加元信息
                result['downloader_used'] = 'generic_no_proxy'
                result['fallback_used'] = True
                result['fallback_reason'] = f'{retry_reason} bypassed by disabling proxy'
                logger.info(f"[SmartDownload] GenericDownloader download succeeded without proxy")
                return result
                
            except Exception as e2:
                # 恢复代理
                enable_proxy()
                logger.warning(f"[SmartDownload] GenericDownloader without proxy also failed: {str(e2)[:200]}")
                # 继续使用原来的错误进行后续处理
        
        # Step 2: 判断是否需要回退
        error_type = classify_error(error_msg, platform)
        
        if error_type == 'non_retryable':
            # 不可重试错误，直接报错
            logger.info(f"[SmartDownload] Non-retryable error, not falling back")
            if progress_callback and task_id:
                await progress_callback({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(generic_error)
                })
            raise generic_error
        
        if error_type != 'auth_required':
            # 未知错误，尝试回退（可能是网络问题等）
            logger.info(f"[SmartDownload] Unknown error type, attempting fallback anyway")
        
        # Step 3: 先尝试专用下载器（即使没有 Cookie，专用下载器可能有更好的处理逻辑）
        # 例如 YouTube 专用下载器有 player_client 回退机制，可以处理公开视频
        specialized = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
        specialized_error = None
        
        # 通知用户正在回退
        if progress_callback and task_id:
            platform_name = get_platform_display_name(platform)
            await progress_callback({
                'task_id': task_id,
                'status': 'fallback',
                'message': f'正在使用 {platform_name} 专用下载器重试...'
            })
        
        try:
            logger.info(f"[SmartDownload] Trying {specialized.platform_name} downloader...")
            result = await specialized.download_video(
                url=url,
                quality=quality,
                output_path=output_path,
                format_id=format_id,
                progress_callback=progress_callback,
                task_id=task_id,
                **kwargs
            )
            
            # 成功，添加元信息
            result['downloader_used'] = specialized.platform_name
            result['fallback_used'] = True
            result['fallback_reason'] = error_msg[:200]
            logger.info(f"[SmartDownload] Specialized downloader download succeeded after fallback")
            return result
            
        except Exception as e:
            specialized_error = e
            logger.warning(f"[SmartDownload] Specialized downloader also failed: {str(e)[:200]}")
        
        # Step 3.5: 如果专用下载器也遇到 SSL 错误或 bot 检测错误，尝试禁用代理重试
        specialized_error_msg = str(specialized_error)
        should_retry_specialized_without_proxy = current_proxy and (is_ssl_proxy_error(specialized_error_msg) or is_bot_detection_error(specialized_error_msg))
        
        if should_retry_specialized_without_proxy:
            retry_reason = "Bot detection" if is_bot_detection_error(specialized_error_msg) else "SSL error"
            logger.info(f"[SmartDownload] {retry_reason} in specialized downloader, trying download without proxy...")
            try:
                disable_proxy_temporarily()
                
                # 通知用户
                if progress_callback and task_id:
                    await progress_callback({
                        'task_id': task_id,
                        'status': 'fallback',
                        'message': f'检测到代理{retry_reason}错误，正在禁用代理重试...'
                    })
                
                # 重新创建专用下载器（不使用代理）
                specialized_no_proxy = DownloaderFactory.get_specialized_downloader(url, self.output_dir)
                result = await specialized_no_proxy.download_video(
                    url=url,
                    quality=quality,
                    output_path=output_path,
                    format_id=format_id,
                    progress_callback=progress_callback,
                    task_id=task_id,
                    **kwargs
                )
                
                enable_proxy()
                
                result['downloader_used'] = f'{specialized.platform_name}_no_proxy'
                result['fallback_used'] = True
                result['fallback_reason'] = f'{retry_reason} bypassed by disabling proxy'
                logger.info(f"[SmartDownload] Specialized downloader download succeeded without proxy")
                return result
                
            except Exception as e3:
                enable_proxy()
                logger.warning(f"[SmartDownload] Specialized downloader without proxy also failed: {str(e3)[:200]}")
                # 使用原来的错误继续
        
        # Step 4: 专用下载器也失败，检查是否需要 Cookie
        
        # 如果是认证错误且没有配置 Cookie，提示用户配置
        if error_type == 'auth_required' or classify_error(specialized_error_msg, platform) == 'auth_required':
            if not has_cookie_for_platform(platform):
                friendly_error = create_friendly_cookie_error(platform, specialized_error_msg)
                logger.info(f"[SmartDownload] Cookie not configured for {platform}, auth required")
                if progress_callback and task_id:
                    await progress_callback({
                        'task_id': task_id,
                        'status': 'error',
                        'error': friendly_error
                    })
                raise Exception(friendly_error)
        
        # 返回综合错误
        logger.error(f"[SmartDownload] All downloaders failed")
        combined_error = (
            f"下载失败。\n\n"
            f"🔹 通用下载器错误:\n{str(generic_error)[:300]}\n\n"
            f"🔹 专用下载器错误:\n{str(specialized_error)[:300]}"
        )
        if progress_callback and task_id:
            await progress_callback({
                'task_id': task_id,
                'status': 'error',
                'error': combined_error
            })
        raise Exception(combined_error)


# 全局单例
_smart_manager: Optional[SmartDownloadManager] = None


def get_smart_download_manager(output_dir: str = None) -> SmartDownloadManager:
    """获取智能下载管理器单例"""
    global _smart_manager
    if _smart_manager is None:
        _smart_manager = SmartDownloadManager(output_dir)
    return _smart_manager
