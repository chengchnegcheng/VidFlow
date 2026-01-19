/**
 * 诊断面板组件测试
 * Task 18.4 - Validates: Requirements 7.1, 7.2, 7.4
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DiagnosticsPanel } from '../../../components/channels/DiagnosticsPanel';
import { DiagnosticInfo } from '../../../types/channels';

describe('DiagnosticsPanel Component', () => {
  const mockOnRefresh = vi.fn();

  const defaultProps = {
    diagnostics: null,
    isLoading: false,
    onRefresh: mockOnRefresh,
  };

  beforeEach(() => {
    mockOnRefresh.mockReset();
  });

  describe('Rendering', () => {
    /**
     * 测试空状态渲染
     */
    it('should render empty state when no diagnostics', () => {
      render(<DiagnosticsPanel {...defaultProps} />);

      expect(screen.getByText('诊断信息')).toBeInTheDocument();
      expect(screen.getByText('暂无检测到的SNI')).toBeInTheDocument();
    });

    /**
     * 测试SNI列表渲染
     * Validates: Requirements 7.1
     */
    it('should render SNI list when available', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: ['finder.video.qq.com', 'wxapp.tc.qq.com'],
        detected_ips: [],
        wechat_processes: [],
        proxy_info: null,
        recent_errors: [],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      expect(screen.getByText('finder.video.qq.com')).toBeInTheDocument();
      expect(screen.getByText('wxapp.tc.qq.com')).toBeInTheDocument();
    });

    /**
     * 测试IP列表渲染
     * Validates: Requirements 7.2
     */
    it('should render IP list when available', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: [],
        detected_ips: ['183.3.0.0/16', '14.17.0.0/16'],
        wechat_processes: [],
        proxy_info: null,
        recent_errors: [],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      // Click on IP tab
      const ipTab = screen.getByRole('tab', { name: /IP/i });
      fireEvent.click(ipTab);

      expect(screen.getByText('183.3.0.0/16')).toBeInTheDocument();
      expect(screen.getByText('14.17.0.0/16')).toBeInTheDocument();
    });

    /**
     * 测试微信进程列表渲染
     */
    it('should render WeChat process list', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: [],
        detected_ips: [],
        wechat_processes: [
          {
            pid: 1234,
            name: 'WeChat.exe',
            exe_path: 'C:\\Program Files\\WeChat\\WeChat.exe',
            ports: [12345, 12346],
            last_seen: '2026-01-17T10:00:00Z',
          },
        ],
        proxy_info: null,
        recent_errors: [],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      // Click on process tab
      const processTab = screen.getByRole('tab', { name: /进程/i });
      fireEvent.click(processTab);

      expect(screen.getByText('WeChat.exe')).toBeInTheDocument();
      expect(screen.getByText('PID: 1234')).toBeInTheDocument();
    });

    /**
     * 测试代理信息渲染
     */
    it('should render proxy info', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: [],
        detected_ips: [],
        wechat_processes: [],
        proxy_info: {
          proxy_type: 'clash',
          proxy_mode: 'system_proxy',
          process_name: 'clash.exe',
          process_pid: 5678,
          api_address: '127.0.0.1:9090',
          is_tun_enabled: false,
          is_fake_ip_enabled: false,
        },
        recent_errors: [],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      // Click on proxy tab
      const proxyTab = screen.getByRole('tab', { name: /代理/i });
      fireEvent.click(proxyTab);

      expect(screen.getByText('Clash')).toBeInTheDocument();
      expect(screen.getByText('系统代理')).toBeInTheDocument();
    });

    /**
     * 测试统计信息渲染
     * Validates: Requirements 7.4
     */
    it('should render statistics', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: [],
        detected_ips: [],
        wechat_processes: [],
        proxy_info: null,
        recent_errors: [],
        capture_log: [],
        statistics: {
          packets_intercepted: 1000,
          videos_detected: 5,
        },
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      // Click on stats tab
      const statsTab = screen.getByRole('tab', { name: /统计/i });
      fireEvent.click(statsTab);

      expect(screen.getByText('1,000')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    /**
     * 测试错误日志渲染
     */
    it('should render error log when errors exist', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: [],
        detected_ips: [],
        wechat_processes: [],
        proxy_info: null,
        recent_errors: ['Connection timeout', 'API error'],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      expect(screen.getByText('最近错误')).toBeInTheDocument();
      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
      expect(screen.getByText('API error')).toBeInTheDocument();
    });

    /**
     * 测试SNI数量徽章
     */
    it('should show SNI count badge', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: ['sni1', 'sni2', 'sni3'],
        detected_ips: [],
        wechat_processes: [],
        proxy_info: null,
        recent_errors: [],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    /**
     * 测试刷新按钮
     */
    it('should call onRefresh when clicking refresh button', async () => {
      render(<DiagnosticsPanel {...defaultProps} />);

      const refreshButton = screen.getByRole('button');
      fireEvent.click(refreshButton);

      expect(mockOnRefresh).toHaveBeenCalled();
    });

    /**
     * 测试加载状态
     */
    it('should show loading state on refresh button', () => {
      render(<DiagnosticsPanel {...defaultProps} isLoading={true} />);

      const refreshButton = screen.getByRole('button');
      expect(refreshButton).toBeDisabled();
    });

    /**
     * 测试标签页切换
     */
    it('should switch tabs correctly', () => {
      const diagnostics: DiagnosticInfo = {
        detected_snis: ['test.sni.com'],
        detected_ips: ['192.168.1.1'],
        wechat_processes: [],
        proxy_info: null,
        recent_errors: [],
        capture_log: [],
        statistics: {},
      };

      render(<DiagnosticsPanel {...defaultProps} diagnostics={diagnostics} />);

      // Initially on SNI tab
      expect(screen.getByText('test.sni.com')).toBeInTheDocument();

      // Switch to IP tab
      const ipTab = screen.getByRole('tab', { name: /IP/i });
      fireEvent.click(ipTab);

      expect(screen.getByText('192.168.1.1')).toBeInTheDocument();
    });
  });
});
