/**
 * 视频列表组件
 * 显示检测到的视频列表，包含缩略图、标题、时长和下载按钮
 */
import React from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Input } from '../ui/input';
import {
  Download,
  Copy,
  Trash2,
  Video,
  Lock,
  Clock,
  HardDrive,
  Check,
  Plus,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import {
  DetectedVideo,
  DownloadRequest,
  formatFileSize,
  formatDuration,
} from '../../types/channels';
import { TaskThumbnail } from '../TaskThumbnail';

const normalizeDecodeKey = (value?: string | null): string | null => {
  if (!value) return null;
  const key = String(value).trim();
  return /^\d+$/.test(key) ? key : null;
};

const requiresDecodeKey = (url?: string | null, encryptionType?: string | null): boolean => {
  const type = String(encryptionType || '').toLowerCase();
  if (type === 'isaac64') return true;
  const normalizedUrl = String(url || '').toLowerCase();
  return normalizedUrl.includes('encfilekey=') || normalizedUrl.includes('/stodownload');
};

interface VideoListProps {
  videos: DetectedVideo[];
  onDownload: (request: DownloadRequest) => Promise<void>;
  onClearAll: () => Promise<void>;
  onAddVideo?: (url: string, title?: string) => Promise<any>;
  qualityPreference?: string;
  downloadDir?: string;
}

interface VideoItemProps {
  video: DetectedVideo;
  onDownload: (request: DownloadRequest) => Promise<void>;
  qualityPreference?: string;
  downloadDir?: string;
}

const VideoItem: React.FC<VideoItemProps> = ({ video, onDownload, qualityPreference, downloadDir }) => {
  const [copied, setCopied] = React.useState(false);
  const [downloading, setDownloading] = React.useState(false);
  const decodeKey = normalizeDecodeKey(video.decryption_key);
  const encryptionType = String(video.encryption_type || '').toLowerCase();
  const isEncrypted = requiresDecodeKey(video.url, encryptionType) || (encryptionType !== 'none' && encryptionType !== 'unknown');
  const missingDecodeKey = isEncrypted && !decodeKey;

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(video.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn('Clipboard API failed, using fallback:', err);
      try {
        const textArea = document.createElement('textarea');
        textArea.value = video.url;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (fallbackErr) {
        console.error('Failed to copy URL:', fallbackErr);
      }
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const request = {
        url: video.url,
        quality: qualityPreference || 'best',
        output_path: downloadDir || undefined,
        auto_decrypt: isEncrypted && Boolean(decodeKey),
        decryption_key: decodeKey,
      };
      console.info('[channels] download click', {
        title: video.title || null,
        urlPreview: video.url ? `${video.url.slice(0, 160)}${video.url.length > 160 ? '...' : ''}` : null,
        encryptionType,
        isEncrypted,
        decodeKeyPresent: Boolean(decodeKey),
        missingDecodeKey,
        isPlaceholder: Boolean(video.is_placeholder),
        placeholderMessage: video.placeholder_message || null,
        request: {
          ...request,
          decryption_key: request.decryption_key ? '[present]' : null,
        },
      });
      await onDownload(request);
    } finally {
      setDownloading(false);
    }
  };

  const getEncryptionBadge = () => {
    if (encryptionType === 'none' || encryptionType === 'unknown') return null;
    return (
      <Badge variant="outline" className="text-xs">
        <Lock className="h-3 w-3 mr-1" />
        {encryptionType.toUpperCase()}
      </Badge>
    );
  };

  const downloadTitle = video.is_placeholder
    ? (video.placeholder_message || '请先在微信中播放该视频后再下载')
    : (missingDecodeKey
        ? '当前还没抓到 decodeKey，将下载加密原文件。如需自动解密，请在启动嗅探后重新打开视频号页面并完整播放一遍。'
        : undefined);

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
      <TaskThumbnail
        thumbnail={video.thumbnail || undefined}
        title={video.title || '微信视频号'}
        className="shrink-0 w-24 h-16"
      />

      <div className="flex-1 min-w-0 space-y-2">
        <div className="space-y-1">
          <h4 className="font-medium text-sm truncate" title={video.title || '微信视频号'}>
            {video.title || '微信视频号'}
          </h4>
          <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
            {video.is_placeholder && video.placeholder_message && (
              <span className="flex items-center gap-1 text-yellow-600">
                <AlertCircle className="h-3 w-3" />
                {video.placeholder_message}
              </span>
            )}
            {video.duration && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDuration(video.duration)}
              </span>
            )}
            {video.filesize && (
              <span className="flex items-center gap-1">
                <HardDrive className="h-3 w-3" />
                {formatFileSize(video.filesize)}
              </span>
            )}
            {video.resolution && (
              <Badge variant="secondary" className="text-xs">
                {video.resolution}
              </Badge>
            )}
            {getEncryptionBadge()}
            {missingDecodeKey && (
              <Badge variant="outline" className="text-xs text-amber-700 border-amber-300">
                <AlertCircle className="h-3 w-3 mr-1" />
                缺少密钥
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyUrl}
            className="h-8"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 mr-1.5 text-green-500" />
                <span>已复制</span>
              </>
            ) : (
              <>
                <Copy className="h-4 w-4 mr-1.5" />
                <span>复制链接</span>
              </>
            )}
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={handleDownload}
            disabled={downloading || !video.url}
            className="h-8"
            title={downloadTitle}
          >
            <Download className="h-4 w-4 mr-1.5" />
            <span className="font-medium">{downloading ? '下载中...' : '下载'}</span>
          </Button>
        </div>

        <p className="text-xs text-muted-foreground truncate font-mono">
          {video.url}
        </p>
      </div>
    </div>
  );
};

export const VideoList: React.FC<VideoListProps> = ({
  videos,
  onDownload,
  onClearAll,
  onAddVideo,
  qualityPreference,
  downloadDir,
}) => {
  const [manualUrl, setManualUrl] = React.useState('');
  const [isAdding, setIsAdding] = React.useState(false);
  const [addError, setAddError] = React.useState<string | null>(null);

  const handleAddVideo = async () => {
    if (!manualUrl.trim() || !onAddVideo) return;

    setIsAdding(true);
    setAddError(null);

    try {
      const result = await onAddVideo(manualUrl.trim());
      if (result.success) {
        setManualUrl('');
      } else {
        setAddError(result.error_message || '添加失败');
      }
    } catch (error: any) {
      setAddError(error.message || '添加失败');
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <div className="space-y-3">
      {onAddVideo && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Input
              placeholder="粘贴视频 URL（从浏览器开发者工具或抓包软件获取）"
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddVideo()}
              className="flex-1"
            />
            <Button
              onClick={handleAddVideo}
              disabled={!manualUrl.trim() || isAdding}
              size="sm"
            >
              {isAdding ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-1" />
                  添加
                </>
              )}
            </Button>
          </div>
          {addError && (
            <p className="text-xs text-destructive">{addError}</p>
          )}
          <p className="text-xs text-muted-foreground">
            提示：可以使用浏览器开发者工具（F12）或 Fiddler 等抓包软件获取视频 URL
          </p>
        </div>
      )}

      {videos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Video className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="font-medium text-lg">暂无检测到的视频</h3>
          <p className="text-sm text-muted-foreground mt-1">
            启动嗅探器后，浏览视频号内容即可自动捕获视频链接
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            或者手动粘贴视频 URL 到上方输入框
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <h3 className="font-medium">
              检测到的视频 ({videos.length})
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearAll}
              className="text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-1" />
              清空列表
            </Button>
          </div>

          <ScrollArea className="h-[400px]">
            <div className="space-y-2 pr-4">
              {videos.map((video) => (
                <VideoItem
                  key={video.id}
                  video={video}
                  onDownload={onDownload}
                  qualityPreference={qualityPreference}
                  downloadDir={downloadDir}
                />
              ))}
            </div>
          </ScrollArea>
        </>
      )}
    </div>
  );
};

export default VideoList;
