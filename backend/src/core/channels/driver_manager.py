"""
WinDivert 驱动管理器

负责 WinDivert 驱动的检测、安装和状态管理。
"""

import os
import sys
import ctypes
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional

from .models import (
    DriverState,
    DriverStatus,
    DriverInstallResult,
    ErrorCode,
    get_error_message,
)


logger = logging.getLogger(__name__)


class DriverManager:
    """WinDivert 驱动管理器"""

    # 驱动文件列表
    DRIVER_FILES_64 = ["WinDivert.dll", "WinDivert64.sys"]
    DRIVER_FILES_32 = ["WinDivert.dll", "WinDivert32.sys"]

    def __init__(self, driver_dir: Optional[Path] = None):
        """初始化驱动管理器

        Args:
            driver_dir: 驱动文件目录，默认为 tools/bin/windivert
        """
        if driver_dir is None:
            # 默认路径：backend/tools/bin/windivert
            base_dir = Path(__file__).parent.parent.parent.parent
            driver_dir = base_dir / "tools" / "bin" / "windivert"

        self.driver_dir = Path(driver_dir)
        self._is_64bit = sys.maxsize > 2**32

    @property
    def driver_files(self) -> list:
        """获取当前系统架构所需的驱动文件列表"""
        return self.DRIVER_FILES_64 if self._is_64bit else self.DRIVER_FILES_32

    def is_installed(self) -> bool:
        """检查 WinDivert 驱动是否已安装

        Returns:
            驱动文件存在返回 True
        """
        if not self.driver_dir.exists():
            return False

        for filename in self.driver_files:
            if not (self.driver_dir / filename).exists():
                return False

        return True

    def get_status(self) -> DriverStatus:
        """获取驱动详细状态

        Returns:
            DriverStatus: 驱动状态详情
        """
        is_admin = self.check_admin_privileges()

        if not self.driver_dir.exists():
            return DriverStatus(
                state=DriverState.NOT_INSTALLED,
                error_message="驱动目录不存在",
                is_admin=is_admin,
            )

        # 检查驱动文件
        missing_files = []
        for filename in self.driver_files:
            file_path = self.driver_dir / filename
            if not file_path.exists():
                missing_files.append(filename)

        if missing_files:
            return DriverStatus(
                state=DriverState.NOT_INSTALLED,
                path=str(self.driver_dir),
                error_message=f"缺少驱动文件: {', '.join(missing_files)}",
                is_admin=is_admin,
            )

        # 尝试获取版本信息
        version = self._get_driver_version()

        return DriverStatus(
            state=DriverState.INSTALLED,
            version=version,
            path=str(self.driver_dir),
            is_admin=is_admin,
        )

    def _get_driver_version(self) -> Optional[str]:
        """获取驱动版本信息

        Returns:
            版本字符串，如果无法获取则返回 None
        """
        try:
            # 尝试从 DLL 获取版本信息
            dll_path = self.driver_dir / "WinDivert.dll"
            if not dll_path.exists():
                return None

            # Windows 版本信息 API
            if sys.platform == 'win32':
                from ctypes import wintypes

                version_dll = ctypes.windll.version

                # 获取版本信息大小
                size = version_dll.GetFileVersionInfoSizeW(str(dll_path), None)
                if size == 0:
                    return None

                # 获取版本信息
                buffer = ctypes.create_string_buffer(size)
                if not version_dll.GetFileVersionInfoW(str(dll_path), 0, size, buffer):
                    return None

                # 查询版本值
                vs_fixedfileinfo = ctypes.c_void_p()
                length = ctypes.c_uint()
                if not version_dll.VerQueryValueW(
                    buffer, "\\", ctypes.byref(vs_fixedfileinfo), ctypes.byref(length)
                ):
                    return None

                # 解析版本号
                class VS_FIXEDFILEINFO(ctypes.Structure):
                    _fields_ = [
                        ("dwSignature", wintypes.DWORD),
                        ("dwStrucVersion", wintypes.DWORD),
                        ("dwFileVersionMS", wintypes.DWORD),
                        ("dwFileVersionLS", wintypes.DWORD),
                        ("dwProductVersionMS", wintypes.DWORD),
                        ("dwProductVersionLS", wintypes.DWORD),
                        ("dwFileFlagsMask", wintypes.DWORD),
                        ("dwFileFlags", wintypes.DWORD),
                        ("dwFileOS", wintypes.DWORD),
                        ("dwFileType", wintypes.DWORD),
                        ("dwFileSubtype", wintypes.DWORD),
                        ("dwFileDateMS", wintypes.DWORD),
                        ("dwFileDateLS", wintypes.DWORD),
                    ]

                info = ctypes.cast(vs_fixedfileinfo, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
                version = (
                    f"{(info.dwFileVersionMS >> 16) & 0xFFFF}."
                    f"{info.dwFileVersionMS & 0xFFFF}."
                    f"{(info.dwFileVersionLS >> 16) & 0xFFFF}."
                    f"{info.dwFileVersionLS & 0xFFFF}"
                )
                return version

            return None

        except Exception as e:
            logger.debug(f"Failed to get driver version: {e}")
            return None

    def check_admin_privileges(self) -> bool:
        """检查当前进程是否有管理员权限

        Returns:
            有管理员权限返回 True
        """
        if sys.platform != 'win32':
            return False

        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def install(self, source_dir: Optional[Path] = None) -> DriverInstallResult:
        """安装 WinDivert 驱动

        将驱动文件复制到目标目录。实际的驱动加载由 pydivert 在首次使用时自动完成。

        Args:
            source_dir: 源驱动文件目录，如果为 None 则假设文件已在目标目录

        Returns:
            DriverInstallResult: 安装结果
        """
        # 检查管理员权限
        if not self.check_admin_privileges():
            return DriverInstallResult(
                success=False,
                error_code=ErrorCode.ADMIN_REQUIRED,
                error_message=get_error_message(ErrorCode.ADMIN_REQUIRED),
            )

        try:
            # 确保目标目录存在
            self.driver_dir.mkdir(parents=True, exist_ok=True)

            # 如果提供了源目录，复制文件
            if source_dir:
                source_dir = Path(source_dir)
                for filename in self.driver_files:
                    src = source_dir / filename
                    dst = self.driver_dir / filename
                    if src.exists():
                        shutil.copy2(src, dst)
                        logger.info(f"Copied driver file: {filename}")
                    else:
                        return DriverInstallResult(
                            success=False,
                            error_code=ErrorCode.DRIVER_MISSING,
                            error_message=f"源文件不存在: {src}",
                        )

            # 验证安装
            if not self.is_installed():
                return DriverInstallResult(
                    success=False,
                    error_code=ErrorCode.DRIVER_MISSING,
                    error_message="驱动文件安装验证失败",
                )

            logger.info("WinDivert driver installed successfully")
            return DriverInstallResult(success=True)

        except PermissionError as e:
            logger.error(f"Permission denied during driver installation: {e}")
            return DriverInstallResult(
                success=False,
                error_code=ErrorCode.PERMISSION_DENIED,
                error_message=get_error_message(ErrorCode.PERMISSION_DENIED),
            )
        except Exception as e:
            logger.exception("Failed to install driver")
            return DriverInstallResult(
                success=False,
                error_code=ErrorCode.DRIVER_LOAD_FAILED,
                error_message=str(e),
            )

    def request_admin_restart(self) -> bool:
        """请求以管理员身份重启应用

        使用 Windows ShellExecute 以管理员身份重新启动当前进程。

        Returns:
            请求成功返回 True（注意：成功只表示请求已发送，不表示用户已确认）
        """
        if sys.platform != 'win32':
            logger.warning("Admin restart is only supported on Windows")
            return False

        try:
            # 获取当前可执行文件路径
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的可执行文件
                executable = sys.executable
                working_dir = str(Path(executable).parent)
                params = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else ''
            else:
                # 开发环境：重新以管理员身份运行当前 Python 脚本
                executable = sys.executable
                script = Path(sys.argv[0]).resolve() if sys.argv else None
                argv = [str(script)] if script else []
                argv.extend(sys.argv[1:])
                params = subprocess.list2cmdline(argv)
                working_dir = str(script.parent) if script else None

            ret = ctypes.windll.shell32.ShellExecuteW(
                None,           # hwnd
                "runas",        # 以管理员身份运行
                executable,     # 可执行文件
                params,         # 参数
                working_dir,    # 工作目录
                1               # SW_SHOWNORMAL
            )

            # ShellExecuteW 返回值 > 32 表示成功
            if ret > 32:
                logger.info("Admin restart requested successfully")
                return True
            else:
                logger.warning(f"ShellExecute returned: {ret}")
                return False

        except Exception as e:
            logger.exception("Failed to request admin restart")
            return False

    def can_load_driver(self) -> bool:
        """检查是否可以加载驱动

        验证驱动文件存在且有管理员权限。

        Returns:
            可以加载返回 True
        """
        return self.is_installed() and self.check_admin_privileges()

    def get_dll_path(self) -> Optional[Path]:
        """获取 WinDivert.dll 路径

        Returns:
            DLL 文件路径，如果不存在返回 None
        """
        dll_path = self.driver_dir / "WinDivert.dll"
        return dll_path if dll_path.exists() else None
