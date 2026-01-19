"""
平台扫码登录Provider实现

包含各平台的具体扫码登录实现。
"""

from .bilibili import BilibiliQRProvider
from .kuaishou import KuaishouQRProvider
from .weibo import WeiboQRProvider
from .iqiyi import IqiyiQRProvider
from .mango import MangoQRProvider
from .tencent import TencentQRProvider
from .douyin import DouyinQRProvider
from .xiaohongshu import XiaohongshuQRProvider
from .youku import YoukuQRProvider

__all__ = [
    'BilibiliQRProvider',
    'KuaishouQRProvider',
    'WeiboQRProvider',
    'IqiyiQRProvider',
    'MangoQRProvider',
    'TencentQRProvider',
    'DouyinQRProvider',
    'XiaohongshuQRProvider',
    'YoukuQRProvider',
]
