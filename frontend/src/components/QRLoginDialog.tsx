/**
 * QR登录弹窗组件
 * 实现平台选择、二维码显示、状态消息显示、刷新和关闭功能
 */
import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Alert, AlertDescription } from './ui/alert';
import { Loader2, RefreshCw, CheckCircle2, XCircle, Clock, QrCode, Smartphone } from 'lucide-react';
import { QRLoginState, QRLoginStatus } from '../types/qr-login';

interface QRLoginDialogProps {
  state: QRLoginState;
  onClose: () => void;
  onRefresh: () => void;
  isTerminalStatus: boolean;
}

/**
 * 状态图标映射
 */
const StatusIcon: React.FC<{ status: QRLoginStatus }> = ({ status }) => {
  switch (status) {
    case 'loading':
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    case 'waiting':
      return <Smartphone className="h-5 w-5 text-blue-500" />;
    case 'scanned':
      return <Clock className="h-5 w-5 text-yellow-500" />;
    case 'success':
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case 'expired':
      return <Clock className="h-5 w-5 text-orange-500" />;
    case 'error':
      return <XCircle className="h-5 w-5 text-red-500" />;
    default:
      return <QrCode className="h-5 w-5 text-gray-500" />;
  }
};

/**
 * 状态背景色映射
 */
const getStatusBgClass = (status: QRLoginStatus): string => {
  switch (status) {
    case 'success':
      return 'bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800';
    case 'scanned':
      return 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950 dark:border-yellow-800';
    case 'error':
      return 'bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800';
    case 'expired':
      return 'bg-orange-50 border-orange-200 dark:bg-orange-950 dark:border-orange-800';
    default:
      return 'bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800';
  }
};

/**
 * QR登录弹窗组件
 */
export const QRLoginDialog: React.FC<QRLoginDialogProps> = ({
  state,
  onClose,
  onRefresh,
  isTerminalStatus,
}) => {
  const { isOpen, platformNameZh, status, message, qrcodeUrl } = state;

  /**
   * 渲染二维码区域
   */
  const renderQRCode = () => {
    if (status === 'loading') {
      return (
        <div className="flex flex-col items-center justify-center h-64 bg-gray-50 dark:bg-gray-900 rounded-lg">
          <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
          <p className="text-sm text-muted-foreground">正在获取二维码...</p>
        </div>
      );
    }

    if (status === 'error' && !qrcodeUrl) {
      return (
        <div className="flex flex-col items-center justify-center h-64 bg-red-50 dark:bg-red-950 rounded-lg">
          <XCircle className="h-12 w-12 text-red-500 mb-4" />
          <p className="text-sm text-red-600 dark:text-red-400 text-center px-4">
            获取二维码失败
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            className="mt-4"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            重新获取
          </Button>
        </div>
      );
    }

    if (!qrcodeUrl) {
      return (
        <div className="flex flex-col items-center justify-center h-64 bg-gray-50 dark:bg-gray-900 rounded-lg">
          <QrCode className="h-12 w-12 text-gray-400 mb-4" />
          <p className="text-sm text-muted-foreground">暂无二维码</p>
        </div>
      );
    }

    // 判断是否为base64图片
    const isBase64 = qrcodeUrl.startsWith('data:image');
    const imgSrc = isBase64 ? qrcodeUrl : qrcodeUrl;

    return (
      <div className="flex flex-col items-center">
        <div className={`relative p-4 bg-white rounded-lg shadow-sm ${status === 'expired' ? 'opacity-50' : ''}`}>
          <img
            src={imgSrc}
            alt="登录二维码"
            className="w-48 h-48 object-contain"
            onError={(e) => {
              // 如果图片加载失败，显示占位符
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
          {status === 'expired' && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg">
              <div className="text-center text-white">
                <Clock className="h-8 w-8 mx-auto mb-2" />
                <p className="text-sm">二维码已过期</p>
              </div>
            </div>
          )}
          {status === 'success' && (
            <div className="absolute inset-0 flex items-center justify-center bg-green-500/80 rounded-lg">
              <div className="text-center text-white">
                <CheckCircle2 className="h-12 w-12 mx-auto mb-2" />
                <p className="text-sm font-medium">登录成功</p>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <QrCode className="h-5 w-5" />
            {platformNameZh} 扫码登录
          </DialogTitle>
          <DialogDescription>
            使用 {platformNameZh} APP 扫描下方二维码完成登录
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 二维码显示区域 */}
          {renderQRCode()}

          {/* 状态消息 */}
          <Alert className={getStatusBgClass(status)}>
            <StatusIcon status={status} />
            <AlertDescription className="ml-2">
              {message}
            </AlertDescription>
          </Alert>

          {/* 扫码提示 */}
          {status === 'waiting' && (
            <div className="text-center text-sm text-muted-foreground">
              <p>1. 打开 {platformNameZh} APP</p>
              <p>2. 扫描上方二维码</p>
              <p>3. 在手机上确认登录</p>
            </div>
          )}

          {status === 'scanned' && (
            <div className="text-center text-sm text-yellow-600 dark:text-yellow-400">
              <p>请在手机上点击确认登录</p>
            </div>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          {/* 刷新按钮 - 在过期或错误状态时显示 */}
          {(status === 'expired' || status === 'error') && (
            <Button
              variant="default"
              onClick={onRefresh}
              className="w-full sm:w-auto"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              重新获取二维码
            </Button>
          )}

          {/* 刷新按钮 - 在等待状态时也可用 */}
          {status === 'waiting' && (
            <Button
              variant="outline"
              onClick={onRefresh}
              className="w-full sm:w-auto"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              刷新二维码
            </Button>
          )}

          {/* 关闭按钮 */}
          <Button
            variant={isTerminalStatus && status === 'success' ? 'default' : 'outline'}
            onClick={onClose}
            className="w-full sm:w-auto"
          >
            {status === 'success' ? '完成' : '关闭'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default QRLoginDialog;
