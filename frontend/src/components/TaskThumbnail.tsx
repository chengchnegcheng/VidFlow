import { useVideoThumbnail } from '../hooks/useVideoThumbnail';
import { getProxiedImageUrl, handleImageError } from '../utils/imageProxy';
import { Video } from 'lucide-react';

interface TaskThumbnailProps {
  filePath?: string;
  thumbnail?: string;
  title: string;
  className?: string;
}

/**
 * 任务缩略图组件
 * 优先使用本地视频文件生成缩略图，如果不存在则使用在线缩略图
 */
export function TaskThumbnail({ filePath, thumbnail, title, className = "w-32 h-20" }: TaskThumbnailProps) {
  // 使用本地视频缩略图，如果不存在则回退到在线缩略图
  const displayThumbnail = useVideoThumbnail(filePath, thumbnail);

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
    <div className={`${className} bg-muted rounded-md flex items-center justify-center flex-shrink-0`}>
      <Video className="size-8 text-muted-foreground/50" />
    </div>
  );
}
