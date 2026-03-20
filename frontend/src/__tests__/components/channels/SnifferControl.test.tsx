/**
 * 嗅探器控制组件测试
 * Validates: Requirements 1.1, 1.2, 1.5, 2.4, 2.5, 4.3
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SnifferControl } from '../../../components/channels/SnifferControl';
import { SnifferStatusResponse, CaptureModeInfo, ProxyInfo, QUICStatusResponse } from '../../../types/channels';

describe('SnifferControl Component', () => {
  const mockOnStart = vi.fn();
  const mockOnStop = vi.fn();
  const mockOnModeChange = vi.fn();
  const mockOnQUICToggle = vi.fn();

  const defaultProps = {
    status: null,
    isLoading: false,
    error: null,
    onStart: mockOnStart,
    onStop: mockOnStop,
  };

  beforeEach(() => {
    mockOnStart.mockReset();
    mockOnStop.mockReset();
    mockOnModeChange.mockReset();
    mockOnQUICToggle.mockReset();
  });

  describe('Rendering', () => {
    /**
     * 测试停止状态渲染
     */
    it('should render stopped state correctly', () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      render(<SnifferControl {...defaultProps} status={status} />);

      expect(screen.getByText('已停止')).toBeInTheDocument();
      expect(screen.getByText('开始嗅探')).toBeInTheDocument();
    });

    /**
     * 测试运行状态渲染
     * Validates: Requirements 1.2
     */
    it('should render running state with video count', () => {
      const status: SnifferStatusResponse = {
        state: 'running',
        proxy_address: '127.0.0.1:8888',
        proxy_port: 8888,
        videos_detected: 5,
        started_at: '2026-01-11T00:00:00Z',
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'running',
        capture_started_at: '2026-01-11T00:00:00Z',
        statistics: null,
      };

      render(<SnifferControl {...defaultProps} status={status} />);

      expect(screen.getByText('运行中')).toBeInTheDocument();
      expect(screen.getByText('停止嗅探')).toBeInTheDocument();
      expect(screen.getByText('已检测到 5 个视频')).toBeInTheDocument();
    });

    /**
     * 测试启动中状态渲染
     */
    it('should render starting state', () => {
      const status: SnifferStatusResponse = {
        state: 'starting',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'starting',
        capture_started_at: null,
        statistics: null,
      };

      render(<SnifferControl {...defaultProps} status={status} />);

      expect(screen.getByText('正在启动...')).toBeInTheDocument();
      expect(screen.getByText('启动中...')).toBeInTheDocument();
    });

    /**
     * 测试错误状态渲染
     */
    it('should render error message', () => {
      render(
        <SnifferControl 
          {...defaultProps} 
          error="端口已被占用" 
        />
      );

      expect(screen.getByText('端口已被占用')).toBeInTheDocument();
    });

    /**
     * 测试代理状态显示
     * Validates: Requirements 2.4
     */
    it('should display proxy info when detected', () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      const proxyInfo: ProxyInfo = {
        proxy_type: 'clash',
        proxy_mode: 'system_proxy',
        process_name: 'clash.exe',
        process_pid: 1234,
        api_address: '127.0.0.1:9090',
        is_tun_enabled: false,
        is_fake_ip_enabled: false,
      };

      render(<SnifferControl {...defaultProps} status={status} proxyInfo={proxyInfo} />);

      expect(screen.getByText('代理配置正常')).toBeInTheDocument();
      expect(screen.getByText(/Clash 使用系统代理模式/)).toBeInTheDocument();
    });

    /**
     * 测试QUIC阻止开关显示
     * Validates: Requirements 4.3
     */
    it('should display QUIC toggle when handler provided', () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      const quicStatus: QUICStatusResponse = {
        blocking_enabled: false,
        packets_blocked: 0,
        packets_allowed: 100,
        target_processes: ['WeChat.exe'],
      };

      render(
        <SnifferControl 
          {...defaultProps} 
          status={status} 
          quicStatus={quicStatus}
          onQUICToggle={mockOnQUICToggle}
        />
      );

      expect(screen.getByText('QUIC 阻止')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    /**
     * 测试点击启动按钮
     * Validates: Requirements 1.1
     */
    it('should call onStart when clicking start button', async () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      render(<SnifferControl {...defaultProps} status={status} />);

      const startButton = screen.getByText('开始嗅探');
      fireEvent.click(startButton);

      expect(mockOnStart).toHaveBeenCalled();
    });

    /**
     * 测试点击停止按钮
     * Validates: Requirements 1.5
     */
    it('should call onStop when clicking stop button', async () => {
      const status: SnifferStatusResponse = {
        state: 'running',
        proxy_address: '127.0.0.1:8888',
        proxy_port: 8888,
        videos_detected: 0,
        started_at: '2026-01-11T00:00:00Z',
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'running',
        capture_started_at: '2026-01-11T00:00:00Z',
        statistics: null,
      };

      render(<SnifferControl {...defaultProps} status={status} />);

      const stopButton = screen.getByText('停止嗅探');
      fireEvent.click(stopButton);

      expect(mockOnStop).toHaveBeenCalled();
    });

    /**
     * 测试加载状态禁用按钮
     */
    it('should disable button when loading', () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      render(<SnifferControl {...defaultProps} status={status} isLoading={true} />);

      const button = screen.getByRole('button', { name: /开始嗅探/i });
      expect(button).toBeDisabled();
    });

    /**
     * 测试QUIC开关交互
     * Validates: Requirements 4.3
     */
    it('should call onQUICToggle when toggling QUIC switch', async () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      const quicStatus: QUICStatusResponse = {
        blocking_enabled: false,
        packets_blocked: 0,
        packets_allowed: 100,
        target_processes: ['WeChat.exe'],
      };

      render(
        <SnifferControl 
          {...defaultProps} 
          status={status} 
          quicStatus={quicStatus}
          onQUICToggle={mockOnQUICToggle}
        />
      );

      const switchElement = screen.getByRole('switch');
      fireEvent.click(switchElement);

      expect(mockOnQUICToggle).toHaveBeenCalledWith(true);
    });
  });

  describe('Mode Selection', () => {
    /**
     * 测试模式选择显示
     * Validates: Requirements 2.4, 2.5
     */
    it('should display mode selector when modes available', () => {
      const status: SnifferStatusResponse = {
        state: 'stopped',
        proxy_address: null,
        proxy_port: 8888,
        videos_detected: 0,
        started_at: null,
        error_message: null,
        capture_mode: 'transparent',
        capture_state: 'stopped',
        capture_started_at: null,
        statistics: null,
      };

      const availableModes: CaptureModeInfo[] = [
        { mode: 'windivert', name: 'WinDivert透明捕获', description: '无需配置代理', available: true, recommended: false },
        { mode: 'clash_api', name: 'Clash API监控', description: '与Clash兼容', available: true, recommended: true },
        { mode: 'hybrid', name: '混合模式', description: '自动选择', available: true, recommended: false },
      ];

      render(
        <SnifferControl 
          {...defaultProps} 
          status={status} 
          availableModes={availableModes}
          currentMultiMode="hybrid"
        />
      );

      expect(screen.getByText('捕获模式')).toBeInTheDocument();
    });
  });
});
