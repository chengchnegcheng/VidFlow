"""
配置管理 API 测试
"""
import pytest
from httpx import AsyncClient
from src.core.config_manager import get_config_manager


@pytest.fixture(autouse=True)
async def reset_config_before_each_test():
    """每个测试前后重置配置"""
    # 测试前重置
    config_manager = get_config_manager()
    config_manager.reset()
    yield
    # 测试后重置
    config_manager.reset()


@pytest.mark.asyncio
class TestConfigAPI:
    """配置管理 API 测试类"""

    async def test_get_all_config(self, client: AsyncClient):
        """测试获取所有配置"""
        response = await client.get("/api/v1/config")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "config" in data
        assert "app" in data["config"]
        assert "download" in data["config"]
        assert "subtitle" in data["config"]
        assert "advanced" in data["config"]

    async def test_get_config_value(self, client: AsyncClient):
        """测试获取指定配置值"""
        # 获取下载质量配置
        response = await client.get("/api/v1/config/download.default_quality")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["key"] == "download.default_quality"
        assert "value" in data

    async def test_get_nested_config_value(self, client: AsyncClient):
        """测试获取嵌套配置值"""
        response = await client.get("/api/v1/config/advanced.proxy.host")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["key"] == "advanced.proxy.host"

    async def test_get_nonexistent_config(self, client: AsyncClient):
        """测试获取不存在的配置"""
        response = await client.get("/api/v1/config/nonexistent.key")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_set_config_value(self, client: AsyncClient):
        """测试设置配置值"""
        # 设置下载质量
        response = await client.post(
            "/api/v1/config/set",
            json={
                "key": "download.default_quality",
                "value": "4k"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "updated successfully" in data["message"]

        # 验证配置已更新
        verify_response = await client.get("/api/v1/config/download.default_quality")
        verify_data = verify_response.json()
        assert verify_data["value"] == "4k"

    async def test_update_config(self, client: AsyncClient):
        """测试批量更新配置"""
        updates = {
            "download": {
                "default_quality": "8k",
                "max_concurrent": 5
            },
            "app": {
                "theme": "dark"
            }
        }

        response = await client.post(
            "/api/v1/config/update",
            json={"updates": updates}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "config" in data

        # 验证更新生效
        assert data["config"]["download"]["default_quality"] == "8k"
        assert data["config"]["download"]["max_concurrent"] == 5
        assert data["config"]["app"]["theme"] == "dark"

    async def test_reset_config(self, client: AsyncClient):
        """测试重置配置"""
        # 先修改一些配置
        await client.post(
            "/api/v1/config/set",
            json={
                "key": "download.default_quality",
                "value": "4k"
            }
        )

        # 重置配置
        response = await client.post("/api/v1/config/reset")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "reset" in data["message"].lower()

        # 验证配置已恢复默认
        assert data["config"]["download"]["default_quality"] == "1080p"

    async def test_update_proxy_config(self, client: AsyncClient):
        """测试更新代理配置"""
        proxy_config = {
            "advanced": {
                "proxy": {
                    "enabled": True,
                    "type": "http",
                    "host": "127.0.0.1",
                    "port": 7890
                }
            }
        }

        response = await client.post(
            "/api/v1/config/update",
            json={"updates": proxy_config}
        )

        assert response.status_code == 200
        data = response.json()

        # 验证代理配置
        assert data["config"]["advanced"]["proxy"]["enabled"] is True
        assert data["config"]["advanced"]["proxy"]["host"] == "127.0.0.1"
        assert data["config"]["advanced"]["proxy"]["port"] == 7890

    async def test_update_subtitle_config(self, client: AsyncClient):
        """测试更新字幕配置"""
        subtitle_config = {
            "subtitle": {
                "default_model": "large-v3",
                "default_target_langs": ["en", "zh", "ja"]
            }
        }

        response = await client.post(
            "/api/v1/config/update",
            json={"updates": subtitle_config}
        )

        assert response.status_code == 200
        data = response.json()

        # 验证字幕配置
        assert data["config"]["subtitle"]["default_model"] == "large-v3"
        assert "en" in data["config"]["subtitle"]["default_target_langs"]
        assert "zh" in data["config"]["subtitle"]["default_target_langs"]
        assert "ja" in data["config"]["subtitle"]["default_target_langs"]

    async def test_invalid_json_update(self, client: AsyncClient):
        """测试无效的 JSON 更新"""
        response = await client.post(
            "/api/v1/config/update",
            json={"invalid": "data"}
        )

        # 应该返回错误（缺少 updates 字段）
        assert response.status_code == 422  # Validation error

    async def test_config_persistence(self, client: AsyncClient):
        """测试配置持久化"""
        # 设置配置
        await client.post(
            "/api/v1/config/set",
            json={
                "key": "download.default_quality",
                "value": "4k"
            }
        )

        # 获取配置（应该仍然是 4k）
        response = await client.get("/api/v1/config/download.default_quality")
        data = response.json()

        assert data["value"] == "4k"

    async def test_multiple_config_updates(self, client: AsyncClient):
        """测试多次配置更新"""
        # 第一次更新
        await client.post(
            "/api/v1/config/set",
            json={
                "key": "download.max_concurrent",
                "value": 5
            }
        )

        # 第二次更新
        await client.post(
            "/api/v1/config/set",
            json={
                "key": "download.max_concurrent",
                "value": 10
            }
        )

        # 验证最后的值生效
        response = await client.get("/api/v1/config/download.max_concurrent")
        data = response.json()

        assert data["value"] == 10

    async def test_get_config_with_default_values(self, client: AsyncClient):
        """测试获取带默认值的配置"""
        # 重置配置确保是默认值
        await client.post("/api/v1/config/reset")

        # 获取默认配置
        response = await client.get("/api/v1/config")
        data = response.json()
        config = data["config"]

        # 验证默认值
        assert config["download"]["default_quality"] == "1080p"
        assert config["download"]["default_format"] == "mp4"
        assert config["download"]["max_concurrent"] == 3
        assert config["download"]["auto_subtitle"] is False
        assert config["app"]["theme"] == "light"
        assert config["app"]["language"] == "zh-CN"


@pytest.mark.asyncio
class TestConfigAPIAdvanced:
    """配置管理 API 高级测试"""

    async def test_concurrent_config_updates(self, client: AsyncClient):
        """测试并发配置更新"""
        import asyncio

        # 并发更新不同的配置
        tasks = [
            client.post("/api/v1/config/set", json={"key": "download.max_concurrent", "value": i})
            for i in range(1, 6)
        ]

        responses = await asyncio.gather(*tasks)

        # 所有请求都应该成功
        for response in responses:
            assert response.status_code == 200

    async def test_config_validation(self, client: AsyncClient):
        """测试配置验证"""
        # 尝试设置无效的配置类型（应该被接受，因为没有类型检查）
        response = await client.post(
            "/api/v1/config/set",
            json={
                "key": "download.max_concurrent",
                "value": "invalid_number"  # 字符串而不是数字
            }
        )

        # API 目前会接受任何值
        assert response.status_code == 200

    async def test_get_nested_config_structure(self, client: AsyncClient):
        """测试获取嵌套配置结构"""
        response = await client.get("/api/v1/config")
        data = response.json()
        config = data["config"]

        # 验证嵌套结构完整
        assert "advanced" in config
        assert "proxy" in config["advanced"]
        assert "enabled" in config["advanced"]["proxy"]
        assert "type" in config["advanced"]["proxy"]
        assert "host" in config["advanced"]["proxy"]
        assert "port" in config["advanced"]["proxy"]
