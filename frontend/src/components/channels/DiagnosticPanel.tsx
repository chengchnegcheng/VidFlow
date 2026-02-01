/**
 * 系统诊断面板组件
 * 显示系统状态和诊断建议
 */
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Alert, AlertDescription } from '../ui/alert';
import { 
  AlertCircle, 
  AlertTriangle, 
  Info, 
  CheckCircle2,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { invoke } from '../TauriIntegration';
import { SystemDiagnosticResponse, DiagnosticLevel } from '../../types/channels';
import { toast } from 'sonner';

/**
 * 诊断级别图标映射
 */
const LEVEL_ICONS: Record<DiagnosticLevel, React.ReactNode> = {
  error: <AlertCircle className="h-5 w-5 text-destructive" />,
  warning: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
  info: <Info className="h-5 w-5 text-blue-500" />,
  success: <CheckCircle2 className="h-5 w-5 text-green-500" />,
};

/**
 * 诊断级别样式映射
 */
const LEVEL_STYLES: Record<DiagnosticLevel, string> = {
  error: 'border-destructive/50 bg-destructive/10',
  warning: 'border-yellow-500/50 bg-yellow-500/10',
  info: 'border-blue-500/50 bg-blue-500/10',
  success: 'border-green-500/50 bg-green-500/10',
};

export const DiagnosticPanel: React.FC = () => {
  const [diagnostic, setDiagnostic] = React.useState<SystemDiagnosticResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  /**
   * 执行诊断
   */
  const runDiagnostic = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await invoke('channels_diagnose');
      setDiagnostic(result);
    } catch (error: any) {
      toast.error('诊断失败', { description: error.message });
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * 组件挂载时自动执行诊断
   */
  React.useEffect(() => {
    runDiagnostic();
  }, [runDiagnostic]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">系统诊断</CardTitle>
            <CardDescription>
              检查系统状态并获取故障排查建议
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={runDiagnostic}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {diagnostic && (
          <>
            {/* 系统状态概览 */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="space-y-1">
                <div className="text-muted-foreground">管理员权限</div>
                <div className={diagnostic.is_admin ? 'text-green-600' : 'text-red-600'}>
                  {diagnostic.is_admin ? '✓ 已获取' : '✗ 未获取'}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-muted-foreground">微信进程</div>
                <div className={diagnostic.wechat_running ? 'text-green-600' : 'text-yellow-600'}>
                  {diagnostic.wechat_running ? `✓ 运行中 (${diagnostic.wechat_processes.length})` : '✗ 未运行'}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-muted-foreground">嗅探器状态</div>
                <div>
                  {diagnostic.sniffer_state === 'running' ? '✓ 运行中' : 
                   diagnostic.sniffer_state === 'stopped' ? '○ 已停止' : 
                   diagnostic.sniffer_state}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-muted-foreground">检测到的视频</div>
                <div className={diagnostic.videos_detected > 0 ? 'text-green-600' : ''}>
                  {diagnostic.videos_detected} 个
                </div>
              </div>
            </div>

            {/* 微信进程详情 */}
            {diagnostic.wechat_processes.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">微信进程详情</div>
                <div className="space-y-1 text-xs">
                  {diagnostic.wechat_processes.map((proc) => (
                    <div key={proc.pid} className="flex items-center gap-2 text-muted-foreground">
                      <span className="font-mono">{proc.name}</span>
                      <span className="text-xs">PID: {proc.pid}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 诊断建议 */}
            {diagnostic.recommendations.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">诊断建议</div>
                <div className="space-y-2">
                  {diagnostic.recommendations.map((rec, index) => (
                    <Alert key={index} className={LEVEL_STYLES[rec.level]}>
                      <div className="flex items-start gap-3">
                        {LEVEL_ICONS[rec.level]}
                        <div className="flex-1 space-y-1">
                          <AlertDescription className="font-medium">
                            {rec.message}
                          </AlertDescription>
                          <AlertDescription className="text-sm text-muted-foreground">
                            {rec.action}
                          </AlertDescription>
                        </div>
                      </div>
                    </Alert>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {!diagnostic && !isLoading && (
          <div className="text-center text-muted-foreground py-8">
            点击刷新按钮开始诊断
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DiagnosticPanel;
