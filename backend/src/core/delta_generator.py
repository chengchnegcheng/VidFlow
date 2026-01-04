"""
差异包生成器 - 用于生成版本间的增量更新包
"""
import hashlib
import json
import zipfile
import bsdiff4
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """文件变更信息"""
    path: str
    action: str  # "add", "delete", "patch", "replace"
    source_hash: Optional[str] = None
    target_hash: Optional[str] = None
    source_size: Optional[int] = None
    target_size: Optional[int] = None
    patch_file: Optional[str] = None
    patch_size: Optional[int] = None


@dataclass
class Manifest:
    """版本清单"""
    version: str
    source_version: str
    platform: str
    arch: str
    created_at: str
    files: List[Dict]
    total_patch_size: int
    full_package_size: int


@dataclass
class DeltaPackage:
    """差异包信息"""
    source_version: str
    target_version: str
    platform: str
    arch: str
    delta_size: int
    full_size: int
    savings_percent: float
    delta_hash: str
    delta_path: Path
    manifest: Manifest
    is_recommended: bool


class DeltaGenerator:
    """差异包生成器"""

    # 差异包大小阈值（超过全量包的80%则不推荐）
    SIZE_THRESHOLD = 0.8

    def __init__(self, storage_dir: Path):
        """
        初始化差异包生成器

        Args:
            storage_dir: 差异包存储目录
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件的 SHA-512 哈希值

        Args:
            file_path: 文件路径

        Returns:
            str: 十六进制哈希字符串
        """
        sha512 = hashlib.sha512()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha512.update(chunk)
        return sha512.hexdigest()

    def _scan_directory(self, directory: Path) -> Dict[str, Tuple[str, int]]:
        """
        扫描目录，生成文件清单

        Args:
            directory: 要扫描的目录

        Returns:
            Dict[相对路径, (哈希值, 文件大小)]
        """
        files = {}
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(directory).as_posix()
                file_hash = self.calculate_file_hash(file_path)
                file_size = file_path.stat().st_size
                files[rel_path] = (file_hash, file_size)
        return files

    def generate_manifest(
        self,
        source_dir: Path,
        target_dir: Path,
        target_version: str,
        source_version: str,
        platform: str,
        arch: str
    ) -> Tuple[Manifest, List[FileChange]]:
        """
        生成版本清单，包含所有文件的哈希和变更类型

        Args:
            source_dir: 源版本目录
            target_dir: 目标版本目录
            target_version: 目标版本号
            source_version: 源版本号
            platform: 平台
            arch: 架构

        Returns:
            Tuple[Manifest, List[FileChange]]: 清单对象和文件变更列表
        """
        logger.info(f"生成清单: {source_version} -> {target_version}")

        source_files = self._scan_directory(source_dir)
        target_files = self._scan_directory(target_dir)

        changes: List[FileChange] = []
        total_patch_size = 0

        # 检测新增和修改的文件
        for rel_path, (target_hash, target_size) in target_files.items():
            if rel_path not in source_files:
                # 新增文件
                changes.append(FileChange(
                    path=rel_path,
                    action="add",
                    target_hash=target_hash,
                    target_size=target_size
                ))
                total_patch_size += target_size
            else:
                source_hash, source_size = source_files[rel_path]
                if source_hash != target_hash:
                    # 文件已修改
                    changes.append(FileChange(
                        path=rel_path,
                        action="patch",
                        source_hash=source_hash,
                        target_hash=target_hash,
                        source_size=source_size,
                        target_size=target_size,
                        patch_file=f"{rel_path}.patch"
                    ))

        # 检测删除的文件
        for rel_path in source_files:
            if rel_path not in target_files:
                changes.append(FileChange(
                    path=rel_path,
                    action="delete"
                ))

        # 计算全量包大小
        full_package_size = sum(size for _, size in target_files.values())

        manifest = Manifest(
            version=target_version,
            source_version=source_version,
            platform=platform,
            arch=arch,
            created_at=datetime.utcnow().isoformat() + "Z",
            files=[asdict(change) for change in changes],
            total_patch_size=total_patch_size,
            full_package_size=full_package_size
        )

        return manifest, changes

    def _create_patch(
        self,
        source_file: Path,
        target_file: Path,
        patch_file: Path
    ) -> int:
        """
        创建二进制差异补丁

        Args:
            source_file: 源文件
            target_file: 目标文件
            patch_file: 补丁文件输出路径

        Returns:
            int: 补丁文件大小
        """
        with open(source_file, 'rb') as sf, open(target_file, 'rb') as tf:
            source_data = sf.read()
            target_data = tf.read()

        patch_data = bsdiff4.diff(source_data, target_data)

        with open(patch_file, 'wb') as pf:
            pf.write(patch_data)

        return len(patch_data)

    def generate_delta(
        self,
        source_version: str,
        target_version: str,
        source_dir: Path,
        target_dir: Path,
        platform: str,
        arch: str
    ) -> DeltaPackage:
        """
        生成两个版本之间的差异包

        Args:
            source_version: 源版本号
            target_version: 目标版本号
            source_dir: 源版本目录
            target_dir: 目标版本目录
            platform: 平台 (win32/darwin/linux)
            arch: 架构 (x64/arm64)

        Returns:
            DeltaPackage: 包含差异包路径和元数据
        """
        logger.info(f"开始生成差异包: {source_version} -> {target_version}")

        # 生成清单
        manifest, changes = self.generate_manifest(
            source_dir, target_dir, target_version, source_version, platform, arch
        )

        # 创建临时工作目录
        work_dir = self.storage_dir / f"temp_{source_version}_to_{target_version}"
        work_dir.mkdir(parents=True, exist_ok=True)

        patches_dir = work_dir / "patches"
        patches_dir.mkdir(exist_ok=True)

        new_dir = work_dir / "new"
        new_dir.mkdir(exist_ok=True)

        total_patch_size = 0

        # 处理文件变更
        for change in changes:
            if change.action == "patch":
                # 生成补丁
                source_file = source_dir / change.path
                target_file = target_dir / change.path
                patch_file = patches_dir / change.patch_file

                patch_file.parent.mkdir(parents=True, exist_ok=True)
                patch_size = self._create_patch(source_file, target_file, patch_file)

                change.patch_size = patch_size
                total_patch_size += patch_size

            elif change.action == "add":
                # 复制新文件
                target_file = target_dir / change.path
                new_file = new_dir / change.path
                new_file.parent.mkdir(parents=True, exist_ok=True)

                import shutil
                shutil.copy2(target_file, new_file)
                total_patch_size += change.target_size

        # 更新清单中的补丁大小
        manifest.total_patch_size = total_patch_size
        manifest.files = [asdict(change) for change in changes]

        # 保存清单文件
        manifest_file = work_dir / "manifest.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(manifest), f, indent=2, ensure_ascii=False)

        # 创建差异包 ZIP
        delta_filename = f"delta-{source_version}-to-{target_version}-{platform}-{arch}.zip"
        delta_path = self.storage_dir / delta_filename

        with zipfile.ZipFile(delta_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 添加清单
            zf.write(manifest_file, "manifest.json")

            # 添加补丁文件
            for patch_file in patches_dir.rglob('*'):
                if patch_file.is_file():
                    arcname = f"patches/{patch_file.relative_to(patches_dir).as_posix()}"
                    zf.write(patch_file, arcname)

            # 添加新文件
            for new_file in new_dir.rglob('*'):
                if new_file.is_file():
                    arcname = f"new/{new_file.relative_to(new_dir).as_posix()}"
                    zf.write(new_file, arcname)

        # 清理临时目录
        import shutil
        shutil.rmtree(work_dir)

        # 计算差异包哈希和大小
        delta_hash = self.calculate_file_hash(delta_path)
        delta_size = delta_path.stat().st_size
        full_size = manifest.full_package_size

        savings_percent = ((full_size - delta_size) / full_size * 100) if full_size > 0 else 0
        is_recommended = delta_size < (full_size * self.SIZE_THRESHOLD)

        logger.info(
            f"差异包生成完成: {delta_filename}, "
            f"大小: {delta_size / 1024 / 1024:.2f}MB, "
            f"节省: {savings_percent:.1f}%, "
            f"推荐: {is_recommended}"
        )

        return DeltaPackage(
            source_version=source_version,
            target_version=target_version,
            platform=platform,
            arch=arch,
            delta_size=delta_size,
            full_size=full_size,
            savings_percent=savings_percent,
            delta_hash=delta_hash,
            delta_path=delta_path,
            manifest=manifest,
            is_recommended=is_recommended
        )
