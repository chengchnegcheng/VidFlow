/**
 * Download Manager - 适配 VidFlow-Tauri UI
 */
import { useState } from 'react';
import { invoke } from './TauriIntegration';
import { useSettings } from '../contexts/SettingsContext';
import { useTaskProgress, DownloadTask } from '../contexts/TaskProgressContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Label } from './ui/label';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import {
  Download,
  Clock,
  CheckCircle,
  AlertCircle,
  Youtube,
  PlayCircle,
  Music,
  Video,
  Globe,
  Trash2,
  FolderOpen,
  Loader2,
  Cookie,
  RotateCw,
  AlertTriangle,
  Settings
} from 'lucide-react';
import { toast } from 'sonner';
import { getProxiedImageUrl, handleImageError } from '../utils/imageProxy';

interface VideoInfo {
  title: string;
  duration: number;  // 时长（秒）
  platform?: string;
  thumbnail?: string;
  quality?: string[];
  formats: { ext: string }[];
  // 智能下载器信息
  downloader_used?: string;
  fallback_used?: boolean;
  fallback_reason?: string;
}

// 格式化时长（秒 -> 分:秒 或 时:分:秒）
function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '未知';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  } else {
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
}

// 格式化字节大小
function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

const platformConfig: Record<string, { icon: any, color: string, name: string }> = {
  youtube: { icon: Youtube, color: 'bg-red-500', name: 'YouTube' },
  bilibili: { icon: PlayCircle, color: 'bg-pink-500', name: 'Bilibili' },
  douyin: { icon: Music, color: 'bg-black', name: '抖音' },
  tiktok: { icon: Music, color: 'bg-black', name: 'TikTok' },
  weixin: { icon: Video, color: 'bg-green-500', name: '微信视频号' },
  xiaohongshu: { icon: PlayCircle, color: 'bg-red-400', name: '小红书' },
  iqiyi: { icon: PlayCircle, color: 'bg-green-600', name: '爱奇艺' },
  youku: { icon: PlayCircle, color: 'bg-blue-500', name: '优酷' },
  tencent: { icon: PlayCircle, color: 'bg-blue-600', name: '腾讯视频' },
  twitter: { icon: PlayCircle, color: 'bg-sky-500', name: 'Twitter/X' },
  instagram: { icon: PlayCircle, color: 'bg-pink-600', name: 'Instagram' },
  facebook: { icon: PlayCircle, color: 'bg-blue-700', name: 'Facebook' },
  generic: { icon: Globe, color: 'bg-gray-500', name: '通用下载' }
};

// 需要Cookie的平台列表（有反爬虫机制或需要登录）
// 与后端 cookie_helper.py 中的 PLATFORM_URLS 保持一致
const PLATFORMS_REQUIRING_COOKIE = [
  'douyin',      // 抖音
  'tiktok',      // TikTok
  'xiaohongshu', // 小红书
  'bilibili',    // B站（部分会员内容）
  'youtube',     // YouTube（部分会员内容）
  'twitter',     // Twitter/X
  'instagram'    // Instagram
];

// 平台检测函数（与后端 downloader_factory.py 保持一致）
function detectPlatform(url: string): string {
  const urlLower = url.toLowerCase();
  if (urlLower.includes('youtube.com') || urlLower.includes('youtu.be')) return 'youtube';
  if (urlLower.includes('bilibili.com') || urlLower.includes('b23.tv')) return 'bilibili';
  if (urlLower.includes('douyin.com') || urlLower.includes('v.douyin.com')) return 'douyin';
  if (urlLower.includes('tiktok.com')) return 'tiktok';
  if (urlLower.includes('xiaohongshu.com') || urlLower.includes('xhslink.com')) return 'xiaohongshu';
  if (urlLower.includes('weixin') || urlLower.includes('qq.com/channels')) return 'weixin';
  if (urlLower.includes('v.qq.com')) return 'tencent';
  if (urlLower.includes('youku.com')) return 'youku';
  if (urlLower.includes('iqiyi.com')) return 'iqiyi';
  if (urlLower.includes('twitter.com') || urlLower.includes('x.com')) return 'twitter';
  if (urlLower.includes('instagram.com')) return 'instagram';
  if (urlLower.includes('facebook.com')) return 'facebook';
  return 'generic';
}

interface DownloadManagerProps {
  onNavigateToSettings?: (targetPlatform?: string) => void;
}

export function DownloadManager({ onNavigateToSettings }: DownloadManagerProps = {}) {
  const { settings } = useSettings();
  const { downloads: currentTasks, refreshDownloads } = useTaskProgress();
  const [url, setUrl] = useState('');
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [selectedQuality, setSelectedQuality] = useState(settings.defaultQuality || 'best');
  const [selectedFormat, setSelectedFormat] = useState(settings.defaultFormat || 'mp4');
  const [loading, setLoading] = useState(false); // downloading state
  const [infoLoading, setInfoLoading] = useState(false); // fetching info state
  const [thumbnailError, setThumbnailError] = useState(false); // thumbnail load error
  const [cookieWarning, setCookieWarning] = useState<{ platform: string; platformName: string } | null>(null);
  
  // 打开文件夹
  const handleOpenFolder = async (filePath?: string) => {
    if (!filePath) {
      toast.error('文件路径不存在');
      return;
    }
    
    try {
      // 检查是否在 Electron 环境
      if (window.electron && window.electron.isElectron) {
        await window.electron.showItemInFolder(filePath);
      } else {
        // 浏览器环境降级
        toast.info('打开文件夹', {
          description: '浏览器环境不支持此功能，请使用 Electron 版本'
        });
      }
    } catch (error) {
      toast.error('打开文件夹失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };
  
  // URL格式验证
  const isValidUrl = (urlString: string): boolean => {
    // 检查是否包含协议
    if (!urlString.startsWith('http://') && !urlString.startsWith('https://')) {
      return false;
    }
    
    try {
      new URL(urlString);
      return true;
    } catch {
      return false;
    }
  };

  // 检查Cookie状态
  const checkCookieStatus = async (platform: string): Promise<boolean> => {
    try {
      const status = await invoke('get_cookies_status');
      const platformStatus = status[platform];
      return platformStatus?.exists || false;
    } catch (error) {
      console.error('Failed to check cookie status:', error);
      return false;
    }
  };

  // 清理和提取 URL
  const cleanUrl = (text: string): string => {
    // 移除首尾空格
    text = text.trim();
    
    // 使用正则提取 URL
    const urlPattern = /(https?:\/\/[^\s]+)/gi;
    const matches = text.match(urlPattern);
    
    if (matches && matches.length > 0) {
      // 获取第一个匹配的 URL
      let cleanedUrl = matches[0];
      
      // 移除 URL 末尾可能的特殊字符和文本
      // 例如：https://v.douyin.com/xxx/ M@W.zt 09/29 UlC:/
      cleanedUrl = cleanedUrl.split(/\s/)[0]; // 按空格分割，取第一部分
      
      // 移除末尾的特殊字符（但保留 / ? # & = 等有效字符）
      cleanedUrl = cleanedUrl.replace(/[^\w\-._~:/?#[\]@!$&'()*+,;=%]+$/, '');
      
      return cleanedUrl;
    }
    
    return text;
  };

  // 获取视频信息
  const handleGetInfo = async () => {
    const cleanedUrl = cleanUrl(url);
    
    // 如果清理后的 URL 与原始输入不同，更新输入框
    if (cleanedUrl !== url) {
      setUrl(cleanedUrl);
    }
    
    if (!cleanedUrl) {
      toast.error('请输入视频链接');
      return;
    }

    // URL格式验证
    if (!isValidUrl(cleanedUrl)) {
      toast.error('请输入有效的视频链接', {
        description: '链接应以 http:// 或 https:// 开头'
      });
      return;
    }

    // 检测平台
    const platform = detectPlatform(cleanedUrl);
    
    // 检查是否需要Cookie
    if (PLATFORMS_REQUIRING_COOKIE.includes(platform)) {
      const hasCookie = await checkCookieStatus(platform);
      if (!hasCookie) {
        const platformNames: Record<string, string> = {
          douyin: '抖音',
          tiktok: 'TikTok',
          xiaohongshu: '小红书',
          instagram: 'Instagram',
          twitter: 'Twitter/X'
        };
        setCookieWarning({ 
          platform, 
          platformName: platformNames[platform] || platform 
        });
        toast.warning(`${platformNames[platform]} 需要配置Cookie`, {
          description: '点击下方提示配置Cookie以获取更好的下载体验'
        });
      } else {
        setCookieWarning(null);
      }
    } else {
      setCookieWarning(null);
    }

    setInfoLoading(true);
    setThumbnailError(false); // 重置缩略图错误状态
    try {
      const info = await invoke('get_video_info', { url: cleanedUrl });
      setVideoInfo(info);
      toast.success('视频信息获取成功');
    } catch (error: any) {
      toast.error('获取视频信息失败', {
        description: error.message || '请检查链接是否正确'
      });
      setVideoInfo(null);
    } finally {
      setInfoLoading(false);
    }
  };

  // 开始下载
  const handleDownload = async () => {
    const cleanedUrl = cleanUrl(url);
    
    // 更新输入框
    if (cleanedUrl !== url) {
      setUrl(cleanedUrl);
    }
    
    if (!cleanedUrl) {
      toast.error('请输入视频链接');
      return;
    }

    // URL格式验证
    if (!isValidUrl(cleanedUrl)) {
      toast.error('请输入有效的视频链接', {
        description: '链接应以 http:// 或 https:// 开头'
      });
      return;
    }

    setLoading(true);
    try {
      const result = await invoke('start_download', {
        url: cleanedUrl,
        quality: selectedQuality,
        format_id: selectedFormat,
        output_path: settings.downloadPath || undefined, // 使用设置中的下载路径
      });
      toast.success(`下载任务已创建！任务ID: ${result.task_id}`);
      setUrl('');
      setVideoInfo(null);
      await refreshDownloads();
    } catch (error: any) {
      toast.error('开始下载失败', {
        description: error.message || '请检查链接是否正确'
      });
    } finally {
      setLoading(false);
    }
  };

  // 删除任务
  const handleDeleteTask = async (taskId: string) => {
    try {
      await invoke('delete_download_task', { task_id: taskId });
      toast.success('任务已删除');
      await refreshDownloads();
    } catch (error: any) {
      toast.error(`删除失败: ${error.message}`);
    }
  };

  // 取消任务
  const handleCancelTask = async (taskId: string) => {
    try {
      await invoke('cancel_download_task', { task_id: taskId });
      toast.success('已发送取消请求');
      await refreshDownloads();
    } catch (error: any) {
      toast.error(`取消失败: ${error.message}`);
    }
  };

  // 重试失败的任务
  const handleRetryTask = async (task: DownloadTask) => {
    try {
      // 先删除失败的任务
      await invoke('delete_download_task', { task_id: task.task_id });

      // 重新提交下载
      const result = await invoke('start_download', {
        url: task.url,
        quality: task.quality || 'best',
        format_id: task.format_id,
        output_path: settings.downloadPath || undefined,
      });

      toast.success(`任务已重新提交！任务ID: ${result.task_id}`);
      await refreshDownloads();
    } catch (error: any) {
      toast.error('重试失败', {
        description: error.message || '请检查网络或配置'
      });
    }
  };

  // 获取状态徽章变体
  const getStatusBadge = (status: string) => {
    const badges: Record<string, { variant: any, icon: any, text: string }> = {
      pending: { variant: 'outline' as const, icon: Clock, text: '等待中' },
      downloading: { variant: 'default' as const, icon: Download, text: '下载中' },
      completed: { variant: 'default' as const, icon: CheckCircle, text: '已完成' },
      failed: { variant: 'destructive' as const, icon: AlertCircle, text: '失败' },
    };
    return badges[status] || badges.pending;
  };

  const getPlatformConfig = (platform?: string) => {
    return platformConfig[platform?.toLowerCase() || ''] || platformConfig.generic;
  };

  return (
    <div className="space-y-6 p-6">
      {/* 输入区域 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="size-5" />
            新建下载任务
          </CardTitle>
          <CardDescription>输入视频链接开始下载</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex gap-2">
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="输入视频链接（支持完整分享文本）"
                disabled={loading || infoLoading}
                onKeyDown={(e) => e.key === 'Enter' && handleGetInfo()}
                onBlur={() => {
                  // 失去焦点时自动清理 URL
                  const cleaned = cleanUrl(url);
                  if (cleaned !== url) {
                    setUrl(cleaned);
                  }
                }}
                onPaste={() => {
                  // 粘贴时自动清理 URL
                  setTimeout(() => {
                    const cleaned = cleanUrl(url);
                    if (cleaned !== url) {
                      setUrl(cleaned);
                    }
                  }, 0);
                }}
                className={url.trim() && !isValidUrl(cleanUrl(url)) ? 'border-destructive' : ''}
              />
              <Button 
                onClick={handleGetInfo} 
                disabled={loading || infoLoading}
                variant="secondary"
              >
                {infoLoading ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    获取中...
                  </>
                ) : (
                    <>获取信息</>
                )}
              </Button>
            </div>
            {url.trim() && !isValidUrl(url.trim()) && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="size-3" />
                请输入有效的视频链接（需以 http:// 或 https:// 开头）
              </p>
            )}
            
            {/* Cookie 警告提示 */}
            {cookieWarning && (
              <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
                <div className="flex items-start gap-3">
                  <Cookie className="size-5 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-amber-900 dark:text-amber-100 mb-1">
                      {cookieWarning.platformName} 需要配置 Cookie
                    </h4>
                    <p className="text-sm text-amber-800 dark:text-amber-200 mb-2">
                      该平台有反爬虫机制，配置Cookie后可以获得更好的下载体验。
                      <br />
                      <span className="text-xs">注：未配置Cookie可能导致下载失败或只能下载低画质视频</span>
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="bg-white dark:bg-gray-900"
                      onClick={() => {
                        onNavigateToSettings?.(cookieWarning.platform);
                      }}
                    >
                      <Settings className="size-3 mr-2" />
                      前往配置 Cookie
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 加载骨架 */}
          {infoLoading && (
            <div className="space-y-4 p-4 border rounded-lg">
              <div className="flex gap-4 animate-pulse">
                <div className="w-32 h-32 bg-muted rounded" />
                <div className="flex-1 space-y-2">
                  <div className="h-5 bg-muted rounded w-3/4" />
                  <div className="h-4 bg-muted rounded w-1/2" />
                  <div className="h-4 bg-muted rounded w-1/3" />
                </div>
              </div>
              <Separator />
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="h-4 bg-muted rounded w-24" />
                  <div className="h-10 bg-muted rounded" />
                </div>
                <div className="space-y-2">
                  <div className="h-4 bg-muted rounded w-16" />
                  <div className="h-10 bg-muted rounded" />
                </div>
              </div>
              <div className="h-10 bg-muted rounded" />
            </div>
          )}

          {/* 视频信息 */}
          {videoInfo && (
            <div className="space-y-4 p-4 border rounded-lg bg-muted/50">
              <div className="flex gap-4">
                {videoInfo.thumbnail && !thumbnailError ? (
                  <img 
                    src={getProxiedImageUrl(videoInfo.thumbnail)} 
                    alt={videoInfo.title}
                    className="w-32 h-32 object-cover rounded bg-muted"
                    onError={(e) => {
                      handleImageError(e);
                      setThumbnailError(true);
                    }}
                  />
                ) : (
                  <div className="w-32 h-32 bg-muted rounded flex items-center justify-center">
                    <Video className="size-12 text-muted-foreground/50" />
                  </div>
                )}
                <div className="flex-1 space-y-2">
                  <h3 className="font-semibold">{videoInfo.title}</h3>
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    {videoInfo.platform && (() => {
                      const config = getPlatformConfig(videoInfo.platform);
                      const PlatformIcon = config.icon;
                      return (
                        <span className="flex items-center gap-1">
                          <PlatformIcon className="size-4" />
                          <span>{config.name}</span>
                        </span>
                      );
                    })()}
                    {videoInfo.duration && <span>时长: {formatDuration(videoInfo.duration)}</span>}
                  </div>
                  {/* 智能下载器信息 */}
                  {videoInfo.downloader_used && (
                    <div className="flex items-center gap-2 text-xs">
                      <Badge variant={videoInfo.fallback_used ? "secondary" : "outline"} className="text-xs">
                        {videoInfo.downloader_used === 'generic' ? '通用下载器' : `${videoInfo.downloader_used} 专用下载器`}
                      </Badge>
                      {videoInfo.fallback_used && (
                        <span className="text-amber-600 dark:text-amber-400">
                          (已自动回退)
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
              
              <Separator />
              
              <div className="flex gap-2">
                <div className="flex-1">
                  <Label>视频质量</Label>
                  <Select value={selectedQuality} onValueChange={setSelectedQuality}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="best">最佳质量</SelectItem>
                      <SelectItem value="2160p">4K (2160p)</SelectItem>
                      <SelectItem value="1440p">2K (1440p)</SelectItem>
                      <SelectItem value="1080p">1080p</SelectItem>
                      <SelectItem value="720p">720p</SelectItem>
                      <SelectItem value="480p">480p</SelectItem>
                      <SelectItem value="audio">仅音频</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="flex-1">
                  <Label>格式</Label>
                  <Select value={selectedFormat} onValueChange={setSelectedFormat}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mp4">MP4</SelectItem>
                      <SelectItem value="mkv">MKV</SelectItem>
                      <SelectItem value="webm">WebM</SelectItem>
                      <SelectItem value="mp3">MP3 (音频)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <Button 
                onClick={handleDownload}
                disabled={loading}
                className="w-full"
              >
                <Download className="mr-2 size-4" />
                开始下载
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 任务列表 */}
      <Card>
        <CardHeader>
          <CardTitle>下载任务</CardTitle>
          <CardDescription>
            共 {currentTasks.length} 个任务
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px]">
            {currentTasks.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Download className="size-12 mx-auto mb-4 opacity-20" />
                <p>暂无下载任务</p>
              </div>
            ) : (
              <div className="space-y-3">
                {currentTasks.map((task) => {
                  const statusInfo = getStatusBadge(task.status);
                  const StatusIcon = statusInfo.icon;
                  const platform = getPlatformConfig(task.platform);
                  const PlatformIcon = platform.icon;
                  
                  return (
                    <div key={task.task_id} className="p-4 border rounded-lg space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <div className={`p-1 rounded ${platform.color}`}>
                              <PlatformIcon className="size-3 text-white" />
                            </div>
                            <h4 className="font-medium">{task.title || '未知标题'}</h4>
                          </div>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Badge variant={statusInfo.variant}>
                              <StatusIcon className="size-3 mr-1" />
                              {statusInfo.text}
                            </Badge>
                            <span>{task.quality}</span>
                            {task.filename && <span className="truncate max-w-[200px]">{task.filename}</span>}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteTask(task.task_id)}
                        >
                          <Trash2 className="size-4 text-muted-foreground hover:text-destructive" />
                        </Button>
                      </div>
                      
                      {(task.status === 'downloading' || task.status === 'pending') && (
                        <div className="flex justify-end mb-2">
                           <Button 
                             variant="outline" 
                             size="sm" 
                             className="h-7 text-xs"
                             onClick={() => handleCancelTask(task.task_id)}
                           >
                             取消下载
                           </Button>
                        </div>
                      )}
                      
                      {task.status === 'downloading' && (
                        <div className="space-y-1">
                          <div className="flex justify-between items-center text-sm text-muted-foreground">
                            <div className="flex items-center gap-2">
                              {task.downloaded && task.total ? (
                                <span>{formatBytes(task.downloaded)} / {formatBytes(task.total)}</span>
                              ) : null}
                              {task.speed && typeof task.speed === 'number' ? (
                                <span>速度: {formatBytes(task.speed)}/s</span>
                              ) : task.speed ? (
                                <span>速度: {task.speed}</span>
                              ) : null}
                            </div>
                            <span className="font-medium">{Math.min(Math.max(task.progress || 0, 0), 100).toFixed(1)}%</span>
                          </div>
                          <Progress value={Math.min(Math.max(task.progress || 0, 0), 100)} className="h-2" />
                        </div>
                      )}

                      {task.status === 'completed' && task.filename && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenFolder((task as any).file_path)}
                        >
                          <FolderOpen className="size-3 mr-1" />
                          打开文件夹
                        </Button>
                      )}

                      {task.status === 'failed' && (
                        <div className="space-y-2">
                          {/* 错误信息显示 */}
                          {task.error_message && (
                            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                              <div className="flex items-start gap-2">
                                <AlertTriangle className="size-4 text-destructive mt-0.5 flex-shrink-0" />
                                <div className="flex-1 space-y-1">
                                  <p className="text-sm font-medium text-destructive">下载失败</p>
                                  <p className="text-xs text-muted-foreground whitespace-pre-wrap break-words">
                                    {task.error_message}
                                  </p>
                                </div>
                              </div>
                            </div>
                          )}
                          {/* 重试按钮 */}
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRetryTask(task)}
                              className="flex-1"
                            >
                              <RotateCw className="size-3 mr-1" />
                              重试下载
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
