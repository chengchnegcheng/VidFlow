"""
数据库备份管理器
"""
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class BackupManager:
    """数据库备份管理器"""

    def __init__(self, db_path: Path, backup_dir: Path):
        """
        初始化备份管理器

        Args:
            db_path: 数据库文件路径
            backup_dir: 备份目录路径
        """
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Path:
        """
        创建数据库备份

        Returns:
            Path: 备份文件路径
        """
        try:
            # 检查数据库文件是否存在
            if not self.db_path.exists():
                logger.warning(f"Database file not found: {self.db_path}")
                return None

            # 生成备份文件名（带时间戳）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"database_backup_{timestamp}.db"
            backup_path = self.backup_dir / backup_name

            # 复制数据库文件
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backup created: {backup_path}")

            # 清理旧备份（保留最近10个）
            self.cleanup_old_backups(keep=10)

            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    def cleanup_old_backups(self, keep: int = 10):
        """
        清理旧备份，只保留最近的 N 个

        Args:
            keep: 保留的备份数量
        """
        try:
            # 获取所有备份文件并按修改时间排序
            backups = sorted(
                self.backup_dir.glob('database_backup_*.db'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # 删除超出保留数量的旧备份
            if len(backups) > keep:
                for old_backup in backups[keep:]:
                    try:
                        old_backup.unlink()
                        logger.info(f"Deleted old backup: {old_backup.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete backup {old_backup.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")

    def list_backups(self) -> List[dict]:
        """
        列出所有备份文件

        Returns:
            List[dict]: 备份文件信息列表
        """
        try:
            backups = []
            for backup_file in sorted(
                self.backup_dir.glob('database_backup_*.db'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            ):
                stat = backup_file.stat()
                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            return backups
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    def restore_backup(self, backup_name: str) -> bool:
        """
        从备份恢复数据库

        Args:
            backup_name: 备份文件名

        Returns:
            bool: 恢复是否成功
        """
        try:
            backup_path = self.backup_dir / backup_name

            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            # 在恢复前创建当前数据库的备份
            if self.db_path.exists():
                emergency_backup = self.db_path.parent / f"database_emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(self.db_path, emergency_backup)
                logger.info(f"Created emergency backup before restore: {emergency_backup}")

            # 恢复备份
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Database restored from backup: {backup_name}")

            return True
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False


async def schedule_backup_task(db_path: Path, backup_dir: Path, interval_hours: int = 24):
    """
    定期备份任务

    Args:
        db_path: 数据库文件路径
        backup_dir: 备份目录路径
        interval_hours: 备份间隔（小时）
    """
    backup_manager = BackupManager(db_path, backup_dir)

    logger.info(f"Backup scheduler started (interval: {interval_hours} hours)")

    while True:
        try:
            # 等待指定时间
            await asyncio.sleep(interval_hours * 3600)

            # 执行备份
            backup_path = backup_manager.create_backup()
            if backup_path:
                logger.info(f"Scheduled backup completed: {backup_path}")
            else:
                logger.warning("Scheduled backup skipped (database not found)")

        except asyncio.CancelledError:
            logger.info("Backup scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")
            # 继续运行，不因单次失败而停止


# 全局备份管理器实例
_backup_manager = None


def get_backup_manager(db_path: Path = None, backup_dir: Path = None):
    """获取备份管理器单例"""
    global _backup_manager

    if _backup_manager is None and db_path and backup_dir:
        _backup_manager = BackupManager(db_path, backup_dir)

    return _backup_manager
