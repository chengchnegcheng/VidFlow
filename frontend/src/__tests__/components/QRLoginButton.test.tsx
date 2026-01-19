/**
 * QR登录按钮组件测试
 * Property 7: QR Login Button Visibility
 * Validates: Requirements 5.2
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QRLoginButton } from '../../components/QRLoginButton';

// Mock TauriIntegration
vi.mock('../../components/TauriIntegration', () => ({
  invoke: vi.fn(),
}));

import { invoke } from '../../components/TauriIntegration';

const mockInvoke = vi.mocked(invoke);

describe('QRLoginButton Component', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  describe('Property 7: QR Login Button Visibility', () => {
    /**
     * Property 7.1: 支持且启用的平台显示按钮
     * 对于支持扫码登录且已启用的平台，应显示扫码登录按钮
     */
    it('should display QR login button for supported and enabled platform', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return {
            platforms: [
              { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: true },
              { platform_id: 'douyin', platform_name_zh: '抖音', qr_expiry_seconds: 180, enabled: true },
            ]
          };
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="bilibili"
          platformNameZh="哔哩哔哩"
        />
      );

      await waitFor(() => {
        expect(screen.getByText('扫码登录')).toBeInTheDocument();
      });
    });

    /**
     * Property 7.2: 不支持的平台不显示按钮
     * 对于不支持扫码登录的平台，不应显示扫码登录按钮
     */
    it('should not display QR login button for unsupported platform', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return {
            platforms: [
              { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: true },
            ]
          };
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="youtube"
          platformNameZh="YouTube"
        />
      );

      // 等待异步加载完成
      await waitFor(() => {
        expect(mockInvoke).toHaveBeenCalledWith('qr_login_get_supported_platforms', {});
      });

      // 按钮不应该存在
      expect(screen.queryByText('扫码登录')).not.toBeInTheDocument();
    });

    /**
     * Property 7.3: 已禁用的平台不显示按钮
     * 对于支持但已禁用扫码登录的平台，不应显示扫码登录按钮
     */
    it('should not display QR login button for disabled platform', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return {
            platforms: [
              { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: false },
            ]
          };
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="bilibili"
          platformNameZh="哔哩哔哩"
        />
      );

      // 等待异步加载完成
      await waitFor(() => {
        expect(mockInvoke).toHaveBeenCalledWith('qr_login_get_supported_platforms', {});
      });

      // 按钮不应该存在
      expect(screen.queryByText('扫码登录')).not.toBeInTheDocument();
    });

    /**
     * Property 7.4: 多平台支持验证
     * 验证多个平台的按钮可见性
     */
    it('should correctly show/hide buttons for multiple platforms', async () => {
      const platforms = [
        { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: true },
        { platform_id: 'douyin', platform_name_zh: '抖音', qr_expiry_seconds: 180, enabled: true },
        { platform_id: 'kuaishou', platform_name_zh: '快手', qr_expiry_seconds: 180, enabled: false },
      ];

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return { platforms };
        }
        return {};
      });

      // 测试启用的平台
      const { rerender } = render(
        <QRLoginButton platformId="bilibili" platformNameZh="哔哩哔哩" />
      );

      await waitFor(() => {
        expect(screen.getByText('扫码登录')).toBeInTheDocument();
      });

      // 测试另一个启用的平台
      rerender(
        <QRLoginButton platformId="douyin" platformNameZh="抖音" />
      );

      await waitFor(() => {
        expect(screen.getByText('扫码登录')).toBeInTheDocument();
      });

      // 测试禁用的平台
      rerender(
        <QRLoginButton platformId="kuaishou" platformNameZh="快手" />
      );

      await waitFor(() => {
        expect(mockInvoke).toHaveBeenCalled();
      });

      // 禁用的平台不应显示按钮
      expect(screen.queryByText('扫码登录')).not.toBeInTheDocument();
    });

    /**
     * Property 7.5: 空平台列表处理
     * 当没有支持的平台时，不应显示按钮
     */
    it('should not display button when no platforms are supported', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return { platforms: [] };
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="bilibili"
          platformNameZh="哔哩哔哩"
        />
      );

      await waitFor(() => {
        expect(mockInvoke).toHaveBeenCalledWith('qr_login_get_supported_platforms', {});
      });

      expect(screen.queryByText('扫码登录')).not.toBeInTheDocument();
    });

    /**
     * Property 7.6: API错误处理
     * 当获取平台列表失败时，不应显示按钮
     */
    it('should not display button when API fails', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          throw new Error('Network error');
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="bilibili"
          platformNameZh="哔哩哔哩"
        />
      );

      await waitFor(() => {
        expect(mockInvoke).toHaveBeenCalledWith('qr_login_get_supported_platforms', {});
      });

      expect(screen.queryByText('扫码登录')).not.toBeInTheDocument();
    });
  });

  describe('Button Props', () => {
    /**
     * 测试禁用状态
     */
    it('should be disabled when disabled prop is true', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return {
            platforms: [
              { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: true },
            ]
          };
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="bilibili"
          platformNameZh="哔哩哔哩"
          disabled={true}
        />
      );

      await waitFor(() => {
        const button = screen.getByText('扫码登录');
        expect(button.closest('button')).toBeDisabled();
      });
    });

    /**
     * 测试自定义类名
     */
    it('should apply custom className', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'qr_login_get_supported_platforms') {
          return {
            platforms: [
              { platform_id: 'bilibili', platform_name_zh: '哔哩哔哩', qr_expiry_seconds: 180, enabled: true },
            ]
          };
        }
        return {};
      });

      render(
        <QRLoginButton
          platformId="bilibili"
          platformNameZh="哔哩哔哩"
          className="custom-class"
        />
      );

      await waitFor(() => {
        const button = screen.getByText('扫码登录').closest('button');
        expect(button).toHaveClass('custom-class');
      });
    });
  });
});
