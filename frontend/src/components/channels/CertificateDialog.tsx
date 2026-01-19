/**
 * 证书管理对话框组件
 * 显示证书状态、生成/导出按钮和安装说明
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
  FileText
} from 'lucide-react';
import { CertInfoResponse, CertGenerateResponse } from '../../types/channels';

interface CertificateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  certInfo: CertInfoResponse | null;
  onGenerate: () => Promise<CertGenerateResponse>;
  onDownload: () => Promise<void>;
  onGetInstructions: () => Promise<string>;
}

/**
 * 证书管理对话框
 */
export const CertificateDialog: React.FC<CertificateDialogProps> = ({
  isOpen,
  onClose,
  certInfo,
  onGenerate,
  onDownload,
  onGetInstructions,
}) => {
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [isDownloading, setIsDownloading] = React.useState(false);
  const [instructions, setInstructions] = React.useState<string>('');
  const [showInstructions, setShowInstructions] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  /**
   * 加载安装说明
   */
  const loadInstructions = React.useCallback(async () => {
    try {
      const text = await onGetInstructions();
      setInstructions(text);
    } catch (err: any) {
      console.error('Failed to load instructions:', err);
    }
  }, [onGetInstructions]);

  /**
   * 对话框打开时加载说明
   */
  React.useEffect(() => {
    if (isOpen) {
      loadInstructions();
    }
  }, [isOpen, loadInstructions]);

  /**
   * 生成证书
   */
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

  /**
   * 下载证书
   */
  const handleDownload = async () => {
    setIsDownloading(true);
    setError(null);
    try {
      await onDownload();
    } catch (err: any) {
      setError(err.message || '下载证书失败');
    } finally {
      setIsDownloading(false);
    }
  };

  /**
   * 格式化日期
   */
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

  /**
   * 获取证书状态图标
   */
  const getCertStatusIcon = () => {
    if (!certInfo?.exists) {
      return <ShieldAlert className="h-12 w-12 text-yellow-500" />;
    }
    if (certInfo.valid) {
      return <ShieldCheck className="h-12 w-12 text-green-500" />;
    }
    return <ShieldAlert className="h-12 w-12 text-red-500" />;
  };

  /**
   * 获取证书状态文本
   */
  const getCertStatusText = () => {
    if (!certInfo?.exists) {
      return { text: '未生成', variant: 'secondary' as const };
    }
    if (certInfo.valid) {
      return { text: '有效', variant: 'default' as const };
    }
    return { text: '无效/已过期', variant: 'destructive' as const };
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
            HTTPS 代理需要安装 CA 证书才能解密加密流量
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 证书状态 */}
          <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
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
                      <Fingerprint className="h-4 w-4 flex-shrink-0 mt-0.5" />
                      <span className="font-mono text-xs break-all">
                        {certInfo.fingerprint}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2">
            <Button
              variant={certInfo?.exists ? 'outline' : 'default'}
              onClick={handleGenerate}
              disabled={isGenerating}
              className="flex-1"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {certInfo?.exists ? '重新生成' : '生成证书'}
                </>
              )}
            </Button>

            {certInfo?.exists && certInfo.valid && (
              <Button
                variant="default"
                onClick={handleDownload}
                disabled={isDownloading}
                className="flex-1"
              >
                {isDownloading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    下载中...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    下载证书
                  </>
                )}
              </Button>
            )}
          </div>

          {/* 错误提示 */}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* 安装说明 */}
          <div className="space-y-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowInstructions(!showInstructions)}
              className="w-full justify-start"
            >
              <FileText className="h-4 w-4 mr-2" />
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
