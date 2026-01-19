"""
QR登录配置文件

提供二维码登录的全局配置选项。
"""

import os
from typing import Optional


class QRLoginConfig:
    """二维码登录配置类"""

    # ========== 浏览器配置 ==========

    # 是否使用有头模式（推荐设置为True以提高成功率）
    # True: 会弹出真实浏览器窗口（更难被检测）
    # False: 无头模式（不显示窗口，但容易被检测）
    HEADLESS_MODE: bool = False

    # 是否使用系统已安装的Chrome（推荐设置为True）
    # True: 使用系统Chrome，具有真实浏览器指纹
    # False: 使用Playwright自带的Chromium
    USE_SYSTEM_CHROME: bool = True

    # 浏览器窗口大小
    BROWSER_WIDTH: int = 1280
    BROWSER_HEIGHT: int = 960

    # ========== 反检测配置 ==========

    # 是否启用增强版反检测脚本
    ENABLE_STEALTH: bool = True

    # 是否模拟人类行为（随机延迟、鼠标移动等）
    ENABLE_HUMAN_BEHAVIOR: bool = True

    # 人类行为延迟范围（秒）
    HUMAN_DELAY_MIN: float = 1.0
    HUMAN_DELAY_MAX: float = 3.0

    # ========== 网络配置 ==========

    # HTTP请求超时时间（秒）
    REQUEST_TIMEOUT: int = 30

    # 是否启用HTTP/2
    ENABLE_HTTP2: bool = True

    # 代理配置（可选）
    # 格式: "http://proxy:port" 或 "socks5://proxy:port"
    PROXY_URL: Optional[str] = None

    # ========== 轮询配置 ==========

    # 二维码状态轮询间隔（秒）
    POLLING_INTERVAL: int = 2

    # 最大轮询次数（防止无限轮询）
    MAX_POLLING_COUNT: int = 90  # 3分钟 / 2秒 = 90次

    # ========== 调试配置 ==========

    # 是否启用调试模式（保存截图和HTML）
    DEBUG_MODE: bool = False

    # 调试文件保存目录
    DEBUG_DIR: str = "./debug_qr_login"

    # 是否在失败时自动保存截图
    SAVE_SCREENSHOT_ON_ERROR: bool = True

    # ========== Docker环境配置 ==========

    # 是否在Docker环境中运行
    IS_DOCKER: bool = os.path.exists('/.dockerenv')

    # Docker环境强制使用无头模式
    @classmethod
    def get_headless_mode(cls) -> bool:
        """获取实际的headless模式设置

        在Docker环境中强制使用无头模式
        """
        if cls.IS_DOCKER:
            return True
        return cls.HEADLESS_MODE

    # ========== 平台特定配置 ==========

    # 小红书特殊配置
    XIAOHONGSHU_WEBID_LENGTH: int = 19  # webId长度

    # 抖音特殊配置
    DOUYIN_WAIT_TIMEOUT: int = 30  # 等待元素超时时间（秒）

    # ========== 日志配置 ==========

    # 是否启用详细日志
    VERBOSE_LOGGING: bool = True


# 全局配置实例
config = QRLoginConfig()


def get_config() -> QRLoginConfig:
    """获取全局配置实例"""
    return config


def update_config(**kwargs):
    """更新配置

    Args:
        **kwargs: 要更新的配置项

    Example:
        update_config(HEADLESS_MODE=True, DEBUG_MODE=True)
    """
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            raise ValueError(f"未知的配置项: {key}")
