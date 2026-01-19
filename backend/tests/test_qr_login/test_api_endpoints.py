"""
QR登录API端点单元测试

测试API端点的正常响应和错误处理。
**Validates: Requirements 5.1-5.7, 6.1-6.4**
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.core.qr_login.models import (
    QRCodeResult,
    QRLoginResult,
    QRLoginStatus,
    QRLoginErrorCode,
)
from src.core.qr_login.registry import PlatformQRRegistry, reset_qr_registry
from src.core.qr_login.service import QRLoginService, reset_qr_login_service
from src.api.qr_login import router, ERROR_MESSAGES


# 创建测试应用
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# ============ Fixtures ============

@pytest.fixture(autouse=True)
def reset_services():
    """每个测试前重置服务"""
    reset_qr_registry()
    reset_qr_login_service()
    yield
    reset_qr_registry()
    reset_qr_login_service()


@pytest.fixture
def mock_registry():
    """创建Mock注册表"""
    registry = MagicMock(spec=PlatformQRRegistry)
    return registry


@pytest.fixture
def mock_service():
    """创建Mock服务"""
    service = MagicMock(spec=QRLoginService)
    return service


# ============ 获取支持平台列表测试 ============

class TestGetSupportedPlatforms:
    """测试获取支持平台列表端点"""
    
    def test_get_supported_platforms_empty(self):
        """测试空平台列表"""
        with patch('src.api.qr_login.get_qr_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_supported_platforms.return_value = []
            mock_get_registry.return_value = mock_registry
            
            response = client.get("/api/v1/admin/cookies/qr/supported")
            
            assert response.status_code == 200
            data = response.json()
            assert "platforms" in data
            assert data["platforms"] == []
    
    def test_get_supported_platforms_with_data(self):
        """测试有平台数据的列表"""
        platforms_data = [
            {
                "platform_id": "bilibili",
                "platform_name_zh": "哔哩哔哩",
                "qr_expiry_seconds": 180,
                "enabled": True
            },
            {
                "platform_id": "douyin",
                "platform_name_zh": "抖音",
                "qr_expiry_seconds": 180,
                "enabled": False
            }
        ]
        
        with patch('src.api.qr_login.get_qr_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_supported_platforms.return_value = platforms_data
            mock_get_registry.return_value = mock_registry
            
            response = client.get("/api/v1/admin/cookies/qr/supported")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["platforms"]) == 2
            assert data["platforms"][0]["platform_id"] == "bilibili"
            assert data["platforms"][0]["enabled"] is True
            assert data["platforms"][1]["platform_id"] == "douyin"
            assert data["platforms"][1]["enabled"] is False


# ============ 获取二维码测试 ============

class TestGetQRCode:
    """测试获取二维码端点"""
    
    def test_get_qrcode_success(self):
        """测试成功获取二维码"""
        qr_result = QRCodeResult(
            qrcode_url="https://example.com/qr/123",
            qrcode_key="test_key_123",
            expires_in=180,
            message="请使用 哔哩哔哩 APP 扫描二维码登录"
        )
        
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_qrcode.return_value = qr_result
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/v1/admin/cookies/qr/bilibili/qrcode")
            
            assert response.status_code == 200
            data = response.json()
            assert data["qrcode_url"] == "https://example.com/qr/123"
            assert data["qrcode_key"] == "test_key_123"
            assert data["expires_in"] == 180
            assert "哔哩哔哩" in data["message"]
    
    def test_get_qrcode_platform_not_supported(self):
        """测试不支持的平台"""
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_qrcode.side_effect = ValueError("平台 unknown 不支持扫码登录")
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/v1/admin/cookies/qr/unknown/qrcode")
            
            assert response.status_code == 400
            data = response.json()["detail"]
            assert data["status"] == "error"
            assert data["error_code"] == QRLoginErrorCode.PLATFORM_NOT_SUPPORTED
    
    def test_get_qrcode_platform_disabled(self):
        """测试已禁用的平台"""
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_qrcode.side_effect = ValueError("平台 bilibili 扫码登录已禁用")
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/v1/admin/cookies/qr/bilibili/qrcode")
            
            assert response.status_code == 400
            data = response.json()["detail"]
            assert data["status"] == "error"
            assert data["error_code"] == QRLoginErrorCode.PLATFORM_DISABLED
    
    def test_get_qrcode_timeout(self):
        """测试网络超时"""
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_qrcode.side_effect = TimeoutError("Connection timeout")
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/v1/admin/cookies/qr/bilibili/qrcode")
            
            assert response.status_code == 504
            data = response.json()["detail"]
            assert data["status"] == "error"
            assert data["error_code"] == QRLoginErrorCode.NETWORK_TIMEOUT
    
    def test_get_qrcode_browser_error(self):
        """测试浏览器错误"""
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_qrcode.side_effect = Exception("Browser launch failed")
            mock_get_service.return_value = mock_service
            
            response = client.get("/api/v1/admin/cookies/qr/douyin/qrcode")
            
            assert response.status_code == 500
            data = response.json()["detail"]
            assert data["status"] == "error"
            assert data["error_code"] == QRLoginErrorCode.BROWSER_ERROR


# ============ 检查扫码状态测试 ============

class TestCheckQRCodeStatus:
    """测试检查扫码状态端点"""
    
    def test_check_status_waiting(self):
        """测试等待扫码状态"""
        status_result = QRLoginResult(
            status=QRLoginStatus.WAITING,
            message="等待扫码..."
        )
        
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.check_status.return_value = status_result
            mock_get_service.return_value = mock_service
            
            response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/check")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "waiting"
            assert "等待" in data["message"]
    
    def test_check_status_scanned(self):
        """测试已扫码状态"""
        status_result = QRLoginResult(
            status=QRLoginStatus.SCANNED,
            message="已扫码，请在手机上确认登录"
        )
        
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.check_status.return_value = status_result
            mock_get_service.return_value = mock_service
            
            response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/check")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "scanned"
            assert "确认" in data["message"]
    
    def test_check_status_success(self):
        """测试登录成功状态"""
        status_result = QRLoginResult(
            status=QRLoginStatus.SUCCESS,
            message="登录成功",
            cookies=".bilibili.com\tTRUE\t/\tFALSE\t1735689600\tSESSDATA\ttest123"
        )
        
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.check_status.return_value = status_result
            mock_get_service.return_value = mock_service
            
            with patch('src.api.qr_login.save_cookies_to_file') as mock_save:
                mock_save.return_value = True
                
                response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/check")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                mock_save.assert_called_once()
    
    def test_check_status_expired(self):
        """测试二维码过期状态"""
        status_result = QRLoginResult(
            status=QRLoginStatus.EXPIRED,
            message="二维码已过期，请重新获取"
        )
        
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.check_status.return_value = status_result
            mock_get_service.return_value = mock_service
            
            response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/check")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "expired"
            assert "过期" in data["message"]
    
    def test_check_status_error(self):
        """测试错误状态"""
        status_result = QRLoginResult(
            status=QRLoginStatus.ERROR,
            message="请先获取二维码"
        )
        
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.check_status.return_value = status_result
            mock_get_service.return_value = mock_service
            
            response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/check")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"


# ============ 取消登录测试 ============

class TestCancelQRLogin:
    """测试取消登录端点"""
    
    def test_cancel_login_success(self):
        """测试成功取消登录"""
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.cancel_login.return_value = None
            mock_get_service.return_value = mock_service
            
            response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/cancel")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_cancel_login_error_still_returns_success(self):
        """测试取消失败仍返回成功（避免前端卡住）"""
        with patch('src.api.qr_login.get_qr_login_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.cancel_login.side_effect = Exception("Cleanup failed")
            mock_get_service.return_value = mock_service
            
            response = client.post("/api/v1/admin/cookies/qr/bilibili/qrcode/cancel")
            
            # 即使出错也返回成功
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"


# ============ 启用/禁用平台测试 ============

class TestEnablePlatform:
    """测试启用/禁用平台端点"""
    
    def test_enable_platform_success(self):
        """测试成功启用平台"""
        with patch('src.api.qr_login.get_qr_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.has_platform.return_value = True
            mock_registry.set_enabled.return_value = True
            mock_get_registry.return_value = mock_registry
            
            response = client.post(
                "/api/v1/admin/cookies/qr/bilibili/enable",
                json={"enabled": True}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "启用" in data["message"]
    
    def test_disable_platform_success(self):
        """测试成功禁用平台"""
        with patch('src.api.qr_login.get_qr_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.has_platform.return_value = True
            mock_registry.set_enabled.return_value = True
            mock_get_registry.return_value = mock_registry
            
            response = client.post(
                "/api/v1/admin/cookies/qr/bilibili/enable",
                json={"enabled": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "禁用" in data["message"]
    
    def test_enable_nonexistent_platform(self):
        """测试启用不存在的平台"""
        with patch('src.api.qr_login.get_qr_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.has_platform.return_value = False
            mock_get_registry.return_value = mock_registry
            
            response = client.post(
                "/api/v1/admin/cookies/qr/unknown/enable",
                json={"enabled": True}
            )
            
            assert response.status_code == 404
            data = response.json()["detail"]
            assert data["status"] == "error"
            assert data["error_code"] == QRLoginErrorCode.PLATFORM_NOT_SUPPORTED


# ============ 错误消息测试 ============

class TestErrorMessages:
    """测试错误消息"""
    
    def test_all_error_codes_have_messages(self):
        """测试所有错误代码都有对应的中文消息"""
        error_codes = [
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
        
        for code in error_codes:
            assert code in ERROR_MESSAGES, f"Missing message for error code: {code}"
            message = ERROR_MESSAGES[code]
            assert message, f"Empty message for error code: {code}"
            # 验证消息是中文
            assert any('\u4e00' <= c <= '\u9fff' for c in message), \
                f"Message for {code} should contain Chinese characters"
    
    def test_error_messages_are_user_friendly(self):
        """测试错误消息对用户友好"""
        # 不应包含技术术语
        technical_terms = ['exception', 'error', 'null', 'undefined', 'traceback']
        
        for code, message in ERROR_MESSAGES.items():
            message_lower = message.lower()
            for term in technical_terms:
                assert term not in message_lower, \
                    f"Message for {code} contains technical term '{term}'"
