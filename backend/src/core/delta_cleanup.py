"""
差异包清理服务 - 自动清理过期的差异包
"""
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import AsyncSessionLocal
from src.models.delta_package import DeltaPackage

logger = logging.getLogger(__name__)


class DeltaCleanupService:
    """差异包清理服务"""

    # 清理配置
    MAX_UNUSED_DAYS = 30  # 超过30天未使用的差异包将被清理
    MAX_PACKAGES_PER_VERSION = 5  # 每个版本最多保留5个差异包
    CLEANUP_INTERVAL_HOURS = 24  # 每24小时运行一次清理

    def __init__(self, storage_dir: Path):
        """
        初始化清理服务

        Args:
            storage_dir: 差异包存储目录
        """
        self.storage_dir = Path(storage_dir)
        self._running = False
        self._task = None

    async def cleanup_unused_packages(self, db: AsyncSession) -> int:
        """
        清理超过30天未使用的差异包

        Args:
            db: 数据库会话

        Returns:
            int: 清理的差异包数量
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.MAX_UNUSED_DAYS)

        # 查询超过30天未使用的差异包
        stmt = select(DeltaPackage).where(
            and_(
                DeltaPackage.last_used_at.isnot(None),
                DeltaPackage.last_used_at < cutoff_date
            )
        )
        result = await db.execute(stmt)
        old_packages = result.scalars().all()

        cleaned_count = 0
        for package in old_packages:
            try:
                # 删除文件
                file_path = Path(package.delta_url.lstrip('/'))
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"删除过期差异包文件: {file_path}")

                # 删除数据库记录
                await db.delete(package)
                cleaned_count += 1

            except Exception as e:
                logger.error(f"清理差异包失败 {package.id}: {e}")

        if cleaned_count > 0:
            await db.commit()
            logger.info(f"清理了 {cleaned_count} 个超过 {self.MAX_UNUSED_DAYS} 天未使用的差异包")

        return cleaned_count

    async def cleanup_excess_packages(self, db: AsyncSession) -> int:
        """
        限制每个版本最多保留5个差异包（保留最新的）

        Args:
            db: 数据库会话

        Returns:
            int: 清理的差异包数量
        """
        # 获取所有目标版本
        stmt = select(DeltaPackage.target_version).distinct()
        result = await db.execute(stmt)
        target_versions = [row[0] for row in result.all()]

        cleaned_count = 0

        for target_version in target_versions:
            # 查询该版本的所有差异包，按创建时间降序
            stmt = select(DeltaPackage).where(
                DeltaPackage.target_version == target_version
            ).order_by(DeltaPackage.created_at.desc())

            result = await db.execute(stmt)
            packages = result.scalars().all()

            # 如果超过限制，删除旧的
            if len(packages) > self.MAX_PACKAGES_PER_VERSION:
                packages_to_delete = packages[self.MAX_PACKAGES_PER_VERSION:]

                for package in packages_to_delete:
                    try:
                        # 删除文件
                        file_path = Path(package.delta_url.lstrip('/'))
                        if file_path.exists():
                            file_path.unlink()
                            logger.info(f"删除多余差异包文件: {file_path}")

                        # 删除数据库记录
                        await db.delete(package)
                        cleaned_count += 1

                    except Exception as e:
                        logger.error(f"清理差异包失败 {package.id}: {e}")

        if cleaned_count > 0:
            await db.commit()
            logger.info(f"清理了 {cleaned_count} 个超出版本限制的差异包")

        return cleaned_count

    async def cleanup_by_disk_space(self, db: AsyncSession, required_space_mb: int = 100) -> int:
        """
        当存储空间不足时，优先删除最旧的差异包

        Args:
            db: 数据库会话
            required_space_mb: 需要的空间（MB）

        Returns:
            int: 清理的差异包数量
        """
        import shutil

        # 检查可用空间
        stat = shutil.disk_usage(self.storage_dir)
        available_mb = stat.free / (1024 * 1024)

        if available_mb >= required_space_mb:
            logger.debug(f"存储空间充足: {available_mb:.2f}MB 可用")
            return 0

        logger.warning(f"存储空间不足: 仅 {available_mb:.2f}MB 可用，需要 {required_space_mb}MB")

        # 查询所有差异包，按创建时间升序（最旧的优先）
        stmt = select(DeltaPackage).order_by(DeltaPackage.created_at.asc())
        result = await db.execute(stmt)
        packages = result.scalars().all()

        cleaned_count = 0
        freed_space_mb = 0

        for package in packages:
            try:
                # 删除文件
                file_path = Path(package.delta_url.lstrip('/'))
                if file_path.exists():
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    file_path.unlink()
                    freed_space_mb += file_size_mb
                    logger.info(f"删除差异包以释放空间: {file_path} ({file_size_mb:.2f}MB)")

                # 删除数据库记录
                await db.delete(package)
                cleaned_count += 1

                # 检查是否已释放足够空间
                if freed_space_mb >= required_space_mb:
                    break

            except Exception as e:
                logger.error(f"清理差异包失败 {package.id}: {e}")

        if cleaned_count > 0:
            await db.commit()
            logger.info(f"清理了 {cleaned_count} 个差异包，释放了 {freed_space_mb:.2f}MB 空间")

        return cleaned_count

    async def run_cleanup(self) -> dict:
        """
        运行完整的清理流程

        Returns:
            dict: 清理结果统计
        """
        logger.info("开始差异包清理任务")

        async with AsyncSessionLocal() as db:
            try:
                # 清理未使用的差异包
                unused_count = await self.cleanup_unused_packages(db)

                # 清理超出版本限制的差异包
                excess_count = await self.cleanup_excess_packages(db)

                # 检查磁盘空间（如果需要则清理）
                space_count = await self.cleanup_by_disk_space(db, required_space_mb=100)

                total_count = unused_count + excess_count + space_count

                result = {
                    "total_cleaned": total_count,
                    "unused_cleaned": unused_count,
                    "excess_cleaned": excess_count,
                    "space_cleaned": space_count,
                    "timestamp": datetime.utcnow().isoformat()
                }

                logger.info(f"差异包清理完成: {result}")
                return result

            except Exception as e:
                logger.error(f"差异包清理失败: {e}")
                return {
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }

    async def start_scheduled_cleanup(self):
        """启动定时清理任务"""
        if self._running:
            logger.warning("清理服务已在运行")
            return

        self._running = True
        logger.info(f"启动差异包定时清理服务（间隔: {self.CLEANUP_INTERVAL_HOURS}小时）")

        async def cleanup_loop():
            while self._running:
                try:
                    await self.run_cleanup()
                except Exception as e:
                    logger.error(f"定时清理任务异常: {e}")

                # 等待下一次清理
                await asyncio.sleep(self.CLEANUP_INTERVAL_HOURS * 3600)

        self._task = asyncio.create_task(cleanup_loop())

    async def stop_scheduled_cleanup(self):
        """停止定时清理任务"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("差异包定时清理服务已停止")


# 全局清理服务实例
_cleanup_service: DeltaCleanupService = None


def get_cleanup_service(storage_dir: Path = None) -> DeltaCleanupService:
    """
    获取清理服务实例（单例）

    Args:
        storage_dir: 差异包存储目录

    Returns:
        DeltaCleanupService: 清理服务实例
    """
    global _cleanup_service

    if _cleanup_service is None:
        if storage_dir is None:
            from pathlib import Path
            storage_dir = Path(__file__).parent.parent.parent / "data" / "deltas"

        _cleanup_service = DeltaCleanupService(storage_dir)

    return _cleanup_service
