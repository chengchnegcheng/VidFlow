"""
错误消息本地化

实现错误码到中文消息的映射，提供针对不同代理软件的具体指导。

Validates: Requirements 1.3, 7.3, 7.6
"""

import logging
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误类别"""
    PROXY = "proxy"
    CAPTURE = "capture"
    PROCESS = "process"
    TLS = "tls"
    VIDEO = "video"
    SYSTEM = "system"
    CONFIG = "config"


class LocalizedErrorCode(Enum):
    """本地化错误码"""
    # 代理相关
    PROXY_TUN_MODE = "PROXY_TUN_MODE"
    PROXY_FAKE_IP = "PROXY_FAKE_IP"
    CLASH_API_FAILED = "CLASH_API_FAILED"
    CLASH_AUTH_FAILED = "CLASH_AUTH_FAILED"
    PROXY_NOT_SUPPORTED = "PROXY_NOT_SUPPORTED"

    # 捕获相关
    WINDIVERT_ADMIN = "WINDIVERT_ADMIN"
    WINDIVERT_DRIVER = "WINDIVERT_DRIVER"
    WINDIVERT_FILTER = "WINDIVERT_FILTER"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    MODE_SWITCH_FAILED = "MODE_SWITCH_FAILED"

    # 进程相关
    WECHAT_NOT_RUNNING = "WECHAT_NOT_RUNNING"
    WECHAT_RESTART_DETECTED = "WECHAT_RESTART_DETECTED"
    PROCESS_ACCESS_DENIED = "PROCESS_ACCESS_DENIED"

    # TLS相关
    ECH_DETECTED = "ECH_DETECTED"
    SNI_EXTRACTION_FAILED = "SNI_EXTRACTION_FAILED"
    TLS_PARSE_ERROR = "TLS_PARSE_ERROR"

    # 视频相关
    NO_VIDEO_DETECTED = "NO_VIDEO_DETECTED"
    VIDEO_EXPIRED = "VIDEO_EXPIRED"
    VIDEO_DECRYPT_FAILED = "VIDEO_DECRYPT_FAILED"
    VIDEO_DOWNLOAD_FAILED = "VIDEO_DOWNLOAD_FAILED"

    # 系统相关
    RECOVERY_FAILED = "RECOVERY_FAILED"
    COMPONENT_FAILED = "COMPONENT_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"

    # 配置相关
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_LOAD_FAILED = "CONFIG_LOAD_FAILED"
    CONFIG_SAVE_FAILED = "CONFIG_SAVE_FAILED"


# 错误消息映射（中文）
ERROR_MESSAGES_ZH: Dict[str, Dict[str, str]] = {
    # 代理相关
    LocalizedErrorCode.PROXY_TUN_MODE.value: {
        "message": "检测到代理软件使用TUN模式",
        "solution": "请切换到系统代理模式，或在代理规则中将微信设为直连",
        "category": ErrorCategory.PROXY.value,
    },
    LocalizedErrorCode.PROXY_FAKE_IP.value: {
        "message": "检测到Fake-IP模式",
        "solution": "系统将使用IP识别替代方案，可能影响检测准确性。建议关闭Fake-IP或将视频号域名加入直连规则",
        "category": ErrorCategory.PROXY.value,
    },
    LocalizedErrorCode.CLASH_API_FAILED.value: {
        "message": "无法连接到Clash API",
        "solution": "请检查Clash是否运行，API地址是否正确（默认为127.0.0.1:9090）",
        "category": ErrorCategory.PROXY.value,
    },
    LocalizedErrorCode.CLASH_AUTH_FAILED.value: {
        "message": "Clash API认证失败",
        "solution": "请检查API密钥是否正确，可在Clash配置文件中查看secret字段",
        "category": ErrorCategory.PROXY.value,
    },
    LocalizedErrorCode.PROXY_NOT_SUPPORTED.value: {
        "message": "不支持的代理软件",
        "solution": "当前代理软件不支持API监控，请尝试使用透明捕获模式或关闭代理",
        "category": ErrorCategory.PROXY.value,
    },

    # 捕获相关
    LocalizedErrorCode.WINDIVERT_ADMIN.value: {
        "message": "需要管理员权限",
        "solution": "请以管理员身份运行程序，或右键选择「以管理员身份运行」",
        "category": ErrorCategory.CAPTURE.value,
    },
    LocalizedErrorCode.WINDIVERT_DRIVER.value: {
        "message": "WinDivert驱动未安装",
        "solution": "请点击「安装驱动」按钮安装WinDivert驱动，安装后需要重启程序",
        "category": ErrorCategory.CAPTURE.value,
    },
    LocalizedErrorCode.WINDIVERT_FILTER.value: {
        "message": "WinDivert过滤器错误",
        "solution": "过滤规则配置错误，请重置为默认配置或联系技术支持",
        "category": ErrorCategory.CAPTURE.value,
    },
    LocalizedErrorCode.CAPTURE_FAILED.value: {
        "message": "流量捕获启动失败",
        "solution": "请检查是否有其他程序占用网络驱动，或尝试重启电脑",
        "category": ErrorCategory.CAPTURE.value,
    },
    LocalizedErrorCode.MODE_SWITCH_FAILED.value: {
        "message": "模式切换失败",
        "solution": "无法切换到目标模式，请检查相关组件是否可用",
        "category": ErrorCategory.CAPTURE.value,
    },

    # 进程相关
    LocalizedErrorCode.WECHAT_NOT_RUNNING.value: {
        "message": "未检测到微信进程",
        "solution": "请先启动微信客户端，确保微信正在运行",
        "category": ErrorCategory.PROCESS.value,
    },
    LocalizedErrorCode.WECHAT_RESTART_DETECTED.value: {
        "message": "检测到微信重启",
        "solution": "微信进程已重启，正在重新建立连接...",
        "category": ErrorCategory.PROCESS.value,
    },
    LocalizedErrorCode.PROCESS_ACCESS_DENIED.value: {
        "message": "无法访问进程信息",
        "solution": "请以管理员身份运行程序以获取进程访问权限",
        "category": ErrorCategory.PROCESS.value,
    },

    # TLS相关
    LocalizedErrorCode.ECH_DETECTED.value: {
        "message": "检测到ECH加密",
        "solution": "已切换到IP识别模式，这是正常现象，不影响视频检测",
        "category": ErrorCategory.TLS.value,
    },
    LocalizedErrorCode.SNI_EXTRACTION_FAILED.value: {
        "message": "SNI提取失败",
        "solution": "无法从TLS握手中提取服务器名称，将使用IP识别替代",
        "category": ErrorCategory.TLS.value,
    },
    LocalizedErrorCode.TLS_PARSE_ERROR.value: {
        "message": "TLS解析错误",
        "solution": "TLS数据包格式异常，可能是非标准实现",
        "category": ErrorCategory.TLS.value,
    },

    # 视频相关
    LocalizedErrorCode.NO_VIDEO_DETECTED.value: {
        "message": "未检测到视频",
        "solution": "请在微信中播放视频号视频，确保视频正在加载。如果使用代理，请检查代理设置",
        "category": ErrorCategory.VIDEO.value,
    },
    LocalizedErrorCode.VIDEO_EXPIRED.value: {
        "message": "视频链接已过期",
        "solution": "请重新播放视频获取新链接，视频号链接通常有效期较短",
        "category": ErrorCategory.VIDEO.value,
    },
    LocalizedErrorCode.VIDEO_DECRYPT_FAILED.value: {
        "message": "视频解密失败",
        "solution": "无法解密视频文件，可能是加密方式已更新，请检查更新",
        "category": ErrorCategory.VIDEO.value,
    },
    LocalizedErrorCode.VIDEO_DOWNLOAD_FAILED.value: {
        "message": "视频下载失败",
        "solution": "下载过程中出错，请检查网络连接或重试",
        "category": ErrorCategory.VIDEO.value,
    },

    # 系统相关
    LocalizedErrorCode.RECOVERY_FAILED.value: {
        "message": "自动恢复失败",
        "solution": "多次恢复尝试均失败，请手动重启捕获功能或重启程序",
        "category": ErrorCategory.SYSTEM.value,
    },
    LocalizedErrorCode.COMPONENT_FAILED.value: {
        "message": "组件启动失败",
        "solution": "部分功能组件无法启动，请检查系统环境或重启程序",
        "category": ErrorCategory.SYSTEM.value,
    },
    LocalizedErrorCode.NETWORK_ERROR.value: {
        "message": "网络连接错误",
        "solution": "请检查网络连接是否正常，如使用代理请确保代理服务正常运行",
        "category": ErrorCategory.SYSTEM.value,
    },

    # 配置相关
    LocalizedErrorCode.CONFIG_INVALID.value: {
        "message": "配置文件无效",
        "solution": "配置文件格式错误，已使用默认配置。如需恢复，请重置配置",
        "category": ErrorCategory.CONFIG.value,
    },
    LocalizedErrorCode.CONFIG_LOAD_FAILED.value: {
        "message": "配置加载失败",
        "solution": "无法读取配置文件，将使用默认配置",
        "category": ErrorCategory.CONFIG.value,
    },
    LocalizedErrorCode.CONFIG_SAVE_FAILED.value: {
        "message": "配置保存失败",
        "solution": "无法保存配置文件，请检查文件权限",
        "category": ErrorCategory.CONFIG.value,
    },
}


# 代理软件特定指导
PROXY_SPECIFIC_GUIDANCE: Dict[str, Dict[str, str]] = {
    "clash": {
        "name": "Clash",
        "tun_disable": "在Clash配置中将tun.enable设为false，或在设置中关闭TUN模式",
        "fake_ip_disable": "在Clash配置中将dns.enhanced-mode设为redir-host，或关闭Fake-IP",
        "direct_rule": "在规则中添加: DOMAIN-SUFFIX,qq.com,DIRECT 和 DOMAIN-SUFFIX,weixin.qq.com,DIRECT",
        "api_enable": "确保配置中有external-controller字段，如: external-controller: 127.0.0.1:9090",
    },
    "clash_verge": {
        "name": "Clash Verge",
        "tun_disable": "在设置 > TUN模式中关闭TUN",
        "fake_ip_disable": "在设置 > DNS设置中将模式改为redir-host",
        "direct_rule": "在规则设置中添加微信和QQ域名的直连规则",
        "api_enable": "Clash Verge默认启用API，端口通常为9097",
    },
    "clash_meta": {
        "name": "Clash Meta (Mihomo)",
        "tun_disable": "在配置中将tun.enable设为false",
        "fake_ip_disable": "在dns配置中将enhanced-mode设为redir-host",
        "direct_rule": "添加规则: DOMAIN-SUFFIX,qq.com,DIRECT",
        "api_enable": "配置external-controller启用API",
    },
    "surge": {
        "name": "Surge",
        "tun_disable": "在设置中关闭增强模式",
        "fake_ip_disable": "Surge默认不使用Fake-IP",
        "direct_rule": "在规则中添加: DOMAIN-SUFFIX,qq.com,DIRECT",
        "api_enable": "在设置中启用HTTP API",
    },
    "v2ray": {
        "name": "V2Ray/Xray",
        "tun_disable": "如使用tun2socks，请关闭或配置绕过规则",
        "fake_ip_disable": "V2Ray默认不使用Fake-IP",
        "direct_rule": "在路由规则中添加qq.com和weixin.qq.com的直连规则",
        "api_enable": "V2Ray API需要单独配置，建议使用透明捕获模式",
    },
    "shadowsocks": {
        "name": "Shadowsocks",
        "tun_disable": "如使用全局模式，请切换到PAC或规则模式",
        "fake_ip_disable": "Shadowsocks默认不使用Fake-IP",
        "direct_rule": "在PAC或规则中添加qq.com和weixin.qq.com的直连",
        "api_enable": "Shadowsocks不支持API监控，请使用透明捕获模式",
    },
}


class ErrorMessageLocalizer:
    """错误消息本地化器

    Property 15: Error Message Localization
    对于任何错误条件，系统应该生成用户友好的中文错误消息，
    描述问题并建议解决方案。技术细节和堆栈跟踪不应暴露给用户。

    Validates: Requirements 7.3, 7.6
    """

    def __init__(self, language: str = "zh"):
        """初始化本地化器

        Args:
            language: 语言代码，目前支持 "zh"
        """
        self.language = language
        self._messages = ERROR_MESSAGES_ZH
        self._proxy_guidance = PROXY_SPECIFIC_GUIDANCE

    def get_message(
        self,
        error_code: str,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """获取本地化错误消息

        Args:
            error_code: 错误码
            **kwargs: 消息模板参数

        Returns:
            包含message、solution和category的字典
        """
        if error_code not in self._messages:
            return {
                "message": f"未知错误: {error_code}",
                "solution": "请联系技术支持",
                "category": ErrorCategory.SYSTEM.value,
            }

        error_info = self._messages[error_code].copy()

        # 格式化消息
        try:
            if kwargs:
                error_info["message"] = error_info["message"].format(**kwargs)
                error_info["solution"] = error_info["solution"].format(**kwargs)
        except KeyError:
            pass

        return error_info

    def get_user_friendly_message(
        self,
        error_code: str,
        include_solution: bool = True,
        **kwargs: Any,
    ) -> str:
        """获取用户友好的错误消息

        Args:
            error_code: 错误码
            include_solution: 是否包含解决方案
            **kwargs: 消息模板参数

        Returns:
            用户友好的错误消息字符串
        """
        error_info = self.get_message(error_code, **kwargs)

        if include_solution:
            return f"{error_info['message']}。{error_info['solution']}"
        else:
            return error_info["message"]

    def get_proxy_guidance(
        self,
        proxy_type: str,
        guidance_type: str,
    ) -> Optional[str]:
        """获取代理软件特定指导

        Args:
            proxy_type: 代理类型（如 "clash", "surge"）
            guidance_type: 指导类型（如 "tun_disable", "direct_rule"）

        Returns:
            指导文本，如果不存在则返回None
        """
        proxy_type_lower = proxy_type.lower()

        if proxy_type_lower not in self._proxy_guidance:
            return None

        guidance = self._proxy_guidance[proxy_type_lower]
        return guidance.get(guidance_type)

    def get_proxy_name(self, proxy_type: str) -> str:
        """获取代理软件显示名称

        Args:
            proxy_type: 代理类型

        Returns:
            显示名称
        """
        proxy_type_lower = proxy_type.lower()

        if proxy_type_lower in self._proxy_guidance:
            return self._proxy_guidance[proxy_type_lower].get("name", proxy_type)

        return proxy_type

    def format_error_for_user(
        self,
        error_code: str,
        proxy_type: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """格式化错误信息供用户查看

        Args:
            error_code: 错误码
            proxy_type: 代理类型（可选，用于提供特定指导）
            **kwargs: 消息模板参数

        Returns:
            格式化的错误信息字典
        """
        error_info = self.get_message(error_code, **kwargs)

        result = {
            "error_code": error_code,
            "message": error_info["message"],
            "solution": error_info["solution"],
            "category": error_info["category"],
        }

        # 如果有代理类型，添加特定指导
        if proxy_type:
            proxy_name = self.get_proxy_name(proxy_type)
            result["proxy_name"] = proxy_name

            # 根据错误类型添加特定指导
            if error_code == LocalizedErrorCode.PROXY_TUN_MODE.value:
                guidance = self.get_proxy_guidance(proxy_type, "tun_disable")
                if guidance:
                    result["proxy_guidance"] = guidance
            elif error_code == LocalizedErrorCode.PROXY_FAKE_IP.value:
                guidance = self.get_proxy_guidance(proxy_type, "fake_ip_disable")
                if guidance:
                    result["proxy_guidance"] = guidance
            elif error_code in (
                LocalizedErrorCode.CLASH_API_FAILED.value,
                LocalizedErrorCode.CLASH_AUTH_FAILED.value,
            ):
                guidance = self.get_proxy_guidance(proxy_type, "api_enable")
                if guidance:
                    result["proxy_guidance"] = guidance

        return result

    def is_warning_level(self, error_code: str) -> bool:
        """判断错误是否为警告级别

        警告级别的错误不会阻止程序运行，只是提示用户。

        Args:
            error_code: 错误码

        Returns:
            是否为警告级别
        """
        warning_codes = {
            LocalizedErrorCode.ECH_DETECTED.value,
            LocalizedErrorCode.PROXY_FAKE_IP.value,
            LocalizedErrorCode.WECHAT_RESTART_DETECTED.value,
            LocalizedErrorCode.SNI_EXTRACTION_FAILED.value,
        }
        return error_code in warning_codes

    def is_fatal_level(self, error_code: str) -> bool:
        """判断错误是否为致命级别

        致命级别的错误会阻止程序运行，需要用户干预。

        Args:
            error_code: 错误码

        Returns:
            是否为致命级别
        """
        fatal_codes = {
            LocalizedErrorCode.WINDIVERT_ADMIN.value,
            LocalizedErrorCode.WINDIVERT_DRIVER.value,
            LocalizedErrorCode.RECOVERY_FAILED.value,
        }
        return error_code in fatal_codes


# 全局实例
_localizer: Optional[ErrorMessageLocalizer] = None


def get_localizer() -> ErrorMessageLocalizer:
    """获取全局本地化器实例"""
    global _localizer
    if _localizer is None:
        _localizer = ErrorMessageLocalizer()
    return _localizer


def get_localized_error(
    error_code: str,
    proxy_type: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """获取本地化错误信息（便捷函数）

    Args:
        error_code: 错误码
        proxy_type: 代理类型
        **kwargs: 消息模板参数

    Returns:
        格式化的错误信息
    """
    return get_localizer().format_error_for_user(error_code, proxy_type, **kwargs)


def get_error_message_zh(error_code: str, **kwargs: Any) -> str:
    """获取中文错误消息（便捷函数）

    Args:
        error_code: 错误码
        **kwargs: 消息模板参数

    Returns:
        中文错误消息
    """
    return get_localizer().get_user_friendly_message(error_code, **kwargs)
