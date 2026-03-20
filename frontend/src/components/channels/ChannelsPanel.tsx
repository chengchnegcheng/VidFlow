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
import { CertificateDialog } from './CertificateDialog';
import { ProcessSelector } from './ProcessSelector';
import { CaptureStatus } from './CaptureStatus';
import { DiagnosticPanel } from './DiagnosticPanel';
import {
  ChannelsConfigUpdateRequest,
  CaptureMode,
  CaptureConfigUpdateRequest,
  getCaptureModeText,
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
    fetchCertInfo,
    generateCert,
    downloadCert,
    installRootCert,
    installWechatP12,
    getCertInstructions,
    proxyInfo,
    quicStatus,
    fetchDriverStatus,
    installDriver,
    requestAdminRestart,
    updateCaptureConfig,
    toggleQUICBlocking,
  } = useChannelsSniffer();

  const [driverDialogOpen, setDriverDialogOpen] = React.useState(false);
  const [certDialogOpen, setCertDialogOpen] = React.useState(false);
  const [configDraft, setConfigDraft] = React.useState<ChannelsConfigUpdateRequest>({});
  const [captureConfigDraft, setCaptureConfigDraft] = React.useState<CaptureConfigUpdateRequest>({});
  const [downloadTasks, setDownloadTasks] = React.useState<any[]>([]);
  // 默认使用透明捕获模式（WinDivert），因为 explicit 代理模式下
  // WeChatAppEx.exe 的 HTTP/2 连接复用会导致后续视频请求绕过代理。
  // 透明模式在 OS 层拦截所有目标进程流量，不受连接状态影响。
  // 如果缺少管理员权限或 WinDivert，后端会返回错误提示用户切换模式。
  const defaultCaptureMode: CaptureMode = 'transparent';
  const effectiveCaptureMode: CaptureMode =
    captureConfigDraft.capture_mode ||
    captureConfig?.capture_mode ||
    state.status?.capture_mode ||
    defaultCaptureMode;

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
        auto_clean_wechat_cache: state.config.auto_clean_wechat_cache,
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
        capture_mode: captureConfig.capture_mode || defaultCaptureMode,
        quic_blocking_enabled: captureConfig.quic_blocking_enabled,
        target_processes: captureConfig.target_processes,
        no_detection_timeout: captureConfig.no_detection_timeout,
        log_unrecognized_domains: captureConfig.log_unrecognized_domains,
      });
    }
  }, [captureConfig, defaultCaptureMode]);

  /**
   * 保存配置
   */
  const handleSaveConfig = async () => {
    try {
      await updateConfig(configDraft);
      if (updateCaptureConfig) {
        await updateCaptureConfig({
          ...captureConfigDraft,
          capture_mode: captureConfigDraft.capture_mode || effectiveCaptureMode,
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
      const res: any = await invoke('channels_delete_download_task', { task_id: taskId });
      toast.success(res?.message || '任务已删除');
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

  const handleCaptureModeChange = (mode: string) => {
    setCaptureConfigDraft((prev) => ({
      ...prev,
      capture_mode: mode as CaptureMode,
    }));
  };

  /**
   * 启动嗅探器
   * 优先使用 WinDivert 本机透明捕获，条件不满足时回退到代理模式。
   */
  const handleStartSniffer = async (port?: number, mode?: CaptureMode) => {
    return startSniffer(port, mode || effectiveCaptureMode);
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
              {effectiveCaptureMode === 'transparent' ? (
                <>当前使用 <span className="font-semibold text-foreground">{getCaptureModeText(effectiveCaptureMode)}</span>。请以管理员身份运行并确认 WinDivert 已安装，然后在嗅探启动后重新打开微信视频号页面并完整播放目标视频一次。</>
              ) : (
                <>当前使用 <span className="font-semibold text-foreground">{getCaptureModeText(effectiveCaptureMode)}</span>。请先确认系统根证书和微信兼容 P12 已安装；如果只能抓到 `stodownload` 且一直缺少 `decodeKey`，请切换到透明捕获模式后重试。</>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void fetchCertInfo();
              setCertDialogOpen(true);
            }}
          >
            HTTPS 证书
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDriverDialogOpen(true)}
          >
            <Monitor className="h-4 w-4 mr-2" />
            透明模式驱动
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
              <CardTitle className="text-lg">视频号嗅探器</CardTitle>
              <CardDescription>
                选择当前嗅探模式。微信 4.x 只能抓到原始视频地址或始终缺少 decodeKey 时，优先改用透明捕获。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="sniffer-capture-mode">嗅探模式</Label>
                <Select
                  value={effectiveCaptureMode}
                  onValueChange={handleCaptureModeChange}
                  disabled={isRunning}
                >
                  <SelectTrigger id="sniffer-capture-mode" className="w-full max-w-sm">
                    <SelectValue placeholder="选择嗅探模式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="proxy_only">{getCaptureModeText('proxy_only')}</SelectItem>
                    <SelectItem value="transparent">{getCaptureModeText('transparent')}</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  显式代理需要安装证书；透明捕获需要管理员权限和 WinDivert 驱动。
                </p>
              </div>

              <SnifferControl
                status={state.status}
                isLoading={state.isLoading}
                error={state.error}
                onStart={handleStartSniffer}
                onStop={stopSniffer}
                driverStatus={driverStatus}
                captureMode={effectiveCaptureMode}
                proxyInfo={proxyInfo}
                quicStatus={quicStatus}
                onQUICToggle={async (enabled) => {
                  await toggleQUICBlocking(enabled);
                }}
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
                downloadDir={state.config?.download_dir}
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

              {/* 启动前自动清微信缓存 */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>启动前自动清微信缓存</Label>
                  <p className="text-xs text-muted-foreground">
                    启动视频号嗅探前自动清理微信视频号页面缓存，并刷新相关页面进程
                  </p>
                </div>
                <Switch
                  checked={configDraft.auto_clean_wechat_cache ?? true}
                  onCheckedChange={(checked) => setConfigDraft({
                    ...configDraft,
                    auto_clean_wechat_cache: checked,
                  })}
                />
              </div>

              <Separator />

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
              <div className="space-y-2">
                <Label htmlFor="settings-capture-mode">默认嗅探模式</Label>
                <Select
                  value={effectiveCaptureMode}
                  onValueChange={handleCaptureModeChange}
                  disabled={isRunning}
                >
                  <SelectTrigger id="settings-capture-mode" className="w-full max-w-sm">
                    <SelectValue placeholder="选择默认嗅探模式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="proxy_only">{getCaptureModeText('proxy_only')}</SelectItem>
                    <SelectItem value="transparent">{getCaptureModeText('transparent')}</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  保存设置后，新的默认模式会写回捕获配置。
                </p>
              </div>

              <Separator />

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
      <CertificateDialog
        isOpen={certDialogOpen}
        onClose={() => setCertDialogOpen(false)}
        certInfo={state.certInfo}
        onGenerate={generateCert}
        onDownload={downloadCert}
        onInstallRoot={installRootCert}
        onInstallWechatP12={installWechatP12}
        onGetInstructions={getCertInstructions}
      />
    </div>
  );
};

export default ChannelsPanel;
