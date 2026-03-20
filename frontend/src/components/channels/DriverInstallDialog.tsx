/**
 * 驱动安装对话框组件
 * 显示 WinDivert 驱动安装状态和安装操作
 */
import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Alert, AlertDescription } from '../ui/alert';
import { Badge } from '../ui/badge';
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Shield,
  AlertTriangle,
  Download,
  RefreshCw,
} from 'lucide-react';
import {
  DriverStatusResponse,
  DriverState,
  getDriverStateText,
  getErrorMessage,
} from '../../types/channels';

interface DriverInstallDialogProps {
  isOpen: boolean;
  onClose: () => void;
  driverStatus: DriverStatusResponse | null;
  isLoading: boolean;
  onInstall: () => Promise<any>;
  onRefresh: () => Promise<void>;
  onRequestAdmin: () => Promise<void>;
}

/**
 * 驱动状态图标
 */
const DriverStateIcon: React.FC<{ state: DriverState; className?: string }> = ({ state, className }) => {
  switch (state) {
    case 'installed':
      return <CheckCircle2 className={`h-5 w-5 text-green-500 ${className}`} />;
    case 'not_installed':
      return <XCircle className={`h-5 w-5 text-gray-500 ${className}`} />;
    case 'loading':
      return <Loader2 className={`h-5 w-5 text-blue-500 animate-spin ${className}`} />;
    case 'error':
      return <AlertTriangle className={`h-5 w-5 text-red-500 ${className}`} />;
    default:
      return <XCircle className={`h-5 w-5 text-gray-500 ${className}`} />;
  }
};

/**
 * 驱动状态徽章颜色
 */
const getDriverBadgeVariant = (state: DriverState): 'default' | 'secondary' | 'destructive' | 'outline' => {
  switch (state) {
    case 'installed':
      return 'default';
    case 'not_installed':
      return 'secondary';
    case 'loading':
      return 'outline';
    case 'error':
      return 'destructive';
    default:
      return 'secondary';
  }
};

/**
 * 驱动安装对话框组件
 */
export const DriverInstallDialog: React.FC<DriverInstallDialogProps> = ({
  isOpen,
  onClose,
  driverStatus,
  isLoading,
  onInstall,
  onRefresh,
  onRequestAdmin,
}) => {
  const [installing, setInstalling] = React.useState(false);
  const [installError, setInstallError] = React.useState<string | null>(null);

  const state = driverStatus?.state || 'not_installed';
  const isInstalled = state === 'installed';
  const isAdmin = driverStatus?.is_admin ?? false;

  /**
   * 处理安装
   */
  const handleInstall = async () => {
    setInstalling(true);
    setInstallError(null);

    try {
      const result = await onInstall();
      if (!result.success) {
        setInstallError(result.error_message || getErrorMessage(result.error_code));
      }
    } catch (error: any) {
      setInstallError(error.message || '安装失败');
    } finally {
      setInstalling(false);
    }
  };

  /**
   * 处理刷新
   */
  const handleRefresh = async () => {
    setInstallError(null);
    await onRefresh();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            WinDivert 驱动管理
          </DialogTitle>
          <DialogDescription>
            透明流量捕获需要安装 WinDivert 驱动
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* 驱动状态 */}
          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-3">
              <DriverStateIcon state={state} />
              <div>
                <p className="font-medium">驱动状态</p>
                <p className="text-sm text-muted-foreground">
                  {driverStatus?.version ? `版本 ${driverStatus.version}` : '未检测到版本'}
                </p>
              </div>
            </div>
            <Badge variant={getDriverBadgeVariant(state)}>
              {getDriverStateText(state)}
            </Badge>
          </div>

          {/* 管理员权限状态 */}
          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-3">
              {isAdmin ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
              )}
              <div>
                <p className="font-medium">管理员权限</p>
                <p className="text-sm text-muted-foreground">
                  {isAdmin ? '已获取管理员权限' : '需要管理员权限才能使用透明捕获'}
                </p>
              </div>
            </div>
            <Badge variant={isAdmin ? 'default' : 'secondary'}>
              {isAdmin ? '已获取' : '未获取'}
            </Badge>
          </div>

          {/* 驱动路径 */}
          {driverStatus?.path && (
            <div className="p-3 bg-muted rounded-lg">
              <p className="text-sm text-muted-foreground">驱动路径</p>
              <p className="text-sm font-mono break-all">{driverStatus.path}</p>
            </div>
          )}

          {/* 安装错误 */}
          {(installError || driverStatus?.error_message) && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {installError || driverStatus?.error_message}
              </AlertDescription>
            </Alert>
          )}

          {/* 未安装提示 */}
          {!isInstalled && !installError && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-2">
                  <p>WinDivert 驱动未安装，无法使用透明捕获模式。</p>
                  <p className="text-xs opacity-80">
                    安装驱动需要管理员权限。如果安装失败，请尝试以管理员身份重新启动 VidFlow。
                  </p>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* 非管理员提示 */}
          {!isAdmin && (
            <Alert>
              <Shield className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-2">
                  <p>当前未以管理员身份运行。</p>
                  <p className="text-xs opacity-80">
                    透明捕获模式需要管理员权限才能拦截系统流量。
                  </p>
                </div>
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            onClick={handleRefresh}
            disabled={isLoading || installing}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            刷新状态
          </Button>

          {!isAdmin && (
            <Button
              variant="outline"
              onClick={onRequestAdmin}
              disabled={isLoading || installing}
            >
              <Shield className="h-4 w-4 mr-2" />
              以管理员身份重启
            </Button>
          )}

          {!isInstalled && (
            <Button
              onClick={handleInstall}
              disabled={isLoading || installing || !isAdmin}
            >
              {installing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  安装中...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  安装驱动
                </>
              )}
            </Button>
          )}

          {isInstalled && (
            <Button onClick={onClose}>
              完成
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DriverInstallDialog;
