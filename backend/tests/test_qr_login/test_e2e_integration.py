"""
端到端集成测试

测试完整的扫码登录流程，包括：
- 前后端API交互
- 各平台的登录流程
- 错误处理流程
- Cookie保存流程

使用Mock模拟外部API响应。

Requirements: 1.1-8.4
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings

from src.core.qr_login import (
    QRLoginStatus,
    QRCodeResult,
    QRLoginResult,
    PlatformQRRegistry,
    QRLoginService,
    BilibiliQRProvider,
    KuaishouQRProvider,
    WeiboQRProvider,
    IqiyiQRProvider,
    MangoQRProvider,
    TencentQRProvider,
)
from src.core.qr_login.models import QRLoginErrorCode
from src.api.qr_login import (
    router,
    ERROR_MESSAGES,
    get_error_message,
    classify_exception,
    save_cookies_to_file,
)


class TestE2ELoginFlow:
    """端到端登录流程测试"""
    
    @pytest.mark.asyncio
    async def test_complete_bilibili_login_flow(self):
        """测试完整的B站登录流程: 获取二维码 -> 轮询状态 -> 登录成功 -> 保存Cookie"""
        # 创建服务
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码响应
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 0,
            "data": {
                "url": "https://qr.bilibili.com/test_e2e_123",
                "qrcode_key": "e2e_test_key_bilibili"
            }
        }
        generate_response.raise_for_status = MagicMock()
        
        # Mock轮询状态响应序列: waiting -> scanned -> success
        waiting_response = MagicMock()
        waiting_response.json.return_value = {
            "code": 0,
            "data": {"code": 86101, "message": "等待扫码"}
        }
        waiting_response.raise_for_status = MagicMock()
        
        scanned_response = MagicMock()
        scanned_response.json.return_value = {
            "code": 0,
            "data": {"code": 86090, "message": "已扫码"}
        }
        scanned_response.raise_for_status = MagicMock()
        
        success_response = MagicMock()
        success_response.json.return_value = {
            "code": 0,
            "data": {
                "code": 0,
                "message": "登录成功",
                "refresh_token": "test_refresh_token"
            }
        }
        success_response.raise_for_status = MagicMock()
        
        # 创建mock cookies
        mock_cookie = MagicMock()
        mock_cookie.name = "SESSDATA"
        mock_cookie.value = "e2e_test_sessdata_value"
        mock_cookie.domain = ".bilibili.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        success_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[
                generate_response,
                waiting_response,
                scanned_response,
                success_response
            ])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # Step 1: 获取二维码
            qr_result = await service.get_qrcode('bilibili')
            assert qr_result.qrcode_url == "https://qr.bilibili.com/test_e2e_123"
            assert qr_result.qrcode_key == "e2e_test_key_bilibili"
            assert qr_result.expires_in > 0
            
            # Step 2: 第一次轮询 - waiting
            result1 = await service.check_status('bilibili')
            assert result1.status == QRLoginStatus.WAITING
            
            # Step 3: 第二次轮询 - scanned
            result2 = await service.check_status('bilibili')
            assert result2.status == QRLoginStatus.SCANNED
            
            # Step 4: 第三次轮询 - success
            result3 = await service.check_status('bilibili')
            assert result3.status == QRLoginStatus.SUCCESS
            assert result3.cookies is not None
            assert "SESSDATA" in result3.cookies
    
    @pytest.mark.asyncio
    async def test_complete_kuaishou_login_flow(self):
        """测试完整的快手登录流程"""
        registry = PlatformQRRegistry()
        registry.register(KuaishouQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "result": 1,
            "data": {
                "qrcodeUrl": "https://passport.kuaishou.com/qrcode/e2e_test",
                "sid": "e2e_test_sid_kuaishou"
            }
        }
        generate_response.raise_for_status = MagicMock()
        
        # Mock登录成功
        success_response = MagicMock()
        success_response.json.return_value = {
            "result": 1,
            "data": {"status": 2}
        }
        success_response.raise_for_status = MagicMock()
        
        mock_cookie = MagicMock()
        mock_cookie.name = "passToken"
        mock_cookie.value = "e2e_test_pass_token"
        mock_cookie.domain = ".kuaishou.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        success_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=generate_response)
            mock_instance.get = AsyncMock(return_value=success_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # 获取二维码
            qr_result = await service.get_qrcode('kuaishou')
            assert qr_result.qrcode_key == "e2e_test_sid_kuaishou"
            
            # 检查状态 - 成功
            result = await service.check_status('kuaishou')
            assert result.status == QRLoginStatus.SUCCESS
            assert result.cookies is not None
    
    @pytest.mark.asyncio
    async def test_complete_weibo_login_flow(self):
        """测试完整的微博登录流程"""
        registry = PlatformQRRegistry()
        registry.register(WeiboQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "retcode": 20000000,
            "data": {
                "image": "https://login.sina.com.cn/qrcode/e2e_test.png",
                "qrid": "e2e_test_qrid_weibo"
            }
        }
        generate_response.raise_for_status = MagicMock()
        
        # Mock登录成功（带alt）
        success_response = MagicMock()
        success_response.json.return_value = {
            "retcode": 20000000,
            "data": {"alt": "test_alt_token"}
        }
        success_response.raise_for_status = MagicMock()
        
        # Mock获取完整Cookie
        alt_response = MagicMock()
        alt_response.raise_for_status = MagicMock()
        
        mock_cookie = MagicMock()
        mock_cookie.name = "SUB"
        mock_cookie.value = "e2e_test_sub_value"
        mock_cookie.domain = ".weibo.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        alt_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[
                generate_response,
                success_response,
                alt_response
            ])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # 获取二维码
            qr_result = await service.get_qrcode('weibo')
            assert qr_result.qrcode_key == "e2e_test_qrid_weibo"
            
            # 检查状态 - 成功
            result = await service.check_status('weibo')
            assert result.status == QRLoginStatus.SUCCESS
            assert result.cookies is not None


class TestE2EErrorHandling:
    """端到端错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_network_timeout_flow(self):
        """测试网络超时错误流程"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=TimeoutError("Connection timed out"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # 尝试获取二维码 - 应该抛出异常
            with pytest.raises(Exception):
                await service.get_qrcode('bilibili')
    
    @pytest.mark.asyncio
    async def test_qr_expired_flow(self):
        """测试二维码过期流程"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 0,
            "data": {
                "url": "https://qr.bilibili.com/test",
                "qrcode_key": "test_key"
            }
        }
        generate_response.raise_for_status = MagicMock()
        
        # Mock过期响应
        expired_response = MagicMock()
        expired_response.json.return_value = {
            "code": 0,
            "data": {"code": 86038, "message": "二维码已过期"}
        }
        expired_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, expired_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # 获取二维码
            await service.get_qrcode('bilibili')
            
            # 检查状态 - 过期
            result = await service.check_status('bilibili')
            assert result.status == QRLoginStatus.EXPIRED
    
    @pytest.mark.asyncio
    async def test_platform_not_supported_flow(self):
        """测试不支持的平台流程"""
        registry = PlatformQRRegistry()
        service = QRLoginService(registry)
        
        # 尝试获取不支持的平台
        with pytest.raises(ValueError) as exc_info:
            await service.get_qrcode('unsupported_platform')
        assert "不支持扫码登录" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_platform_disabled_flow(self):
        """测试平台禁用流程"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=False)  # 禁用
        service = QRLoginService(registry)
        
        # 尝试获取禁用的平台
        with pytest.raises(ValueError) as exc_info:
            await service.get_qrcode('bilibili')
        assert "不支持扫码登录" in str(exc_info.value) or "禁用" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_check_status_without_qrcode(self):
        """测试未获取二维码时检查状态"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # 直接检查状态（未获取二维码）
        result = await service.check_status('bilibili')
        assert result.status == QRLoginStatus.ERROR
        assert "请先获取二维码" in result.message


class TestE2EErrorMessageLocalization:
    """端到端错误消息本地化测试"""
    
    def test_all_error_codes_have_chinese_messages(self):
        """测试所有错误代码都有中文消息"""
        for error_code in QRLoginErrorCode.__dict__.values():
            if isinstance(error_code, str) and not error_code.startswith('_'):
                message = get_error_message(error_code)
                # 验证消息包含中文
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in message)
                assert has_chinese or error_code not in ERROR_MESSAGES, \
                    f"错误代码 {error_code} 的消息不包含中文: {message}"
    
    def test_classify_exception_returns_chinese_messages(self):
        """测试异常分类返回中文消息"""
        test_cases = [
            (TimeoutError("Connection timed out"), "网络"),
            (Exception("browser launch failed"), "浏览器"),
            (Exception("需要验证码"), "验证"),
            (Exception("cookie convert error"), "Cookie"),
            (Exception("network connection failed"), "网络"),
        ]
        
        for exception, expected_keyword in test_cases:
            error_code, message = classify_exception(exception)
            # 验证消息包含预期关键词或中文
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in message)
            assert has_chinese or expected_keyword.lower() in message.lower(), \
                f"异常 {exception} 的消息不包含预期内容: {message}"


class TestE2ECookieSaving:
    """端到端Cookie保存测试"""
    
    def test_save_cookies_to_file_success(self):
        """测试Cookie保存成功"""
        test_cookies = """# Netscape HTTP Cookie File
.bilibili.com\tTRUE\t/\tTRUE\t1735689600\tSESSDATA\ttest_value
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.api.qr_login.get_cookies_dir', return_value=Path(temp_dir)):
                result = save_cookies_to_file('bilibili', test_cookies)
                assert result is True
                
                # 验证文件已创建
                cookie_file = Path(temp_dir) / "bilibili_cookies.txt"
                assert cookie_file.exists()
                
                # 验证文件不为空（内容可能被加密）
                content = cookie_file.read_text()
                assert len(content) > 0
    
    def test_save_cookies_unknown_platform(self):
        """测试保存未知平台的Cookie"""
        test_cookies = "# Netscape HTTP Cookie File\n"
        result = save_cookies_to_file('unknown_platform', test_cookies)
        assert result is False


class TestE2EMultiPlatformFlow:
    """端到端多平台流程测试"""
    
    @pytest.mark.asyncio
    async def test_switch_between_platforms(self):
        """测试在多个平台之间切换"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        registry.register(KuaishouQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock B站响应
        bilibili_generate = MagicMock()
        bilibili_generate.json.return_value = {
            "code": 0,
            "data": {"url": "https://qr.bilibili.com/test", "qrcode_key": "bilibili_key"}
        }
        bilibili_generate.raise_for_status = MagicMock()
        
        # Mock快手响应
        kuaishou_generate = MagicMock()
        kuaishou_generate.json.return_value = {
            "result": 1,
            "data": {"qrcodeUrl": "https://kuaishou.com/qr", "sid": "kuaishou_sid"}
        }
        kuaishou_generate.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=bilibili_generate)
            mock_instance.post = AsyncMock(return_value=kuaishou_generate)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # 获取B站二维码
            bilibili_qr = await service.get_qrcode('bilibili')
            assert bilibili_qr.qrcode_key == "bilibili_key"
            
            # 获取快手二维码
            kuaishou_qr = await service.get_qrcode('kuaishou')
            assert kuaishou_qr.qrcode_key == "kuaishou_sid"
            
            # 验证两个平台的缓存都存在
            assert 'bilibili' in service._qrcode_cache
            assert 'kuaishou' in service._qrcode_cache
    
    @pytest.mark.asyncio
    async def test_cancel_login_clears_cache(self):
        """测试取消登录清除缓存"""
        registry = PlatformQRRegistry()
        registry.register(BilibiliQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 0,
            "data": {"url": "https://qr.bilibili.com/test", "qrcode_key": "test_key"}
        }
        generate_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=generate_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            # 获取二维码
            await service.get_qrcode('bilibili')
            assert 'bilibili' in service._qrcode_cache
            
            # 取消登录
            await service.cancel_login('bilibili')
            assert 'bilibili' not in service._qrcode_cache


class TestE2EAllPlatformsLoginFlow:
    """所有平台端到端登录流程测试"""
    
    @pytest.mark.asyncio
    async def test_iqiyi_complete_flow(self):
        """测试爱奇艺完整登录流程"""
        registry = PlatformQRRegistry()
        registry.register(IqiyiQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": "A00000",
            "data": {"token": "e2e_iqiyi_token"}
        }
        generate_response.raise_for_status = MagicMock()
        
        # Mock登录成功
        success_response = MagicMock()
        success_response.json.return_value = {
            "code": "A00000",
            "data": {"status": 2}
        }
        success_response.raise_for_status = MagicMock()
        
        mock_cookie = MagicMock()
        mock_cookie.name = "P00001"
        mock_cookie.value = "e2e_test_p00001"
        mock_cookie.domain = ".iqiyi.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        success_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, success_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            qr_result = await service.get_qrcode('iqiyi')
            assert qr_result.qrcode_key == "e2e_iqiyi_token"
            
            result = await service.check_status('iqiyi')
            assert result.status == QRLoginStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_mango_complete_flow(self):
        """测试芒果TV完整登录流程"""
        registry = PlatformQRRegistry()
        registry.register(MangoQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码
        generate_response = MagicMock()
        generate_response.json.return_value = {
            "code": 200,
            "data": {"qrcode": "https://mgtv.com/qr", "token": "e2e_mango_token"}
        }
        generate_response.raise_for_status = MagicMock()
        
        # Mock登录成功
        success_response = MagicMock()
        success_response.json.return_value = {
            "code": 200,
            "data": {"status": 2}
        }
        success_response.raise_for_status = MagicMock()
        
        mock_cookie = MagicMock()
        mock_cookie.name = "PM_CHKID"
        mock_cookie.value = "e2e_test_pm_chkid"
        mock_cookie.domain = ".mgtv.com"
        mock_cookie.path = "/"
        mock_cookie.secure = True
        mock_cookie.expires = 1735689600
        
        mock_cookies = MagicMock()
        mock_cookies.jar = [mock_cookie]
        success_response.cookies = mock_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, success_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            qr_result = await service.get_qrcode('mango')
            assert qr_result.qrcode_key == "e2e_mango_token"
            
            result = await service.check_status('mango')
            assert result.status == QRLoginStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_tencent_complete_flow(self):
        """测试腾讯视频完整登录流程"""
        registry = PlatformQRRegistry()
        registry.register(TencentQRProvider(), enabled=True)
        service = QRLoginService(registry)
        
        # Mock生成二维码 - 需要正确设置status_code和cookies
        generate_response = MagicMock()
        generate_response.status_code = 200
        generate_response.content = b'\x89PNG\r\n\x1a\n'  # PNG header
        
        # 创建mock cookies jar
        mock_qrsig_cookie = MagicMock()
        mock_qrsig_cookie.name = "qrsig"
        mock_qrsig_cookie.value = "e2e_tencent_qrsig"
        mock_qrsig_cookie.domain = ".qq.com"
        mock_qrsig_cookie.path = "/"
        mock_qrsig_cookie.secure = True
        mock_qrsig_cookie.expires = 1735689600
        
        mock_cookies_jar = MagicMock()
        mock_cookies_jar.jar = [mock_qrsig_cookie]
        mock_cookies_jar.get = MagicMock(return_value="e2e_tencent_qrsig")
        generate_response.cookies = mock_cookies_jar
        generate_response.raise_for_status = MagicMock()
        
        # Mock登录成功响应
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "ptuiCB('0','0','https://v.qq.com/','0','登录成功!', 'test_nick');"
        success_response.raise_for_status = MagicMock()
        
        mock_p_skey_cookie = MagicMock()
        mock_p_skey_cookie.name = "p_skey"
        mock_p_skey_cookie.value = "e2e_test_p_skey"
        mock_p_skey_cookie.domain = ".qq.com"
        mock_p_skey_cookie.path = "/"
        mock_p_skey_cookie.secure = True
        mock_p_skey_cookie.expires = 1735689600
        
        mock_success_cookies = MagicMock()
        mock_success_cookies.jar = [mock_p_skey_cookie]
        success_response.cookies = mock_success_cookies
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=[generate_response, success_response, success_response])
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            qr_result = await service.get_qrcode('tencent')
            assert qr_result.qrcode_key == "e2e_tencent_qrsig"
            
            result = await service.check_status('tencent')
            assert result.status == QRLoginStatus.SUCCESS
