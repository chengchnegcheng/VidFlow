import { useState, useEffect } from 'react';
import { invoke } from './TauriIntegration';
import { useTaskProgress, BurnSubtitleTask } from '../contexts/TaskProgressContext';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import {
  Film,
  FileVideo,
  FileText,
  Sparkles,
  FolderOpen,
  CheckCircle,
  Clock,
  AlertCircle,
  Trash2,
  Play,
  RefreshCw,
  Ban
} from 'lucide-react';

export default function BurnSubtitle() {
  const [videoPath, setVideoPath] = useState('');
  const [subtitlePath, setSubtitlePath] = useState('');
  const [outputPath, setOutputPath] = useState('');
  const [isBurning, setIsBurning] = useState(false);
  const { burnTasks: tasks, refreshBurns } = useTaskProgress();

  useEffect(() => {
    refreshBurns();
  }, [refreshBurns]);

  // 选择视频文件
  const handleSelectVideo = async () => {
    try {
      const result = await invoke('select_file', {
        filters: [
          { name: '视频文件', extensions: ['mp4', 'mkv', 'avi', 'mov', 'flv', 'wmv', 'webm'] }
        ]
      });
      if (result) {
        setVideoPath(result);
        // 自动设置输出路径
        if (!outputPath) {
          const pathParts = result.split(/[\\/]/);
          const fileName = pathParts.pop() || '';
          const fileNameWithoutExt = fileName.replace(/\.[^/.]+$/, '');
          const dir = pathParts.join('\\');
          setOutputPath(`${dir}\\${fileNameWithoutExt}_subtitled.mp4`);
        }
      }
    } catch (error) {
      console.error('选择视频失败:', error);
    }
  };

  const handleCancelTask = async (taskId: string) => {
    try {
      await invoke('cancel_burn_subtitle_task', { task_id: taskId });
      toast.success('已发送取消请求');
      await refreshBurns();
    } catch (error) {
      toast.error('取消失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 选择字幕文件
  const handleSelectSubtitle = async () => {
    try {
      const result = await invoke('select_file', {
        filters: [
          { name: '字幕文件', extensions: ['srt', 'vtt', 'ass', 'ssa'] }
        ]
      });
      if (result) {
        setSubtitlePath(result);
      }
    } catch (error) {
      console.error('选择字幕失败:', error);
    }
  };

  // 选择输出路径
  const handleSelectOutput = async () => {
    try {
      const result = await invoke('save_file', {
        defaultPath: outputPath,
        filters: [
          { name: '视频文件', extensions: ['mp4'] }
        ]
      });
      if (result) {
        setOutputPath(result);
      }
    } catch (error) {
      console.error('选择输出路径失败:', error);
    }
  };

  // 开始烧录
  const handleBurn = async () => {
    if (!videoPath || !subtitlePath) {
      toast.error('请选择视频和字幕文件');
      return;
    }

    setIsBurning(true);

    try {
      await invoke('create_burn_subtitle_task', {
        video_path: videoPath,
        subtitle_path: subtitlePath,
        output_path: outputPath || undefined,
        video_title: videoPath.split(/[\\/]/).pop() || ''
      });

      toast.success('任务已创建', {
        description: '字幕烧录任务已加入队列，正在处理中...'
      });

      // 重置表单
      setVideoPath('');
      setSubtitlePath('');
      setOutputPath('');

      // 刷新任务列表
      await refreshBurns();
    } catch (error) {
      toast.error('创建任务失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    } finally {
      setIsBurning(false);
    }
  };

  // 删除任务
  const handleDeleteTask = async (taskId: string) => {
    try {
      await invoke('delete_burn_subtitle_task', { task_id: taskId });
      toast.success('任务已删除');
      await refreshBurns();
    } catch (error) {
      toast.error('删除失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 打开输出文件夹
  const handleOpenOutputFolder = async (outputPath: string) => {
    try {
      const pathParts = outputPath.split(/[\\/]/);
      pathParts.pop();
      const folder = pathParts.join('\\');
      await invoke('open_folder', { path: folder });
    } catch (error) {
      toast.error('打开文件夹失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 重试失败的烧录任务
  const handleRetryBurnTask = async (task: BurnSubtitleTask) => {
    try {
      await invoke('create_burn_subtitle_task', {
        video_path: task.video_path,
        subtitle_path: task.subtitle_path,
        output_path: task.output_path,
        video_title: task.video_title
      });

      toast.success('任务已重新创建', {
        description: '字幕烧录任务已加入队列，正在处理中...'
      });

      // 刷新任务列表
      await refreshBurns();
    } catch (error) {
      toast.error('重试失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 获取状态徽章
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-500"><CheckCircle className="size-3 mr-1" />已完成</Badge>;
      case 'burning':
        return <Badge className="bg-blue-500"><Film className="size-3 mr-1" />烧录中</Badge>;
      case 'cancelled':
        return <Badge variant="secondary"><Ban className="size-3 mr-1" />已取消</Badge>;
      case 'failed':
        return <Badge variant="destructive"><AlertCircle className="size-3 mr-1" />失败</Badge>;
      case 'pending':
        return <Badge variant="secondary"><Clock className="size-3 mr-1" />等待中</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  // 获取文件名
  const getFileName = (path: string) => {
    if (!path) return '';
    const parts = path.split(/[\\/]/);
    return parts[parts.length - 1];
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">烧录字幕</h2>
          <p className="text-muted-foreground mt-1">将字幕永久嵌入到视频中</p>
        </div>
        <Button variant="outline" onClick={refreshBurns}>
          <RefreshCw className="size-4 mr-2" />
          刷新
        </Button>
      </div>

      <Tabs defaultValue="burn" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="burn">烧录字幕</TabsTrigger>
          <TabsTrigger value="tasks">任务列表</TabsTrigger>
        </TabsList>

        {/* 烧录字幕 */}
        <TabsContent value="burn" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-5 text-purple-500" />
                字幕烧录配置
              </CardTitle>
              <CardDescription>
                选择视频文件和字幕文件，系统将把字幕永久嵌入到视频画面中
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
          {/* 视频文件选择 */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <FileVideo className="size-4" />
              视频文件
            </Label>
            <div className="flex gap-2">
              <Input
                value={getFileName(videoPath)}
                placeholder="点击右侧按钮选择视频文件..."
                readOnly
                className="flex-1"
              />
              <Button onClick={handleSelectVideo} variant="outline">
                <FolderOpen className="size-4 mr-2" />
                选择视频
              </Button>
            </div>
            {videoPath && (
              <p className="text-xs text-muted-foreground">{videoPath}</p>
            )}
          </div>

          {/* 字幕文件选择 */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <FileText className="size-4" />
              字幕文件
            </Label>
            <div className="flex gap-2">
              <Input
                value={getFileName(subtitlePath)}
                placeholder="点击右侧按钮选择字幕文件..."
                readOnly
                className="flex-1"
              />
              <Button onClick={handleSelectSubtitle} variant="outline">
                <FolderOpen className="size-4 mr-2" />
                选择字幕
              </Button>
            </div>
            {subtitlePath && (
              <p className="text-xs text-muted-foreground">{subtitlePath}</p>
            )}
          </div>

          {/* 输出路径 */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Film className="size-4" />
              输出文件
            </Label>
            <div className="flex gap-2">
              <Input
                value={getFileName(outputPath)}
                placeholder="自动生成输出路径..."
                readOnly
                className="flex-1"
              />
              <Button onClick={handleSelectOutput} variant="outline">
                <FolderOpen className="size-4 mr-2" />
                自定义路径
              </Button>
            </div>
            {outputPath && (
              <p className="text-xs text-muted-foreground">{outputPath}</p>
            )}
          </div>

          {/* 提示信息 */}
          <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">
              💡 使用说明
            </h4>
            <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
              <li>• 支持格式：SRT, VTT, ASS, SSA 字幕文件</li>
              <li>• 烧录后字幕将永久显示在视频画面上</li>
              <li>• 处理时间取决于视频长度（约 1-5 分钟/10 分钟视频）</li>
              <li>• 原视频不会被修改，会生成新的视频文件</li>
            </ul>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-3">
            <Button
              onClick={handleBurn}
              disabled={!videoPath || !subtitlePath || isBurning}
              className="w-full"
              size="lg"
            >
              <Film className="size-4 mr-2" />
              {isBurning ? '烧录中...' : '开始烧录'}
            </Button>
          </div>
        </CardContent>
      </Card>
        </TabsContent>

        {/* 任务列表 */}
        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5" />
                烧录任务
                <Badge variant="secondary">{tasks.length} 个任务</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tasks.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Film className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">暂无烧录任务</p>
                  <p className="text-sm">在"烧录字幕"标签中创建新任务</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {tasks.map((task) => (
                    <Card key={task.id}>
                      <CardContent className="p-4">
                        <div className="flex gap-4">
                          <FileVideo className="size-10 text-primary flex-shrink-0 mt-1" />

                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-4 mb-2">
                              <div className="flex-1 min-w-0">
                                <h3 className="font-medium truncate mb-1">{task.video_title}</h3>
                                <p className="text-xs text-muted-foreground truncate">
                                  {task.subtitle_path.split(/[\\/]/).pop()}
                                </p>
                              </div>
                              {getStatusBadge(task.status)}
                            </div>

                            {task.status === 'burning' && (
                              <div className="mb-2">
                                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                  <span>
                                    {task.status === 'burning'
                                      ? `烧录进度${task.duration ? ` (${(task.current ?? 0).toFixed(1)}/${task.duration.toFixed(1)}s)` : ''}`
                                      : '烧录进度'}
                                  </span>
                                  <span>{task.progress?.toFixed ? task.progress.toFixed(1) : task.progress}%</span>
                                </div>
                                <Progress value={task.progress} className="h-2" />
                              </div>
                            )}

                            {task.status === 'failed' && task.error && (
                              <div className="mb-2">
                                <p className="text-sm text-red-600">{task.error}</p>
                                {task.error_detail?.hint && (
                                  <p className="text-xs text-red-600 mt-1">{task.error_detail.hint}</p>
                                )}
                              </div>
                            )}

                            {task.status === 'completed' && (
                              <div className="mb-2">
                                <p className="text-sm text-muted-foreground">
                                  输出文件: {task.output_path.split(/[\\/]/).pop()}
                                </p>
                              </div>
                            )}

                            <div className="flex gap-2 flex-wrap">
                              {task.status === 'completed' && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleOpenOutputFolder(task.output_path)}
                                >
                                  <FolderOpen className="size-4 mr-2" />
                                  打开文件夹
                                </Button>
                              )}
                              {(task.status === 'pending' || task.status === 'burning') && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleCancelTask(task.id)}
                                >
                                  <Ban className="size-4 mr-2" />
                                  取消
                                </Button>
                              )}
                              {task.status === 'failed' && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleRetryBurnTask(task)}
                                >
                                  <Play className="size-4 mr-2" />
                                  重试
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDeleteTask(task.id)}
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
      </Tabs>
    </div>
  );
}
