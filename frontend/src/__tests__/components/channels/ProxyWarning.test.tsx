/**
 * 代理警告组件测试
 * Task 18.4 - Validates: Requirements 1.3, 7.6
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProxyWarning } from '../../../components/channels/ProxyWarning';
import { ProxyInfo } from '../../../types/channels';

describe('ProxyWarning Component', () => {
  const mockOnSwitchMode = vi.fn();
  const mockOnOpenSettings = vi.fn();

  beforeEach(() => {
    mockOnSwitchMode.mockReset();
    mockOnOpenSettings.mockReset();
  });

  describe('Rendering', () => {
    /**
     * 测试无代理时不渲染
     */
    it('should not render when proxyInfo is null', () => {
      const { container } = render(<ProxyWarning proxyInfo={null} />);
      expect(container.firstChild).toBeNull();
    });

    /**
     * 测试无代理检测成功状态
     */
    it('should render success state when no proxy detected', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'none',
        proxy_mode: 'none',
        process_name: null,
        process_pid: null,
        api_address: null,
        is_tun_enabled: false,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('未检测到代理')).toBeInTheDocument();
      expect(screen.getByText(/WinDivert 透明捕获模式/)).toBeInTheDocument();
    });

    /**
     * 测试系统代理模式成功状态
     */
    it('should render success state for system proxy mode', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'system_proxy',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: '127.0.0.1:9090',
        is_tun_enabled: false,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('代理配置正常')).toBeInTheDocument();
      expect(screen.getByText(/系统代理模式/)).toBeInTheDocument();
    });

    /**
     * 测试TUN模式警告
     * Validates: Requirements 1.3
     */
    it('should render warning for TUN mode', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'tun',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: '127.0.0.1:9090',
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('检测到 TUN 模式')).toBeInTheDocument();
      expect(screen.getByText(/流量捕获失败/)).toBeInTheDocument();
    });

    /**
     * 测试Fake-IP模式提示
     * Validates: Requirements 7.6
     */
    it('should render info for Fake-IP mode', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash_meta',
        proxy_mode: 'fake_ip',
        process_name: 'mihomo.exe',
        process_pid: 5678,
        api_address: '127.0.0.1:9090',
        is_tun_enabled: false,
        is_fake_ip_enabled: true,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('检测到 Fake-IP 模式')).toBeInTheDocument();
      expect(screen.getByText(/IP 识别替代方案/)).toBeInTheDocument();
    });

    /**
     * 测试Clash Verge TUN模式指导
     */
    it('should show Clash Verge specific guidance for TUN mode', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash_verge',
        proxy_mode: 'tun',
        process_name: 'Clash Verge.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('检测到 TUN 模式')).toBeInTheDocument();
      expect(screen.getByText(/Clash Verge 设置/)).toBeInTheDocument();
    });

    /**
     * 测试显示进程名徽章
     */
    it('should display process name badge', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'tun',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('clash.exe')).toBeInTheDocument();
    });

    /**
     * 测试显示API地址
     */
    it('should display API address when available', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'tun',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: '127.0.0.1:9090',
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('API: 127.0.0.1:9090')).toBeInTheDocument();
    });

    /**
     * 测试加载状态
     */
    it('should render loading state', () => {
      render(<ProxyWarning proxyInfo={null} isLoading={true} />);

      expect(screen.getByText('正在检测代理...')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    /**
     * 测试切换模式按钮
     */
    it('should call onSwitchMode when clicking switch mode button', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'tun',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(
        <ProxyWarning 
          proxyInfo={proxyInfo} 
          onSwitchMode={mockOnSwitchMode}
        />
      );

      const switchButton = screen.getByText('切换捕获模式');
      fireEvent.click(switchButton);

      expect(mockOnSwitchMode).toHaveBeenCalled();
    });

    /**
     * 测试打开设置按钮
     */
    it('should call onOpenSettings when clicking open settings button', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'tun',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(
        <ProxyWarning 
          proxyInfo={proxyInfo} 
          onOpenSettings={mockOnOpenSettings}
        />
      );

      const settingsButton = screen.getByText('打开代理设置');
      fireEvent.click(settingsButton);

      expect(mockOnOpenSettings).toHaveBeenCalled();
    });

    /**
     * 测试不显示按钮当没有处理函数
     */
    it('should not show buttons when handlers not provided', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'tun',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.queryByText('切换捕获模式')).not.toBeInTheDocument();
      expect(screen.queryByText('打开代理设置')).not.toBeInTheDocument();
    });
  });

  describe('Different Proxy Types', () => {
    /**
     * 测试V2Ray代理
     */
    it('should handle V2Ray proxy', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'v2ray',
        proxy_mode: 'tun',
        process_name: 'v2ray.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('检测到 TUN 模式')).toBeInTheDocument();
      expect(screen.getByText(/V2Ray 配置/)).toBeInTheDocument();
    });

    /**
     * 测试Surge代理
     */
    it('should handle Surge proxy', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'surge',
        proxy_mode: 'tun',
        process_name: 'surge.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('检测到 TUN 模式')).toBeInTheDocument();
      expect(screen.getByText(/Surge 设置/)).toBeInTheDocument();
    });

    /**
     * 测试其他代理类型
     */
    it('should handle other proxy types', () => {
      const proxyInfo: ProxyInfo = {
        proxy_type: 'other',
        proxy_mode: 'tun',
        process_name: 'unknown-proxy.exe',
        process_pid: 1234,
        api_address: null,
        is_tun_enabled: true,
        is_fake_ip_enabled: false,
      };

      render(<ProxyWarning proxyInfo={proxyInfo} />);

      expect(screen.getByText('检测到 TUN 模式')).toBeInTheDocument();
      expect(screen.getByText(/关闭代理软件的 TUN/)).toBeInTheDocument();
    });
  });
});
