"""
错误消息本地化属性测试

**Property 5: Error Message Localization**
**Validates: Requirements 1.8, 2.8, 3.8, 4.8**

测试所有错误消息都是中文且对用户友好。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
import re

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.core.qr_login.models import QRLoginErrorCode, QRLoginStatus, get_status_message
from src.api.qr_login import ERROR_MESSAGES, get_error_message, get_error_response, classify_exception


# ============ 策略定义 ============

# 所有错误代码
all_error_codes = [
    QRLoginErrorCode.NETWORK_TIMEOUT,
    QRLoginErrorCode.API_ERROR,
    QRLoginErrorCode.QR_EXPIRED,
    QRLoginErrorCode.VERIFICATION_REQUIRED,
    QRLoginErrorCode.COOKIE_CONVERSION_FAILED,
    QRLoginErrorCode.PLATFORM_NOT_SUPPORTED,
    QRLoginErrorCode.PLATFORM_DISABLED,
    QRLoginErrorCode.NO_QRCODE,
    QRLoginErrorCode.BROWSER_ERROR,
    QRLoginErrorCode.INTERNAL_ERROR,
]

error_code_strategy = st.sampled_from(all_error_codes)

# 所有登录状态
all_login_statuses = [
    QRLoginStatus.LOADING,
    QRLoginStatus.WAITING,
    QRLoginStatus.SCANNED,
    QRLoginStatus.SUCCESS,
    QRLoginStatus.EXPIRED,
    QRLoginStatus.ERROR,
]

login_status_strategy = st.sampled_from(all_login_statuses)

# 平台中文名称策略
platform_name_zh_strategy = st.sampled_from([
    "哔哩哔哩", "抖音", "快手", "小红书", "微博",
    "腾讯视频", "爱奇艺", "优酷", "芒果TV"
])

# 异常消息策略
exception_message_strategy = st.text(min_size=1, max_size=100)


# ============ 辅助函数 ============

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def is_user_friendly(text: str) -> bool:
    """检查文本是否对用户友好（不包含技术术语）"""
    technical_terms = [
        'exception', 'error', 'null', 'undefined', 'traceback',
        'stack', 'debug', 'fatal', 'panic', 'crash',
        'NoneType', 'TypeError', 'ValueError', 'KeyError',
        'AttributeError', 'IndexError', 'RuntimeError'
    ]
    text_lower = text.lower()
    return not any(term.lower() in text_lower for term in technical_terms)


# ============ 属性测试 ============

class TestErrorMessageLocalization:
    """错误消息本地化属性测试类

    **Feature: multi-platform-qr-login, Property 5: Error Message Localization**
    """

    @given(error_code=error_code_strategy)
    @settings(max_examples=100, deadline=None)
    def test_all_error_codes_have_chinese_messages(self, error_code: str):
        """
        Property 5.1: 所有错误代码都有中文消息

        *For any* error code in the system, there SHALL exist a corresponding
        Chinese error message.

        **Validates: Requirements 1.8, 2.8, 3.8, 4.8**
        """
        message = get_error_message(error_code)

        assert message is not None, f"Error code {error_code} has no message"
        assert len(message) > 0, f"Error code {error_code} has empty message"
        assert contains_chinese(message), \
            f"Error message for {error_code} should contain Chinese: '{message}'"

    @given(error_code=error_code_strategy)
    @settings(max_examples=100, deadline=None)
    def test_error_messages_are_user_friendly(self, error_code: str):
        """
        Property 5.2: 错误消息对用户友好

        *For any* error message, it SHALL NOT contain technical jargon
        that would confuse end users.

        **Validates: Requirements 1.8, 2.8, 3.8, 4.8**
        """
        message = get_error_message(error_code)

        assert is_user_friendly(message), \
            f"Error message for {error_code} contains technical terms: '{message}'"

    @given(error_code=error_code_strategy)
    @settings(max_examples=100, deadline=None)
    def test_error_response_format_consistency(self, error_code: str):
        """
        Property 5.3: 错误响应格式一致

        *For any* error code, the error response SHALL have consistent format
        with status, error message, and error code fields.

        **Validates: Requirements 1.8, 2.8, 3.8, 4.8**
        """
        response = get_error_response(error_code)

        # 验证响应格式
        assert "status" in response, "Response missing 'status' field"
        assert "error" in response, "Response missing 'error' field"
        assert "error_code" in response, "Response missing 'error_code' field"

        # 验证字段值
        assert response["status"] == "error", "Status should be 'error'"
        assert response["error_code"] == error_code, "Error code mismatch"
        assert contains_chinese(response["error"]), "Error message should be Chinese"

    @given(
        error_code=error_code_strategy,
        custom_message=st.text(
            alphabet=st.characters(whitelist_categories=('Lo', 'L', 'N', 'P', 'Z')),
            min_size=1,
            max_size=50
        ).filter(lambda x: x.strip())
    )
    @settings(max_examples=100, deadline=None)
    def test_custom_message_override(self, error_code: str, custom_message: str):
        """
        Property 5.4: 自定义消息可以覆盖默认消息

        *For any* error code with a custom message, the custom message
        SHALL be used instead of the default.

        **Validates: Requirements 1.8, 2.8, 3.8, 4.8**
        """
        response = get_error_response(error_code, custom_message)

        assert response["error"] == custom_message, \
            f"Custom message not used: expected '{custom_message}', got '{response['error']}'"

    @given(status=login_status_strategy, platform_name=platform_name_zh_strategy)
    @settings(max_examples=100, deadline=None)
    def test_status_messages_contain_platform_name(self, status: QRLoginStatus, platform_name: str):
        """
        Property 5.5: 状态消息包含平台名称

        *For any* login status that requires platform context, the message
        SHALL include the platform name in Chinese.

        **Validates: Requirements 6.1, 6.3**
        """
        message = get_status_message(status, platform_name)

        assert message is not None, f"Status {status} has no message"
        assert contains_chinese(message), \
            f"Status message should contain Chinese: '{message}'"

        # 对于需要平台名称的状态，验证包含平台名
        if status in [QRLoginStatus.WAITING, QRLoginStatus.SUCCESS]:
            assert platform_name in message, \
                f"Status message for {status} should contain platform name '{platform_name}': '{message}'"

    @given(status=login_status_strategy)
    @settings(max_examples=100, deadline=None)
    def test_status_messages_without_platform_name(self, status: QRLoginStatus):
        """
        Property 5.6: 无平台名称时状态消息仍有效

        *For any* login status without platform context, the message
        SHALL still be valid and meaningful.

        **Validates: Requirements 6.1, 6.3**
        """
        message = get_status_message(status, "")

        assert message is not None, f"Status {status} has no message"
        assert len(message) > 0, f"Status {status} has empty message"
        assert contains_chinese(message), \
            f"Status message should contain Chinese: '{message}'"


class TestExceptionClassification:
    """异常分类测试类"""

    def test_timeout_exception_classification(self):
        """测试超时异常分类"""
        timeout_exceptions = [
            TimeoutError("Connection timeout"),
            Exception("Request timeout after 30s"),
            Exception("timeout error occurred"),
        ]

        for exc in timeout_exceptions:
            error_code, message = classify_exception(exc)
            assert error_code == QRLoginErrorCode.NETWORK_TIMEOUT, \
                f"Timeout exception should be classified as NETWORK_TIMEOUT: {exc}"
            assert contains_chinese(message), \
                f"Message should be Chinese: {message}"

    def test_browser_exception_classification(self):
        """测试浏览器异常分类"""
        browser_exceptions = [
            Exception("Browser launch failed"),
            Exception("Playwright error: chromium not found"),
            Exception("browser context closed"),
        ]

        for exc in browser_exceptions:
            error_code, message = classify_exception(exc)
            assert error_code == QRLoginErrorCode.BROWSER_ERROR, \
                f"Browser exception should be classified as BROWSER_ERROR: {exc}"
            assert contains_chinese(message), \
                f"Message should be Chinese: {message}"

    def test_verification_exception_classification(self):
        """测试验证异常分类"""
        verification_exceptions = [
            Exception("需要手动验证"),
            Exception("Captcha required"),
            Exception("Please verify your identity"),
        ]

        for exc in verification_exceptions:
            error_code, message = classify_exception(exc)
            assert error_code == QRLoginErrorCode.VERIFICATION_REQUIRED, \
                f"Verification exception should be classified as VERIFICATION_REQUIRED: {exc}"
            assert contains_chinese(message), \
                f"Message should be Chinese: {message}"

    def test_network_exception_classification(self):
        """测试网络异常分类"""
        network_exceptions = [
            Exception("Connection refused"),
            Exception("Network unreachable"),
            Exception("网络连接失败"),
        ]

        for exc in network_exceptions:
            error_code, message = classify_exception(exc)
            assert error_code == QRLoginErrorCode.NETWORK_TIMEOUT, \
                f"Network exception should be classified as NETWORK_TIMEOUT: {exc}"
            assert contains_chinese(message), \
                f"Message should be Chinese: {message}"

    def test_generic_exception_classification(self):
        """测试通用异常分类"""
        generic_exceptions = [
            Exception("Unknown error"),
            Exception("Something went wrong"),
            ValueError("Invalid value"),
        ]

        for exc in generic_exceptions:
            error_code, message = classify_exception(exc)
            # 通用异常应该被分类为API_ERROR
            assert error_code == QRLoginErrorCode.API_ERROR, \
                f"Generic exception should be classified as API_ERROR: {exc}"
            assert contains_chinese(message), \
                f"Message should be Chinese: {message}"


# ============ 单元测试 ============

class TestErrorMessagesUnit:
    """错误消息单元测试"""

    def test_error_messages_dict_not_empty(self):
        """测试错误消息字典非空"""
        assert len(ERROR_MESSAGES) > 0, "ERROR_MESSAGES should not be empty"

    def test_all_error_codes_covered(self):
        """测试所有错误代码都有消息"""
        for code in all_error_codes:
            assert code in ERROR_MESSAGES, f"Missing message for error code: {code}"

    def test_get_error_message_with_default(self):
        """测试获取错误消息带默认值"""
        # 已知错误代码
        message = get_error_message(QRLoginErrorCode.NETWORK_TIMEOUT)
        assert "超时" in message or "网络" in message

        # 未知错误代码
        message = get_error_message("UNKNOWN_CODE", "默认消息")
        assert message == "默认消息"

        # 未知错误代码无默认值
        message = get_error_message("UNKNOWN_CODE")
        assert "未知" in message or "错误" in message

    def test_specific_error_messages(self):
        """测试特定错误消息内容"""
        # 网络超时
        assert "超时" in ERROR_MESSAGES[QRLoginErrorCode.NETWORK_TIMEOUT] or \
               "网络" in ERROR_MESSAGES[QRLoginErrorCode.NETWORK_TIMEOUT]

        # 二维码过期
        assert "过期" in ERROR_MESSAGES[QRLoginErrorCode.QR_EXPIRED]

        # 平台不支持
        assert "不支持" in ERROR_MESSAGES[QRLoginErrorCode.PLATFORM_NOT_SUPPORTED]

        # 浏览器错误
        assert "浏览器" in ERROR_MESSAGES[QRLoginErrorCode.BROWSER_ERROR] or \
               "Playwright" in ERROR_MESSAGES[QRLoginErrorCode.BROWSER_ERROR]
