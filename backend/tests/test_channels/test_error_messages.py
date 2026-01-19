"""
错误消息本地化测试

Property 15: Error Message Localization
对于任何错误条件，系统应该生成用户友好的中文错误消息，
描述问题并建议解决方案。技术细节和堆栈跟踪不应暴露给用户。

Validates: Requirements 7.3, 7.6
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.channels.error_messages import (
    ErrorMessageLocalizer,
    LocalizedErrorCode,
    ErrorCategory,
    ERROR_MESSAGES_ZH,
    PROXY_SPECIFIC_GUIDANCE,
    get_localizer,
    get_localized_error,
    get_error_message_zh,
)


class TestErrorMessageLocalizer:
    """错误消息本地化器测试"""
    
    def test_init_default_language(self):
        """测试默认语言初始化"""
        localizer = ErrorMessageLocalizer()
        assert localizer.language == "zh"
    
    def test_get_message_known_code(self):
        """测试获取已知错误码的消息"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.get_message(LocalizedErrorCode.PROXY_TUN_MODE.value)
        
        assert "message" in result
        assert "solution" in result
        assert "category" in result
        assert result["category"] == ErrorCategory.PROXY.value
        assert "TUN" in result["message"]
    
    def test_get_message_unknown_code(self):
        """测试获取未知错误码的消息"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.get_message("UNKNOWN_ERROR_CODE")
        
        assert "message" in result
        assert "未知错误" in result["message"]
        assert result["category"] == ErrorCategory.SYSTEM.value
    
    def test_get_user_friendly_message_with_solution(self):
        """测试获取包含解决方案的用户友好消息"""
        localizer = ErrorMessageLocalizer()
        
        message = localizer.get_user_friendly_message(
            LocalizedErrorCode.WECHAT_NOT_RUNNING.value,
            include_solution=True
        )
        
        assert "微信" in message
        assert "启动" in message
    
    def test_get_user_friendly_message_without_solution(self):
        """测试获取不包含解决方案的用户友好消息"""
        localizer = ErrorMessageLocalizer()
        
        message = localizer.get_user_friendly_message(
            LocalizedErrorCode.WECHAT_NOT_RUNNING.value,
            include_solution=False
        )
        
        # 只包含消息，不包含解决方案
        assert "微信" in message
        assert len(message) < 50  # 消息应该较短
    
    def test_get_proxy_guidance_clash(self):
        """测试获取Clash代理指导"""
        localizer = ErrorMessageLocalizer()
        
        guidance = localizer.get_proxy_guidance("clash", "tun_disable")
        
        assert guidance is not None
        assert "tun" in guidance.lower() or "TUN" in guidance
    
    def test_get_proxy_guidance_unknown_proxy(self):
        """测试获取未知代理的指导"""
        localizer = ErrorMessageLocalizer()
        
        guidance = localizer.get_proxy_guidance("unknown_proxy", "tun_disable")
        
        assert guidance is None
    
    def test_get_proxy_name(self):
        """测试获取代理显示名称"""
        localizer = ErrorMessageLocalizer()
        
        assert localizer.get_proxy_name("clash") == "Clash"
        assert localizer.get_proxy_name("clash_verge") == "Clash Verge"
        assert localizer.get_proxy_name("unknown") == "unknown"
    
    def test_format_error_for_user_basic(self):
        """测试基本错误格式化"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.format_error_for_user(
            LocalizedErrorCode.CAPTURE_FAILED.value
        )
        
        assert "error_code" in result
        assert "message" in result
        assert "solution" in result
        assert "category" in result
        assert result["error_code"] == LocalizedErrorCode.CAPTURE_FAILED.value
    
    def test_format_error_for_user_with_proxy(self):
        """测试带代理类型的错误格式化"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.format_error_for_user(
            LocalizedErrorCode.PROXY_TUN_MODE.value,
            proxy_type="clash"
        )
        
        assert "proxy_name" in result
        assert result["proxy_name"] == "Clash"
        assert "proxy_guidance" in result
    
    def test_is_warning_level(self):
        """测试警告级别判断"""
        localizer = ErrorMessageLocalizer()
        
        # ECH检测是警告级别
        assert localizer.is_warning_level(LocalizedErrorCode.ECH_DETECTED.value)
        
        # 驱动缺失不是警告级别
        assert not localizer.is_warning_level(LocalizedErrorCode.WINDIVERT_DRIVER.value)
    
    def test_is_fatal_level(self):
        """测试致命级别判断"""
        localizer = ErrorMessageLocalizer()
        
        # 需要管理员权限是致命级别
        assert localizer.is_fatal_level(LocalizedErrorCode.WINDIVERT_ADMIN.value)
        
        # ECH检测不是致命级别
        assert not localizer.is_fatal_level(LocalizedErrorCode.ECH_DETECTED.value)


class TestErrorMessageCoverage:
    """错误消息覆盖测试"""
    
    def test_all_error_codes_have_messages(self):
        """测试所有错误码都有对应消息"""
        for code in LocalizedErrorCode:
            assert code.value in ERROR_MESSAGES_ZH, f"Missing message for {code.value}"
    
    def test_all_messages_have_required_fields(self):
        """测试所有消息都有必需字段"""
        required_fields = {"message", "solution", "category"}
        
        for code, info in ERROR_MESSAGES_ZH.items():
            for field in required_fields:
                assert field in info, f"Missing {field} for {code}"
    
    def test_all_messages_are_chinese(self):
        """测试所有消息都是中文"""
        for code, info in ERROR_MESSAGES_ZH.items():
            message = info["message"]
            solution = info["solution"]
            
            # 检查是否包含中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in message)
            assert has_chinese, f"Message for {code} should be in Chinese"
            
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in solution)
            assert has_chinese, f"Solution for {code} should be in Chinese"
    
    def test_no_technical_details_in_messages(self):
        """测试消息中不包含技术细节"""
        technical_terms = [
            "Exception", "Error:", "Traceback", "stack trace",
            "0x", "null", "undefined", "NoneType",
        ]
        
        for code, info in ERROR_MESSAGES_ZH.items():
            message = info["message"]
            solution = info["solution"]
            
            for term in technical_terms:
                assert term not in message, f"Technical term '{term}' found in message for {code}"
                assert term not in solution, f"Technical term '{term}' found in solution for {code}"


class TestProxyGuidance:
    """代理指导测试"""
    
    def test_all_proxy_types_have_guidance(self):
        """测试所有代理类型都有指导"""
        expected_proxies = ["clash", "clash_verge", "clash_meta", "surge", "v2ray", "shadowsocks"]
        
        for proxy in expected_proxies:
            assert proxy in PROXY_SPECIFIC_GUIDANCE, f"Missing guidance for {proxy}"
    
    def test_all_guidance_types_exist(self):
        """测试所有指导类型都存在"""
        expected_types = ["name", "tun_disable", "fake_ip_disable", "direct_rule", "api_enable"]
        
        for proxy, guidance in PROXY_SPECIFIC_GUIDANCE.items():
            for guidance_type in expected_types:
                assert guidance_type in guidance, f"Missing {guidance_type} for {proxy}"


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    def test_get_localizer_singleton(self):
        """测试全局本地化器单例"""
        localizer1 = get_localizer()
        localizer2 = get_localizer()
        
        assert localizer1 is localizer2
    
    def test_get_localized_error(self):
        """测试获取本地化错误"""
        result = get_localized_error(LocalizedErrorCode.VIDEO_EXPIRED.value)
        
        assert "message" in result
        assert "过期" in result["message"]
    
    def test_get_error_message_zh(self):
        """测试获取中文错误消息"""
        message = get_error_message_zh(LocalizedErrorCode.NO_VIDEO_DETECTED.value)
        
        assert "视频" in message
        assert isinstance(message, str)


# ============ Property Tests ============

def run_async(coro):
    """运行异步函数的辅助方法"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestProperty15ErrorMessageLocalization:
    """Property 15: Error Message Localization
    
    对于任何错误条件，系统应该生成用户友好的中文错误消息，
    描述问题并建议解决方案。技术细节和堆栈跟踪不应暴露给用户。
    """
    
    @given(st.sampled_from(list(LocalizedErrorCode)))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_error_codes_produce_chinese_messages(self, error_code: LocalizedErrorCode):
        """测试所有错误码都能产生中文消息"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.get_message(error_code.value)
        
        # 消息应该包含中文
        message = result["message"]
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in message)
        assert has_chinese, f"Message for {error_code.value} should contain Chinese characters"
    
    @given(st.sampled_from(list(LocalizedErrorCode)))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_error_codes_have_solutions(self, error_code: LocalizedErrorCode):
        """测试所有错误码都有解决方案"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.get_message(error_code.value)
        
        # 解决方案不应为空
        solution = result["solution"]
        assert len(solution) > 0, f"Solution for {error_code.value} should not be empty"
        
        # 解决方案应该包含中文
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in solution)
        assert has_chinese, f"Solution for {error_code.value} should contain Chinese characters"
    
    @given(st.sampled_from(list(LocalizedErrorCode)))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_no_stack_traces_in_messages(self, error_code: LocalizedErrorCode):
        """测试消息中不包含堆栈跟踪"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.get_message(error_code.value)
        message = result["message"]
        solution = result["solution"]
        
        # 不应包含堆栈跟踪相关的关键词
        stack_trace_indicators = [
            "Traceback", "File \"", "line ", "in <module>",
            "Exception", "Error:", "at 0x", "NoneType",
        ]
        
        for indicator in stack_trace_indicators:
            assert indicator not in message, f"Stack trace indicator '{indicator}' found in message"
            assert indicator not in solution, f"Stack trace indicator '{indicator}' found in solution"
    
    @given(
        st.sampled_from(list(LocalizedErrorCode)),
        st.sampled_from(["clash", "clash_verge", "surge", "v2ray", None])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_format_error_always_returns_valid_structure(
        self,
        error_code: LocalizedErrorCode,
        proxy_type
    ):
        """测试格式化错误总是返回有效结构"""
        localizer = ErrorMessageLocalizer()
        
        result = localizer.format_error_for_user(error_code.value, proxy_type)
        
        # 必须包含基本字段
        assert "error_code" in result
        assert "message" in result
        assert "solution" in result
        assert "category" in result
        
        # 字段类型正确
        assert isinstance(result["error_code"], str)
        assert isinstance(result["message"], str)
        assert isinstance(result["solution"], str)
        assert isinstance(result["category"], str)
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unknown_error_codes_handled_gracefully(self, random_code: str):
        """测试未知错误码被优雅处理"""
        localizer = ErrorMessageLocalizer()
        
        # 跳过已知的错误码
        known_codes = {code.value for code in LocalizedErrorCode}
        if random_code in known_codes:
            return
        
        result = localizer.get_message(random_code)
        
        # 应该返回有效结构
        assert "message" in result
        assert "solution" in result
        assert "category" in result
        
        # 消息应该表明是未知错误
        assert "未知" in result["message"] or random_code in result["message"]


class TestErrorCategoryClassification:
    """错误类别分类测试"""
    
    def test_proxy_errors_have_proxy_category(self):
        """测试代理错误有正确的类别"""
        proxy_codes = [
            LocalizedErrorCode.PROXY_TUN_MODE,
            LocalizedErrorCode.PROXY_FAKE_IP,
            LocalizedErrorCode.CLASH_API_FAILED,
            LocalizedErrorCode.CLASH_AUTH_FAILED,
        ]
        
        for code in proxy_codes:
            info = ERROR_MESSAGES_ZH[code.value]
            assert info["category"] == ErrorCategory.PROXY.value
    
    def test_capture_errors_have_capture_category(self):
        """测试捕获错误有正确的类别"""
        capture_codes = [
            LocalizedErrorCode.WINDIVERT_ADMIN,
            LocalizedErrorCode.WINDIVERT_DRIVER,
            LocalizedErrorCode.CAPTURE_FAILED,
        ]
        
        for code in capture_codes:
            info = ERROR_MESSAGES_ZH[code.value]
            assert info["category"] == ErrorCategory.CAPTURE.value
    
    def test_video_errors_have_video_category(self):
        """测试视频错误有正确的类别"""
        video_codes = [
            LocalizedErrorCode.NO_VIDEO_DETECTED,
            LocalizedErrorCode.VIDEO_EXPIRED,
            LocalizedErrorCode.VIDEO_DECRYPT_FAILED,
        ]
        
        for code in video_codes:
            info = ERROR_MESSAGES_ZH[code.value]
            assert info["category"] == ErrorCategory.VIDEO.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
