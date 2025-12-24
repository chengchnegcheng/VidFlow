"""
图片代理API - 解决防盗链问题
用于代理B站、YouTube等平台的图片请求
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import httpx
import logging

router = APIRouter(prefix="/api/v1/proxy", tags=["proxy"])
logger = logging.getLogger(__name__)

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
        referer = "https://www.bilibili.com"
        if "youtube" in url or "ytimg" in url:
            referer = "https://www.youtube.com"
        elif "douyin" in url or "tiktok" in url:
            referer = "https://www.douyin.com"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': referer,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            
            # 返回图片
            return Response(
                content=response.content,
                media_type=response.headers.get('content-type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=3600',  # 缓存1小时
                }
            )
    
    except httpx.HTTPError as e:
        logger.error(f"Failed to proxy image {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {str(e)}")
    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        raise HTTPException(status_code=500, detail=str(e))
