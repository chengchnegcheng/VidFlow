"""
配置管理器属性测试

Property 13: Configuration Persistence Round-Trip (已在test_models.py中测试)
Property 14: Configuration Validation
Validates: Requirements 10.4, 10.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch
from typing import Dict, Any
from pathlib import Path
import tempfile
import json
import os

from src.core.channels.config_manager import ConfigManager
from src.core.channels.models import MultiModeCaptureConfig, CaptureMode


# ============================================================================
# Strategies for generating test data
# ============================================================================

@st.composite
def valid_config_strategy(draw):
    """生成有效配置"""
    return {
        "preferred_mode": draw(st.sampled_from([m.value for m in CaptureMode])),
        "auto_fallback": draw(st.booleans()),
        "clash_api_address": f"127.0.0.1:{draw(st.integers(min_value=1024, max_value=65535))}",
        "clash_api_secret": draw(st.text(max_size=32)),
        "quic_blocking_enabled": draw(st.booleans()),
        "target_processes": ["WeChat.exe"],
        "diagnostic_mode": draw(st.booleans()),
        "no_detection_timeout": draw(st.integers(min_value=0, max_value=300)),
        "api_timeout": draw(st.integers(min_value=0, max_value=60)),
        "max_recovery_attempts": draw(st.integers(min_value=0, max_value=10)),
        "recovery_backoff_base": draw(st.floats(min_value=0.1, max_value=10.0)),
        "recovery_backoff_max": draw(st.floats(min_value=10.0, max_value=120.0)),
    }


@st.composite
def invalid_config_strategy(draw):
    """生成无效配置"""
    invalid_type = draw(st.sampled_from([
        "invalid_port",
        "negative_timeout",
        "empty_processes",
        "invalid_backoff",
    ]))
    
    config = {
        "preferred_mode": "hybrid",
        "auto_fallback": True,
        "clash_api_address": "127.0.0.1:9090",
        "target_processes": ["WeChat.exe"],
        "no_detection_timeout": 60,
        "api_timeout": 10,
        "max_recovery_attempts": 3,
        "recovery_backoff_base": 1.0,
        "recovery_backoff_max": 30.0,
    }
    
    if invalid_type == "invalid_port":
        config["clash_api_address"] = "127.0.0.1:invalid"
    elif invalid_type == "negative_timeout":
        config["no_detection_timeout"] = -1
    elif invalid_type == "empty_processes":
        config["target_processes"] = []
    elif invalid_type == "invalid_backoff":
        config["recovery_backoff_base"] = 50.0
        config["recovery_backoff_max"] = 10.0  # max < base
    
    return config


# ============================================================================
# Property 14: Configuration Validation
# Validates: Requirements 10.4, 10.6
# ============================================================================

class TestConfigurationValidation:
    """
    Property 14: Configuration Validation
    
    For any configuration dictionary, the validate() function should return an
    empty list for valid configurations and a non-empty list of error messages
    for invalid configurations. Invalid configurations should not be applied.
    
    **Feature: weixin-channels-deep-research, Property 14: Configuration Validation**
    **Validates: Requirements 10.4, 10.6**
    """

    @given(config_dict=valid_config_strategy())
    @settings(max_examples=100)
    def test_valid_config_returns_empty_errors(self, config_dict):
        """测试有效配置返回空错误列表
        
        Property: 对于有效配置，validate()应该返回空列表。
        """
        config = MultiModeCaptureConfig.from_dict(config_dict)
        errors = config.validate()
        
        assert isinstance(errors, list), "validate() should return a list"
        assert len(errors) == 0, f"Valid config should have no errors, got: {errors}"

    @given(config_dict=invalid_config_strategy())
    @settings(max_examples=100)
    def test_invalid_config_returns_errors(self, config_dict):
        """测试无效配置返回非空错误列表
        
        Property: 对于无效配置，validate()应该返回非空错误消息列表。
        """
        config = MultiModeCaptureConfig.from_dict(config_dict)
        errors = config.validate()
        
        assert isinstance(errors, list), "validate() should return a list"
        assert len(errors) > 0, f"Invalid config should have errors: {config_dict}"

    def test_invalid_port_format(self):
        """测试无效端口格式"""
        config = MultiModeCaptureConfig(clash_api_address="invalid")
        errors = config.validate()
        assert len(errors) > 0
        assert any("地址格式" in e or "端口" in e for e in errors)

    def test_port_out_of_range(self):
        """测试端口超出范围"""
        config = MultiModeCaptureConfig(clash_api_address="127.0.0.1:99999")
        errors = config.validate()
        assert len(errors) > 0
        assert any("端口" in e for e in errors)

    def test_negative_timeout(self):
        """测试负数超时"""
        config = MultiModeCaptureConfig(no_detection_timeout=-1)
        errors = config.validate()
        assert len(errors) > 0
        assert any("超时" in e or "负数" in e for e in errors)

    def test_empty_target_processes(self):
        """测试空目标进程列表"""
        config = MultiModeCaptureConfig(target_processes=[])
        errors = config.validate()
        assert len(errors) > 0
        assert any("进程" in e or "空" in e for e in errors)

    def test_invalid_backoff_range(self):
        """测试无效退避范围"""
        config = MultiModeCaptureConfig(
            recovery_backoff_base=50.0,
            recovery_backoff_max=10.0,
        )
        errors = config.validate()
        assert len(errors) > 0
        assert any("退避" in e for e in errors)


# ============================================================================
# Additional Unit Tests
# ============================================================================

class TestConfigManagerBasics:
    """配置管理器基础测试"""

    def test_default_config_path(self):
        """测试默认配置路径"""
        manager = ConfigManager()
        assert manager.config_path.name == ConfigManager.DEFAULT_CONFIG_FILENAME

    def test_custom_config_path(self):
        """测试自定义配置路径"""
        custom_path = Path("/custom/path/config.json")
        manager = ConfigManager(config_path=custom_path)
        assert manager.config_path == custom_path

    def test_initial_config_is_default(self):
        """测试初始配置是默认配置"""
        manager = ConfigManager()
        config = manager.get_config()
        default = MultiModeCaptureConfig.get_defaults()
        
        assert config.preferred_mode == default.preferred_mode
        assert config.auto_fallback == default.auto_fallback


class TestConfigPersistence:
    """配置持久化测试"""

    def test_save_and_load(self):
        """测试保存和加载配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.json"
            manager = ConfigManager(config_path=config_path)
            
            # 修改配置
            config = MultiModeCaptureConfig(
                preferred_mode=CaptureMode.CLASH_API,
                quic_blocking_enabled=True,
            )
            
            # 保存
            assert manager.save(config) is True
            assert config_path.exists()
            
            # 重新加载
            manager2 = ConfigManager(config_path=config_path)
            loaded = manager2.load()
            
            assert loaded.preferred_mode == CaptureMode.CLASH_API
            assert loaded.quic_blocking_enabled is True

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"
            manager = ConfigManager(config_path=config_path)
            
            config = manager.load()
            
            # 应该返回默认配置
            default = MultiModeCaptureConfig.get_defaults()
            assert config.preferred_mode == default.preferred_mode

    def test_load_invalid_json(self):
        """测试加载无效JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "invalid.json"
            
            # 写入无效JSON
            with open(config_path, 'w') as f:
                f.write("not valid json {{{")
            
            manager = ConfigManager(config_path=config_path)
            config = manager.load()
            
            # 应该返回默认配置
            default = MultiModeCaptureConfig.get_defaults()
            assert config.preferred_mode == default.preferred_mode

    def test_save_creates_backup(self):
        """测试保存时创建备份"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.json"
            manager = ConfigManager(config_path=config_path)
            
            # 第一次保存
            manager.save(MultiModeCaptureConfig(preferred_mode=CaptureMode.WINDIVERT))
            
            # 第二次保存
            manager.save(MultiModeCaptureConfig(preferred_mode=CaptureMode.CLASH_API))
            
            # 检查备份文件
            backup_path = manager.get_backup_path()
            assert backup_path.exists()


class TestConfigExportImport:
    """配置导入导出测试"""

    def test_export_config(self):
        """测试导出配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            export_path = Path(tmpdir) / "export.json"
            
            manager = ConfigManager(config_path=config_path)
            manager.set_config(MultiModeCaptureConfig(
                preferred_mode=CaptureMode.HYBRID,
                quic_blocking_enabled=True,
            ))
            
            assert manager.export_config(export_path) is True
            assert export_path.exists()
            
            # 验证导出内容
            with open(export_path, 'r') as f:
                data = json.load(f)
            assert data["preferred_mode"] == "hybrid"
            assert data["quic_blocking_enabled"] is True

    def test_import_config(self):
        """测试导入配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            import_path = Path(tmpdir) / "import.json"
            
            # 创建导入文件
            import_data = {
                "preferred_mode": "clash_api",
                "quic_blocking_enabled": True,
                "target_processes": ["WeChat.exe"],
            }
            with open(import_path, 'w') as f:
                json.dump(import_data, f)
            
            manager = ConfigManager()
            config = manager.import_config(import_path)
            
            assert config is not None
            assert config.preferred_mode == CaptureMode.CLASH_API
            assert config.quic_blocking_enabled is True

    def test_import_nonexistent_file(self):
        """测试导入不存在的文件"""
        manager = ConfigManager()
        config = manager.import_config(Path("/nonexistent/file.json"))
        assert config is None

    def test_import_invalid_json(self):
        """测试导入无效JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            import_path = Path(tmpdir) / "invalid.json"
            
            with open(import_path, 'w') as f:
                f.write("not valid json")
            
            manager = ConfigManager()
            config = manager.import_config(import_path)
            assert config is None


class TestConfigOperations:
    """配置操作测试"""

    def test_reset_to_defaults(self):
        """测试重置为默认值"""
        manager = ConfigManager()
        manager.set_config(MultiModeCaptureConfig(
            preferred_mode=CaptureMode.CLASH_API,
            quic_blocking_enabled=True,
        ))
        
        config = manager.reset_to_defaults()
        default = MultiModeCaptureConfig.get_defaults()
        
        assert config.preferred_mode == default.preferred_mode
        assert config.quic_blocking_enabled == default.quic_blocking_enabled

    def test_update_config(self):
        """测试更新配置"""
        manager = ConfigManager()
        
        config = manager.update_config(
            preferred_mode="clash_api",
            quic_blocking_enabled=True,
        )
        
        assert config.preferred_mode == CaptureMode.CLASH_API
        assert config.quic_blocking_enabled is True

    def test_is_valid(self):
        """测试配置有效性检查"""
        manager = ConfigManager()
        
        # 有效配置
        manager.set_config(MultiModeCaptureConfig())
        assert manager.is_valid() is True
        
        # 无效配置
        manager.set_config(MultiModeCaptureConfig(target_processes=[]))
        assert manager.is_valid() is False

    def test_config_exists(self):
        """测试配置文件存在检查"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            manager = ConfigManager(config_path=config_path)
            
            assert manager.config_exists() is False
            
            manager.save()
            assert manager.config_exists() is True

    def test_delete_config(self):
        """测试删除配置文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            manager = ConfigManager(config_path=config_path)
            
            manager.save()
            assert config_path.exists()
            
            assert manager.delete_config() is True
            assert not config_path.exists()

    def test_restore_from_backup(self):
        """测试从备份恢复"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            manager = ConfigManager(config_path=config_path)
            
            # 保存原始配置
            manager.save(MultiModeCaptureConfig(preferred_mode=CaptureMode.WINDIVERT))
            
            # 保存新配置（创建备份）
            manager.save(MultiModeCaptureConfig(preferred_mode=CaptureMode.CLASH_API))
            
            # 从备份恢复
            assert manager.restore_from_backup() is True
            
            # 验证恢复的配置
            config = manager.get_config()
            assert config.preferred_mode == CaptureMode.WINDIVERT

    def test_restore_from_backup_no_backup(self):
        """测试没有备份时恢复失败"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            manager = ConfigManager(config_path=config_path)
            
            assert manager.restore_from_backup() is False


class TestConfigTimestamps:
    """配置时间戳测试"""

    def test_load_updates_timestamp(self):
        """测试加载更新时间戳"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            manager = ConfigManager(config_path=config_path)
            
            manager.save()
            
            assert manager.last_load_time is None
            manager.load()
            assert manager.last_load_time is not None

    def test_save_updates_timestamp(self):
        """测试保存更新时间戳"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            manager = ConfigManager(config_path=config_path)
            
            assert manager.last_save_time is None
            manager.save()
            assert manager.last_save_time is not None
