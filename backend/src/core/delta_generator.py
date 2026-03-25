"""
差异包生成器 - 用于生成版本间的增量更新包

针对 Electron + PyInstaller 应用优化：
1. 只打包变化的文件（不使用 bsdiff，直接替换）
2. 排除大型依赖库目录（如 playwright、selenium）
3. 支持文件白名单/黑名单
4. 支持从 releases/vX.X.X 目录结构生成差异包

releases 目录结构:
  releases/
    v1.0.2/
      VidFlow-Backend/          -> 映射到 backend/
        VidFlow-Backend.exe
        _internal/
      frontend/
        dist/                   -> 映射到 frontend/dist/
          index.html
          assets/
      VidFlow Setup 1.0.2.exe   -> 忽略
"""
import hashlib
import json
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 排除的目录（这些目录很少变化，且体积巨大）
EXCLUDE_DIRS = {
    'playwright',
    'selenium',
    'pip',
    'setuptools',
    '_tcl_data',
    '_tk_data',
    'tcl8',
    'Pythonwin',
    'win32',
    'win32com',
}

# 排除的文件模式
EXCLUDE_PATTERNS = {
    '*.pyc',
    '*.pyo',
    '__pycache__',
    '.git',
    '.DS_Store',
    'Thumbs.db',
    '*.exe',  # 排除安装包
}

# 重要文件（这些文件变化时必须包含）
IMPORTANT_FILES = {
    'VidFlow-Backend.exe',
    'index.html',
    'main.js',
    'preload.js',
}

# 目录映射：从 releases 结构映射到安装目录结构
DIR_MAPPING = {
    'VidFlow-Backend': 'backend',
    'frontend/dist': 'frontend/dist',
}


@dataclass
class FileChange:
    """文件变更信息"""
    path: str
    action: str  # "add", "delete", "replace"
    target_hash: Optional[str] = None
    target_size: Optional[int] = None
    source_hash: Optional[str] = None


@dataclass
class DeltaManifest:
    """差异包清单"""
    version: str
    source_version: str
    platform: str
    arch: str
    created_at: str
    files: List[Dict]
    total_size: int
    full_package_size: int
    file_count: int

    def to_dict(self):
        return asdict(self)


@dataclass
class DeltaResult:
    """差异包生成结果"""
    source_version: str
    target_version: str
    platform: str
    arch: str
    delta_size: int
    full_size: int
    savings_percent: float
    delta_hash: str
    delta_path: Path
    manifest: DeltaManifest
    is_recommended: bool
    file_count: int


class DeltaGenerator:
    """差异包生成器"""

    # 差异包大小阈值（超过全量包的70%则不推荐）
    SIZE_THRESHOLD = 0.7

    # 最小节省比例（低于20%不推荐增量更新）
    MIN_SAVINGS = 0.2

    def __init__(self, storage_dir: Path):
        """
        初始化差异包生成器

        Args:
            storage_dir: 差异包存储目录
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def calculate_file_hash(self, file_path: Path) -> str:
        """计算文件的 SHA-256 哈希值（比 SHA-512 快）"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(65536):  # 64KB chunks
                sha256.update(chunk)
        return sha256.hexdigest()

    def _should_exclude(self, rel_path: str) -> bool:
        """检查文件是否应该被排除"""
        path_parts = Path(rel_path).parts

        # 检查目录排除
        for part in path_parts:
            if part in EXCLUDE_DIRS:
                return True

        # 检查文件模式排除
        filename = Path(rel_path).name
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith('*'):
                if filename.endswith(pattern[1:]):
                    # 特殊处理：VidFlow-Backend.exe 不排除
                    if filename == 'VidFlow-Backend.exe':
                        continue
                    return True
            elif pattern in rel_path:
                return True

        return False

    def _is_important_file(self, rel_path: str) -> bool:
        """检查是否是重要文件"""
        filename = Path(rel_path).name
        return filename in IMPORTANT_FILES

    def _scan_directory(self, directory: Path, prefix: str = "") -> Dict[str, Tuple[str, int]]:
        """
        扫描目录，生成文件清单（排除大型依赖）

        Args:
            directory: 要扫描的目录
            prefix: 路径前缀

        Returns:
            Dict[相对路径, (哈希值, 文件大小)]
        """
        files = {}

        for file_path in directory.rglob('*'):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(directory).as_posix()
            if prefix:
                rel_path = f"{prefix}/{rel_path}"

            # 跳过排除的文件
            if self._should_exclude(rel_path):
                continue

            try:
                file_hash = self.calculate_file_hash(file_path)
                file_size = file_path.stat().st_size
                files[rel_path] = (file_hash, file_size)
            except Exception as e:
                logger.warning(f"无法处理文件 {rel_path}: {e}")

        return files

    def _scan_release_directory(self, release_dir: Path) -> Dict[str, Tuple[str, int, Path]]:
        """
        扫描 releases/vX.X.X 目录，生成文件清单并映射到安装目录结构

        Args:
            release_dir: releases/vX.X.X 目录

        Returns:
            Dict[安装路径, (哈希值, 文件大小, 源文件路径)]
        """
        files = {}

        # 扫描 VidFlow-Backend 目录 -> 映射到 backend/
        backend_dir = release_dir / "VidFlow-Backend"
        if backend_dir.exists():
            for file_path in backend_dir.rglob('*'):
                if not file_path.is_file():
                    continue

                # 相对于 VidFlow-Backend 的路径
                rel_to_backend = file_path.relative_to(backend_dir).as_posix()
                # 映射到安装目录结构: backend/xxx
                install_path = f"backend/{rel_to_backend}"

                if self._should_exclude(install_path):
                    continue

                try:
                    file_hash = self.calculate_file_hash(file_path)
                    file_size = file_path.stat().st_size
                    files[install_path] = (file_hash, file_size, file_path)
                except Exception as e:
                    logger.warning(f"无法处理文件 {install_path}: {e}")

        # 扫描 frontend/dist 目录 -> 映射到 frontend/dist/
        frontend_dist_dir = release_dir / "frontend" / "dist"
        if frontend_dist_dir.exists():
            for file_path in frontend_dist_dir.rglob('*'):
                if not file_path.is_file():
                    continue

                # 相对于 frontend/dist 的路径
                rel_to_dist = file_path.relative_to(frontend_dist_dir).as_posix()
                # 映射到安装目录结构: frontend/dist/xxx
                install_path = f"frontend/dist/{rel_to_dist}"

                if self._should_exclude(install_path):
                    continue

                try:
                    file_hash = self.calculate_file_hash(file_path)
                    file_size = file_path.stat().st_size
                    files[install_path] = (file_hash, file_size, file_path)
                except Exception as e:
                    logger.warning(f"无法处理文件 {install_path}: {e}")

        return files

    def _compare_directories(
        self,
        source_files: Dict[str, Tuple[str, int, Path]],
        target_files: Dict[str, Tuple[str, int, Path]]
    ) -> List[FileChange]:
        """
        比较两个版本的文件差异

        Returns:
            List[FileChange]: 文件变更列表
        """
        changes: List[FileChange] = []

        # 检测新增和修改的文件
        for rel_path, (target_hash, target_size, _) in target_files.items():
            if rel_path not in source_files:
                # 新增文件
                changes.append(FileChange(
                    path=rel_path,
                    action="add",
                    target_hash=target_hash,
                    target_size=target_size
                ))
            else:
                source_hash, _, _ = source_files[rel_path]
                if source_hash != target_hash:
                    # 文件已修改
                    changes.append(FileChange(
                        path=rel_path,
                        action="replace",
                        target_hash=target_hash,
                        target_size=target_size,
                        source_hash=source_hash
                    ))

        # 检测删除的文件
        for rel_path in source_files:
            if rel_path not in target_files:
                changes.append(FileChange(
                    path=rel_path,
                    action="delete"
                ))

        return changes

    def generate_delta(
        self,
        source_version: str,
        target_version: str,
        source_dir: Path,
        target_dir: Path,
        platform: str,
        arch: str
    ) -> DeltaResult:
        """
        生成两个版本之间的差异包

        Args:
            source_version: 源版本号
            target_version: 目标版本号
            source_dir: 源版本目录 (releases/vX.X.X)
            target_dir: 目标版本目录 (releases/vX.X.X)
            platform: 平台 (win32/darwin/linux)
            arch: 架构 (x64/arm64)

        Returns:
            DeltaResult: 包含差异包路径和元数据
        """
        logger.info(f"开始生成差异包: {source_version} -> {target_version}")
        logger.info(f"源目录: {source_dir}")
        logger.info(f"目标目录: {target_dir}")

        # 扫描两个版本的文件（使用 release 目录结构）
        logger.info("扫描源版本文件...")
        source_files = self._scan_release_directory(source_dir)
        logger.info(f"源版本文件数: {len(source_files)}")

        logger.info("扫描目标版本文件...")
        target_files = self._scan_release_directory(target_dir)
        logger.info(f"目标版本文件数: {len(target_files)}")

        # 比较差异
        changes = self._compare_directories(source_files, target_files)

        # 统计
        added = sum(1 for c in changes if c.action == "add")
        replaced = sum(1 for c in changes if c.action == "replace")
        deleted = sum(1 for c in changes if c.action == "delete")

        logger.info(f"文件变更: 新增 {added}, 修改 {replaced}, 删除 {deleted}")

        if not changes:
            raise ValueError("两个版本没有差异，无需生成差异包")

        # 创建临时工作目录
        work_dir = self.storage_dir / f"temp_{source_version}_to_{target_version}"
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        files_dir = work_dir / "files"
        files_dir.mkdir(exist_ok=True)

        total_size = 0

        # 复制变更的文件
        for change in changes:
            if change.action in ("add", "replace"):
                # 从 target_files 获取源文件路径
                _, _, source_file = target_files[change.path]
                dest_file = files_dir / change.path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                try:
                    shutil.copy2(source_file, dest_file)
                    total_size += change.target_size
                    logger.debug(f"复制文件: {change.path}")
                except Exception as e:
                    logger.error(f"复制文件失败 {change.path}: {e}")
                    raise

        # 计算全量包大小（只计算扫描到的文件）
        full_size = sum(size for _, size, _ in target_files.values())

        # 创建清单
        manifest = DeltaManifest(
            version=target_version,
            source_version=source_version,
            platform=platform,
            arch=arch,
            created_at=datetime.utcnow().isoformat() + "Z",
            files=[asdict(change) for change in changes],
            total_size=total_size,
            full_package_size=full_size,
            file_count=len([c for c in changes if c.action != "delete"])
        )

        # 保存清单文件
        manifest_file = work_dir / "manifest.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)

        # 创建差异包 ZIP
        delta_filename = f"delta-{source_version}-to-{target_version}-{platform}-{arch}.zip"
        delta_path = self.storage_dir / delta_filename

        logger.info(f"创建差异包: {delta_path}")

        with zipfile.ZipFile(delta_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            # 添加清单
            zf.write(manifest_file, "manifest.json")

            # 添加文件
            for file_path in files_dir.rglob('*'):
                if file_path.is_file():
                    arcname = f"files/{file_path.relative_to(files_dir).as_posix()}"
                    zf.write(file_path, arcname)

        # 清理临时目录
        shutil.rmtree(work_dir)

        # 计算差异包哈希和大小
        delta_hash = self.calculate_file_hash(delta_path)
        delta_size = delta_path.stat().st_size

        savings_percent = ((full_size - delta_size) / full_size * 100) if full_size > 0 else 0

        # 判断是否推荐使用增量更新
        is_recommended = (
            delta_size < (full_size * self.SIZE_THRESHOLD) and
            savings_percent >= (self.MIN_SAVINGS * 100)
        )

        logger.info("=" * 50)
        logger.info(f"差异包生成完成!")
        logger.info(f"  文件: {delta_filename}")
        logger.info(f"  大小: {delta_size / 1024 / 1024:.2f} MB")
        logger.info(f"  全量: {full_size / 1024 / 1024:.2f} MB")
        logger.info(f"  节省: {savings_percent:.1f}%")
        logger.info(f"  文件数: {manifest.file_count}")
        logger.info(f"  推荐: {'是' if is_recommended else '否'}")
        logger.info("=" * 50)

        return DeltaResult(
            source_version=source_version,
            target_version=target_version,
            platform=platform,
            arch=arch,
            delta_size=delta_size,
            full_size=full_size,
            savings_percent=round(savings_percent, 2),
            delta_hash=delta_hash,
            delta_path=delta_path,
            manifest=manifest,
            is_recommended=is_recommended,
            file_count=manifest.file_count
        )


def main():
    """命令行入口"""
    import sys

    if len(sys.argv) < 5:
        print("用法: python delta_generator.py <source_version> <target_version> <source_dir> <target_dir> [platform] [arch]")
        print("示例: python delta_generator.py 1.0.2 1.0.3 releases/v1.0.2 releases/v1.0.3 win32 x64")
        sys.exit(1)

    source_version = sys.argv[1]
    target_version = sys.argv[2]
    source_dir = Path(sys.argv[3])
    target_dir = Path(sys.argv[4])
    platform = sys.argv[5] if len(sys.argv) > 5 else "win32"
    arch = sys.argv[6] if len(sys.argv) > 6 else "x64"

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 生成差异包
    generator = DeltaGenerator(Path("releases/deltas"))
    result = generator.generate_delta(
        source_version, target_version,
        source_dir, target_dir,
        platform, arch
    )

    print(f"\n[完成] 差异包已生成: {result.delta_path}")
    print(f"   哈希: {result.delta_hash[:32]}...")


if __name__ == "__main__":
    main()
