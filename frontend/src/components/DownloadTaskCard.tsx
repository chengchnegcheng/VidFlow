import { DownloadTask } from '../contexts/TaskProgressContext';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { TaskThumbnail } from './TaskThumbnail';
import {
  Trash2,
  FolderOpen,
  Pause,
  Play,
  RotateCw
} from 'lucide-react';

interface DownloadTaskCardProps {
  task: DownloadTask;
  statusInfo: {
    variant: any;
    icon: any;
    text: string;
  };
  platformConfig: {
    icon: any;
    color: string;
    name: string;
  };
  onDelete: (taskId: string) => void;
  onPause: (taskId: string) => void;
  onResume: (taskId: string) => void;
  onCancel: (taskId: string) => void;
  onRetry: (task: DownloadTask) => void;
  onOpenFolder: (filePath?: string) => void;
}

function formatBytes(bytes?: number) {
  if (bytes === undefined || bytes === null || isNaN(bytes)) return '';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
}

export function DownloadTaskCard({
  task,
  statusInfo,
  platformConfig,
  onDelete,
  onPause,
  onResume,
  onCancel,
  onRetry,
  onOpenFolder
}: DownloadTaskCardProps) {
  const StatusIcon = statusInfo.icon;
  const PlatformIcon = platformConfig.icon;

  return (
    <div className="p-4 border rounded-lg">
      <div className="flex gap-3">
        {/* Thumbnail Section */}
        <TaskThumbnail
          filePath={(task as any).file_path}
          thumbnail={task.thumbnail}
          title={task.title || '视频缩略图'}
        />

        {/* Content Section */}
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2">
                <div className={`p-1 rounded ${platformConfig.color}`}>
                  <PlatformIcon className="size-3 text-white" />
                </div>
                <h4 className="font-semibold truncate">{task.title || '未知标题'}</h4>
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
              onClick={() => onDelete(task.task_id)}
            >
              <Trash2 className="size-4 text-muted-foreground hover:text-destructive" />
            </Button>
          </div>

          {(task.status === 'downloading' || task.status === 'pending') && (
            <div className="flex justify-end gap-2">
               {task.status === 'downloading' && (
                 <Button
                   variant="outline"
                   size="sm"
                   className="h-7 text-xs"
                   onClick={() => onPause(task.task_id)}
                 >
                   <Pause className="size-3 mr-1" />
                   暂停
                 </Button>
               )}
               <Button
                 variant="outline"
                 size="sm"
                 className="h-7 text-xs"
                 onClick={() => onCancel(task.task_id)}
               >
                 取消下载
               </Button>
            </div>
          )}

          {task.status === 'paused' && (
            <div className="flex justify-end gap-2">
               <Button
                 variant="outline"
                 size="sm"
                 className="h-7 text-xs"
                 onClick={() => onResume(task.task_id)}
               >
                 <Play className="size-3 mr-1" />
                 继续下载
               </Button>
               <Button
                 variant="outline"
                 size="sm"
                 className="h-7 text-xs"
                 onClick={() => onCancel(task.task_id)}
               >
                 取消下载
               </Button>
            </div>
          )}

          {task.status === 'downloading' && (
            <div className="space-y-1">
              <div className="flex justify-between items-center text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  {(task.downloaded !== undefined || task.total !== undefined) && (
                    <span>{formatBytes(task.downloaded)} / {formatBytes(task.total)}</span>
                  )}
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

          {task.status === 'paused' && (
            <div className="space-y-1">
              <div className="flex justify-between items-center text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  {(task.downloaded !== undefined || task.total !== undefined) && (
                    <span>{formatBytes(task.downloaded)} / {formatBytes(task.total)}</span>
                  )}
                  <span className="text-amber-600 dark:text-amber-400">已暂停</span>
                </div>
                <span className="font-medium">{Math.min(Math.max(task.progress || 0, 0), 100).toFixed(1)}%</span>
              </div>
              <Progress value={Math.min(Math.max(task.progress || 0, 0), 100)} className="h-2 [&>div]:bg-amber-500" />
            </div>
          )}

          {task.status === 'completed' && task.filename && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onOpenFolder((task as any).file_path)}
            >
              <FolderOpen className="size-3 mr-1" />
              打开文件夹
            </Button>
          )}

          {task.status === 'failed' && (
            <div className="space-y-2">
              {(task.error_message || task.error) && (
                <div className="p-2 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded text-xs text-red-700 dark:text-red-400">
                  {task.error_message || task.error}
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => onRetry(task)}
              >
                <RotateCw className="size-3 mr-1" />
                重试
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
