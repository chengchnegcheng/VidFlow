"""
JavaScript 运行时管理器
用于检测和管理 YouTube 下载所需的 JavaScript 运行时（Deno/Node.js/Bun/QuickJS）
"""
import shutil
import subprocess
import logging
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class JSRuntimeManager:
    """JavaScript 运行时管理器"""

    # 支持的运行时列表（按优先级排序）
    SUPPORTED_RUNTIMES = ['deno', 'node', 'bun', 'qjs']

    # 运行时最低版本要求
    MIN_VERSIONS = {
        'deno': '1.0.0',
        'node': '12.0.0',
        'bun': '1.0.0',
        'qjs': None,  # QuickJS 没有版本要求
    }

    def __init__(self):
        self._available_runtime: Optional[str] = None
        self._runtime_version: Optional[str] = None
        self._checked = False

    def check_js_runtime(self) -> Optional[str]:
        """
        检查可用的 JavaScript 运行时

        Returns:
            str: 可用的运行时名称（deno/node/bun/qjs）
            None: 没有可用的运行时
        """
        if self._checked:
            return self._available_runtime

        for runtime in self.SUPPORTED_RUNTIMES:
            if self._check_runtime(runtime):
                self._available_runtime = runtime
                self._checked = True
                logger.info(f"检测到可用的 JavaScript 运行时: {runtime} {self._runtime_version or ''}")
                return runtime

        self._checked = True
        logger.warning("未检测到任何 JavaScript 运行时，YouTube 下载可能受限")
        return None

    def _check_runtime(self, runtime: str) -> bool:
        """
        检查特定运行时是否可用

        Args:
            runtime: 运行时名称

        Returns:
            bool: 是否可用
        """
        try:
            # 检查运行时是否在 PATH 中
            runtime_path = shutil.which(runtime)
            if not runtime_path:
                return False

            # 尝试获取版本号
            version = self._get_runtime_version(runtime)
            if version:
                self._runtime_version = version
                return True

            return False

        except Exception as e:
            logger.debug(f"检查 {runtime} 失败: {e}")
            return False

    def _get_runtime_version(self, runtime: str) -> Optional[str]:
        """
        获取运行时版本号

        Args:
            runtime: 运行时名称

        Returns:
            str: 版本号
            None: 无法获取版本号
        """
        try:
            # 不同运行时的版本检查命令
            version_commands = {
                'deno': ['deno', '--version'],
                'node': ['node', '--version'],
                'bun': ['bun', '--version'],
                'qjs': ['qjs', '--version'],
            }

            cmd = version_commands.get(runtime)
            if not cmd:
                return None

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            if result.returncode == 0:
                # 提取版本号（简化处理）
                output = result.stdout.strip()
                if runtime == 'deno':
                    # Deno 输出格式: deno 1.x.x (release, x86_64-pc-windows-msvc)
                    parts = output.split('\n')[0].split()
                    if len(parts) >= 2:
                        return parts[1]
                elif runtime == 'node':
                    # Node 输出格式: v18.x.x
                    return output.replace('v', '')
                elif runtime == 'bun':
                    # Bun 输出格式: 1.x.x
                    return output
                elif runtime == 'qjs':
                    # QuickJS 输出格式可能各不相同
                    return output

            return None

        except Exception as e:
            logger.debug(f"获取 {runtime} 版本失败: {e}")
            return None

    def get_install_guide(self) -> Dict[str, str]:
        """
        获取 JavaScript 运行时安装指南

        Returns:
            dict: 包含各平台安装指南的字典
        """
        return {
            'windows': '''
YouTube 下载需要 JavaScript 运行时。推荐安装 Deno（最简单）：

方法 1：使用 PowerShell（推荐）
1. 打开 PowerShell（管理员权限）
2. 运行命令：
   irm https://deno.land/install.ps1 | iex

方法 2：使用 Scoop
   scoop install deno

方法 3：使用 Chocolatey
   choco install deno

方法 4：手动下载
   访问 https://github.com/denoland/deno/releases
   下载 deno-x86_64-pc-windows-msvc.zip
   解压并将 deno.exe 添加到 PATH

其他选择：
- Node.js: https://nodejs.org/
- Bun: https://bun.sh/
''',
            'macos': '''
YouTube 下载需要 JavaScript 运行时。推荐安装 Deno：

方法 1：使用 Homebrew（推荐）
   brew install deno

方法 2：使用安装脚本
   curl -fsSL https://deno.land/install.sh | sh

其他选择：
- Node.js: brew install node
- Bun: brew install bun
''',
            'linux': '''
YouTube 下载需要 JavaScript 运行时。推荐安装 Deno：

方法 1：使用安装脚本（推荐）
   curl -fsSL https://deno.land/install.sh | sh

方法 2：使用包管理器
   # Ubuntu/Debian
   sudo apt install deno

   # Arch Linux
   sudo pacman -S deno

   # Fedora
   sudo dnf install deno

其他选择：
- Node.js: sudo apt install nodejs (Ubuntu/Debian)
- Bun: curl -fsSL https://bun.sh/install | bash
''',
        }

    def get_status_message(self) -> str:
        """
        获取运行时状态消息

        Returns:
            str: 状态消息
        """
        runtime = self.check_js_runtime()

        if runtime:
            return f"✓ JavaScript 运行时可用: {runtime} {self._runtime_version or ''}"
        else:
            return "✗ 未检测到 JavaScript 运行时，YouTube 下载功能可能受限"

    def is_runtime_available(self) -> bool:
        """
        检查是否有可用的运行时

        Returns:
            bool: 是否有可用的运行时
        """
        return self.check_js_runtime() is not None

    def get_runtime_config(self) -> Dict[str, str]:
        """
        获取 yt-dlp 的运行时配置

        Returns:
            dict: 运行时配置（用于 yt-dlp）
        """
        runtime = self.check_js_runtime()

        if runtime:
            # yt-dlp 会自动检测运行时，但我们可以显式指定
            return {
                'js_runtime': runtime,
                'js_runtime_version': self._runtime_version or 'unknown',
            }

        return {}


# 全局单例
_js_runtime_manager: Optional[JSRuntimeManager] = None


def get_js_runtime_manager() -> JSRuntimeManager:
    """
    获取全局 JavaScript 运行时管理器实例

    Returns:
        JSRuntimeManager: 管理器实例
    """
    global _js_runtime_manager
    if _js_runtime_manager is None:
        _js_runtime_manager = JSRuntimeManager()
    return _js_runtime_manager


def check_and_warn_js_runtime() -> bool:
    """
    检查 JavaScript 运行时并在缺失时发出警告

    Returns:
        bool: 是否有可用的运行时
    """
    manager = get_js_runtime_manager()
    if not manager.is_runtime_available():
        logger.warning("=" * 60)
        logger.warning("警告: 未检测到 JavaScript 运行时")
        logger.warning("YouTube 下载可能失败或功能受限")
        logger.warning("请安装以下任一运行时：")
        logger.warning("  - Deno (推荐): https://deno.land/")
        logger.warning("  - Node.js: https://nodejs.org/")
        logger.warning("  - Bun: https://bun.sh/")
        logger.warning("=" * 60)
        return False

    return True


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    manager = get_js_runtime_manager()
    print(manager.get_status_message())

    if not manager.is_runtime_available():
        import platform
        system = platform.system().lower()
        if system == 'darwin':
            system = 'macos'
        elif system not in ['windows', 'linux']:
            system = 'linux'

        guides = manager.get_install_guide()
        print("\n安装指南：")
        print(guides.get(system, guides['linux']))
