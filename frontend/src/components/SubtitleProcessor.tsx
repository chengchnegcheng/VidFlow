import { useState, useEffect } from 'react';
import { invoke } from './TauriIntegration';
import { useTaskProgress, SubtitleTask } from '../contexts/TaskProgressContext';
import { useInstallProgress } from '../contexts/InstallProgressContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Separator } from './ui/separator';
import { toast } from 'sonner';
import { AIToolsPrompt } from './AIToolsPrompt';
import { getApiBaseUrl } from './TauriIntegration';
import {
  FileVideo,
  FileText,
  Upload,
  Download,
  Languages,
  Wand2,
  CheckCircle,
  Clock,
  Ban,
  AlertCircle,
  Trash2,
  Play,
  RefreshCw,
  Settings,
  FolderOpen
} from 'lucide-react';

export function SubtitleProcessor() {
  const { subtitleTasks: tasks, refreshSubtitles } = useTaskProgress();
  const { installProgress } = useInstallProgress();
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [sourceLanguage, setSourceLanguage] = useState('auto');
  const [targetLanguages, setTargetLanguages] = useState<string[]>([]);
  const [model, setModel] = useState('base');
  const [loading, setLoading] = useState(false);
  const [showAIPrompt, setShowAIPrompt] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [aiInstalled, setAiInstalled] = useState(false);

  // 检查 AI 工具状态
  useEffect(() => {
    const checkAIStatus = async () => {
      try {
        const apiUrl = getApiBaseUrl();
        if (!apiUrl) return;
        const response = await fetch(`${apiUrl}/api/v1/system/tools/ai/status`);
        if (response.ok) {
          const data = await response.json();
          setAiInstalled(data.installed);
        }
      } catch (err) {
        console.error('Failed to check AI status:', err);
      }
    };
    checkAIStatus();
  }, []);

  // 监听 AI 工具安装完成
  useEffect(() => {
    const aiProgress = installProgress['ai-tools'];
    if (aiProgress?.progress === 100 && installing) {
      setInstalling(false);
      setAiInstalled(true);
      toast.success('AI 工具安装完成');
    }
  }, [installProgress, installing]);

  // 语言选项
  const languages = [
    { code: 'auto', name: '自动检测' },
    { code: 'zh', name: '中文' },
    { code: 'en', name: 'English' },
    { code: 'ja', name: '日本語' },
    { code: 'ko', name: '한국어' },
    { code: 'es', name: 'Español' },
    { code: 'fr', name: 'Français' },
    { code: 'de', name: 'Deutsch' },
    { code: 'ru', name: 'Русский' }
  ];

  // Whisper 模型选项
  const models = [
    { value: 'tiny', name: 'Tiny (最快，精度较低)' },
    { value: 'base', name: 'Base (推荐)' },
    { value: 'small', name: 'Small (较慢，精度较高)' },
    { value: 'medium', name: 'Medium (慢，高精度)' },
    { value: 'large', name: 'Large (最慢，最高精度)' }
  ];

  useEffect(() => {
    refreshSubtitles();
  }, [refreshSubtitles]);

  // 选择视频文件
  const handleSelectFile = async () => {
    try {
      const result = await invoke('select_file', {
        filters: [
          { name: '视频文件', extensions: ['mp4', 'mkv', 'avi', 'mov', 'flv', 'wmv', 'webm'] }
        ]
      });
      if (result) {
        setSelectedFile(result);
        toast.success('文件已选择', {
          description: result.split(/[/\\]/).pop()
        });
      }
    } catch (error) {
      toast.error('选择文件失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 开始生成字幕
  const handleGenerateSubtitle = async () => {
    if (!selectedFile) {
      toast.error('请先选择视频文件');
      return;
    }

    // 检查 AI 工具是否安装
    if (!aiInstalled) {
      setShowAIPrompt(true);
      return;
    }

    setLoading(true);
    try {
      await invoke('generate_subtitle', {
        video_path: selectedFile,
        video_title: selectedFile.split('\\').pop() || selectedFile.split('/').pop(),
        source_language: sourceLanguage,
        target_languages: targetLanguages,
        model: model,
        formats: ['srt', 'vtt']
      });

      toast.success('任务已创建', {
        description: '字幕生成任务已加入队列，正在处理中...'
      });

      // 重置表单
      setSelectedFile('');

      // 刷新任务列表
      await refreshSubtitles();
    } catch (error) {
      toast.error('创建任务失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    } finally {
      setLoading(false);
    }
  };

  // 安装 AI 工具
  const handleInstallAITools = async () => {
    setInstalling(true);
    try {
      const apiUrl = getApiBaseUrl();
      const platform = window.electron?.platform;

      // 从 localStorage 读取用户选择的版本
      let version = 'cpu';
      try {
        const saved = localStorage.getItem('vidflow_ai_version');
        if (saved === 'cuda' || saved === 'cpu') {
          version = saved;
        }
      } catch {
        // 忽略错误，使用默认 cpu
      }

      if (platform === 'darwin') {
        version = 'cpu';
        try {
          localStorage.setItem('vidflow_ai_version', 'cpu');
        } catch {
          // ignore
        }
      }

      const response = await fetch(`${apiUrl}/api/v1/system/tools/ai/install?version=${version}`, {
        method: 'POST'
      });

      if (response.ok) {
        toast.success('AI 工具安装已开始', {
          description: '请稍候，安装需要 3-5 分钟...'
        });
        setShowAIPrompt(false);

        // 注意：AI 工具安装进度由 InstallProgressContext 全局管理
        // 安装完成后会自动刷新状态，无需本地轮询
      } else {
        const error = await response.json();
        toast.error('安装失败', {
          description: error.detail || '未知错误'
        });
      }
    } catch (error) {
      toast.error('安装失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    } finally {
      setInstalling(false);
    }
  };

  // 删除任务
  const handleDeleteTask = async (taskId: string) => {
    try {
      await invoke('delete_subtitle_task', { task_id: taskId });
      toast.success('任务已删除');
      await refreshSubtitles();
    } catch (error) {
      toast.error('删除失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  const handleCancelTask = async (taskId: string) => {
    try {
      await invoke('cancel_subtitle_task', { task_id: taskId });
      toast.success('已发送取消请求');
      await refreshSubtitles();
    } catch (error) {
      toast.error('取消失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 打开字幕文件夹
  const handleOpenSubtitleFolder = async (videoPath: string) => {
    try {
      // 构造字幕文件夹路径
      const pathParts = videoPath.split(/[\\/]/);
      pathParts.pop(); // 移除文件名
      const subtitleFolder = pathParts.join('\\') + '\\subtitles';
      
      await invoke('open_folder', { path: subtitleFolder });
    } catch (error) {
      toast.error('打开文件夹失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 下载字幕（打开字幕文件夹）
  const handleDownloadSubtitle = async (videoPath: string) => {
    try {
      // 构造字幕文件夹路径
      const pathParts = videoPath.split(/[\\/]/);
      pathParts.pop(); // 移除文件名
      const subtitleFolder = pathParts.join('\\') + '\\subtitles';
      
      await invoke('open_folder', { path: subtitleFolder });
      toast.success('已打开字幕文件夹');
    } catch (error) {
      toast.error('打开文件夹失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 重试失败的任务
  const handleRetryTask = async (task: SubtitleTask) => {
    try {
      await invoke('generate_subtitle', {
        video_path: task.video_path,
        video_title: task.video_title,
        source_language: task.source_language,
        target_languages: task.target_languages,
        model: task.model,
        formats: ['srt', 'vtt']
      });

      toast.success('任务已重新创建', {
        description: '字幕生成任务已加入队列，正在处理中...'
      });

      // 刷新任务列表
      await refreshSubtitles();
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
      case 'processing':
        return <Badge className="bg-blue-500"><RefreshCw className="size-3 mr-1 animate-spin" />处理中</Badge>;
      case 'generating':
        return <Badge className="bg-blue-500"><Wand2 className="size-3 mr-1" />生成中</Badge>;
      case 'translating':
        return <Badge className="bg-purple-500"><Languages className="size-3 mr-1" />翻译中</Badge>;
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

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">字幕处理</h2>
          <p className="text-muted-foreground mt-1">使用 AI 自动生成和翻译视频字幕</p>
        </div>
        <Button variant="outline" onClick={refreshSubtitles}>
          <RefreshCw className="size-4 mr-2" />
          刷新
        </Button>
      </div>

      <Tabs defaultValue="generate" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="generate">生成字幕</TabsTrigger>
          <TabsTrigger value="tasks">任务列表</TabsTrigger>
        </TabsList>

        {/* 生成字幕 */}
        <TabsContent value="generate" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileVideo className="size-5" />
                选择视频文件
              </CardTitle>
              <CardDescription>选择需要生成字幕的视频文件</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="videoFile">视频文件</Label>
                <div className="flex gap-2">
                  <Input
                    id="videoFile"
                    value={selectedFile}
                    placeholder="点击选择视频文件..."
                    readOnly
                    className="flex-1"
                  />
                  <Button variant="outline" onClick={handleSelectFile}>
                    <Upload className="size-4 mr-2" />
                    选择文件
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  支持 MP4, MKV, AVI, MOV 等常见视频格式
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="size-5" />
                字幕设置
              </CardTitle>
              <CardDescription>配置字幕生成和翻译选项</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="sourceLanguage">源语言</Label>
                  <Select value={sourceLanguage} onValueChange={setSourceLanguage}>
                    <SelectTrigger id="sourceLanguage">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {languages.map(lang => (
                        <SelectItem key={lang.code} value={lang.code}>
                          {lang.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    视频的原始语言，选择"自动检测"让 AI 识别
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="model">AI 模型</Label>
                  <Select value={model} onValueChange={setModel}>
                    <SelectTrigger id="model">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map(m => (
                        <SelectItem key={m.value} value={m.value}>
                          {m.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    模型越大，识别越准确，但速度越慢
                  </p>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  目标语言（翻译）
                  <Badge variant="secondary" className="text-xs bg-green-500/10 text-green-600 border-green-200">无需代理</Badge>
                </Label>
                <div className="grid grid-cols-3 gap-2">
                  {languages.filter(l => l.code !== 'auto').map(lang => (
                    <Button
                      key={lang.code}
                      variant={targetLanguages.includes(lang.code) ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => {
                        if (targetLanguages.includes(lang.code)) {
                          setTargetLanguages(targetLanguages.filter(l => l !== lang.code));
                        } else {
                          setTargetLanguages([...targetLanguages, lang.code]);
                        }
                      }}
                    >
                      {lang.name}
                    </Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  选择需要翻译的目标语言（可多选）• 智能翻译（免费，无需代理）
                </p>
              </div>

              <Separator />

              <Button
                className="w-full"
                size="lg"
                onClick={handleGenerateSubtitle}
                disabled={loading || !selectedFile}
              >
                <Wand2 className="size-4 mr-2" />
                {loading ? '处理中...' : '开始生成字幕'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 任务列表 */}
        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5" />
                字幕任务
                <Badge variant="secondary">{tasks.length} 个任务</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tasks.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="size-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">暂无字幕任务</p>
                  <p className="text-sm">在"生成字幕"标签中创建新任务</p>
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
                                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                                  <Badge variant="outline" className="text-xs">
                                    {task.model.toUpperCase()}
                                  </Badge>
                                  <span>{task.source_language}</span>
                                  {task.target_languages.length > 0 && (
                                    <>
                                      <Languages className="size-3" />
                                      <span>{task.target_languages.join(', ')}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                              {getStatusBadge(task.status)}
                            </div>

                            {(task.status === 'processing' || task.status === 'generating' || task.status === 'translating') && (
                              <div className="mb-2">
                                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                  <span className="truncate max-w-[220px]">
                                    {task.message ||
                                      (task.status === 'processing' && '处理中') ||
                                      (task.status === 'generating' && '生成进度') ||
                                      (task.status === 'translating' && '翻译进度')}
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

                            {task.status === 'completed' && task.output_files.length > 0 && (
                              <div className="mb-2">
                                <p className="text-sm font-medium mb-1">输出文件:</p>
                                <div className="flex flex-wrap gap-2">
                                  {task.output_files.map((file, index) => (
                                    <Badge key={index} variant="secondary" className="text-xs">
                                      {file.split('\\').pop()}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}

                            <div className="flex gap-2 flex-wrap">
                              {task.status === 'completed' && (
                                <>
                                  <Button 
                                    size="sm" 
                                    variant="outline"
                                    onClick={() => handleOpenSubtitleFolder(task.video_path)}
                                  >
                                    <FolderOpen className="size-4 mr-2" />
                                    打开文件夹
                                  </Button>
                                  <Button 
                                    size="sm" 
                                    variant="outline"
                                    onClick={() => handleDownloadSubtitle(task.video_path)}
                                  >
                                    <Download className="size-4 mr-2" />
                                    下载字幕
                                  </Button>
                                </>
                              )}
                              {task.status === 'failed' && (
                                <Button 
                                  size="sm" 
                                  variant="outline"
                                  onClick={() => handleRetryTask(task)}
                                >
                                  <Play className="size-4 mr-2" />
                                  重试
                                </Button>
                              )}
                              {(task.status === 'pending' || task.status === 'processing' || task.status === 'generating' || task.status === 'translating') && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleCancelTask(task.id)}
                                >
                                  <Ban className="size-4 mr-2" />
                                  取消
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

      {/* AI 工具安装提示 */}
      <AIToolsPrompt
        open={showAIPrompt}
        onOpenChange={setShowAIPrompt}
        onInstall={handleInstallAITools}
        onGoToSettings={() => {
          toast.info('请在左侧导航打开“系统设置 → 工具配置”进行安装');
          setShowAIPrompt(false);
        }}
        installing={installing}
      />
    </div>
  );
}
