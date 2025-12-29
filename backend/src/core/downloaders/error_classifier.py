"""
错误分类模块
用于判断下载错误类型，决定是否需要回退到专用下载器
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 各平台的认证错误关键词
AUTH_ERROR_KEYWORDS = {
    'youtube': [
        'sign in',
        'login required',
        'members-only',
        'private video',
        'this video is private',
        'confirm you\'re not a bot',
        'confirm your age',
        'age-restricted',
        'age restricted',
        'please sign in',
        'video is unavailable',
    ],
    'bilibili': [
        '需要登录',
        '请先登录',
        '大会员',
        '付费',
        '仅限会员',
        '会员专享',
        '充电专属',
        '登录后观看',
        '仅对大会员开放',
    ],
    'douyin': [
        '登录',
        '私密视频',
        '好友可见',
        '仅自己可见',
        '需要验证',
    ],
    'tiktok': [
        'login',
        'private video',
        'friends only',
        'sign in',
    ],
    'xiaohongshu': [
        '登录',
        '私密',
        '仅自己可见',
    ],
    'instagram': [
        'login',
        'sign in',
        'private',
    ],
    'twitter': [
        'login',
        'sign in',
        'protected',
    ],
    'generic': [
        'sign in',
        'login',
        'authentication',
        'unauthorized',
        'members only',
        'private',
    ],
}

# HTTP 状态码相关的认证错误
AUTH_HTTP_CODES = ['401', '403']

# 不可重试的错误关键词（这些错误即使回退也不会成功）
# 注意：'unable to extract' 不在此列表中，因为它可能是认证问题导致的
NON_RETRYABLE_ERROR_KEYWORDS = [
    'video not found',
    'video deleted',
    'video unavailable',
    'video has been removed',
    'video is no longer available',
    '404',
    'not found',
    'unsupported url',
    'no video formats found',
    # 'unable to extract' 已移除 - 可能是认证问题，应尝试回退
    'is not a valid url',
    'invalid url',
    '视频不存在',
    '视频已删除',
    '视频已下架',
    '链接无效',
    '无法找到视频',
    '该视频不存在',
    'this video has been removed',
    'copyright',
    'blocked',
    'geo-restricted',  # 地区限制通常不是认证问题
]


def is_auth_required_error(error_msg: str, platform: str = 'generic') -> bool:
    """
    判断错误是否为认证相关错误（需要登录/会员）
    
    Args:
        error_msg: 错误消息字符串
        platform: 平台名称（youtube, bilibili, douyin 等）
        
    Returns:
        是否为认证错误
    """
    if not error_msg:
        return False
    
    error_lower = error_msg.lower()
    
    # 首先检查是否为不可重试错误（优先级更高）
    if is_non_retryable_error(error_msg):
        return False
    
    # 检查 HTTP 状态码（403 需要结合上下文判断）
    for code in AUTH_HTTP_CODES:
        if code in error_msg:
            # 403 可能是认证问题，也可能是其他问题
            # 如果同时包含认证相关词汇，则认为是认证错误
            if code == '403':
                # 检查是否有认证相关的上下文
                auth_context_words = ['forbidden', 'access denied', 'permission', 'login', 'sign in', '登录', '权限']
                if any(word in error_lower for word in auth_context_words):
                    logger.debug(f"Detected auth error: HTTP {code} with auth context")
                    return True
            elif code == '401':
                logger.debug(f"Detected auth error: HTTP {code}")
                return True
    
    # 获取平台特定的关键词
    platform_keywords = AUTH_ERROR_KEYWORDS.get(platform.lower(), [])
    generic_keywords = AUTH_ERROR_KEYWORDS.get('generic', [])
    
    # 合并关键词列表
    all_keywords = platform_keywords + generic_keywords
    
    # 检查是否包含认证错误关键词
    for keyword in all_keywords:
        if keyword.lower() in error_lower:
            logger.debug(f"Detected auth error: keyword '{keyword}' found in error message")
            return True
    
    return False


def is_non_retryable_error(error_msg: str) -> bool:
    """
    判断错误是否为不可重试错误（即使回退也不会成功）
    
    Args:
        error_msg: 错误消息字符串
        
    Returns:
        是否为不可重试错误
    """
    if not error_msg:
        return False
    
    error_lower = error_msg.lower()
    
    for keyword in NON_RETRYABLE_ERROR_KEYWORDS:
        if keyword.lower() in error_lower:
            logger.debug(f"Detected non-retryable error: keyword '{keyword}' found")
            return True
    
    return False


def classify_error(error_msg: str, platform: str = 'generic') -> str:
    """
    对错误进行分类
    
    Args:
        error_msg: 错误消息字符串
        platform: 平台名称
        
    Returns:
        错误类型: 'auth_required', 'non_retryable', 'unknown'
    """
    if is_non_retryable_error(error_msg):
        return 'non_retryable'
    elif is_auth_required_error(error_msg, platform):
        return 'auth_required'
    else:
        return 'unknown'
