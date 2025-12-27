"""
Cookie 有效期验证模块
用于检测和验证 Cookie 文件的有效性
"""
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def read_cookie_file(cookie_path: Path) -> str:
    """
    读取 Cookie 文件内容

    Args:
        cookie_path: Cookie 文件路径

    Returns:
        str: Cookie 文件内容
    """
    try:
        with open(cookie_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # 如果 UTF-8 解码失败，尝试其他编码
        try:
            with open(cookie_path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取 Cookie 文件失败（编码错误）: {e}")
            raise
    except Exception as e:
        logger.error(f"读取 Cookie 文件失败: {e}")
        raise


def parse_netscape_cookie_line(line: str) -> Optional[Dict[str, any]]:
    """
    解析 Netscape Cookie 格式的一行

    Netscape Cookie 格式：
    domain	flag	path	secure	expiration	name	value

    Args:
        line: Cookie 行内容

    Returns:
        dict: 解析后的 Cookie 信息，如果解析失败返回 None
    """
    try:
        parts = line.split('\t')
        if len(parts) != 7:
            return None

        domain, flag, path, secure, expiration, name, value = parts

        return {
            'domain': domain.strip(),
            'flag': flag.strip(),
            'path': path.strip(),
            'secure': secure.strip() == 'TRUE',
            'expiration': int(expiration.strip()) if expiration.strip().isdigit() else 0,
            'name': name.strip(),
            'value': value.strip()
        }
    except Exception as e:
        logger.debug(f"解析 Cookie 行失败: {line[:50]}... - {e}")
        return None


def check_cookie_validity(cookie_path: Path, platform: str) -> Dict[str, any]:
    """
    检查 Cookie 文件是否有效

    Args:
        cookie_path: Cookie 文件路径
        platform: 平台名称（用于验证域名）

    Returns:
        dict: {
            'valid': bool,              # 是否有效
            'reason': str,              # 失败原因（如果无效）
            'total_cookies': int,       # 总 Cookie 数量
            'expired_cookies': int,     # 已过期 Cookie 数量
            'valid_cookies': int,       # 有效 Cookie 数量
            'expires_soon': bool,       # 是否即将过期（7天内）
            'earliest_expiry': int,     # 最早过期时间戳
            'details': str              # 详细信息
        }
    """
    # 检查文件是否存在
    if not cookie_path.exists():
        return {
            'valid': False,
            'reason': 'Cookie 文件不存在',
            'total_cookies': 0,
            'expired_cookies': 0,
            'valid_cookies': 0,
            'expires_soon': False,
            'earliest_expiry': 0,
            'details': f'文件路径: {cookie_path}'
        }

    try:
        content = read_cookie_file(cookie_path)
    except Exception as e:
        return {
            'valid': False,
            'reason': f'无法读取 Cookie 文件: {str(e)}',
            'total_cookies': 0,
            'expired_cookies': 0,
            'valid_cookies': 0,
            'expires_soon': False,
            'earliest_expiry': 0,
            'details': ''
        }

    # 解析 Cookie 行
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]

    if not lines:
        return {
            'valid': False,
            'reason': 'Cookie 文件为空',
            'total_cookies': 0,
            'expired_cookies': 0,
            'valid_cookies': 0,
            'expires_soon': False,
            'earliest_expiry': 0,
            'details': '文件中没有有效的 Cookie 数据'
        }

    # 统计 Cookie 信息
    now = int(time.time())
    seven_days = 7 * 24 * 60 * 60

    total_cookies = 0
    expired_cookies = 0
    valid_cookies = 0
    earliest_expiry = float('inf')
    platform_cookies = []

    # 平台域名映射（与 cookie_helper.py 保持一致）
    platform_domains = {
        "douyin": "douyin.com",
        "tiktok": "tiktok.com",
        "xiaohongshu": "xiaohongshu.com",
        "bilibili": "bilibili.com",
        "youtube": "youtube.com",
        "twitter": "twitter.com",
        "instagram": "instagram.com"
    }

    expected_domain = platform_domains.get(platform, "")

    for line in lines:
        cookie = parse_netscape_cookie_line(line)
        if not cookie:
            continue

        total_cookies += 1
        expiry = cookie['expiration']

        # 检查是否是目标平台的 Cookie
        if expected_domain and expected_domain in cookie['domain']:
            platform_cookies.append(cookie)

        # 检查过期状态
        if expiry > 0:  # expiry = 0 表示会话 Cookie
            if expiry < now:
                expired_cookies += 1
            else:
                valid_cookies += 1
                if expiry < earliest_expiry:
                    earliest_expiry = expiry
        else:
            # 会话 Cookie 也算有效
            valid_cookies += 1

    # 判断是否有效
    if total_cookies == 0:
        return {
            'valid': False,
            'reason': 'Cookie 文件中没有有效的 Cookie',
            'total_cookies': 0,
            'expired_cookies': 0,
            'valid_cookies': 0,
            'expires_soon': False,
            'earliest_expiry': 0,
            'details': '无法解析任何 Cookie 数据'
        }

    # 检查是否大部分 Cookie 已过期
    if expired_cookies > total_cookies * 0.7:  # 超过 70% 的 Cookie 已过期
        return {
            'valid': False,
            'reason': f'大部分 Cookie 已过期（{expired_cookies}/{total_cookies}）',
            'total_cookies': total_cookies,
            'expired_cookies': expired_cookies,
            'valid_cookies': valid_cookies,
            'expires_soon': False,
            'earliest_expiry': int(earliest_expiry) if earliest_expiry != float('inf') else 0,
            'details': '建议重新获取 Cookie'
        }

    # 检查是否有平台相关的 Cookie
    if expected_domain and len(platform_cookies) == 0:
        return {
            'valid': False,
            'reason': f'Cookie 文件中没有 {platform} ({expected_domain}) 的 Cookie',
            'total_cookies': total_cookies,
            'expired_cookies': expired_cookies,
            'valid_cookies': valid_cookies,
            'expires_soon': False,
            'earliest_expiry': int(earliest_expiry) if earliest_expiry != float('inf') else 0,
            'details': f'请确保从 {expected_domain} 导出 Cookie'
        }

    # 检查是否即将过期
    expires_soon = False
    if earliest_expiry != float('inf') and (earliest_expiry - now) < seven_days:
        expires_soon = True

    # 生成详细信息
    details_lines = [
        f'总 Cookie 数: {total_cookies}',
        f'有效 Cookie: {valid_cookies}',
        f'已过期: {expired_cookies}',
    ]

    if expected_domain:
        details_lines.append(f'{platform} 相关 Cookie: {len(platform_cookies)}')

    if earliest_expiry != float('inf'):
        expiry_date = datetime.fromtimestamp(earliest_expiry).strftime('%Y-%m-%d %H:%M:%S')
        days_until_expiry = (earliest_expiry - now) // (24 * 60 * 60)
        details_lines.append(f'最早过期时间: {expiry_date} ({days_until_expiry} 天后)')

    return {
        'valid': True,
        'reason': '',
        'total_cookies': total_cookies,
        'expired_cookies': expired_cookies,
        'valid_cookies': valid_cookies,
        'expires_soon': expires_soon,
        'earliest_expiry': int(earliest_expiry) if earliest_expiry != float('inf') else 0,
        'details': '\n'.join(details_lines)
    }


def get_cookie_info_summary(cookie_path: Path, platform: str) -> str:
    """
    获取 Cookie 信息摘要（用于显示给用户）

    Args:
        cookie_path: Cookie 文件路径
        platform: 平台名称

    Returns:
        str: 摘要信息
    """
    result = check_cookie_validity(cookie_path, platform)

    if result['valid']:
        summary = f"✓ Cookie 文件有效\n\n{result['details']}"
        if result['expires_soon']:
            summary += "\n\n⚠️ 提示: 部分 Cookie 将在 7 天内过期，建议更新"
        return summary
    else:
        return f"✗ Cookie 文件无效\n\n原因: {result['reason']}\n\n{result['details']}"


def validate_all_platform_cookies(cookie_dir: Path) -> Dict[str, Dict]:
    """
    验证所有平台的 Cookie 文件

    Args:
        cookie_dir: Cookie 目录路径

    Returns:
        dict: {platform: validation_result}
    """
    platforms = ["youtube", "bilibili", "douyin", "tiktok", "xiaohongshu", "twitter", "instagram"]
    results = {}

    for platform in platforms:
        cookie_file = cookie_dir / f"{platform}_cookies.txt"
        if cookie_file.exists():
            results[platform] = check_cookie_validity(cookie_file, platform)
        else:
            results[platform] = {
                'valid': False,
                'reason': 'Cookie 文件不存在',
                'total_cookies': 0,
                'expired_cookies': 0,
                'valid_cookies': 0,
                'expires_soon': False,
                'earliest_expiry': 0,
                'details': ''
            }

    return results


if __name__ == '__main__':
    # 测试代码
    import sys
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        cookie_path = Path(sys.argv[1])
        platform = sys.argv[2] if len(sys.argv) > 2 else "youtube"

        print(get_cookie_info_summary(cookie_path, platform))
    else:
        print("用法: python cookie_validator.py <cookie_file_path> [platform]")
        print("示例: python cookie_validator.py data/cookies/youtube_cookies.txt youtube")
