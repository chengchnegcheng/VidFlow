"""
YouTube 下载诊断工具
用于检查 yt-dlp 版本、JS 运行时、代理等配置
"""
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_ytdlp_version():
    """检查 yt-dlp 版本"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', 'yt-dlp'],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    version = line.split(':', 1)[1].strip()
                    logger.info(f"✓ yt-dlp 版本: {version}")
                    return version
        else:
            logger.error("✗ yt-dlp 未安装")
            return None
    except Exception as e:
        logger.error(f"✗ 检查 yt-dlp 版本失败: {e}")
        return None


def check_js_runtime():
    """检查 JavaScript 运行时"""
    runtimes = {
        'deno': 'Deno',
        'node': 'Node.js',
        'bun': 'Bun',
        'qjs': 'QuickJS'
    }

    found = []
    for cmd, name in runtimes.items():
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                found.append(f"{name} ({version})")
                logger.info(f"✓ {name}: {version}")
        except FileNotFoundError:
            continue
        except Exception:
            continue

    if not found:
        logger.warning("✗ 未找到任何 JavaScript 运行时")
        logger.info("  建议安装 Deno: https://deno.land/")

    return found


def check_proxy():
    """检查代理配置"""
    import os

    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')

    if http_proxy or https_proxy:
        logger.info("✓ 代理配置:")
        if http_proxy:
            logger.info(f"  HTTP_PROXY: {http_proxy}")
        if https_proxy:
            logger.info(f"  HTTPS_PROXY: {https_proxy}")
    else:
        logger.warning("✗ 未配置代理")
        logger.info("  YouTube 在国内需要代理访问")
        logger.info("  设置方法: set HTTP_PROXY=http://127.0.0.1:7890")


def check_po_token():
    """检查 PO Token 配置"""
    import os

    po_token = os.environ.get('YTDLP_YOUTUBE_PO_TOKEN')
    visitor_data = os.environ.get('YTDLP_YOUTUBE_VISITOR_DATA')

    if po_token:
        logger.info(f"✓ PO Token: {po_token[:20]}...")
        if visitor_data:
            logger.info(f"  Visitor Data: {visitor_data[:20]}...")
    else:
        logger.warning("✗ 未配置 PO Token")
        logger.info("  PO Token 可以提高 YouTube 下载成功率")


def test_youtube_connection():
    """测试 YouTube 连接"""
    logger.info("\n测试 YouTube 连接...")

    try:
        import yt_dlp

        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - 永不失效的测试视频

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # 只获取基本信息
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"测试 URL: {test_url}")
            info = ydl.extract_info(test_url, download=False)
            logger.info(f"✓ YouTube 连接成功!")
            logger.info(f"  视频标题: {info.get('title', 'Unknown')}")
            return True

    except Exception as e:
        logger.error(f"✗ YouTube 连接失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("YouTube 下载诊断工具")
    print("=" * 60)
    print()

    logger.info("1. 检查 yt-dlp 版本")
    logger.info("-" * 40)
    version = check_ytdlp_version()
    if version:
        # 检查是否是最新版本
        try:
            from packaging import version as pkg_version
            if pkg_version.parse(version) < pkg_version.parse("2024.12.13"):
                logger.warning(f"  ⚠️ 当前版本较旧，建议升级到 2024.12.13 或更高版本")
                logger.info(f"  升级命令: pip install --upgrade yt-dlp")
        except:
            pass
    print()

    logger.info("2. 检查 JavaScript 运行时")
    logger.info("-" * 40)
    check_js_runtime()
    print()

    logger.info("3. 检查代理配置")
    logger.info("-" * 40)
    check_proxy()
    print()

    logger.info("4. 检查 PO Token 配置")
    logger.info("-" * 40)
    check_po_token()
    print()

    logger.info("5. 测试 YouTube 连接")
    logger.info("-" * 40)
    test_youtube_connection()
    print()

    print("=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
