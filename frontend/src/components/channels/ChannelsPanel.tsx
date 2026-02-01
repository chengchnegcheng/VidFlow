/**
 * 视频号面板组件
 * 整合嗅探器控制、视频列表和配置面板
 * 使用透明捕获模式捕获 Windows PC 端微信流量
 */
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Separator } from '../ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { 
  Video, 
  Settings, 
  Loader2,
  RefreshCw,
  Monitor,
} from 'lucide-react';
import { useChannelsSniffer } from '../../hooks/useChannelsSniffer';
import { SnifferControl } from './SnifferControl';
import { VideoList } from './VideoList';
import { DownloadTaskList } from './DownloadTaskList';
import { DriverInstallDialog } from './DriverInstallDialog';
import { ProcessSelector } from './ProcessSelector';
import { CaptureStatus } from './CaptureStatus';
import { DiagnosticPanel } from './DiagnosticPanel';
import { 
  ChannelsConfigUpdateRequest,
  CaptureMode,
  CaptureConfigUpdateRequest,
} from '../../types/channels';
import { invoke } from '../TauriIntegration';
import { toast } from 'sonner';

/**
 * 视频号面板组件
 */
export const ChannelsPanel: React.FC = () => {
  const {
    state,
    isRunning,
    startSniffer,
    stopSniffer,
    clearVideos,
    addVideoManually,
    downloadVideo,
    updateConfig,
    initialize,
    // 透明捕获相关
    driverStatus,
    captureConfig,
    captureStatistics,
    captureState,
    captureStartedAt,
    fetchDriverStatus,
    installDriver,
    requestAdminRestart,
    updateCaptureConfig,
  } = useChannelsSniffer();

  const [driverDialogOpen, setDriverDialogOpen] = React.useState(false);
  const [configDraft, setConfigDraft] = React.useState<ChannelsConfigUpdateRequest>({});
  const [captureConfigDraft, setCaptureConfigDraft] = React.useState<CaptureConfigUpdateRequest>({});
  const [downloadTasks, setDownloadTasks] = React.useState<any[]>([]);

  /**
   * 获取下载任务列表
   */
  const fetchDownloadTasks = React.useCallback(async () => {
    try {
      const tasks = await invoke('channels_get_download_tasks');
      setDownloadTasks(tasks);
    } catch (error) {
      console.error('Failed to fetch download tasks:', error);
    }
  }, []);

  /**
   * 定期刷新下载任务
   */
  React.useEffect(() => {
    fetchDownloadTasks();
    const interval = setInterval(fetchDownloadTasks, 2000); // 每 2 秒刷新
    return () => clearInterval(interval);
  }, [fetchDownloadTasks]);

  /**
   * 同步配置草稿
   */
  React.useEffect(() => {
    if (state.config) {
      setConfigDraft({
        proxy_port: state.config.proxy_port,
        download_dir: state.config.download_dir,
        auto_decrypt: state.config.auto_decrypt,
        quality_preference: state.config.quality_preference,
        clear_on_exit: state.config.clear_on_exit,
      });
    }
  }, [state.config]);

  /**
   * 同步捕获配置草稿
   */
  React.useEffect(() => {
    if (captureConfig) {
      setCaptureConfigDraft({
        capture_mode: 'transparent', // 固定为透明模式
        target_processes: captureConfig.target_processes,
        no_detection_timeout: captureConfig.no_detection_timeout,
        log_unrecognized_domains: captureConfig.log_unrecognized_domains,
      });
    }
  }, [captureConfig]);

  /**
   * 保存配置
   */
  const handleSaveConfig = async () => {
    try {
      await updateConfig(configDraft);
      if (updateCaptureConfig) {
        await updateCaptureConfig({
          ...captureConfigDraft,
          capture_mode: 'transparent', // 确保始终是透明模式
        });
      }
    } catch (err) {
      console.error('Failed to save config:', err);
    }
  };

  /**
   * 处理下载
   */
  const handleDownload = async (request: any) => {
    try {
      console.log('[Channels] Starting download:', request);
      const result = await downloadVideo(request);
      console.log('[Channels] Download result:', result);
      
      if (!result.success) {
        toast.error('下载失败', { description: result.error });
      } else {
        toast.success('下载任务已创建');
        // 立即刷新任务列表
        fetchDownloadTasks();
      }
    } catch (err: any) {
      console.error('Download error:', err);
      toast.error('下载失败', { description: err.message });
    }
  };

  /**
   * 取消下载任务
   */
  const handleCancelTask = async (taskId: string) => {
    try {
      await invoke('channels_cancel_download', { task_id: taskId });
      toast.success('任务已取消');
      fetchDownloadTasks();
    } catch (err: any) {
      toast.error('取消失败', { description: err.message });
    }
  };

  /**
   * 删除下载任务
   */
  const handleDeleteTask = async (taskId: string) => {
    try {
      await invoke('channels_delete_download_task', { task_id: taskId });
      toast.success('任务已删除');
      fetchDownloadTasks();
    } catch (err: any) {
      toast.error('删除失败', { description: err.message });
    }
  };

  /**
   * 打开文件夹
   */
  const handleOpenFolder = async (filePath: string) => {
    try {
      if (window.electron && window.electron.isElectron) {
        await window.electron.showItemInFolder(filePath);
      } else {
        toast.info('浏览器环境不支持此功能');
      }
    } catch (err: any) {
      toast.error('打开文件夹失败', { description: err.message });
    }
  };

  /**
   * 处理目标进程变更
   */
  const handleTargetProcessesChange = (processes: string[]) => {
    setCaptureConfigDraft({
      ...captureConfigDraft,
      target_processes: processes,
    });
  };

  /**
   * 启动嗅探器（优先使用代理模式以获取可下载的完整URL；透明模式通常只能得到占位符）
   */
  const handleStartSniffer = async (port?: number, _mode?: CaptureMode) => {
    return startSniffer(port, 'proxy');
  };

  return (
    <div className="space-y-6 p-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Video className="h-6 w-6" />
            微信视频号下载
          </h1>
          <p className="text-muted-foreground mt-1">
            自动捕获 Windows PC 端微信视频号视频链接并下载
          </p>
          {!isRunning && state.videos.length === 0 && (
            <div className="mt-2 text-sm text-muted-foreground">
              💡 使用提示：需要以<span className="font-semibold text-foreground">管理员身份</span>运行应用，然后在微信中播放视频号视频
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDriverDialogOpen(true)}
          >
            <Monitor className="h-4 w-4 mr-2" />
            驱动管理
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={initialize}
            disabled={state.isLoading}
          >
            {state.isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="sniffer" className="space-y-4">
        <TabsList>
          <TabsTrigger value="sniffer">嗅探器</TabsTrigger>
          <TabsTrigger value="diagnostic">系统诊断</TabsTrigger>
          <TabsTrigger value="settings">设置</TabsTrigger>
        </TabsList>

        {/* 嗅探器标签页 */}
        <TabsContent value="sniffer" className="space-y-4">
          {/* 嗅探器控制 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">透明嗅探器</CardTitle>
              <CardDescription>
                自动拦截 Windows PC 端微信流量以捕获视频链接
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <SnifferControl
                status={state.status}
                isLoading={state.isLoading}
                error={state.error}
                onStart={handleStartSniffer}
                onStop={stopSniffer}
                driverStatus={driverStatus}
                captureMode="transparent"
                onOpenDriverDialog={() => setDriverDialogOpen(true)}
                onRequestAdmin={requestAdminRestart}
              />

              {/* 透明捕获状态 */}
              {isRunning && (
                <CaptureStatus
                  state={captureState}
                  statistics={captureStatistics}
                  startedAt={captureStartedAt}
                  noDetectionTimeout={captureConfig?.no_detection_timeout || 60}
                />
              )}
            </CardContent>
          </Card>

          {/* 视频列表 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">检测到的视频</CardTitle>
              <CardDescription>
                浏览视频号时自动捕获的视频链接
              </CardDescription>
            </CardHeader>
            <CardContent>
              <VideoList
                videos={state.videos}
                onDownload={handleDownload}
                onClearAll={clearVideos}
                onAddVideo={addVideoManually}
                qualityPreference={state.config?.quality_preference}
              />
            </CardContent>
          </Card>

          {/* 下载任务列表 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">下载任务</CardTitle>
              <CardDescription>
                当前下载任务列表 ({downloadTasks.length})
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DownloadTaskList
                tasks={downloadTasks}
                onCancel={handleCancelTask}
                onDelete={handleDeleteTask}
                onOpenFolder={handleOpenFolder}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* 系统诊断标签页 */}
        <TabsContent value="diagnostic" className="space-y-4">
          <DiagnosticPanel />
        </TabsContent>

        {/* 设置标签页 */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Settings className="h-5 w-5" />
                基本配置
              </CardTitle>
              <CardDescription>
                自定义下载设置
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 下载目录 */}
              <div className="space-y-2">
                <Label htmlFor="download-dir">下载目录</Label>
                <Input
                  id="download-dir"
                  value={configDraft.download_dir || ''}
                  onChange={(e) => setConfigDraft({
                    ...configDraft,
                    download_dir: e.target.value,
                  })}
                  placeholder="留空使用默认目录"
                />
                <p className="text-xs text-muted-foreground">
                  视频下载保存的目录，留空使用默认下载目录
                </p>
              </div>

              <Separator />

              {/* 画质偏好 */}
              <div className="space-y-2">
                <Label htmlFor="quality">画质偏好</Label>
                <Select
                  value={configDraft.quality_preference || 'best'}
                  onValueChange={(value) => setConfigDraft({
                    ...configDraft,
                    quality_preference: value,
                  })}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="选择画质" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="best">最佳画质</SelectItem>
                    <SelectItem value="1080p">1080p</SelectItem>
                    <SelectItem value="720p">720p</SelectItem>
                    <SelectItem value="480p">480p</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  当有多个画质可选时的默认选择
                </p>
              </div>

              <Separator />

              {/* 自动解密 */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>自动解密</Label>
                  <p className="text-xs text-muted-foreground">
                    下载后自动解密加密的视频文件
                  </p>
                </div>
                <Switch
                  checked={configDraft.auto_decrypt ?? true}
                  onCheckedChange={(checked) => setConfigDraft({
                    ...configDraft,
                    auto_decrypt: checked,
                  })}
                />
              </div>

              <Separator />

              {/* 退出时清空 */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>退出时清空列表</Label>
                  <p className="text-xs text-muted-foreground">
                    关闭应用时自动清空检测到的视频列表
                  </p>
                </div>
                <Switch
                  checked={configDraft.clear_on_exit ?? false}
                  onCheckedChange={(checked) => setConfigDraft({
                    ...configDraft,
                    clear_on_exit: checked,
                  })}
                />
              </div>
            </CardContent>
          </Card>

          {/* 透明捕获配置 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Monitor className="h-5 w-5" />
                透明捕获配置
              </CardTitle>
              <CardDescription>
                配置 Windows 透明流量捕获选项
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 目标进程 */}
              <div className="space-y-2">
                <Label>目标进程</Label>
                <ProcessSelector
                  selectedProcesses={captureConfigDraft.target_processes || []}
                  onChange={handleTargetProcessesChange}
                  disabled={isRunning}
                />
                <p className="text-xs text-muted-foreground">
                  选择要捕获流量的微信进程
                </p>
              </div>

              <Separator />

              {/* 无检测超时 */}
              <div className="space-y-2">
                <Label htmlFor="timeout">无检测超时（秒）</Label>
                <Input
                  id="timeout"
                  type="number"
                  value={captureConfigDraft.no_detection_timeout || 60}
                  onChange={(e) => setCaptureConfigDraft({
                    ...captureConfigDraft,
                    no_detection_timeout: parseInt(e.target.value) || 60,
                  })}
                  className="w-32"
                />
                <p className="text-xs text-muted-foreground">
                  超过此时间未检测到视频时显示故障排查提示
                </p>
              </div>

              <Separator />

              {/* 记录未识别域名 */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>记录未识别域名</Label>
                  <p className="text-xs text-muted-foreground">
                    将未识别的域名记录到日志，便于后续分析
                  </p>
                </div>
                <Switch
                  checked={captureConfigDraft.log_unrecognized_domains ?? true}
                  onCheckedChange={(checked) => setCaptureConfigDraft({
                    ...captureConfigDraft,
                    log_unrecognized_domains: checked,
                  })}
                />
              </div>

              <Separator />

              {/* 保存按钮 */}
              <div className="flex justify-end">
                <Button onClick={handleSaveConfig}>
                  保存设置
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 驱动安装对话框 */}
      <DriverInstallDialog
        isOpen={driverDialogOpen}
        onClose={() => setDriverDialogOpen(false)}
        driverStatus={driverStatus}
        isLoading={state.isLoading}
        onInstall={installDriver}
        onRefresh={fetchDriverStatus}
        onRequestAdmin={requestAdminRestart}
      />
    </div>
  );
};

export default ChannelsPanel;
