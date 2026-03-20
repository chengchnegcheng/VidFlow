import { useState, useEffect } from 'react';
import { invoke } from './TauriIntegration';
import { useTaskProgress, DownloadTask, SubtitleTask, BurnSubtitleTask } from '../contexts/TaskProgressContext';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Checkbox } from './ui/checkbox';
import { toast } from 'sonner';
import { TaskThumbnail } from './TaskThumbnail';
import {
  Search,
  Download,
  CheckCircle,
  XCircle,
  Clock,
  Ban,
  Trash2,
  Pause,
  Play,
  RotateCcw,
  FolderOpen,
  Calendar,
  FileVideo,
  FileText,
  Archive,
  Film
} from 'lucide-react';

export function TaskManager() {
  const { downloads: tasks, subtitleTasks, burnTasks, refreshAll, refreshDownloads, refreshSubtitles, refreshBurns, loading: tasksLoading } = useTaskProgress();
  const [filteredTasks, setFilteredTasks] = useState<DownloadTask[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<string>('date_desc');
  const [activeTab, setActiveTab] = useState<string>('downloads');

  useEffect(() => {
    // 初始刷新
    refreshAll();
  }, [refreshAll]);

  // 注意：轮询已由 TaskProgressContext 全局管理，这里不需要额外的轮询

  // 过滤和排序任务
  useEffect(() => {
    let filtered = [...tasks];

    // 搜索过滤
    if (searchQuery) {
      filtered = filtered.filter(task =>
        task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        task.url.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // 状态过滤
    if (statusFilter !== 'all') {
      filtered = filtered.filter(task => task.status === statusFilter);
    }

    // 平台过滤
    if (platformFilter !== 'all') {
      filtered = filtered.filter(task => task.platform === platformFilter);
    }

    // 排序
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'date_desc':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'date_asc':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case 'name_asc':
          return a.title.localeCompare(b.title);
        case 'name_desc':
          return b.title.localeCompare(a.title);
        default:
          return 0;
      }
    });

    setFilteredTasks(filtered);
  }, [tasks, searchQuery, statusFilter, platformFilter, sortBy]);

  // 删除任务（同时删除本机文件）
  const handleDeleteTask = async (taskId: string) => {
    try {
      const res: any = await invoke('delete_download_task', { task_id: taskId });
      const fileDeleted = res?.file_deleted;
      toast.success(fileDeleted ? '任务和文件已删除' : '任务已删除');
      refreshDownloads();
    } catch (error) {
      toast.error('删除失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  // 暂停任务
  const handlePauseTask = async (taskId: string) => {
    try {
      await invoke('pause_download_task', { task_id: taskId });
      toast.success('下载已暂停');
      refreshDownloads();
    } catch (error) {
      toast.error('暂停失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  // 恢复任务
  const handleResumeTask = async (taskId: string) => {
    try {
      await invoke('resume_download_task', { task_id: taskId });
      toast.success('下载已恢复');
      refreshDownloads();
    } catch (error) {
      toast.error('恢复失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  // 取消任务
  const handleCancelTask = async (taskId: string) => {
    try {
      await invoke('cancel_download_task', { task_id: taskId });
      toast.success('已发送取消请求');
      refreshDownloads();
    } catch (error) {
      toast.error('取消失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handleCancelBurnTask = async (taskId: string) => {
    try {
      await invoke('cancel_burn_subtitle_task', { task_id: taskId });
      toast.success('已发送取消请求');
      refreshBurns();
    } catch (error) {
      toast.error('取消失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handleDeleteSubtitleTask = async (taskId: string) => {
    try {
      await invoke('delete_subtitle_task', { task_id: taskId });
      toast.success('任务已删除');
      refreshSubtitles();
    } catch (error) {
      toast.error('删除失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handleCancelSubtitleTask = async (taskId: string) => {
    try {
      await invoke('cancel_subtitle_task', { task_id: taskId });
      toast.success('已发送取消请求');
      refreshSubtitles();
    } catch (error) {
      toast.error('取消失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handlePauseSubtitleTask = async (taskId: string) => {
    try {
      await invoke('pause_subtitle_task', { task_id: taskId });
      toast.success('任务已暂停');
      refreshSubtitles();
    } catch (error) {
      toast.error('暂停失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handleResumeSubtitleTask = async (taskId: string) => {
    try {
      await invoke('resume_subtitle_task', { task_id: taskId });
      toast.success('任务已恢复，将从头开始处理');
      refreshSubtitles();
    } catch (error) {
      toast.error('恢复失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handleDeleteBurnTask = async (taskId: string) => {
    try {
      await invoke('delete_burn_subtitle_task', { task_id: taskId });
      toast.success('任务已删除');
      refreshBurns();
    } catch (error) {
      toast.error('删除失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handlePauseBurnTask = async (taskId: string) => {
    try {
      await invoke('pause_burn_subtitle_task', { task_id: taskId });
      toast.success('任务已暂停');
      refreshBurns();
    } catch (error) {
      toast.error('暂停失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  const handleResumeBurnTask = async (taskId: string) => {
    try {
      await invoke('resume_burn_subtitle_task', { task_id: taskId });
      toast.success('任务已恢复，将从头开始处理');
      refreshBurns();
    } catch (error) {
      toast.error('恢复失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  // 重试任务
  const handleRetryTask = async (task: DownloadTask) => {
    try {
      await invoke('start_download', {
        url: task.url,
        quality: task.quality,
        format_id: task.format_id,
        output_path: task.output_path
      });
      toast.success('任务已重新开始');
      // 删除失败的任务
      await invoke('delete_download_task', { task_id: task.task_id });
      refreshDownloads();
    } catch (error) {
      toast.error('重试失败', {
        description: error instanceof Error ? error.message : '操作失败'
      });
    }
  };

  // 批量删除
  const handleBatchDelete = async () => {
    if (selectedTasks.size === 0) {
      toast.error('请先选择任务');
      return;
    }

    try {
      for (const taskId of selectedTasks) {
        await invoke('delete_download_task', { task_id: taskId });
      }
      toast.success(`已删除 ${selectedTasks.size} 个任务`);
      setSelectedTasks(new Set());
      refreshDownloads();
    } catch (error) {
      toast.error('批量删除失败');
    }
  };

  // 全选/取消全选
  const handleToggleAll = () => {
    if (selectedTasks.size === filteredTasks.length) {
      setSelectedTasks(new Set());
    } else {
      setSelectedTasks(new Set(filteredTasks.map(t => t.task_id)));
    }
  };

  // 打开文件夹
  const handleOpenFolder = async (task: any) => {
    const path = task?.file_path || task?.filename;
    
    if (!path) {
      console.log('Task data:', task); // 调试信息
      toast.error('文件路径不存在', {
        description: `文件名: ${task?.filename || '未知'}\n输出路径: ${task?.output_path || '未知'}`
      });
      return;
    }
    
    try {
      // 检查是否在 Electron 环境
      if (window.electron && window.electron.isElectron) {
        // 检查文件是否存在
        const exists = await window.electron.fileExists(path);
        if (!exists) {
          toast.error('文件不存在', {
            description: `路径: ${path}`
          });
          return;
        }
        await window.electron.showItemInFolder(path);
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

  // 获取状态统计
  const getStatusStats = () => {
    return {
      all: tasks.length,
      completed: tasks.filter(t => t.status === 'completed').length,
      downloading: tasks.filter(t => t.status === 'downloading').length,
      paused: tasks.filter(t => t.status === 'paused').length,
      failed: tasks.filter(t => t.status === 'failed').length,
      pending: tasks.filter(t => t.status === 'pending').length
    };
  };

  const stats = getStatusStats();

  // 获取状态样式
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-500"><CheckCircle className="size-3 mr-1" />已完成</Badge>;
      case 'downloading':
        return <Badge className="bg-blue-500"><Download className="size-3 mr-1" />下载中</Badge>;
      case 'failed':
        return <Badge variant="destructive"><XCircle className="size-3 mr-1" />失败</Badge>;
      case 'pending':
        return <Badge variant="secondary"><Clock className="size-3 mr-1" />等待中</Badge>;
      case 'paused':
        return <Badge variant="outline"><Pause className="size-3 mr-1" />已暂停</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getSubtitleStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-500"><CheckCircle className="size-3 mr-1" />已完成</Badge>;
      case 'processing':
      case 'generating':
      case 'translating':
        return <Badge className="bg-blue-500"><Clock className="size-3 mr-1" />处理中</Badge>;
      case 'paused':
        return <Badge className="bg-amber-500"><Pause className="size-3 mr-1" />已暂停</Badge>;
      case 'cancelled':
        return <Badge variant="secondary"><Ban className="size-3 mr-1" />已取消</Badge>;
      case 'failed':
        return <Badge variant="destructive"><XCircle className="size-3 mr-1" />失败</Badge>;
      case 'pending':
        return <Badge variant="secondary"><Clock className="size-3 mr-1" />等待中</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getBurnStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-500"><CheckCircle className="size-3 mr-1" />已完成</Badge>;
      case 'burning':
        return <Badge className="bg-blue-500"><Film className="size-3 mr-1" />烧录中</Badge>;
      case 'paused':
        return <Badge className="bg-amber-500"><Pause className="size-3 mr-1" />已暂停</Badge>;
      case 'cancelled':
        return <Badge variant="secondary"><Ban className="size-3 mr-1" />已取消</Badge>;
      case 'failed':
        return <Badge variant="destructive"><XCircle className="size-3 mr-1" />失败</Badge>;
      case 'pending':
        return <Badge variant="secondary"><Clock className="size-3 mr-1" />等待中</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  // 格式化日期
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatBytes = (bytes?: number) => {
    if (bytes === undefined || bytes === null || isNaN(bytes)) return '';
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, i);
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
    };

  const formatSpeed = (speed?: number | string) => {
    if (speed === undefined || speed === null || speed === '') return '';
    const num = typeof speed === 'string' ? parseFloat(speed) : speed;
    if (isNaN(num)) return `${speed}`;
    return `${formatBytes(num)}/s`;
  };

  const formatEta = (eta?: number | string) => {
    if (eta === undefined || eta === null || eta === '') return '';
    const num = typeof eta === 'string' ? parseFloat(eta) : eta;
    if (isNaN(num) || num < 0) return '';
    const minutes = Math.floor(num / 60);
    const seconds = Math.floor(num % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">任务中心</h2>
          <p className="text-muted-foreground mt-1">查看和管理所有任务</p>
        </div>
        <Button variant="outline" onClick={refreshAll}>
          <RotateCcw className="size-4 mr-2" />
          刷新
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="downloads" className="flex items-center gap-2">
            <Download className="size-4" />
            下载任务 ({tasks.length})
          </TabsTrigger>
          <TabsTrigger value="subtitles" className="flex items-center gap-2">
            <FileText className="size-4" />
            字幕生成 ({subtitleTasks.length})
          </TabsTrigger>
          <TabsTrigger value="burns" className="flex items-center gap-2">
            <Film className="size-4" />
            字幕烧录 ({burnTasks.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="downloads" className="space-y-6">

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setStatusFilter('all')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">全部任务</p>
                <p className="text-2xl font-bold">{stats.all}</p>
              </div>
              <Archive className="size-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setStatusFilter('completed')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">已完成</p>
                <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
              </div>
              <CheckCircle className="size-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setStatusFilter('downloading')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">下载中</p>
                <p className="text-2xl font-bold text-blue-600">{stats.downloading}</p>
              </div>
              <Download className="size-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setStatusFilter('pending')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">等待中</p>
                <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
              </div>
              <Clock className="size-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setStatusFilter('failed')}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">失败</p>
                <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
              </div>
              <XCircle className="size-8 text-red-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  placeholder="搜索任务标题或链接..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Status Filter */}
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="状态筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="downloading">下载中</SelectItem>
                <SelectItem value="pending">等待中</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
              </SelectContent>
            </Select>

            {/* Platform Filter */}
            <Select value={platformFilter} onValueChange={setPlatformFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="平台筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部平台</SelectItem>
                <SelectItem value="YouTube">YouTube</SelectItem>
                <SelectItem value="Bilibili">Bilibili</SelectItem>
                <SelectItem value="抖音">抖音</SelectItem>
                <SelectItem value="其他">其他</SelectItem>
              </SelectContent>
            </Select>

            {/* Sort */}
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="排序方式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date_desc">最新优先</SelectItem>
                <SelectItem value="date_asc">最旧优先</SelectItem>
                <SelectItem value="name_asc">标题 A-Z</SelectItem>
                <SelectItem value="name_desc">标题 Z-A</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Batch Actions */}
      {selectedTasks.size > 0 && (
        <Card className="border-primary">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={selectedTasks.size === filteredTasks.length}
                  onCheckedChange={handleToggleAll}
                />
                <span className="text-sm font-medium">
                  已选择 {selectedTasks.size} 项
                </span>
              </div>
              <div className="flex gap-2">
                <Button variant="destructive" size="sm" onClick={handleBatchDelete}>
                  <Trash2 className="size-4 mr-2" />
                  批量删除
                </Button>
                <Button variant="outline" size="sm" onClick={() => setSelectedTasks(new Set())}>
                  取消选择
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tasks List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileVideo className="size-5" />
              <span>任务列表</span>
              <Badge variant="secondary">{filteredTasks.length} 个任务</Badge>
            </div>
            <Button variant="ghost" size="sm" onClick={handleToggleAll}>
              {selectedTasks.size === filteredTasks.length ? '取消全选' : '全选'}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tasksLoading ? (
            <div className="text-center py-12 text-muted-foreground">
              <Download className="size-12 mx-auto mb-4 animate-bounce" />
              <p>加载任务列表...</p>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <FileVideo className="size-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">暂无任务</p>
              <p className="text-sm">尝试调整筛选条件或创建新的下载任务</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredTasks.map((task) => (
                <Card key={task.task_id} className={selectedTasks.has(task.task_id) ? 'border-primary bg-primary/5' : ''}>
                  <CardContent className="p-4">
                    <div className="flex gap-4">
                      {/* Checkbox */}
                      <div className="flex items-start pt-1">
                        <Checkbox
                          checked={selectedTasks.has(task.task_id)}
                          onCheckedChange={(checked) => {
                            const newSelected = new Set(selectedTasks);
                            if (checked) {
                              newSelected.add(task.task_id);
                            } else {
                              newSelected.delete(task.task_id);
                            }
                            setSelectedTasks(newSelected);
                          }}
                        />
                      </div>

                      {/* Thumbnail */}
                      <TaskThumbnail
                        filePath={(task as any).file_path}
                        thumbnail={task.thumbnail}
                        title={task.title}
                      />

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-4 mb-2">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-medium truncate mb-1">{task.title}</h3>
                            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                              <Badge variant="outline" className="text-xs">
                                {task.platform || 'Unknown'}
                              </Badge>
                              <span>{task.quality || 'best'}</span>
                              {task.format_id && (
                                <>
                                  <span>•</span>
                                  <span>{task.format_id}</span>
                                </>
                              )}
                              {task.file_size && (
                                <>
                                  <span>•</span>
                                  <span>{task.file_size}</span>
                                </>
                              )}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            {getStatusBadge(task.status)}
                            <div className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Calendar className="size-3" />
                              {formatDate(task.created_at)}
                            </div>
                          </div>
                        </div>

                        {/* Progress */}
                        {(task.status === 'downloading' || task.status === 'pending') && (
                          <div className="mb-2">
                            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                              <span>下载进度</span>
                              <span>{task.progress?.toFixed(1) || 0}%</span>
                            </div>
                            <Progress value={task.progress || 0} className="h-2" />
                            <div className="mt-1 text-[11px] text-muted-foreground flex flex-wrap gap-3">
                              {(task.downloaded !== undefined || task.total !== undefined) && (
                                <span>
                                  {formatBytes(task.downloaded)} / {formatBytes(task.total)}
                                </span>
                              )}
                              {formatSpeed(task.speed) && (
                                <span>速度 {formatSpeed(task.speed)}</span>
                              )}
                              {formatEta(task.eta) && (
                                <span>剩余 {formatEta(task.eta)}</span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Paused Progress */}
                        {task.status === 'paused' && (
                          <div className="mb-2">
                            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                              <span>下载进度（已暂停）</span>
                              <span>{task.progress?.toFixed(1) || 0}%</span>
                            </div>
                            <Progress value={task.progress || 0} className="h-2 [&>div]:bg-amber-500" />
                            <div className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">
                              {(task.downloaded !== undefined || task.total !== undefined) && (
                                <span>
                                  已下载 {formatBytes(task.downloaded)} / {formatBytes(task.total)}
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Error Message */}
                        {task.status === 'failed' && (task.error_message || task.error) && (
                          <div className="mb-2 p-3 bg-red-50 border border-red-200 rounded-md">
                            <div className="flex items-start gap-2">
                              <XCircle className="size-4 text-red-600 flex-shrink-0 mt-0.5" />
                              <div className="flex-1">
                                <p className="text-sm font-medium text-red-900 mb-1">下载失败</p>
                                <p className="text-xs text-red-700">{task.error_message || task.error}</p>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex gap-2">
                          {task.status === 'downloading' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handlePauseTask(task.task_id)}
                            >
                              <Pause className="size-4 mr-2" />
                              暂停
                            </Button>
                          )}
                          {task.status === 'paused' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleResumeTask(task.task_id)}
                            >
                              <Play className="size-4 mr-2" />
                              继续
                            </Button>
                          )}
                          {(task.status === 'downloading' || task.status === 'pending' || task.status === 'paused') && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCancelTask(task.task_id)}
                            >
                              <Ban className="size-4 mr-2" />
                              取消
                            </Button>
                          )}
                          {task.status === 'completed' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleOpenFolder(task)}
                            >
                              <FolderOpen className="size-4 mr-2" />
                              打开文件夹
                            </Button>
                          )}
                          {task.status === 'failed' && (
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => handleRetryTask(task)}
                            >
                              <RotateCcw className="size-4 mr-2" />
                              重试
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDeleteTask(task.task_id)}
                          >
                            <Trash2 className="size-4 mr-2" />
                            删除
                          </Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

        </TabsContent>

        <TabsContent value="subtitles" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5" />
                <span>字幕生成任务</span>
                <Badge variant="secondary">{subtitleTasks.length} 个任务</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tasksLoading ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Download className="size-12 mx-auto mb-4 animate-bounce" />
                  <p>加载任务列表...</p>
                </div>
              ) : subtitleTasks.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">暂无字幕生成任务</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {[...subtitleTasks]
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                    .map((task: SubtitleTask) => (
                      <Card key={task.id}>
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-4 mb-2">
                                <div className="flex-1 min-w-0">
                                  <h3 className="font-medium truncate mb-1">{task.video_title}</h3>
                                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                                    <Badge variant="outline" className="text-xs">{task.model}</Badge>
                                    <span>{task.source_language}</span>
                                    {task.target_languages?.length > 0 && (
                                      <>
                                        <span>•</span>
                                        <span>{task.target_languages.join(', ')}</span>
                                      </>
                                    )}
                                  </div>
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                  {getSubtitleStatusBadge(task.status)}
                                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <Calendar className="size-3" />
                                    {formatDate(task.created_at)}
                                  </div>
                                </div>
                              </div>

                              {task.status !== 'completed' && task.status !== 'failed' && task.status !== 'cancelled' && (
                                <div className="mb-2">
                                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                    <span>{task.message || '处理中...'}</span>
                                    <span>{task.progress?.toFixed(1) || 0}%</span>
                                  </div>
                                  <Progress value={task.progress || 0} className="h-2" />
                                </div>
                              )}

                              {task.status === 'failed' && task.error && (
                                <div className="mb-2 p-3 bg-red-50 border border-red-200 rounded-md">
                                  <div className="flex items-start gap-2">
                                    <XCircle className="size-4 text-red-600 flex-shrink-0 mt-0.5" />
                                    <div className="flex-1">
                                      <p className="text-sm font-medium text-red-900 mb-1">任务失败</p>
                                      <p className="text-xs text-red-700">{task.error}</p>
                                      {task.error_detail?.hint && (
                                        <p className="text-xs text-red-700 mt-2">{task.error_detail.hint}</p>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )}

                              {task.status === 'completed' && task.output_files?.length > 0 && (
                                <div className="mt-2">
                                  <div className="flex flex-wrap gap-2">
                                    {task.output_files.map((file, index) => (
                                      <Badge key={index} variant="outline" className="text-xs">
                                        {file.split(/[/\\]/).pop() || file}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>

                            <div className="flex flex-col gap-2">
                              {(task.status === 'pending' || task.status === 'processing' || task.status === 'generating' || task.status === 'translating') && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handlePauseSubtitleTask(task.id)}
                                    title="暂停任务"
                                  >
                                    <Pause className="size-4" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handleCancelSubtitleTask(task.id)}
                                    title="取消任务"
                                  >
                                    <Ban className="size-4" />
                                  </Button>
                                </>
                              )}
                              {task.status === 'paused' && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleResumeSubtitleTask(task.id)}
                                  title="继续任务（从头开始）"
                                  className="text-amber-600 hover:text-amber-700"
                                >
                                  <Play className="size-4" />
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDeleteSubtitleTask(task.id)}
                                title="删除任务"
                              >
                                <Trash2 className="size-4" />
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="burns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Film className="size-5" />
                <span>字幕烧录任务</span>
                <Badge variant="secondary">{burnTasks.length} 个任务</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tasksLoading ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Download className="size-12 mx-auto mb-4 animate-bounce" />
                  <p>加载任务列表...</p>
                </div>
              ) : burnTasks.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Film className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">暂无字幕烧录任务</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {[...burnTasks]
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                    .map((task: BurnSubtitleTask) => (
                      <Card key={task.id}>
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-4 mb-2">
                                <div className="flex-1 min-w-0">
                                  <h3 className="font-medium truncate mb-1">{task.video_title}</h3>
                                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                                    <Badge variant="outline" className="text-xs">
                                      {task.output_path?.split(/[/\\]/).pop() || ''}
                                    </Badge>
                                  </div>
                                </div>
                                <div className="flex flex-col items-end gap-2">
                                  {getBurnStatusBadge(task.status)}
                                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <Calendar className="size-3" />
                                    {formatDate(task.created_at)}
                                  </div>
                                </div>
                              </div>

                              {task.status !== 'completed' && task.status !== 'failed' && task.status !== 'cancelled' && (
                                <div className="mb-2">
                                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                    <span>烧录进度</span>
                                    <span>{task.progress?.toFixed(1) || 0}%</span>
                                  </div>
                                  <Progress value={task.progress || 0} className="h-2" />
                                </div>
                              )}

                              {task.status === 'failed' && task.error && (
                                <div className="mb-2 p-3 bg-red-50 border border-red-200 rounded-md">
                                  <div className="flex items-start gap-2">
                                    <XCircle className="size-4 text-red-600 flex-shrink-0 mt-0.5" />
                                    <div className="flex-1">
                                      <p className="text-sm font-medium text-red-900 mb-1">任务失败</p>
                                      <p className="text-xs text-red-700">{task.error}</p>
                                      {task.error_detail?.hint && (
                                        <p className="text-xs text-red-700 mt-2">{task.error_detail.hint}</p>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )}

                              {task.status === 'completed' && task.output_path && (
                                <div className="flex gap-2">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handleOpenFolder({ file_path: task.output_path, filename: task.output_path })}
                                  >
                                    <FolderOpen className="size-4 mr-2" />
                                    打开文件夹
                                  </Button>
                                </div>
                              )}
                            </div>

                            <div className="flex flex-col gap-2">
                              {(task.status === 'pending' || task.status === 'burning') && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handlePauseBurnTask(task.id)}
                                    title="暂停任务"
                                  >
                                    <Pause className="size-4" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handleCancelBurnTask(task.id)}
                                    title="取消任务"
                                  >
                                    <Ban className="size-4" />
                                  </Button>
                                </>
                              )}
                              {task.status === 'paused' && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleResumeBurnTask(task.id)}
                                  title="继续任务（从头开始）"
                                  className="text-amber-600 hover:text-amber-700"
                                >
                                  <Play className="size-4" />
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDeleteBurnTask(task.id)}
                                title="删除任务"
                              >
                                <Trash2 className="size-4" />
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
