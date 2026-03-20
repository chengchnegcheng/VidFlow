"""
图片代理API - 解决防盗链问题
用于代理B站、YouTube等平台的图片请求
"""
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import httpx
import logging

router = APIRouter(prefix="/api/v1/proxy", tags=["proxy"])
logger = logging.getLogger(__name__)

_WECHAT_IMAGE_HOST_MARKERS = (
    "qpic.cn",
    "qlogo.cn",
    "wx.qlogo.cn",
    "wx.qpic.cn",
    "weixin.qq.com",
    "wechat.com",
    "qq.com",
)


def _resolve_image_referer(url: str) -> str:
    """Choose a referer that matches the remote image host."""
    lowered = (url or "").lower()

    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""

    if "youtube" in lowered or "ytimg" in lowered:
        return "https://www.youtube.com"
    if "douyin" in lowered or "tiktok" in lowered:
        return "https://www.douyin.com"
    if any(marker in host or marker in lowered for marker in _WECHAT_IMAGE_HOST_MARKERS):
        return "https://channels.weixin.qq.com/"
    return "https://www.bilibili.com"

@router.get("/image")
async def proxy_image(url: str):
    """
    代理图片请求，添加正确的Referer头

    Args:
        url: 图片URL

    Returns:
        图片二进制数据
    """
    try:
        # 根据URL确定Referer
        referer = _resolve_image_referer(url)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': referer,
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        # 增加超时时间到30秒，并添加重试机制
        # verify=False: 当系统代理指向 mitmproxy 时，SSL 证书链不受信任
        # trust_env=False: 避免走系统/环境变量代理，直接连接目标服务器
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            # 返回图片
            return Response(
                content=response.content,
                media_type=response.headers.get('content-type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=3600',  # 缓存1小时
                    'Access-Control-Allow-Origin': '*',  # 允许跨域
                }
            )

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching image: {url}")
        raise HTTPException(status_code=504, detail="Image fetch timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching image {url}: {e.response.status_code}")
        raise HTTPException(status_code=502, detail=f"Image server returned {e.response.status_code}")
    except httpx.HTTPError as e:
        logger.error(f"Failed to proxy image {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {str(e)}")
    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

