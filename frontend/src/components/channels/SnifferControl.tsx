/**
 * 嗅探器控制组件
 * 提供启动/停止按钮和状态指示器
 * 支持多模式捕获：WinDivert透明捕获、Clash API监控、系统代理拦截
 * Task 18.1 - Requirements 2.4, 2.5, 4.3
 */
import React from 'react';
import { Button } from '../ui/button';
import { Alert, AlertDescription } from '../ui/alert';
import { Badge } from '../ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { Switch } from '../ui/switch';
import { Label } from '../ui/label';
import { ProxyWarning } from './ProxyWarning';
import {
  Play,
  Square,
  Loader2,
  Wifi,
  WifiOff,
  AlertCircle,
  Shield,
  Download,
  Zap,
} from 'lucide-react';
import {
  SnifferStatusResponse,
  SnifferState,
  DriverStatusResponse,
  CaptureMode,
  MultiCaptureMode,
  ProxyInfo,
  QUICStatusResponse,
  CaptureModeInfo,
  getSnifferStateText,
  getDriverStateText,
  getMultiCaptureModeText,
} from '../../types/channels';

interface SnifferControlProps {
  status: SnifferStatusResponse | null;
  isLoading: boolean;
  error: string | null;
  onStart: (port?: number, captureMode?: CaptureMode) => Promise<any>;
  onStop: () => Promise<any>;
  // 透明捕获相关
  driverStatus?: DriverStatusResponse | null;
  captureMode?: CaptureMode;
  onOpenDriverDialog?: () => void;
  onRequestAdmin?: () => void;
  // 多模式捕获相关（Task 18.1）
  proxyInfo?: ProxyInfo | null;
  quicStatus?: QUICStatusResponse | null;
  availableModes?: CaptureModeInfo[];
  currentMultiMode?: MultiCaptureMode;
  onModeChange?: (mode: MultiCaptureMode) => Promise<void>;
  onQUICToggle?: (enabled: boolean) => Promise<void>;
}

/**
 * 状态徽章颜色映射
 */
const getStateBadgeVariant = (state: SnifferState): 'default' | 'secondary' | 'destructive' | 'outline' => {
  switch (state) {
    case 'running':
      return 'default';
    case 'stopped':
      return 'secondary';
    case 'starting':
    case 'stopping':
      return 'outline';
    case 'error':
      return 'destructive';
    default:
      return 'secondary';
  }
};

/**
 * 状态图标
 */
const StateIcon: React.FC<{ state: SnifferState }> = ({ state }) => {
  switch (state) {
    case 'running':
      return <Wifi className="h-4 w-4 text-green-500" />;
    case 'stopped':
      return <WifiOff className="h-4 w-4 text-gray-500" />;
    case 'starting':
    case 'stopping':
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case 'error':
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    default:
      return <WifiOff className="h-4 w-4 text-gray-500" />;
  }
};

/**
 * 嗅探器控制组件
 */
export const SnifferControl: React.FC<SnifferControlProps> = ({
  status,
  isLoading,
  error,
  onStart,
  onStop,
  driverStatus,
  captureMode = 'proxy_only',
  onOpenDriverDialog,
  onRequestAdmin,
  // 多模式捕获相关
  proxyInfo,
  quicStatus,
  availableModes,
  currentMultiMode,
  onModeChange,
  onQUICToggle,
}) => {
  const [startWarning, setStartWarning] = React.useState<string | null>(null);
  const [selectedMode, setSelectedMode] = React.useState<MultiCaptureMode>(currentMultiMode || 'hybrid');

  const state = status?.state || 'stopped';
  const isRunning = state === 'running';
  const isStopped = state === 'stopped';
  const isTransitioning = state === 'starting' || state === 'stopping';

  // 透明捕获相关状态
  const isDriverInstalled = driverStatus?.state === 'installed';
  const isAdmin = driverStatus?.is_admin ?? false;
  const canStartTransparent = isDriverInstalled && isAdmin;

  // 同步选中模式
  React.useEffect(() => {
    if (currentMultiMode) {
      setSelectedMode(currentMultiMode);
    }
  }, [currentMultiMode]);

  /**
   * 处理模式选择变化
   */
  const handleModeSelect = async (mode: string) => {
    const newMode = mode as MultiCaptureMode;
    setSelectedMode(newMode);
    if (onModeChange && isRunning) {
      await onModeChange(newMode);
    }
  };

  /**
   * 处理QUIC开关变化
   */
  const handleQUICToggle = async (checked: boolean) => {
    if (onQUICToggle) {
      await onQUICToggle(checked);
    }
  };

  /**
   * 处理启动/停止
   */
  const handleToggle = async () => {
    console.log('[SnifferControl] handleToggle called', {
      isRunning,
      isStopped,
      state,
      captureMode,
      canStartTransparent,
      isDriverInstalled,
      isAdmin,
      driverStatus,
    });

    setStartWarning(null);

    try {
      if (isRunning) {
        await onStop();
      } else if (isStopped) {
        console.log('[SnifferControl] Calling onStart with captureMode:', captureMode);
        const result = await onStart(undefined, captureMode);

        // 检查返回结果，即使 success=true 也可能有警告信息
        if (result) {
          if (result.success) {
            const guidance = captureMode === 'transparent'
              ? '嗅探已启动。请重新打开视频号页面并完整播放目标视频一次，否则只能抓到原始视频地址，拿不到真实标题、缩略图和 decodeKey。'
              : '嗅探已启动。请在代理已生效的前提下重新打开视频号页面并完整播放目标视频一次。';
            setStartWarning(result.error_message ? `${result.error_message} ${guidance}` : guidance);
            if (captureMode !== 'transparent') {
              const proxyGuidance = '嗅探已启动。请确认系统根证书和微信兼容 P12 已安装，然后重新打开视频号页面并完整播放目标视频一次。';
              setStartWarning(result.error_message ? `${result.error_message} ${proxyGuidance}` : proxyGuidance);
            }
          }
          if (!result.success) {
            setStartWarning(result.error_message || '启动失败，请检查 WinDivert 驱动和管理员权限。');
            if (captureMode !== 'transparent' && !result.error_message) {
              setStartWarning('启动失败，请检查 mitmproxy 证书、微信兼容 P12 和系统代理设置。');
            }
          }
        }
      } else {
        console.log('[SnifferControl] State is neither running nor stopped:', state);
      }
    } catch (error) {
      console.error('[SnifferControl] Error in handleToggle:', error);
    }
  };

  /**
   * 检查是否可以启动
   */
  const canStart = () => {
    if (captureMode !== 'transparent') {
      return true;
    }
    return canStartTransparent;
  };

  /**
   * 获取启动按钮禁用原因
   */
  const getStartDisabledReason = (): string | null => {
    if (captureMode !== 'transparent') return null;
    if (!isDriverInstalled) return '需要先安装 WinDivert 驱动';
    if (!isAdmin) return '需要管理员权限';
    return null;
  };

  const startDisabledReason = getStartDisabledReason();

  return (
    <div className="space-y-4">
      {/* 多模式选择（Task 18.1） */}
      {availableModes && availableModes.length > 0 && !isRunning && (
        <div className="space-y-2">
          <Label className="text-sm font-medium">捕获模式</Label>
          <Select value={selectedMode} onValueChange={handleModeSelect}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="选择捕获模式" />
            </SelectTrigger>
            <SelectContent>
              {availableModes.map((mode) => (
                <SelectItem
                  key={mode.mode}
                  value={mode.mode}
                  disabled={!mode.available}
                >
                  <div className="flex items-center gap-2">
                    <span>{mode.name}</span>
                    {mode.recommended && (
                      <Badge variant="secondary" className="text-xs">推荐</Badge>
                    )}
                    {!mode.available && (
                      <Badge variant="outline" className="text-xs">不可用</Badge>
                    )}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {availableModes.find(m => m.mode === selectedMode)?.description && (
            <p className="text-xs text-muted-foreground">
              {availableModes.find(m => m.mode === selectedMode)?.description}
            </p>
          )}
        </div>
      )}

      {/* 代理状态显示（Task 18.1） */}
      {proxyInfo && proxyInfo.proxy_type !== 'none' && (
        <ProxyWarning proxyInfo={proxyInfo} />
      )}

      {/* 透明捕获模式状态提示 */}
      {!isRunning && selectedMode === 'windivert' && (
        <div className="space-y-2">
          {/* 驱动状态 */}
          <div className="flex items-center justify-between p-2 bg-muted rounded-lg">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              <span className="text-sm">WinDivert 驱动</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={isDriverInstalled ? 'default' : 'secondary'}>
                {driverStatus ? getDriverStateText(driverStatus.state) : '未知'}
              </Badge>
              {!isDriverInstalled && onOpenDriverDialog && (
                <Button variant="ghost" size="sm" onClick={onOpenDriverDialog}>
                  <Download className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {/* 管理员权限状态 */}
          <div className="flex items-center justify-between p-2 bg-muted rounded-lg">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              <span className="text-sm">管理员权限</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={isAdmin ? 'default' : 'secondary'}>
                {isAdmin ? '已获取' : '未获取'}
              </Badge>
              {!isAdmin && onRequestAdmin && (
                <Button variant="ghost" size="sm" onClick={onRequestAdmin}>
                  <Shield className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* QUIC阻止开关（Task 18.1） */}
      {onQUICToggle && (
        <div className="flex items-center justify-between p-2 bg-muted rounded-lg">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            <div>
              <span className="text-sm">QUIC 阻止</span>
              <p className="text-xs text-muted-foreground">
                阻止微信QUIC流量，强制使用TCP
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={quicStatus?.blocking_enabled ?? false}
              onCheckedChange={handleQUICToggle}
              disabled={isLoading}
            />
            {quicStatus && quicStatus.packets_blocked > 0 && (
              <Badge variant="outline" className="text-xs">
                已阻止 {quicStatus.packets_blocked}
              </Badge>
            )}
          </div>
        </div>
      )}

      {/* 状态和控制 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StateIcon state={state} />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium">
                {currentMultiMode ? getMultiCaptureModeText(currentMultiMode) : (captureMode === 'transparent' ? '透明嗅探器' : '显式代理嗅探器')}
              </span>
              <Badge variant={getStateBadgeVariant(state)}>
                {getSnifferStateText(state)}
              </Badge>
            </div>
            {isRunning && status?.videos_detected !== undefined && (
              <p className="text-sm text-muted-foreground">
                已检测到 {status.videos_detected} 个视频
              </p>
            )}
          </div>
        </div>

        <Button
          onClick={handleToggle}
          disabled={isLoading || isTransitioning || (!isRunning && selectedMode === 'windivert' && !canStart())}
          variant={isRunning ? 'destructive' : 'default'}
          size="sm"
          title={selectedMode === 'windivert' ? startDisabledReason || undefined : undefined}
        >
          {isTransitioning ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              {state === 'starting' ? '启动中...' : '停止中...'}
            </>
          ) : isRunning ? (
            <>
              <Square className="h-4 w-4 mr-2" />
              停止嗅探
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              开始嗅探
            </>
          )}
        </Button>
      </div>

      {/* 使用说明 - 根据模式显示 */}
      {isRunning && (
        <div className="text-sm text-muted-foreground space-y-1">
          {currentMultiMode === 'clash_api' ? (
            <>
              <p>Clash API 监控已启动，正在通过 Clash 监控连接...</p>
              <p>打开微信视频号，浏览想要下载的视频即可自动捕获</p>
            </>
          ) : currentMultiMode === 'system_proxy' ? (
            <>
              <p>系统代理拦截已启动，请确保已安装 CA 证书</p>
              <p>打开微信视频号，浏览想要下载的视频即可自动捕获</p>
            </>
          ) : captureMode === 'transparent' ? (
            <>
              <p>透明捕获已启动，正在监控微信流量...</p>
              <p>请重新打开视频号页面并完整播放目标视频一次；如果拿不到标题、缩略图或 decodeKey，请改用显式代理模式。</p>
            </>
          ) : (
            <>
              <p>显式代理模式已启动，系统代理已切换到本地嗅探器。</p>
              <p>请确认系统根证书和微信兼容 P12 已安装，然后重新打开视频号页面并完整播放目标视频一次。</p>
            </>
          )}
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* 嗅探器错误 */}
      {status?.error_message && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <p>{status.error_message}</p>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* 透明捕获条件不满足提示 */}
      {startDisabledReason && !isRunning && selectedMode === 'windivert' && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <p>透明捕获模式需要：{startDisabledReason}</p>
              <div className="flex gap-2">
                {!isDriverInstalled && onOpenDriverDialog && (
                  <Button variant="link" size="sm" className="h-auto p-0" onClick={onOpenDriverDialog}>
                    安装驱动
                  </Button>
                )}
                {!isAdmin && onRequestAdmin && (
                  <Button variant="link" size="sm" className="h-auto p-0" onClick={onRequestAdmin}>
                    以管理员身份重启
                  </Button>
                )}
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* 启动警告提示 */}
      {startWarning && (
        <Alert variant="default" className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950">
          <AlertCircle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800 dark:text-yellow-200">
            {startWarning}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};

export default SnifferControl;
