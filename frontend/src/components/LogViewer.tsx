import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from './TauriIntegration';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { toast } from 'sonner';
import {
  FileText,
  RefreshCw,
  Trash2,
  Download,
  Search,
  Pause,
  Play,
  AlertCircle,
  AlertTriangle,
  Info,
  Bug,
  FolderOpen
} from 'lucide-react';

interface LogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  line_number: number;
}

interface LogStats {
  total_lines: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  debug_count: number;
  file_size: number;
  last_modified: string;
}

export function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 切换日志级别过滤
  const handleLevelChange = (newLevel: string) => {
    setLevelFilter(newLevel);
  };

  // 获取日志
  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = { limit: 200 };

      if (levelFilter !== 'ALL') {
        params.level = levelFilter;
      }

      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }

      const result = await invoke('get_logs', params);
      setLogs(result || []);
    } catch (error) {
      console.error('获取日志失败:', error);
      toast.error('加载失败', { description: '无法获取日志数据' });
    } finally {
      setLoading(false);
    }
  }, [levelFilter, searchQuery]);

  // 获取统计
  const fetchStats = useCallback(async () => {
    try {
      const result = await invoke('get_log_stats');
      setStats(result);
    } catch (error) {
      console.error('获取统计失败:', error);
    }
  }, []);

  // 自动刷新
  useEffect(() => {
    fetchLogs();
    fetchStats();

    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchLogs();
        fetchStats();
      }, 3000); // 每3秒刷新

      return () => clearInterval(interval);
    }
  }, [fetchLogs, fetchStats, autoRefresh]);

  // 打开清空确认对话框
  const handleClearClick = () => {
    setShowClearDialog(true);
  };

  // 确认清空日志
  const handleConfirmClear = async () => {
    setShowClearDialog(false);
    try {
      await invoke('clear_logs');
      toast.success('日志已清空');
      setLogs([]);
      await fetchStats();
    } catch (error) {
      toast.error('清空失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  // 下载日志
  const handleDownloadLogs = async () => {
    try {
      await invoke('download_logs');
      toast.success('日志下载成功');
    } catch (error) {
      toast.error('下载失败', {
        description: error instanceof Error ? error.message : '下载失败'
      });
    }
  };

  // 打开日志目录
  const handleOpenLogFolder = async () => {
    try {
      const result = await invoke('get_log_path') as { success: boolean; path: string };
      if (result?.path) {
        await invoke('open_folder', { path: result.path });
      }
    } catch (error) {
      toast.error('打开失败', {
        description: error instanceof Error ? error.message : '无法打开日志目录'
      });
    }
  };

  // 获取级别样式
  const getLevelBadge = (level: string) => {
    switch (level) {
      case 'ERROR':
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertCircle className="size-3" />
            ERROR
          </Badge>
        );
      case 'WARNING':
        return (
          <Badge className="bg-yellow-500 gap-1">
            <AlertTriangle className="size-3" />
            WARNING
          </Badge>
        );
      case 'INFO':
        return (
          <Badge variant="default" className="gap-1">
            <Info className="size-3" />
            INFO
          </Badge>
        );
      case 'DEBUG':
        return (
          <Badge variant="outline" className="gap-1">
            <Bug className="size-3" />
            DEBUG
          </Badge>
        );
      default:
        return <Badge variant="secondary">{level}</Badge>;
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="space-y-6 p-6">
      {/* 页面标题和统计 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <FileText className="size-8" />
              日志中心
            </h1>
            <p className="text-muted-foreground mt-1">
              查看和管理系统运行日志
            </p>
          </div>
        </div>

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-5 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="text-sm text-muted-foreground">总日志数</div>
                <div className="text-2xl font-bold">{stats.total_lines.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-sm text-muted-foreground flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  错误
                </div>
                <div className="text-2xl font-bold text-red-500">{stats.error_count}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-sm text-muted-foreground flex items-center gap-1">
                  <AlertTriangle className="size-3" />
                  警告
                </div>
                <div className="text-2xl font-bold text-yellow-500">{stats.warning_count}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-sm text-muted-foreground flex items-center gap-1">
                  <Info className="size-3" />
                  信息
                </div>
                <div className="text-2xl font-bold text-blue-500">{stats.info_count}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="text-sm text-muted-foreground flex items-center gap-1">
                  <Bug className="size-3" />
                  调试
                </div>
                <div className="text-2xl font-bold text-gray-500">{stats.debug_count}</div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* 日志查看器 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
          <div>
            <CardTitle>日志记录</CardTitle>
            <CardDescription>
              实时显示最近 200 条日志，{autoRefresh ? '自动刷新中' : '已暂停自动刷新'}
              {stats && ` · 文件大小: ${formatFileSize(stats.file_size)}`}
            </CardDescription>
          </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                {autoRefresh ? (
                  <>
                    <Pause className="size-4 mr-2" />
                    暂停刷新
                  </>
                ) : (
                  <>
                    <Play className="size-4 mr-2" />
                    恢复刷新
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchLogs}
                disabled={loading}
              >
                <RefreshCw className={`size-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                刷新
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenLogFolder}
              >
                <FolderOpen className="size-4 mr-2" />
                打开目录
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadLogs}
              >
                <Download className="size-4 mr-2" />
                下载
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleClearClick}
              >
                <Trash2 className="size-4 mr-2" />
                清空
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 过滤和搜索 */}
          <div className="flex gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  placeholder="搜索日志内容..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant={levelFilter === 'ALL' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleLevelChange('ALL')}
              >
                全部
              </Button>
              <Button
                variant={levelFilter === 'ERROR' ? 'destructive' : 'outline'}
                size="sm"
                onClick={() => handleLevelChange('ERROR')}
              >
                <AlertCircle className="size-3 mr-1" />
                错误
              </Button>
              <Button
                variant={levelFilter === 'WARNING' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleLevelChange('WARNING')}
                className={levelFilter === 'WARNING' ? 'bg-yellow-500 hover:bg-yellow-600' : ''}
              >
                <AlertTriangle className="size-3 mr-1" />
                警告
              </Button>
              <Button
                variant={levelFilter === 'INFO' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleLevelChange('INFO')}
              >
                <Info className="size-3 mr-1" />
                信息
              </Button>
              <Button
                variant={levelFilter === 'DEBUG' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleLevelChange('DEBUG')}
              >
                <Bug className="size-3 mr-1" />
                调试
              </Button>
            </div>
          </div>

          <Separator />

          {/* 日志列表 */}
          <ScrollArea className="h-[500px] w-full rounded-md border" ref={scrollRef}>
            <div className="p-4 space-y-2 font-mono text-sm select-text">
              {logs.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="size-12 mx-auto mb-4 opacity-20" />
                  {levelFilter !== 'ALL' ? (
                    <>
                      <p className="font-medium">暂无 {levelFilter} 级别的日志</p>
                      <p className="text-xs mt-2">点击"全部"查看所有日志</p>
                    </>
                  ) : searchQuery ? (
                    <>
                      <p className="font-medium">未找到匹配的日志</p>
                      <p className="text-xs mt-2">尝试修改搜索关键词</p>
                    </>
                  ) : (
                  <p>暂无日志记录</p>
                  )}
                </div>
              ) : (
                logs.map((log, index) => (
                  <div
                    key={`${log.line_number}-${index}`}
                    className={`p-2 rounded hover:bg-muted/50 transition-colors cursor-text ${
                      log.level === 'ERROR' ? 'bg-red-50 dark:bg-red-950/20' :
                      log.level === 'WARNING' ? 'bg-yellow-50 dark:bg-yellow-950/20' :
                      ''
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-muted-foreground text-xs mt-0.5 w-32 flex-shrink-0 select-text">
                        {log.timestamp}
                      </span>
                      {getLevelBadge(log.level)}
                      <span className="text-muted-foreground text-xs mt-0.5 w-32 flex-shrink-0 truncate select-text">
                        {log.logger}
                      </span>
                      <span className="flex-1 break-words select-text">{log.message}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>

          {logs.length > 0 && (
            <div className="text-sm text-muted-foreground text-center">
              显示最近 {logs.length} 条日志
            </div>
          )}
        </CardContent>
      </Card>

      {/* 清空确认对话框 */}
      <AlertDialog open={showClearDialog} onOpenChange={setShowClearDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认清空日志</AlertDialogTitle>
            <AlertDialogDescription>
              确定要清空所有日志吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmClear} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              确定
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
