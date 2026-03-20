import React from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { ScrollArea } from '../ui/scroll-area';
import {
  Download,
  Trash2,
  FolderOpen,
  X,
  CheckCircle,
  AlertCircle,
  Loader2,
  Clock,
} from 'lucide-react';
import { TaskThumbnail } from '../TaskThumbnail';

interface DownloadTask {
  task_id: string;
  url: string;
  title: string;
  thumbnail?: string;
  status: 'pending' | 'downloading' | 'decrypting' | 'completed' | 'encrypted' | 'failed' | 'cancelled';
  progress: number;
  speed: number;
  downloaded: number;
  total: number;
  file_path?: string;
  error?: string;
  created_at: number;
}

interface DownloadTaskListProps {
  tasks: DownloadTask[];
  onCancel: (taskId: string) => Promise<void>;
  onDelete: (taskId: string) => Promise<void>;
  onOpenFolder: (filePath: string) => Promise<void>;
}

function formatFileSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function formatSpeed(bytesPerSecond: number): string {
  if (!bytesPerSecond || bytesPerSecond === 0) return '0 B/s';
  return `${formatFileSize(bytesPerSecond)}/s`;
}

function getStatusInfo(status: string) {
  const statusMap: Record<string, { icon: any; text: string; variant: 'outline' | 'default' | 'destructive' }> = {
    pending: { icon: Clock, text: '等待中', variant: 'outline' },
    downloading: { icon: Download, text: '下载中', variant: 'default' },
    decrypting: { icon: Loader2, text: '解密中', variant: 'default' },
    completed: { icon: CheckCircle, text: '已完成', variant: 'default' },
    encrypted: { icon: AlertCircle, text: '需密钥', variant: 'outline' },
    failed: { icon: AlertCircle, text: '失败', variant: 'destructive' },
    cancelled: { icon: X, text: '已取消', variant: 'outline' },
  };
  return statusMap[status] || statusMap.pending;
}

const TaskItem: React.FC<{
  task: DownloadTask;
  onCancel: (taskId: string) => Promise<void>;
  onDelete: (taskId: string) => Promise<void>;
  onOpenFolder: (filePath: string) => Promise<void>;
}> = ({ task, onCancel, onDelete, onOpenFolder }) => {
  const [isProcessing, setIsProcessing] = React.useState(false);
  const statusInfo = getStatusInfo(task.status);
  const StatusIcon = statusInfo.icon;
  const isActive = task.status === 'downloading' || task.status === 'decrypting';
  const isEncryptedTask = task.status === 'encrypted';
  const isCompleted = task.status === 'completed' || isEncryptedTask;
  const isFailed = task.status === 'failed' || task.status === 'cancelled';
  const hasWarning = Boolean(task.error);
  const warningOnly = (task.status === 'completed' && hasWarning) || isEncryptedTask;

  const handleCancel = async () => {
    setIsProcessing(true);
    try {
      await onCancel(task.task_id);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDelete = async () => {
    setIsProcessing(true);
    try {
      await onDelete(task.task_id);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleOpenFolder = async () => {
    if (task.file_path) {
      await onOpenFolder(task.file_path);
    }
  };

  return (
    <div className="flex items-start gap-3 rounded-lg border bg-card p-3">
      <TaskThumbnail
        filePath={task.file_path}
        thumbnail={task.thumbnail}
        title={task.title}
        className="h-14 w-20 shrink-0"
      />

      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h4 className="flex-1 truncate text-sm font-medium" title={task.title}>
            {task.title}
          </h4>
          <Badge
            variant={warningOnly ? 'outline' : statusInfo.variant}
            className={`shrink-0 text-xs ${warningOnly ? 'border-amber-300 bg-amber-50 text-amber-700' : ''}`}
          >
            <StatusIcon className={`mr-1 h-3 w-3 ${task.status === 'decrypting' ? 'animate-spin' : ''}`} />
            {statusInfo.text}
          </Badge>
        </div>

        {isActive && (
          <div className="space-y-1">
            <Progress value={task.progress} className="h-2" />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{task.progress}%</span>
              {task.total > 0 && (
                <span>
                  {formatFileSize(task.downloaded)} / {formatFileSize(task.total)}
                </span>
              )}
              {task.speed > 0 && <span>{formatSpeed(task.speed)}</span>}
            </div>
          </div>
        )}

        {hasWarning && (
          <div className={`flex items-center gap-1 text-xs ${isFailed ? 'text-red-600' : 'text-amber-600'}`}>
            <AlertCircle className="h-3 w-3 shrink-0" />
            <span>{task.error}</span>
          </div>
        )}

        <div className="flex items-center gap-2">
          {isCompleted && task.file_path && (
            <Button variant="outline" size="sm" onClick={handleOpenFolder} className="h-7 text-xs">
              <FolderOpen className="mr-1 h-3 w-3" />
              打开文件夹
            </Button>
          )}

          {isActive && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancel}
              disabled={isProcessing}
              className="h-7 text-xs"
            >
              <X className="mr-1 h-3 w-3" />
              取消
            </Button>
          )}

          {!isActive && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              disabled={isProcessing}
              className="h-7 text-xs text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="mr-1 h-3 w-3" />
              删除
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export const DownloadTaskList: React.FC<DownloadTaskListProps> = ({
  tasks,
  onCancel,
  onDelete,
  onOpenFolder,
}) => {
  if (tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Download className="mb-3 h-10 w-10 text-muted-foreground opacity-50" />
        <p className="text-sm text-muted-foreground">暂无下载任务</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[300px]">
      <div className="space-y-2 pr-4">
        {tasks.map((task) => (
          <TaskItem
            key={task.task_id}
            task={task}
            onCancel={onCancel}
            onDelete={onDelete}
            onOpenFolder={onOpenFolder}
          />
        ))}
      </div>
    </ScrollArea>
  );
};

export default DownloadTaskList;
