"""
API边界情况和错误处理测试
"""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.api
class TestAPIEdgeCases:
    """API边界情况测试"""
    
    @pytest.mark.asyncio
    async def test_empty_json_body(self):
        """测试空JSON body"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={}
            )
        
        # 应该返回验证错误
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_very_long_url(self):
        """测试超长URL"""
        long_url = "https://example.com/" + "a" * 10000
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": long_url}
            )
        
        # 可能返回400、422或500
        assert response.status_code in [400, 422, status.HTTP_500_INTERNAL_SERVER_ERROR]
    
    @pytest.mark.asyncio
    async def test_special_characters_in_url(self):
        """测试URL中的特殊字符"""
        urls_with_special_chars = [
            "https://example.com/video?title=测试视频",
            "https://example.com/video?title=Test%20Video",
            "https://example.com/video#fragment",
        ]
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for url in urls_with_special_chars:
                response = await client.post(
                    "/api/v1/downloads/info",
                    json={"url": url}
                )
                # 应该能处理或返回错误（400是智能下载器返回的用户友好错误）
                assert response.status_code in [
                    status.HTTP_200_OK,
                    400,
                    422,
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ]
    
    @pytest.mark.asyncio
    async def test_null_values(self):
        """测试null值"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": None}
            )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_wrong_data_type(self):
        """测试错误的数据类型"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                json={"url": 123}  # 应该是字符串
            )
        
        assert response.status_code == 422


@pytest.mark.api
class TestAPILimits:
    """API限制测试"""
    
    @pytest.mark.asyncio
    async def test_tasks_pagination_limits(self):
        """测试任务分页限制"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 测试大limit
            response = await client.get("/api/v1/downloads/tasks?limit=1000")
            assert response.status_code == status.HTTP_200_OK
            
            # 测试零limit
            response = await client.get("/api/v1/downloads/tasks?limit=0")
            assert response.status_code == status.HTTP_200_OK
            
            # 测试负数limit
            response = await client.get("/api/v1/downloads/tasks?limit=-1")
            assert response.status_code in [status.HTTP_200_OK, 422]
    
    @pytest.mark.asyncio
    async def test_tasks_offset_limits(self):
        """测试任务偏移限制"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 测试大offset
            response = await client.get("/api/v1/downloads/tasks?offset=10000")
            assert response.status_code == status.HTTP_200_OK
            
            # 测试负数offset
            response = await client.get("/api/v1/downloads/tasks?offset=-1")
            assert response.status_code in [status.HTTP_200_OK, 422]


@pytest.mark.api
class TestAPIContentTypes:
    """API内容类型测试"""
    
    @pytest.mark.asyncio
    async def test_json_content_type(self):
        """测试JSON内容类型"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/system/info")
        
        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers.get("content-type", "")
    
    @pytest.mark.asyncio
    async def test_wrong_content_type(self):
        """测试错误的内容类型"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/downloads/info",
                content="url=test",
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
        
        # 应该返回错误或处理
        assert response.status_code in [422, status.HTTP_400_BAD_REQUEST]


@pytest.mark.api
class TestAPIQueryParameters:
    """API查询参数测试"""
    
    @pytest.mark.asyncio
    async def test_unknown_query_parameters(self):
        """测试未知查询参数"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/downloads/tasks?unknown_param=value&another=test"
            )
        
        # 应该忽略未知参数并正常返回
        assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_multiple_status_filters(self):
        """测试多个状态过滤器"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/downloads/tasks?status=pending&status=downloading"
            )
        
        # 应该能处理
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
class TestAPIResponseFormats:
    """API响应格式测试"""
    
    @pytest.mark.asyncio
    async def test_error_response_format(self):
        """测试错误响应格式"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/nonexistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        # 验证有响应体
        assert len(response.content) > 0
    
    @pytest.mark.asyncio
    async def test_success_response_format(self):
        """测试成功响应格式"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
