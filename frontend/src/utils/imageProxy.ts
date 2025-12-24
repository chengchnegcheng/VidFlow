/**
 * 图片代理工具 - 解决防盗链问题
 */
import { getApiBaseUrl } from '../components/TauriIntegration';

/**
 * 将可能被防盗链保护的图片URL转换为代理URL
 * @param url 原始图片URL
 * @returns 代理后的URL
 */
export function getProxiedImageUrl(url: string | undefined | null): string {
  if (!url) {
    return '';
  }

  // 如果是本地图片或data URL，直接返回
  if (url.startsWith('data:') || url.startsWith('blob:') || url.startsWith('/')) {
    return url;
  }

  // 检查是否需要代理（B站、YouTube、抖音等）
  const needsProxy = 
    url.includes('hdslb.com') ||      // B站
    url.includes('bilibili.com') ||   
    url.includes('ytimg.com') ||      // YouTube
    url.includes('ggpht.com') ||      
    url.includes('douyin.com') ||     // 抖音
    url.includes('tiktok.com');

  if (needsProxy) {
    // 使用后端代理（通过 TauriIntegration 获取正确的动态端口）
    const apiBaseUrl = getApiBaseUrl();
    return `${apiBaseUrl}/api/v1/proxy/image?url=${encodeURIComponent(url)}`;
  }

  // 其他URL直接返回
  return url;
}

/**
 * 图片加载错误处理
 * @param e 错误事件
 * @param fallbackUrl 备用图片URL
 */
export function handleImageError(
  e: React.SyntheticEvent<HTMLImageElement, Event>,
  fallbackUrl?: string
) {
  const img = e.currentTarget;
  
  // 避免无限循环
  if (img.dataset.errorHandled === 'true') {
    return;
  }
  img.dataset.errorHandled = 'true';

  console.warn('Image failed to load:', img.src);

  if (fallbackUrl) {
    img.src = fallbackUrl;
  } else {
    // 使用默认占位图
    img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTYiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7mlbDmja7kuI3lrZjlnKg8L3RleHQ+PC9zdmc+';
  }
}
