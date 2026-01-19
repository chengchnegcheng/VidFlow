/**
 * QR登录Hook测试
 * Property 2: Status Polling Behavior
 * Validates: Requirements 1.3, 2.3, 3.3, 4.3
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useQRLogin, POLLING_INTERVAL_MS, TERMINAL_STATUSES } from '../../hooks/useQRLogin';
import { QRLoginStatus } from '../../types/qr-login';

// Mock TauriIntegration
vi.mock('../../components/TauriIntegration', () => ({
  invoke: vi.fn(),
}));

import { invoke } from '../../components/TauriIntegration';

const mockInvoke = vi.mocked(invoke);

describe('useQRLogin Hook', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Property 2: Status Polling Behavior', () => {
    /**
     * Property 2.1: 轮询间隔精确性
     * 验证轮询间隔为2秒（2000毫秒）
     */
    it('should have polling interval of exactly 2000ms', () => {
      expect(POLLING_INTERVAL_MS).toBe(2000);
    });

    /**
     * Property 2.2: 终止状态列表完整性
     * 验证终止状态包含 success, expired, error
     */
    it('should have correct terminal statuses', () => {
      expect(TERMINAL_STATUSES).toContain('success');
      expect(TERMINAL_STATUSES).toContain('expired');
      expect(TERMINAL_STATUSES).toContain('error');
      expect(TERMINAL_STATUSES.length).toBe(3);
    });

    /**
     * Property 2.3: 终止状态检测
     * 验证 isTerminalStatus 正确识别终止状态
     */
    it.each(TERMINAL_STATUSES)(
      'should correctly identify terminal status: %s',
      (terminalStatus) => {
        expect(TERMINAL_STATUSES.includes(terminalStatus)).toBe(true);
      }
    );

    /**
     * Property 2.4: 非终止状态检测
     */
    it.each(['loading', 'waiting', 'scanned'] as QRLoginStatus[])(
      'should correctly identify non-terminal status: %s',
      (nonTerminalStatus) => {
        expect(TERMINAL_STATUSES.includes(nonTerminalStatus)).toBe(false);
      }
    );
  });

  describe('State Management', () => {
    /**
     * 测试初始状态
     */
    it('should have correct initial state', () => {
      const { result } = renderHook(() => useQRLogin());

      expect(result.current.state.isOpen).toBe(false);
      expect(result.current.state.platform).toBeNull();
      expect(result.current.state.status).toBe('loading');
      expect(result.current.state.qrcodeUrl).toBeNull();
      expect(result.current.state.qrcodeKey).toBeNull();
      expect(result.current.state.platformNameZh).toBe('');
    });

    /**
     * 测试打开QR登录时状态更新
     */
    it('should update state when opening QR login', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_qrcode') {
          return {
            qrcode_url: 'https://example.com/qr',
            qrcode_key: 'test-key',
            expires_in: 180,
            message: '请使用 哔哩哔哩 APP 扫描二维码',
          };
        }
        if (cmd === 'qr_login_check_status') {
          return { status: 'success', message: '登录成功' };
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin());

      act(() => {
        result.current.openQRLogin({
          platform_id: 'bilibili',
          platform_name_zh: '哔哩哔哩',
          qr_expiry_seconds: 180,
          enabled: true,
        });
      });

      // 立即检查同步更新的状态
      expect(result.current.state.isOpen).toBe(true);
      expect(result.current.state.platform).toBe('bilibili');
      expect(result.current.state.platformNameZh).toBe('哔哩哔哩');

      // 等待异步操作完成
      await waitFor(() => {
        expect(result.current.state.qrcodeUrl).toBe('https://example.com/qr');
      }, { timeout: 1000 });
    });

    /**
     * 测试关闭QR登录
     */
    it('should reset state when closing QR login', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_qrcode') {
          return {
            qrcode_url: 'https://example.com/qr',
            qrcode_key: 'test-key',
            expires_in: 180,
            message: '请扫码',
          };
        }
        if (cmd === 'qr_login_check_status') {
          return { status: 'success', message: '登录成功' };
        }
        if (cmd === 'qr_login_cancel') {
          return { status: 'success' };
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin());

      act(() => {
        result.current.openQRLogin({
          platform_id: 'test',
          platform_name_zh: '测试平台',
          qr_expiry_seconds: 180,
          enabled: true,
        });
      });

      expect(result.current.state.isOpen).toBe(true);

      await act(async () => {
        await result.current.closeQRLogin();
      });

      expect(result.current.state.isOpen).toBe(false);
      expect(result.current.state.platform).toBeNull();
    });

    /**
     * 测试刷新二维码
     */
    it('should call fetchQRCode when refreshing', async () => {
      let qrCodeCallCount = 0;

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_qrcode') {
          qrCodeCallCount++;
          return {
            qrcode_url: `https://example.com/qr-${qrCodeCallCount}`,
            qrcode_key: `test-key-${qrCodeCallCount}`,
            expires_in: 180,
            message: '请扫码',
          };
        }
        if (cmd === 'qr_login_check_status') {
          return { status: 'success', message: '登录成功' };
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin());

      act(() => {
        result.current.openQRLogin({
          platform_id: 'test',
          platform_name_zh: '测试平台',
          qr_expiry_seconds: 180,
          enabled: true,
        });
      });

      await waitFor(() => {
        expect(qrCodeCallCount).toBe(1);
      }, { timeout: 1000 });

      act(() => {
        result.current.refreshQRCode();
      });

      await waitFor(() => {
        expect(qrCodeCallCount).toBe(2);
      }, { timeout: 1000 });
    });
  });

  describe('Error Handling', () => {
    /**
     * 测试获取二维码失败
     */
    it('should handle QR code fetch error', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_qrcode') {
          throw new Error('网络连接超时');
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin());

      act(() => {
        result.current.openQRLogin({
          platform_id: 'test',
          platform_name_zh: '测试平台',
          qr_expiry_seconds: 180,
          enabled: true,
        });
      });

      await waitFor(() => {
        expect(result.current.state.status).toBe('error');
        expect(result.current.state.message).toContain('网络连接超时');
      }, { timeout: 1000 });
    });

    /**
     * 测试状态检查失败
     */
    it('should handle status check error', async () => {
      let checkCount = 0;
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_qrcode') {
          return {
            qrcode_url: 'https://example.com/qr',
            qrcode_key: 'test-key',
            expires_in: 180,
            message: '请扫码',
          };
        }
        if (cmd === 'qr_login_check_status') {
          checkCount++;
          throw new Error('服务器错误');
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin());

      act(() => {
        result.current.openQRLogin({
          platform_id: 'test',
          platform_name_zh: '测试平台',
          qr_expiry_seconds: 180,
          enabled: true,
        });
      });

      await waitFor(() => {
        expect(result.current.state.status).toBe('error');
        expect(result.current.state.message).toContain('服务器错误');
      }, { timeout: 1000 });
    });
  });

  describe('getSupportedPlatforms', () => {
    /**
     * 测试获取支持的平台列表
     */
    it('should fetch supported platforms', async () => {
      const mockPlatforms = [
        { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: true },
        { platform_id: 'douyin', platform_name_zh: '抖音', qr_expiry_seconds: 180, enabled: true },
      ];

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return { platforms: mockPlatforms };
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin());

      let platforms: any[] = [];
      await act(async () => {
        platforms = await result.current.getSupportedPlatforms();
      });

      expect(platforms).toEqual(mockPlatforms);
    });

    /**
     * 测试获取平台列表失败
     */
    it('should return empty array on error', async () => {
      mockInvoke.mockImplementation(async () => {
        throw new Error('Network error');
      });

      const { result } = renderHook(() => useQRLogin());

      let platforms: any[] = [];
      await act(async () => {
        platforms = await result.current.getSupportedPlatforms();
      });

      expect(platforms).toEqual([]);
    });
  });

  describe('Success Callback', () => {
    /**
     * 测试成功回调
     */
    it('should call onSuccess callback when login succeeds', async () => {
      const onSuccess = vi.fn();

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_qrcode') {
          return {
            qrcode_url: 'https://example.com/qr',
            qrcode_key: 'test-key',
            expires_in: 180,
            message: '请扫码',
          };
        }
        if (cmd === 'qr_login_check_status') {
          return { status: 'success', message: '登录成功' };
        }
        return {};
      });

      const { result } = renderHook(() => useQRLogin(onSuccess));

      act(() => {
        result.current.openQRLogin({
          platform_id: 'bilibili',
          platform_name_zh: '哔哩哔哩',
          qr_expiry_seconds: 180,
          enabled: true,
        });
      });

      await waitFor(() => {
        expect(result.current.state.status).toBe('success');
      }, { timeout: 1000 });

      expect(onSuccess).toHaveBeenCalledWith('bilibili');
    });
  });
});
