/**
 * 证书管理对话框组件
 * 显示根证书和微信兼容 P12 的状态，并提供生成/安装/下载入口
 */
import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Alert, AlertDescription } from '../ui/alert';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Download,
  RefreshCw,
  Loader2,
  Calendar,
  Fingerprint,
  FileText,
  KeyRound,
  Import,
} from 'lucide-react';
import {
  CertInfoResponse,
  CertGenerateResponse,
  CertInstallResponse,
} from '../../types/channels';

interface CertificateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  certInfo: CertInfoResponse | null;
  onGenerate: () => Promise<CertGenerateResponse>;
  onDownload: (format?: 'cer' | 'p12') => Promise<void>;
  onInstallRoot: () => Promise<CertInstallResponse>;
  onInstallWechatP12: () => Promise<CertInstallResponse>;
  onGetInstructions: () => Promise<string>;
}

export const CertificateDialog: React.FC<CertificateDialogProps> = ({
  isOpen,
  onClose,
  certInfo,
  onGenerate,
  onDownload,
  onInstallRoot,
  onInstallWechatP12,
  onGetInstructions,
}) => {
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [busyAction, setBusyAction] = React.useState<string | null>(null);
  const [instructions, setInstructions] = React.useState<string>('');
  const [showInstructions, setShowInstructions] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const loadInstructions = React.useCallback(async () => {
    try {
      const text = await onGetInstructions();
      setInstructions(text);
    } catch (err: any) {
      console.error('Failed to load instructions:', err);
    }
  }, [onGetInstructions]);

  React.useEffect(() => {
    if (isOpen) {
      loadInstructions();
    }
  }, [isOpen, loadInstructions]);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const result = await onGenerate();
      if (!result.success) {
        setError(result.error_message || '生成证书失败');
      }
    } catch (err: any) {
      setError(err.message || '生成证书失败');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async (format: 'cer' | 'p12') => {
    setBusyAction(`download:${format}`);
    setError(null);
    try {
      await onDownload(format);
    } catch (err: any) {
      setError(err.message || '下载证书失败');
    } finally {
      setBusyAction(null);
    }
  };

  const handleInstallRoot = async () => {
    setBusyAction('install-root');
    setError(null);
    try {
      const result = await onInstallRoot();
      if (!result.success) {
        setError(result.message || '安装系统根证书失败');
      }
    } catch (err: any) {
      setError(err.message || '安装系统根证书失败');
    } finally {
      setBusyAction(null);
    }
  };

  const handleInstallWechatP12 = async () => {
    setBusyAction('install-p12');
    setError(null);
    try {
      const result = await onInstallWechatP12();
      if (!result.success) {
        setError(result.message || '导入微信兼容 P12 失败');
      }
    } catch (err: any) {
      setError(err.message || '导入微信兼容 P12 失败');
    } finally {
      setBusyAction(null);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '未知';
    try {
      return new Date(dateStr).toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const getCertStatusIcon = () => {
    if (!certInfo?.exists) {
      return <ShieldAlert className="h-12 w-12 text-yellow-500" />;
    }
    if (certInfo.valid) {
      return <ShieldCheck className="h-12 w-12 text-green-500" />;
    }
    return <ShieldAlert className="h-12 w-12 text-red-500" />;
  };

  const getCertStatusText = () => {
    if (!certInfo?.exists) {
      return { text: '未生成', variant: 'secondary' as const };
    }
    if (certInfo.valid) {
      return { text: '有效', variant: 'default' as const };
    }
    return { text: '无效/未安装', variant: 'destructive' as const };
  };

  const statusInfo = getCertStatusText();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            HTTPS 证书管理
          </DialogTitle>
          <DialogDescription>
            微信 4.x 若只抓到 stodownload，通常还需要导入微信兼容 P12。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center gap-4 rounded-lg bg-muted p-4">
            {getCertStatusIcon()}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">证书状态</span>
                <Badge variant={statusInfo.variant}>
                  {statusInfo.text}
                </Badge>
              </div>

              {certInfo?.exists && (
                <div className="mt-2 space-y-1 text-sm text-muted-foreground min-w-0">
                  {certInfo.expires_at && (
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 flex-shrink-0" />
                      <span>有效期至: {formatDate(certInfo.expires_at)}</span>
                    </div>
                  )}
                  {certInfo.fingerprint && (
                    <div className="flex items-start gap-2 min-w-0">
                      <Fingerprint className="mt-0.5 h-4 w-4 flex-shrink-0" />
                      <span className="break-all font-mono text-xs">
                        {certInfo.fingerprint}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4 flex-shrink-0" />
                    <span>Windows 根证书：{certInfo.root_installed ? '已安装' : '未安装'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <KeyRound className="h-4 w-4 flex-shrink-0" />
                    <span>微信兼容 P12：{certInfo.wechat_p12_installed ? '已导入' : '未导入'}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Button
              variant={certInfo?.exists ? 'outline' : 'default'}
              onClick={handleGenerate}
              disabled={isGenerating}
              className="w-full"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {certInfo?.exists ? '重新生成' : '生成证书'}
                </>
              )}
            </Button>

            <Button
              variant="secondary"
              onClick={handleInstallRoot}
              disabled={busyAction !== null || !certInfo?.exists}
              className="w-full"
            >
              {busyAction === 'install-root' ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  安装中...
                </>
              ) : (
                <>
                  <Shield className="mr-2 h-4 w-4" />
                  安装系统 CER
                </>
              )}
            </Button>

            {certInfo?.exists && (
              <Button
                variant="default"
                onClick={handleInstallWechatP12}
                disabled={busyAction !== null}
                className="w-full"
              >
                {busyAction === 'install-p12' ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    导入中...
                  </>
                ) : (
                  <>
                    <Import className="mr-2 h-4 w-4" />
                    导入微信 P12
                  </>
                )}
              </Button>
            )}

            {certInfo?.exists && (
              <Button
                variant="default"
                onClick={() => handleDownload('p12')}
                disabled={busyAction !== null}
                className="w-full"
              >
                {busyAction === 'download:p12' ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    下载中...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    下载微信 P12
                  </>
                )}
              </Button>
            )}

            {certInfo?.exists && (
              <Button
                variant="outline"
                onClick={() => handleDownload('cer')}
                disabled={busyAction !== null}
                className="w-full sm:col-span-2"
              >
                {busyAction === 'download:cer' ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    下载中...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    下载系统 CER
                  </>
                )}
              </Button>
            )}
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            {certInfo?.wechat_p12_path && (
              <Alert>
                <AlertDescription className="break-all text-xs">
                  推荐优先处理微信兼容 P12：{certInfo.wechat_p12_path}
                </AlertDescription>
              </Alert>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowInstructions(!showInstructions)}
              className="w-full justify-start"
            >
              <FileText className="mr-2 h-4 w-4" />
              {showInstructions ? '隐藏安装说明' : '查看安装说明'}
            </Button>

            {showInstructions && instructions && (
              <ScrollArea className="h-48 rounded-lg border p-4">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <pre className="whitespace-pre-wrap text-xs">
                    {instructions}
                  </pre>
                </div>
              </ScrollArea>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CertificateDialog;
