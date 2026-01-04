"""
增量更新 API
"""
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from src.models.database import get_session
from src.models.delta_package import DeltaPackage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/updates", tags=["updates"])


class DeltaInfo(BaseModel):
    """差异包信息"""
    source_version: str
    target_version: str
    delta_size: int
    delta_hash: str
    delta_url: str
    full_size: int
    savings_percent: float


class UpdateCheckResponse(BaseModel):
    """更新检查响应"""
    has_update: bool
    latest_version: str
    delta_available: bool = False
    delta_info: Optional[DeltaInfo] = None
    recommended_update_type: str = "full"  # "delta" | "full"


@router.post("/check")
async def check_updates(
    request: dict,
    db: AsyncSession = Depends(get_session)
):
    """
    检查更新（扩展支持增量更新）

    请求体:
    {
        "current_version": "1.0.0",
        "platform": "win32",
        "arch": "x64"
    }
    """
    try:
        current_version = request.get("current_version")
        platform = request.get("platform", "win32")
        arch = request.get("arch", "x64")

        if not current_version:
            raise HTTPException(status_code=400, detail="缺少 current_version 参数")

        # TODO: 从配置或数据库获取最新版本
        # 这里暂时硬编码，实际应该从版本管理系统获取
        latest_version = "1.0.1"  # 示例

        has_update = current_version != latest_version

        if not has_update:
            return UpdateCheckResponse(
                has_update=False,
                latest_version=current_version
            )

        # 查询是否存在增量更新包
        stmt = select(DeltaPackage).where(
            and_(
                DeltaPackage.source_version == current_version,
                DeltaPackage.target_version == latest_version,
                DeltaPackage.platform == platform,
                DeltaPackage.arch == arch
            )
        )
        result = await db.execute(stmt)
        delta_package = result.scalar_one_or_none()

        if delta_package:
            # 存在增量更新包
            delta_info = DeltaInfo(
                source_version=delta_package.source_version,
                target_version=delta_package.target_version,
                delta_size=delta_package.delta_size,
                delta_hash=delta_package.delta_hash,
                delta_url=delta_package.delta_url,
                full_size=delta_package.full_size,
                savings_percent=float(delta_package.savings_percent)
            )

            # 推荐使用增量更新（如果差异包更小且被推荐）
            recommended = "delta" if delta_package.is_recommended else "full"

            return UpdateCheckResponse(
                has_update=True,
                latest_version=latest_version,
                delta_available=True,
                delta_info=delta_info,
                recommended_update_type=recommended
            )
        else:
            # 不存在增量更新包，使用全量更新
            return UpdateCheckResponse(
                has_update=True,
                latest_version=latest_version,
                delta_available=False,
                recommended_update_type="full"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查更新失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deltas/{target_version}/from/{source_version}")
async def download_delta_package(
    target_version: str,
    source_version: str,
    platform: str = "win32",
    arch: str = "x64",
    db: AsyncSession = Depends(get_session)
):
    """
    下载差异包

    支持断点续传（Range 请求）
    """
    try:
        # 查询差异包
        stmt = select(DeltaPackage).where(
            and_(
                DeltaPackage.source_version == source_version,
                DeltaPackage.target_version == target_version,
                DeltaPackage.platform == platform,
                DeltaPackage.arch == arch
            )
        )
        result = await db.execute(stmt)
        delta_package = result.scalar_one_or_none()

        if not delta_package:
            raise HTTPException(status_code=404, detail="差异包不存在")

        # 更新下载统计
        delta_package.download_count += 1
        delta_package.last_used_at = datetime.utcnow()
        await db.commit()

        # 从 delta_url 解析文件路径
        # 假设 delta_url 格式为: /deltas/delta-1.0.0-to-1.0.1-win32-x64.zip
        file_path = Path(delta_package.delta_url.lstrip('/'))

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="差异包文件不存在")

        # 返回文件（支持断点续传）
        return FileResponse(
            path=str(file_path),
            media_type="application/zip",
            filename=file_path.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载差异包失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deltas/{target_version}/manifest")
async def get_delta_manifest(
    target_version: str,
    source_version: str,
    platform: str = "win32",
    arch: str = "x64",
    db: AsyncSession = Depends(get_session)
):
    """
    获取差异包清单文件
    """
    try:
        # 查询差异包
        stmt = select(DeltaPackage).where(
            and_(
                DeltaPackage.source_version == source_version,
                DeltaPackage.target_version == target_version,
                DeltaPackage.platform == platform,
                DeltaPackage.arch == arch
            )
        )
        result = await db.execute(stmt)
        delta_package = result.scalar_one_or_none()

        if not delta_package:
            raise HTTPException(status_code=404, detail="差异包不存在")

        # 返回清单
        return {
            "status": "success",
            "manifest": delta_package.manifest
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取清单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deltas/stats")
async def get_delta_stats(db: AsyncSession = Depends(get_session)):
    """
    获取差异包使用统计
    """
    try:
        # 总差异包数量
        total_count_stmt = select(func.count()).select_from(DeltaPackage)
        total_result = await db.execute(total_count_stmt)
        total_count = total_result.scalar() or 0

        # 总下载次数
        total_downloads_stmt = select(func.sum(DeltaPackage.download_count))
        downloads_result = await db.execute(total_downloads_stmt)
        total_downloads = downloads_result.scalar() or 0

        # 成功率
        success_stmt = select(
            func.sum(DeltaPackage.success_count),
            func.sum(DeltaPackage.failure_count)
        )
        success_result = await db.execute(success_stmt)
        success_row = success_result.first()

        total_success = success_row[0] or 0
        total_failure = success_row[1] or 0
        total_attempts = total_success + total_failure
        success_rate = (total_success / total_attempts * 100) if total_attempts > 0 else 0

        # 平均节省空间
        avg_savings_stmt = select(func.avg(DeltaPackage.savings_percent))
        avg_result = await db.execute(avg_savings_stmt)
        avg_savings = avg_result.scalar() or 0

        return {
            "status": "success",
            "stats": {
                "total_packages": total_count,
                "total_downloads": total_downloads,
                "success_rate": round(success_rate, 2),
                "average_savings_percent": round(float(avg_savings), 2)
            }
        }

    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deltas/report")
async def report_update_result(
    request: dict,
    db: AsyncSession = Depends(get_session)
):
    """
    上报更新结果（用于统计）

    请求体:
    {
        "source_version": "1.0.0",
        "target_version": "1.0.1",
        "platform": "win32",
        "arch": "x64",
        "update_type": "delta",
        "success": true,
        "download_size": 10485760,
        "duration": 30.5,
        "error": null
    }
    """
    try:
        source_version = request.get("source_version")
        target_version = request.get("target_version")
        platform = request.get("platform", "win32")
        arch = request.get("arch", "x64")
        update_type = request.get("update_type")
        success = request.get("success", False)

        if update_type == "delta":
            # 更新差异包统计
            stmt = select(DeltaPackage).where(
                and_(
                    DeltaPackage.source_version == source_version,
                    DeltaPackage.target_version == target_version,
                    DeltaPackage.platform == platform,
                    DeltaPackage.arch == arch
                )
            )
            result = await db.execute(stmt)
            delta_package = result.scalar_one_or_none()

            if delta_package:
                if success:
                    delta_package.success_count += 1
                else:
                    delta_package.failure_count += 1

                await db.commit()

        logger.info(
            f"更新结果上报: {source_version} -> {target_version}, "
            f"类型: {update_type}, 成功: {success}"
        )

        return {
            "status": "success",
            "message": "统计已记录"
        }

    except Exception as e:
        logger.error(f"上报更新结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
