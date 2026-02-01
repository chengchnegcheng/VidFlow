/**
 * 视频号下载任务列表组件
 * 显示下载进度、状态和管理功能
 */
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
  Clock
} from 'lucide-react';
import { TaskThumbnail } from '../TaskThumbnail';

interface DownloadTask {
  task_id: string;
  url: string;
  title: string;
  thumbnail?: string;
  status: 'pending' | 'downloading' | 'decrypting' | 'completed' | 'failed' | 'cancelled';
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

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

/**
 * 格式化速度
 */
function formatSpeed(bytesPerSecond: number): string {
  if (!bytesPerSecond || bytesPerSecond === 0) return '0 B/s';
  return `${formatFileSize(bytesPerSecond)}/s`;
}

/**
 * 获取状态信息
 */
function getStatusInfo(status: string) {
  const statusMap: Record<string, { icon: any; text: string; variant: any }> = {
    pending: { icon: Clock, text: '等待中', variant: 'outline' as const },
    downloading: { icon: Download, text: '下载中', variant: 'default' as const },
    decrypting: { icon: Loader2, text: '解密中', variant: 'default' as const },
    completed: { icon: CheckCircle, text: '已完成', variant: 'default' as const },
    failed: { icon: AlertCircle, text: '失败', variant: 'destructive' as const },
    cancelled: { icon: X, text: '已取消', variant: 'outline' as const },
  };
  return statusMap[status] || statusMap.pending;
}

/**
 * 单个任务项组件
 */
const TaskItem: React.FC<{
  task: DownloadTask;
  onCancel: (taskId: string) => Promise<void>;
  onDelete: (taskId: string) => Promise<void>;
  onOpenFolder: (filePath: string) => Promise<void>;
}> = ({ task, onCancel, onDelete, onOpenFolder }) => {
  const [isProcessing, setIsProcessing] = React.useState(false);
  const statusInfo = getStatusInfo(task.status);
  const StatusIcon = statusInfo.icon;

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

  const isActive = task.status === 'downloading' || task.status === 'decrypting';
  const isCompleted = task.status === 'completed';
  const isFailed = task.status === 'failed' || task.status === 'cancelled';

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-card">
      {/* 缩略图 */}
      <TaskThumbnail
        thumbnail={task.thumbnail}
        title={task.title}
        className="shrink-0 w-20 h-14"
      />

      {/* 任务信息 */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* 标题和状态 */}
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-medium text-sm truncate flex-1" title={task.title}>
            {task.title}
          </h4>
          <Badge variant={statusInfo.variant} className="text-xs shrink-0">
            <StatusIcon className={`h-3 w-3 mr-1 ${task.status === 'decrypting' ? 'animate-spin' : ''}`} />
            {statusInfo.text}
          </Badge>
        </div>

        {/* 进度条 */}
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

        {/* 错误信息 */}
        {isFailed && task.error && (
          <div className="flex items-center gap-1 text-xs text-red-600">
            <AlertCircle className="h-3 w-3" />
            <span>{task.error}</span>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex items-center gap-2">
          {isCompleted && task.file_path && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleOpenFolder}
              className="h-7 text-xs"
            >
              <FolderOpen className="h-3 w-3 mr-1" />
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
              <X className="h-3 w-3 mr-1" />
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
              <Trash2 className="h-3 w-3 mr-1" />
              删除
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * 下载任务列表组件
 */
export const DownloadTaskList: React.FC<DownloadTaskListProps> = ({
  tasks,
  onCancel,
  onDelete,
  onOpenFolder,
}) => {
  if (tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Download className="h-10 w-10 text-muted-foreground mb-3 opacity-50" />
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
