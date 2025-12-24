"""
测试日志API
"""
import pytest
from httpx import AsyncClient
from pathlib import Path

@pytest.mark.asyncio
async def test_get_logs(client: AsyncClient):
    """测试获取日志列表"""
    response = await client.get("/api/v1/logs/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_logs_with_filter(client: AsyncClient):
    """测试带过滤的日志获取"""
    response = await client.get("/api/v1/logs/?level=ERROR&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_log_stats(client: AsyncClient):
    """测试获取日志统计"""
    response = await client.get("/api/v1/logs/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_lines" in data
    assert "error_count" in data
    assert "warning_count" in data
    assert "info_count" in data
    assert "file_size" in data

@pytest.mark.asyncio
async def test_tail_logs(client: AsyncClient):
    """测试获取最新日志"""
    response = await client.get("/api/v1/logs/tail?lines=20")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_clear_logs(client: AsyncClient):
    """测试清空日志"""
    response = await client.delete("/api/v1/logs/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
