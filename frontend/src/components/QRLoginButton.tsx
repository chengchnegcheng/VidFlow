/**
 * QR登录按钮组件
 * 为支持扫码登录的平台显示扫码登录按钮
 */
import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { QrCode } from 'lucide-react';
import { QRLoginDialog } from './QRLoginDialog';
import { useQRLogin } from '../hooks/useQRLogin';
import { QRSupportedPlatform } from '../types/qr-login';

interface QRLoginButtonProps {
  /** 平台ID */
  platformId: string;
  /** 平台中文名称 */
  platformNameZh: string;
  /** 登录成功回调 */
  onSuccess?: () => void;
  /** 是否禁用 */
  disabled?: boolean;
  /** 按钮大小 */
  size?: 'default' | 'sm' | 'lg' | 'icon';
  /** 按钮变体 */
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  /** 自定义类名 */
  className?: string;
}

/**
 * QR登录按钮组件
 */
export const QRLoginButton: React.FC<QRLoginButtonProps> = ({
  platformId,
  platformNameZh: _platformNameZh,
  onSuccess,
  disabled = false,
  size = 'sm',
  variant = 'outline',
  className = '',
}) => {
  const [supportedPlatforms, setSupportedPlatforms] = useState<QRSupportedPlatform[]>([]);
  const [isSupported, setIsSupported] = useState(false);
  const [isEnabled, setIsEnabled] = useState(false);

  const {
    state,
    openQRLogin,
    closeQRLogin,
    refreshQRCode,
    getSupportedPlatforms,
    isTerminalStatus,
  } = useQRLogin(onSuccess);

  // 加载支持的平台列表
  useEffect(() => {
    const loadPlatforms = async () => {
      const platforms = await getSupportedPlatforms();
      setSupportedPlatforms(platforms);
      
      // 检查当前平台是否支持扫码登录
      const platform = platforms.find(p => p.platform_id === platformId);
      setIsSupported(!!platform);
      setIsEnabled(platform?.enabled ?? false);
    };

    loadPlatforms();
  }, [platformId, getSupportedPlatforms]);

  // 处理点击
  const handleClick = () => {
    const platform = supportedPlatforms.find(p => p.platform_id === platformId);
    if (platform) {
      openQRLogin(platform);
    }
  };

  // 如果平台不支持扫码登录或未启用，不显示按钮
  if (!isSupported || !isEnabled) {
    return null;
  }

  return (
    <>
      <Button
        variant={variant}
        size={size}
        onClick={handleClick}
        disabled={disabled || state.isOpen}
        className={`${className}`}
      >
        <QrCode className="size-4 mr-2" />
        扫码登录
      </Button>

      <QRLoginDialog
        state={state}
        onClose={closeQRLogin}
        onRefresh={refreshQRCode}
        isTerminalStatus={isTerminalStatus}
      />
    </>
  );
};

export default QRLoginButton;
