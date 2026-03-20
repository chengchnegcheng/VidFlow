"""
配置管理 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import logging

from src.core.config_manager import get_config_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    updates: Dict[str, Any]


class ConfigValueRequest(BaseModel):
    """单个配置值请求"""
    key: str
    value: Any


@router.get("")
async def get_all_config():
    """获取所有配置"""
    try:
        config_manager = get_config_manager()
        return {
            "status": "success",
            "config": config_manager.get_all()
        }
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key_path:path}")
async def get_config_value(key_path: str):
    """
    获取指定配置值

    Args:
        key_path: 配置路径，如 download.default_quality
    """
    try:
        config_manager = get_config_manager()
        value = config_manager.get(key_path)

        if value is None:
            raise HTTPException(status_code=404, detail=f"Config key not found: {key_path}")

        return {
            "status": "success",
            "key": key_path,
            "value": value
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config value: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set")
async def set_config_value(request: ConfigValueRequest):
    """设置单个配置值"""
    try:
        config_manager = get_config_manager()
        config_manager.set(request.key, request.value)

        return {
            "status": "success",
            "message": f"Config '{request.key}' updated successfully"
        }
    except Exception as e:
        logger.error(f"Failed to set config value: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def update_config(request: ConfigUpdateRequest):
    """批量更新配置"""
    try:
        config_manager = get_config_manager()
        config_manager.update(request.updates)

        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "config": config_manager.get_all()
        }
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_config():
    """重置配置为默认值"""
    try:
        config_manager = get_config_manager()
        config_manager.reset()

        return {
            "status": "success",
            "message": "Configuration reset to default",
            "config": config_manager.get_all()
        }
    except Exception as e:
        logger.error(f"Failed to reset config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
