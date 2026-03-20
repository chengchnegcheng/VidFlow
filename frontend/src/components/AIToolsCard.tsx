import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Alert, AlertDescription } from './ui/alert';
import { CheckCircle2, Info, Download, Loader2 } from 'lucide-react';

interface AIToolsCardProps {
  status: {
    installed: boolean;
    faster_whisper: boolean;
    torch: boolean;
    version: string | null;
    device: string;
    python_compatible?: boolean;
    error?: string;
  } | null;
  version: 'cpu' | 'cuda';
  installing: boolean;
  uninstalling: boolean;
  progress?: { progress: number; message: string };
  uninstallProgress?: { progress: number; message: string };
  onVersionChange: (version: 'cpu' | 'cuda') => void;
  onInstall: () => void;
  onUninstall: () => void;
}

export function AIToolsCard({
  status,
  version,
  installing,
  uninstalling,
  progress,
  uninstallProgress,
  onVersionChange,
  onInstall,
  onUninstall
}: AIToolsCardProps) {
  const platform = window.electron?.platform;
  const arch = window.electron?.arch;
  const isMacOS = platform === 'darwin';
  const isAppleSilicon = isMacOS && arch === 'arm64';
  const supportsCudaInstall = !isMacOS;

  React.useEffect(() => {
    if (!supportsCudaInstall && version === 'cuda') {
      onVersionChange('cpu');
    }
  }, [supportsCudaInstall, version, onVersionChange]);

  console.log('[AIToolsCard] Props:', {
    installing,
    uninstalling,
    progress,
    uninstallProgress
  });

  const activeProgress = uninstalling ? uninstallProgress : progress;
  const shouldShowProgress = Boolean(activeProgress) || installing || uninstalling;
  const effectiveProgress =
    activeProgress ||
    (installing
      ? { progress: 0, message: '正在安装 AI 工具...' }
      : uninstalling
        ? { progress: 0, message: '正在卸载 AI 工具...' }
        : null);

  console.log('[AIToolsCard] Computed:', {
    activeProgress,
    shouldShowProgress,
    effectiveProgress
  });

  // 使用 useMemo 缓存进度值，避免频繁重渲染导致的"心跳"
  const progressValue = React.useMemo(() => {
    return effectiveProgress?.progress ?? 0;
  }, [effectiveProgress?.progress]);

  const getStatusIcon = () => {
    if (status?.installed) {
      return <CheckCircle2 className="w-5 h-5 text-green-500" />;
    }
    return <Info className="w-5 h-5 text-blue-500" />;
  };

  const getStatusBadge = () => {
    if (status?.installed) {
      return <Badge className="text-xs bg-green-500/10 text-green-600 border-green-200">已安装</Badge>;
    }
    return <Badge variant="secondary" className="text-xs">未安装</Badge>;
  };

  const getDeviceLabel = (device: string | undefined) => {
    if (device === 'cuda') return 'CUDA (GPU) 可用';
    if (device === 'mps') return 'Metal (MPS) 可用';
    if (device === 'cpu') return 'CPU';
    return '未知';
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            {getStatusIcon()}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg">AI 字幕生成</CardTitle>
                {getStatusBadge()}
              </div>
              <CardDescription className="mt-1">
                使用 faster-whisper 进行语音识别
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 状态信息 */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">状态</span>
            <div className="font-medium mt-1">
              {status?.installed ? '已安装' : '未安装'}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">版本</span>
            <div className="font-medium mt-1">
              {status?.version || 'N/A'}
            </div>
          </div>
          {status?.torch && (
            <div>
              <span className="text-muted-foreground">PyTorch 后端</span>
              <div className="font-medium mt-1">
                {getDeviceLabel(status.device)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                仅表示 PyTorch 可用后端，faster-whisper 实际仅支持 CPU/CUDA
              </div>
            </div>
          )}
        </div>

        {/* 版本选择（仅未安装时显示） */}
        {!status?.installed && (
          <div className="space-y-2">
            <label className="text-sm font-medium">选择版本</label>
            <div className={supportsCudaInstall ? "grid grid-cols-2 gap-2" : "grid grid-cols-1 gap-2"}>
              <Button
                variant={version === 'cpu' ? 'default' : 'outline'}
                onClick={() => onVersionChange('cpu')}
                disabled={installing}
                className="w-full"
              >
                <div className="text-left w-full">
                  <div className="font-medium">CPU 版本 ⭐</div>
                  <div className="text-xs opacity-70">{isAppleSilicon ? 'Apple Silicon 优化（CPU）' : '约 300 MB'}</div>
                </div>
              </Button>
              {supportsCudaInstall && (
                <Button
                  variant={version === 'cuda' ? 'default' : 'outline'}
                  onClick={() => onVersionChange('cuda')}
                  disabled={installing}
                  className="w-full"
                >
                  <div className="text-left w-full">
                    <div className="font-medium">GPU 版本</div>
                    <div className="text-xs opacity-70">约 1 GB</div>
                  </div>
                </Button>
              )}
            </div>
          </div>
        )}

        {/* 提示信息 */}
        <Alert className={status?.installed ? "border-green-200 bg-green-50/50" : ""}>
          {status?.installed ? (
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          ) : (
            <Info className="h-4 w-4" />
          )}
          <AlertDescription className={status?.installed ? "text-green-900" : ""}>
            {status?.installed ? (
              <>
                <span className="font-medium">AI 工具已就绪</span>
                <br />
                faster-whisper {status.version}
                <br />
                <span className="text-xs">可在字幕功能中使用 AI 语音识别</span>
              </>
            ) : (
              <>
                <span className="font-medium">可选组件</span>
                <br />
                AI 字幕生成功能需要安装 faster-whisper 和 PyTorch。
                <br />
                <span className="text-xs font-medium text-blue-600">
                  • CPU 版本（推荐）：兼容所有机器，体积小
                  {supportsCudaInstall ? (
                    <>
                      <br />
                      • GPU 版本：需要 NVIDIA 显卡，速度更快
                    </>
                  ) : (
                    isAppleSilicon ? (
                      <>
                        <br />
                        • Apple Silicon 可正常使用（CPU 模式，已针对 Apple 芯片优化）
                      </>
                    ) : null
                  )}
                </span>
              </>
            )}
          </AlertDescription>
        </Alert>

        {/* WebSocket 连接警告 - 已移除，由全局状态管理 */}

        {/* Python 版本警告 - 已移除，软件内置 Python 3.11，不需要版本检查 */}

        {/* 安装/卸载进度（无事件时也显示占位） */}
        {shouldShowProgress && effectiveProgress && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{effectiveProgress.message}</span>
              <span className="font-medium">{progressValue.toFixed(1)}%</span>
            </div>
            <Progress value={progressValue} className="h-2" />
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-2">
          {status?.installed ? (
            <Button
              onClick={onUninstall}
              disabled={installing || uninstalling}
              variant="outline"
              className="flex-1"
            >
              {uninstalling ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  卸载中...
                </>
              ) : (
                '卸载 AI 工具'
              )}
            </Button>
          ) : (
            <Button
              onClick={onInstall}
              disabled={installing || uninstalling}
              className="flex-1"
            >
              {installing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  安装中（3-5 分钟）...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  安装 {version === 'cpu' ? 'CPU' : 'GPU'} 版本
                </>
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
