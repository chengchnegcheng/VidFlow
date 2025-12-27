"""
下载速率限制器
用于防止触发平台的速率限制和 Bot 检测
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """下载速率限制器"""

    def __init__(self):
        """初始化速率限制器"""
        self.request_counts: Dict[str, list] = defaultdict(list)

        # 平台速率限制配置（请求数, 时间窗口（秒））
        self.limits = {
            # YouTube 限制（基于官方文档和社区经验）
            'youtube_guest': (300, 3600),      # 访客：300次/小时
            'youtube_account': (2000, 3600),   # 账号：2000次/小时

            # Bilibili 限制（保守估计）
            'bilibili_guest': (100, 3600),     # 访客：100次/小时
            'bilibili_account': (500, 3600),   # 账号：500次/小时

            # 抖音/TikTok 限制（非常严格）
            'douyin_guest': (50, 3600),        # 访客：50次/小时
            'douyin_account': (200, 3600),     # 账号：200次/小时
            'tiktok_guest': (50, 3600),
            'tiktok_account': (200, 3600),

            # 小红书限制
            'xiaohongshu_guest': (60, 3600),
            'xiaohongshu_account': (300, 3600),

            # Twitter/Instagram（保守）
            'twitter_guest': (100, 3600),
            'twitter_account': (500, 3600),
            'instagram_guest': (100, 3600),
            'instagram_account': (500, 3600),

            # Vimeo 限制（相对宽松）
            'vimeo_guest': (200, 3600),        # 访客：200次/小时
            'vimeo_account': (1000, 3600),     # 账号：1000次/小时

            # Facebook 限制
            'facebook_guest': (100, 3600),
            'facebook_account': (500, 3600),

            # Dailymotion 限制
            'dailymotion_guest': (150, 3600),
            'dailymotion_account': (600, 3600),

            # 通用默认限制
            'default_guest': (100, 3600),
            'default_account': (500, 3600),
        }

        # 警告阈值（达到限制的百分比）
        self.warning_threshold = 0.8  # 80%

    def get_limit_key(self, platform: str, has_cookie: bool = False) -> str:
        """
        获取限制键

        Args:
            platform: 平台名称
            has_cookie: 是否有登录 Cookie

        Returns:
            str: 限制键
        """
        account_type = 'account' if has_cookie else 'guest'
        key = f"{platform}_{account_type}"

        # 如果没有特定平台的限制，使用默认值
        if key not in self.limits:
            key = f"default_{account_type}"

        return key

    def get_limit_info(self, platform: str, has_cookie: bool = False) -> Tuple[int, int]:
        """
        获取限制信息

        Args:
            platform: 平台名称
            has_cookie: 是否有登录 Cookie

        Returns:
            Tuple[int, int]: (限制次数, 时间窗口（秒）)
        """
        key = self.get_limit_key(platform, has_cookie)
        return self.limits.get(key, (100, 3600))

    async def wait_if_needed(self, platform: str, has_cookie: bool = False) -> Dict[str, any]:
        """
        如果达到速率限制则等待

        Args:
            platform: 平台名称
            has_cookie: 是否有登录 Cookie

        Returns:
            dict: {
                'waited': bool,         # 是否等待了
                'wait_time': float,     # 等待时间（秒）
                'remaining': int,       # 剩余可用次数
                'limit': int,           # 总限制次数
                'warning': str,         # 警告信息（如果接近限制）
            }
        """
        key = self.get_limit_key(platform, has_cookie)
        limit, window = self.limits.get(key, (100, 3600))

        now = datetime.now()
        cutoff = now - timedelta(seconds=window)

        # 清理过期记录
        self.request_counts[key] = [
            t for t in self.request_counts[key] if t > cutoff
        ]

        current_count = len(self.request_counts[key])
        remaining = limit - current_count

        result = {
            'waited': False,
            'wait_time': 0,
            'remaining': remaining,
            'limit': limit,
            'warning': '',
        }

        # 检查是否达到限制
        if current_count >= limit:
            # 计算需要等待的时间（等到最早的请求过期）
            earliest_request = self.request_counts[key][0]
            wait_time = (earliest_request - cutoff).total_seconds() + 1

            logger.warning(
                f"达到 {platform} 速率限制 ({current_count}/{limit})，"
                f"等待 {wait_time:.0f} 秒"
            )

            result['waited'] = True
            result['wait_time'] = wait_time

            await asyncio.sleep(wait_time)

            # 重新清理过期记录
            now = datetime.now()
            cutoff = now - timedelta(seconds=window)
            self.request_counts[key] = [
                t for t in self.request_counts[key] if t > cutoff
            ]

            result['remaining'] = limit - len(self.request_counts[key])

        # 检查是否接近限制（警告）
        elif current_count >= limit * self.warning_threshold:
            percentage = (current_count / limit) * 100
            result['warning'] = (
                f"警告: {platform} 请求次数已达 {percentage:.0f}% "
                f"({current_count}/{limit})，接近速率限制"
            )
            logger.warning(result['warning'])

        # 记录本次请求
        self.request_counts[key].append(now)

        return result

    def get_current_usage(self, platform: str, has_cookie: bool = False) -> Dict[str, any]:
        """
        获取当前使用情况

        Args:
            platform: 平台名称
            has_cookie: 是否有登录 Cookie

        Returns:
            dict: {
                'platform': str,        # 平台名称
                'current': int,         # 当前请求数
                'limit': int,           # 限制数
                'remaining': int,       # 剩余可用次数
                'percentage': float,    # 使用百分比
                'window': int,          # 时间窗口（秒）
                'has_cookie': bool,     # 是否有 Cookie
            }
        """
        key = self.get_limit_key(platform, has_cookie)
        limit, window = self.limits.get(key, (100, 3600))

        now = datetime.now()
        cutoff = now - timedelta(seconds=window)

        # 清理过期记录
        self.request_counts[key] = [
            t for t in self.request_counts[key] if t > cutoff
        ]

        current_count = len(self.request_counts[key])
        remaining = limit - current_count
        percentage = (current_count / limit) * 100 if limit > 0 else 0

        return {
            'platform': platform,
            'current': current_count,
            'limit': limit,
            'remaining': remaining,
            'percentage': percentage,
            'window': window,
            'has_cookie': has_cookie,
        }

    def reset_platform(self, platform: str, has_cookie: bool = False):
        """
        重置平台的速率限制计数器

        Args:
            platform: 平台名称
            has_cookie: 是否有 Cookie
        """
        key = self.get_limit_key(platform, has_cookie)
        self.request_counts[key] = []
        logger.info(f"已重置 {platform} 的速率限制计数器")

    def reset_all(self):
        """重置所有平台的速率限制计数器"""
        self.request_counts.clear()
        logger.info("已重置所有平台的速率限制计数器")

    def get_all_usage(self) -> Dict[str, Dict]:
        """
        获取所有平台的使用情况

        Returns:
            dict: {key: usage_info}
        """
        result = {}

        # 获取所有有记录的平台
        for key in self.request_counts.keys():
            # 解析 key（格式：platform_type）
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                platform, account_type = parts
                has_cookie = account_type == 'account'
                result[key] = self.get_current_usage(platform, has_cookie)

        return result

    def get_ip_rotation_guide(self, platform: str) -> str:
        """
        获取 IP 轮换建议

        Args:
            platform: 平台名称

        Returns:
            str: IP 轮换指南
        """
        guides = {
            'youtube': '''
如果频繁遇到 "Sign in to confirm you're not a bot" 错误：

1. 切换网络：
   - 使用移动数据网络（手机热点）
   - 切换到不同的 WiFi 网络
   - 使用 VPN 更换 IP 地址

2. 等待恢复：
   - 通常 1-2 小时后会自动解除限制
   - 严重情况可能需要 24 小时

3. 配置 Cookie：
   - 使用已登录账号的 Cookie 可提高限额
   - 账号限额：2000 次/小时（vs 访客 300 次/小时）

4. 降低请求频率：
   - 在多个视频下载之间增加延迟
   - 避免短时间内大量请求
''',
            'bilibili': '''
B站速率限制建议：

1. 使用账号 Cookie：
   - 提高下载限额
   - 解锁高清画质（1080P+）

2. 避免频繁请求：
   - 单个 IP 每小时不超过 100 次请求
   - 请求间隔至少 1-2 秒

3. 遇到限制时：
   - 等待 30-60 分钟
   - 或切换网络/IP
''',
            'douyin': '''
抖音速率限制（最严格）：

1. 强烈建议使用 Cookie：
   - 抖音对访客请求限制非常严格
   - 使用账号 Cookie 可显著提高成功率

2. 降低请求频率：
   - 每次请求间隔至少 3-5 秒
   - 避免批量下载

3. IP 轮换：
   - 如遇到频繁失败，必须更换 IP
   - 使用移动网络（4G/5G）效果较好

4. 短链接解析：
   - 短链接 (v.douyin.com) 也算请求
   - 建议缓存已解析的链接
''',
        }

        return guides.get(platform, '''
通用速率限制建议：

1. 配置 Cookie（如支持）
2. 降低请求频率
3. 遇到限制时等待或切换 IP
4. 使用代理服务（如需要）
''')


# 全局单例
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    获取全局速率限制器实例

    Returns:
        RateLimiter: 限制器实例
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


if __name__ == '__main__':
    # 测试代码
    import sys

    logging.basicConfig(level=logging.INFO)

    async def test():
        limiter = get_rate_limiter()

        # 测试 YouTube 限制
        print("测试 YouTube 速率限制...")
        print(f"YouTube 访客限制: {limiter.get_limit_info('youtube', False)}")
        print(f"YouTube 账号限制: {limiter.get_limit_info('youtube', True)}")

        # 模拟几次请求
        for i in range(5):
            result = await limiter.wait_if_needed('youtube', False)
            print(f"请求 {i+1}: 剩余 {result['remaining']}/{result['limit']}")

        # 显示使用情况
        usage = limiter.get_current_usage('youtube', False)
        print(f"\n当前使用情况:")
        print(f"  已使用: {usage['current']}/{usage['limit']} ({usage['percentage']:.1f}%)")
        print(f"  剩余: {usage['remaining']}")

    asyncio.run(test())
