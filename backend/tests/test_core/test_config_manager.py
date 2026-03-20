"""
配置管理器测试
"""
import pytest
import json
import tempfile
from pathlib import Path
from src.core.config_manager import ConfigManager, DEFAULT_CONFIG


@pytest.fixture
def temp_config_file(tmp_path):
    """创建临时配置文件"""
    config_file = tmp_path / "test_config.json"
    return config_file


@pytest.fixture
def config_manager(temp_config_file):
    """创建配置管理器实例"""
    # 直接传入临时配置文件路径
    manager = ConfigManager(config_file=temp_config_file)
    return manager


class TestConfigManager:
    """配置管理器测试类"""

    def test_default_config_structure(self, config_manager):
        """测试默认配置结构"""
        config = config_manager.load_config()

        # 检查主要配置节
        assert "app" in config
        assert "download" in config
        assert "subtitle" in config
        assert "advanced" in config

        # 检查 app 配置
        assert config["app"]["version"] == "3.1.0"
        assert config["app"]["first_run"] is True
        assert config["app"]["language"] == "zh-CN"

        # 检查 download 配置
        assert config["download"]["default_quality"] == "1080p"
        assert config["download"]["default_format"] == "mp4"
        assert config["download"]["max_concurrent"] == 3

    def test_load_nonexistent_config(self, config_manager):
        """测试加载不存在的配置文件"""
        # 配置文件不存在时应创建默认配置
        config = config_manager.load_config()

        assert config == DEFAULT_CONFIG
        assert config_manager.config_file.exists()

    def test_save_config(self, config_manager):
        """测试保存配置"""
        config_manager.load_config()
        config_manager.save_config()

        # 验证文件存在
        assert config_manager.config_file.exists()

        # 验证内容正确
        with open(config_manager.config_file, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)

        assert saved_config == config_manager.config

    def test_get_config_value(self, config_manager):
        """测试获取配置值"""
        config_manager.load_config()

        # 获取简单值
        quality = config_manager.get('download.default_quality')
        assert quality == '1080p'

        # 获取嵌套值
        version = config_manager.get('app.version')
        assert version == '3.1.0'

        # 获取不存在的值（使用默认值）
        unknown = config_manager.get('unknown.key', 'default_value')
        assert unknown == 'default_value'

    def test_set_config_value(self, config_manager):
        """测试设置配置值"""
        config_manager.load_config()

        # 设置简单值
        config_manager.set('download.default_quality', '4k')
        assert config_manager.get('download.default_quality') == '4k'

        # 验证已保存到文件
        with open(config_manager.config_file, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
        assert saved_config['download']['default_quality'] == '4k'

    def test_set_nested_config(self, config_manager):
        """测试设置嵌套配置"""
        config_manager.load_config()

        # 设置深层嵌套值
        config_manager.set('advanced.proxy.host', 'localhost')
        config_manager.set('advanced.proxy.port', 7890)

        assert config_manager.get('advanced.proxy.host') == 'localhost'
        assert config_manager.get('advanced.proxy.port') == 7890

    def test_update_config(self, config_manager):
        """测试批量更新配置"""
        config_manager.load_config()

        updates = {
            "download": {
                "default_quality": "4k",
                "max_concurrent": 5
            },
            "app": {
                "theme": "dark"
            }
        }

        config_manager.update(updates)

        # 验证更新生效
        assert config_manager.get('download.default_quality') == '4k'
        assert config_manager.get('download.max_concurrent') == 5
        assert config_manager.get('app.theme') == 'dark'

        # 验证其他值未被影响
        assert config_manager.get('download.default_format') == 'mp4'

    def test_reset_config(self, config_manager):
        """测试重置配置"""
        config_manager.load_config()

        # 修改一些配置
        config_manager.set('download.default_quality', '4k')
        config_manager.set('app.theme', 'dark')

        # 重置
        config_manager.reset()

        # 验证恢复默认值
        assert config_manager.get('download.default_quality') == '1080p'
        assert config_manager.get('app.theme') == 'light'

    def test_get_all_config(self, config_manager):
        """测试获取所有配置"""
        config_manager.load_config()

        all_config = config_manager.get_all()

        # 验证返回完整配置
        assert "app" in all_config
        assert "download" in all_config
        assert "subtitle" in all_config
        assert "advanced" in all_config

        # 验证是副本（不会影响原配置）
        all_config["app"]["version"] = "99.99.99"
        assert config_manager.get('app.version') == '3.1.0'

    def test_merge_config(self, config_manager):
        """测试配置合并"""
        base = {
            "a": 1,
            "b": {
                "c": 2,
                "d": 3
            }
        }

        updates = {
            "b": {
                "c": 20,
                "e": 4
            },
            "f": 5
        }

        result = config_manager._merge_config(base, updates)

        # 验证合并结果
        assert result["a"] == 1
        assert result["b"]["c"] == 20  # 覆盖
        assert result["b"]["d"] == 3   # 保留
        assert result["b"]["e"] == 4   # 新增
        assert result["f"] == 5        # 新增

    def test_load_existing_config(self, config_manager, temp_config_file):
        """测试加载已存在的配置文件"""
        # 创建配置文件
        existing_config = {
            "app": {
                "version": "3.0.0",
                "theme": "dark"
            },
            "download": {
                "default_quality": "4k"
            }
        }

        with open(temp_config_file, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f)

        # 加载配置
        config = config_manager.load_config()

        # 验证用户配置被保留
        assert config["app"]["theme"] == "dark"
        assert config["download"]["default_quality"] == "4k"

        # 验证缺失的配置被补全
        assert "subtitle" in config
        assert config["download"]["default_format"] == "mp4"

    def test_invalid_json_handling(self, config_manager, temp_config_file):
        """测试处理无效的 JSON 文件"""
        # 创建损坏的配置文件
        with open(temp_config_file, 'w') as f:
            f.write("{ invalid json }")

        # 加载配置（应该使用默认配置）
        config = config_manager.load_config()

        assert config == DEFAULT_CONFIG

    def test_config_persistence(self, config_manager):
        """测试配置持久化"""
        config_manager.load_config()

        # 修改并保存
        config_manager.set('download.default_quality', '8k')

        # 创建新的管理器实例，加载同一文件
        new_manager = ConfigManager(config_file=config_manager.config_file)

        # 验证配置已持久化
        assert new_manager.get('download.default_quality') == '8k'

    def test_proxy_config(self, config_manager):
        """测试代理配置"""
        config_manager.load_config()

        # 设置代理配置
        config_manager.set('advanced.proxy.enabled', True)
        config_manager.set('advanced.proxy.type', 'http')
        config_manager.set('advanced.proxy.host', '127.0.0.1')
        config_manager.set('advanced.proxy.port', 7890)

        # 验证代理配置
        assert config_manager.get('advanced.proxy.enabled') is True
        assert config_manager.get('advanced.proxy.type') == 'http'
        assert config_manager.get('advanced.proxy.host') == '127.0.0.1'
        assert config_manager.get('advanced.proxy.port') == 7890

    def test_subtitle_default_config(self, config_manager):
        """测试字幕默认配置"""
        config_manager.load_config()

        # 验证字幕默认配置
        assert config_manager.get('subtitle.default_model') == 'base'
        assert config_manager.get('subtitle.default_source_lang') == 'auto'
        assert config_manager.get('subtitle.default_target_langs') == ['zh']

    def test_download_config_defaults(self, config_manager):
        """测试下载配置默认值"""
        config_manager.load_config()

        # 验证下载配置默认值
        default_path = config_manager.get('download.default_path')
        assert isinstance(default_path, str)
        assert default_path.strip() != ''
        assert config_manager.get('download.default_quality') == '1080p'
        assert config_manager.get('download.default_format') == 'mp4'
        assert config_manager.get('download.max_concurrent') == 3
        assert config_manager.get('download.auto_subtitle') is False
        assert config_manager.get('download.auto_translate') is False

    def test_concurrent_access(self, config_manager):
        """测试并发访问配置"""
        config_manager.load_config()

        # 模拟并发修改
        config_manager.set('download.max_concurrent', 5)
        value1 = config_manager.get('download.max_concurrent')

        config_manager.set('download.max_concurrent', 10)
        value2 = config_manager.get('download.max_concurrent')

        # 验证最后的值生效
        assert value1 == 5
        assert value2 == 10
        assert config_manager.get('download.max_concurrent') == 10


class TestConfigManagerAdvanced:
    """配置管理器高级测试"""

    def test_multiple_config_managers(self, temp_config_file):
        """测试多个配置管理器实例"""
        # 创建两个管理器
        manager1 = ConfigManager(config_file=temp_config_file)

        manager2 = ConfigManager(config_file=temp_config_file)

        # 通过 manager1 修改
        manager1.set('download.default_quality', '4k')

        # manager2 重新加载后应该看到更新
        manager2.load_config()
        assert manager2.get('download.default_quality') == '4k'

    def test_config_file_permissions(self, config_manager, tmp_path):
        """测试配置文件权限问题"""
        # 创建只读目录（Windows 可能不支持，跳过）
        import platform
        if platform.system() != 'Windows':
            readonly_dir = tmp_path / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)

            config_manager.config_file = readonly_dir / "config.json"

            # 尝试保存应该处理错误
            config_manager.load_config()
            # 不应该抛出异常

    def test_empty_config_file(self, config_manager, temp_config_file):
        """测试空配置文件"""
        # 创建空文件
        temp_config_file.write_text('')

        # 加载应该使用默认配置
        config = config_manager.load_config()
        assert config == DEFAULT_CONFIG

    def test_partial_config_file(self, config_manager, temp_config_file):
        """测试部分配置文件"""
        # 只包含部分配置
        partial_config = {
            "app": {
                "theme": "dark"
            }
        }

        with open(temp_config_file, 'w', encoding='utf-8') as f:
            json.dump(partial_config, f)

        # 加载配置
        config = config_manager.load_config()

        # 验证部分配置被保留
        assert config["app"]["theme"] == "dark"

        # 验证缺失配置被补全
        assert "download" in config
        assert "subtitle" in config
        assert config["app"]["version"] == "3.1.0"
