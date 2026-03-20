import { useVideoThumbnail } from '../hooks/useVideoThumbnail';
import { getProxiedImageUrl, handleImageError } from '../utils/imageProxy';
import { Video } from 'lucide-react';

interface TaskThumbnailProps {
  filePath?: string;
  thumbnail?: string;
  title: string;
  className?: string;
}

function getFallbackLabel(title: string): string {
  const value = (title || '').trim();
  if (!value) {
    return 'CHANNELS VIDEO';
  }

  return value.length > 28 ? `${value.slice(0, 28)}...` : value;
}

/**
 * 任务缩略图组件
 * 优先使用本地视频文件生成缩略图，如果不存在则使用在线缩略图
 */
export function TaskThumbnail({ filePath, thumbnail, title, className = "w-32 h-20" }: TaskThumbnailProps) {
  // 使用本地视频缩略图，如果不存在则回退到在线缩略图
  const displayThumbnail = useVideoThumbnail(filePath, thumbnail);
  const fallbackLabel = getFallbackLabel(title);

  if (displayThumbnail) {
    return (
      <img
        src={displayThumbnail.startsWith('data:') ? displayThumbnail : getProxiedImageUrl(displayThumbnail)}
        alt={title}
        className={`${className} object-cover rounded-md flex-shrink-0 bg-muted`}
        onError={handleImageError}
      />
    );
  }

  return (
    <div
      className={`${className} rounded-md flex-shrink-0 overflow-hidden bg-gradient-to-br from-slate-100 via-slate-200 to-slate-300 text-slate-700`}
    >
      <div className="flex h-full w-full flex-col justify-between p-3">
        <Video className="size-5 text-slate-500" />
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Preview</div>
          <div className="max-h-8 overflow-hidden text-xs font-medium leading-tight">{fallbackLabel}</div>
        </div>
      </div>
    </div>
  );
}
