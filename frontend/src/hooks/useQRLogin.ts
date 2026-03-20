/**
 * QR登录状态管理Hook
 * 实现二维码登录的状态管理和轮询逻辑
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { invoke } from '../components/TauriIntegration';
import {
  QRLoginState,
  QRLoginStatus,
  QRCodeResponse,
  QRStatusResponse,
  QRSupportedPlatform,
  getStatusMessage,
} from '../types/qr-login';

/** 轮询间隔（毫秒） */
const POLLING_INTERVAL_MS = 2000;

/** 终止状态 - 到达这些状态后停止轮询 */
const TERMINAL_STATUSES: QRLoginStatus[] = ['success', 'expired', 'error'];

/**
 * 初始状态
 */
const initialState: QRLoginState = {
  isOpen: false,
  platform: null,
  platformNameZh: '',
  status: 'loading',
  message: '',
  qrcodeUrl: null,
  qrcodeKey: null,
  expiresIn: 0,
  pollingInterval: null,
};

/**
 * QR登录Hook
 */
export function useQRLogin(onSuccess?: (platformId: string) => void) {
  const [state, setState] = useState<QRLoginState>(initialState);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  /**
   * 清理轮询定时器
   */
  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  /**
   * 安全更新状态（检查组件是否已卸载）
   */
  const safeSetState = useCallback((updater: Partial<QRLoginState> | ((prev: QRLoginState) => QRLoginState)) => {
    if (isMountedRef.current) {
      if (typeof updater === 'function') {
        setState(updater);
      } else {
        setState(prev => ({ ...prev, ...updater }));
      }
    }
  }, []);

  /**
   * 检查扫码状态
   */
  const checkStatus = useCallback(async (platformId: string, platformNameZh: string) => {
    try {
      const response = await invoke('qr_login_check_status', { platformId }) as QRStatusResponse;

      if (!isMountedRef.current) return;

      const newStatus = response.status;
      const message = response.message || getStatusMessage(newStatus, platformNameZh);

      safeSetState({
        status: newStatus,
        message,
      });

      // 如果到达终止状态，停止轮询
      if (TERMINAL_STATUSES.includes(newStatus)) {
        clearPolling();

        // 登录成功回调
        if (newStatus === 'success' && onSuccess) {
          onSuccess(platformId);
        }
      }
    } catch (error: any) {
      if (!isMountedRef.current) return;

      console.error('Failed to check QR login status:', error);
      safeSetState({
        status: 'error',
        message: getStatusMessage('error', platformNameZh, error.message),
      });
      clearPolling();
    }
  }, [clearPolling, onSuccess, safeSetState]);

  /**
   * 开始轮询
   */
  const startPolling = useCallback((platformId: string, platformNameZh: string) => {
    clearPolling();

    // 立即检查一次
    checkStatus(platformId, platformNameZh);

    // 设置定时轮询
    pollingRef.current = setInterval(() => {
      checkStatus(platformId, platformNameZh);
    }, POLLING_INTERVAL_MS);
  }, [checkStatus, clearPolling]);

  /**
   * 获取二维码
   */
  const fetchQRCode = useCallback(async (platformId: string, platformNameZh: string) => {
    safeSetState({
      status: 'loading',
      message: getStatusMessage('loading'),
      qrcodeUrl: null,
      qrcodeKey: null,
    });

    try {
      const response = await invoke('qr_login_get_qrcode', { platformId }) as QRCodeResponse;

      if (!isMountedRef.current) return;

      safeSetState({
        status: 'waiting',
        message: response.message || getStatusMessage('waiting', platformNameZh),
        qrcodeUrl: response.qrcode_url,
        qrcodeKey: response.qrcode_key,
        expiresIn: response.expires_in,
      });

      // 开始轮询状态
      startPolling(platformId, platformNameZh);
    } catch (error: any) {
      if (!isMountedRef.current) return;

      console.error('Failed to get QR code:', error);
      safeSetState({
        status: 'error',
        message: getStatusMessage('error', platformNameZh, error.message),
      });
    }
  }, [safeSetState, startPolling]);

  /**
   * 打开QR登录弹窗
   */
  const openQRLogin = useCallback((platform: QRSupportedPlatform) => {
    safeSetState({
      isOpen: true,
      platform: platform.platform_id,
      platformNameZh: platform.platform_name_zh,
      status: 'loading',
      message: getStatusMessage('loading'),
      qrcodeUrl: null,
      qrcodeKey: null,
      expiresIn: platform.qr_expiry_seconds,
    });

    // 获取二维码
    fetchQRCode(platform.platform_id, platform.platform_name_zh);
  }, [fetchQRCode, safeSetState]);

  /**
   * 关闭QR登录弹窗
   */
  const closeQRLogin = useCallback(async () => {
    clearPolling();

    // 如果有正在进行的登录，取消它
    if (state.platform) {
      try {
        await invoke('qr_login_cancel', { platformId: state.platform });
      } catch (error) {
        console.error('Failed to cancel QR login:', error);
      }
    }

    safeSetState(initialState);
  }, [clearPolling, safeSetState, state.platform]);

  /**
   * 刷新二维码
   */
  const refreshQRCode = useCallback(() => {
    if (state.platform && state.platformNameZh) {
      fetchQRCode(state.platform, state.platformNameZh);
    }
  }, [fetchQRCode, state.platform, state.platformNameZh]);

  /**
   * 获取支持扫码登录的平台列表
   */
  const getSupportedPlatforms = useCallback(async (): Promise<QRSupportedPlatform[]> => {
    try {
      const response = await invoke('qr_login_get_supported_platforms', {}) as { platforms: QRSupportedPlatform[] };
      return response.platforms || [];
    } catch (error) {
      console.error('Failed to get supported platforms:', error);
      return [];
    }
  }, []);

  /**
   * 组件卸载时清理
   */
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      clearPolling();
    };
  }, [clearPolling]);

  return {
    state,
    openQRLogin,
    closeQRLogin,
    refreshQRCode,
    getSupportedPlatforms,
    isTerminalStatus: TERMINAL_STATUSES.includes(state.status),
  };
}

export { POLLING_INTERVAL_MS, TERMINAL_STATUSES };
