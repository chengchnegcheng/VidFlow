/**
 * QR登录相关类型定义
 */

/**
 * QR登录状态枚举
 */
export type QRLoginStatus = 'loading' | 'waiting' | 'scanned' | 'success' | 'expired' | 'error';

/**
 * 支持扫码登录的平台信息
 */
export interface QRSupportedPlatform {
  platform_id: string;
  platform_name_zh: string;
  qr_expiry_seconds: number;
  enabled: boolean;
}

/**
 * 二维码响应
 */
export interface QRCodeResponse {
  qrcode_url: string;
  qrcode_key: string;
  expires_in: number;
  message: string;
}

/**
 * 扫码状态响应
 */
export interface QRStatusResponse {
  status: QRLoginStatus;
  message: string;
}

/**
 * QR登录状态
 */
export interface QRLoginState {
  isOpen: boolean;
  platform: string | null;
  platformNameZh: string;
  status: QRLoginStatus;
  message: string;
  qrcodeUrl: string | null;
  qrcodeKey: string | null;
  expiresIn: number;
  pollingInterval: ReturnType<typeof setInterval> | null;
}

/**
 * 状态消息映射
 */
export const STATUS_MESSAGES: Record<QRLoginStatus, (platformName?: string) => string> = {
  loading: () => '正在获取二维码...',
  waiting: (platformName) => `请使用 ${platformName || '对应APP'} 扫描二维码`,
  scanned: () => '已扫码，请在手机上确认登录',
  success: (platformName) => `${platformName || '平台'} Cookie 获取成功并已保存`,
  expired: () => '二维码已过期，请重新获取',
  error: () => '网络请求失败，请重试',
};

/**
 * 获取状态消息
 */
export function getStatusMessage(status: QRLoginStatus, platformName?: string, errorMessage?: string): string {
  if (status === 'error' && errorMessage) {
    return `网络请求失败: ${errorMessage}`;
  }
  return STATUS_MESSAGES[status](platformName);
}
