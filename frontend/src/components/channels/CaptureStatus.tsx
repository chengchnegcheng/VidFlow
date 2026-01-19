/**
 * 捕获状态组件
 * 显示透明捕获的实时状态和统计信息
 */
import React from 'react';
import { Alert, AlertDescription } from '../ui/alert';
import { Badge } from '../ui/badge';
import {
  Activity,
  Clock,
  Video,
  Network,
  AlertTriangle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import {
  CaptureStatistics,
  CaptureState,
  formatLastDetectionTime,
} from '../../types/channels';

interface CaptureStatusProps {
  state: CaptureState;
  statistics: CaptureStatistics | null;
  startedAt: string | null;
  noDetectionTimeout: number; // 秒
  onTroubleshoot?: () => void;
}

/**
 * 捕获状态图标
 */
const CaptureStateIcon: React.FC<{ state: CaptureState }> = ({ state }) => {
  switch (state) {
    case 'running':
      return <Activity className="h-4 w-4 text-green-500 animate-pulse" />;
    case 'stopped':
      return <CheckCircle2 className="h-4 w-4 text-gray-500" />;
    case 'starting':
    case 'stopping':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case 'error':
      return <AlertTriangle className="h-4 w-4 text-red-500" />;
    default:
      return <Activity className="h-4 w-4 text-gray-500" />;
  }
};

/**
 * 状态文本映射
 */
const CAPTURE_STATE_TEXT: Record<CaptureState, string> = {
  stopped: '已停止',
  starting: '正在启动...',
  running: '捕获中',
  stopping: '正在停止...',
  error: '错误',
};

/**
 * 捕获状态组件
 */
export const CaptureStatus: React.FC<CaptureStatusProps> = ({
  state,
  statistics,
  startedAt,
  noDetectionTimeout,
  onTroubleshoot,
}) => {
  const [showTimeoutWarning, setShowTimeoutWarning] = React.useState(false);

  // 检查是否超时未检测到视频
  React.useEffect(() => {
    if (state !== 'running' || !statistics) {
      setShowTimeoutWarning(false);
      return;
    }

    const checkTimeout = () => {
      const lastDetection = statistics.last_detection_at;
      if (!lastDetection) {
        // 从未检测到，检查启动时间
        if (startedAt) {
          const startTime = new Date(startedAt).getTime();
          const elapsed = (Date.now() - startTime) / 1000;
          setShowTimeoutWarning(elapsed > noDetectionTimeout);
        }
      } else {
        const lastTime = new Date(lastDetection).getTime();
        const elapsed = (Date.now() - lastTime) / 1000;
        setShowTimeoutWarning(elapsed > noDetectionTimeout);
      }
    };

    checkTimeout();
    const interval = setInterval(checkTimeout, 5000);
    return () => clearInterval(interval);
  }, [state, statistics, startedAt, noDetectionTimeout]);

  if (state === 'stopped') {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* 状态标题 */}
      <div className="flex items-center gap-2">
        <CaptureStateIcon state={state} />
        <span className="font-medium">{CAPTURE_STATE_TEXT[state]}</span>
        {state === 'running' && (
          <Badge variant="default" className="ml-auto">
            透明捕获
          </Badge>
        )}
      </div>

      {/* 统计信息 */}
      {statistics && state === 'running' && (
        <div className="grid grid-cols-2 gap-3">
          {/* 拦截包数 */}
          <div className="flex items-center gap-2 p-2 bg-muted rounded-lg">
            <Network className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">拦截数据包</p>
              <p className="font-medium">{statistics.packets_intercepted.toLocaleString()}</p>
            </div>
          </div>

          {/* 重定向连接数 */}
          <div className="flex items-center gap-2 p-2 bg-muted rounded-lg">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">重定向连接</p>
              <p className="font-medium">{statistics.connections_redirected.toLocaleString()}</p>
            </div>
          </div>

          {/* 检测视频数 */}
          <div className="flex items-center gap-2 p-2 bg-muted rounded-lg">
            <Video className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">检测视频</p>
              <p className="font-medium">{statistics.videos_detected}</p>
            </div>
          </div>

          {/* 最后检测时间 */}
          <div className="flex items-center gap-2 p-2 bg-muted rounded-lg">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">最后检测</p>
              <p className="font-medium text-sm">
                {formatLastDetectionTime(statistics.last_detection_at)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 超时警告 */}
      {showTimeoutWarning && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <p>长时间未检测到视频，请检查：</p>
              <ul className="text-xs list-disc list-inside space-y-1 opacity-80">
                <li>微信是否已打开并正在播放视频号</li>
                <li>目标进程是否已添加到捕获列表</li>
                <li>防火墙是否阻止了流量捕获</li>
                <li>是否以管理员身份运行 VidFlow</li>
              </ul>
              {onTroubleshoot && (
                <button
                  onClick={onTroubleshoot}
                  className="text-xs text-primary hover:underline"
                >
                  查看故障排查指南
                </button>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* 未识别域名提示 */}
      {statistics && statistics.unrecognized_domains.length > 0 && (
        <div className="p-2 bg-muted rounded-lg">
          <p className="text-xs text-muted-foreground mb-1">
            未识别的域名（可能包含视频）：
          </p>
          <div className="flex flex-wrap gap-1">
            {statistics.unrecognized_domains.slice(0, 5).map(domain => (
              <Badge key={domain} variant="outline" className="text-xs">
                {domain}
              </Badge>
            ))}
            {statistics.unrecognized_domains.length > 5 && (
              <Badge variant="outline" className="text-xs">
                +{statistics.unrecognized_domains.length - 5} 更多
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CaptureStatus;
