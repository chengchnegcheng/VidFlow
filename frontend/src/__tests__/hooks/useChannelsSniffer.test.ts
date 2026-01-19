/**
 * 微信视频号嗅探器 Hook 测试
 * Validates: Requirements 1.1, 1.5, 2.5
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { 
  useChannelsSniffer, 
  STATUS_POLLING_INTERVAL_MS, 
  VIDEOS_POLLING_INTERVAL_MS 
} from '../../hooks/useChannelsSniffer';
import { SnifferState } from '../../types/channels';

// Mock TauriIntegration
vi.mock('../../components/TauriIntegration', () => ({
  invoke: vi.fn(),
}));

import { invoke } from '../../components/TauriIntegration';

const mockInvoke = vi.mocked(invoke);

// Mock 嗅探器状态响应
const mockStoppedStatus = {
  state: 'stopped' as SnifferState,
  proxy_address: null,
  proxy_port: 8888,
  videos_detected: 0,
  started_at: null,
  error_message: null,
};

const mockRunningStatus = {
  state: 'running' as SnifferState,
  proxy_address: '127.0.0.1:8888' as string | null,
  proxy_port: 8888,
  videos_detected: 2,
  started_at: '2026-01-11T00:00:00Z' as string | null,
  error_message: null as string | null,
};

// Mock 视频列表
const mockVideos = [
  {
    id: 'video-1',
    url: 'https://finder.video.qq.com/video1.mp4',
    title: '测试视频1',
    duration: 120,
    resolution: '1080p',
    filesize: 10485760,
    thumbnail: null,
    detected_at: '2026-01-11T00:00:00Z',
    encryption_type: 'none',
    decryption_key: null,
  },
  {
    id: 'video-2',
    url: 'https://finder.video.qq.com/video2.mp4',
    title: '测试视频2',
    duration: 60,
    resolution: '720p',
    filesize: 5242880,
    thumbnail: null,
    detected_at: '2026-01-11T00:01:00Z',
    encryption_type: 'xor',
    decryption_key: 'abc123',
  },
];

// Mock 证书信息
const mockCertInfo = {
  exists: true,
  valid: true,
  expires_at: '2027-01-11T00:00:00Z',
  fingerprint: 'AA:BB:CC:DD:EE:FF',
  path: '/path/to/cert.pem',
};

// Mock 配置
const mockConfig = {
  proxy_port: 8888,
  download_dir: '/downloads',
  auto_decrypt: true,
  quality_preference: 'best',
  clear_on_exit: false,
};

describe('useChannelsSniffer Hook', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
    // 默认 mock 所有 API 调用
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'channels_get_status') {
        return mockStoppedStatus;
      }
      if (cmd === 'channels_get_videos') {
        return [];
      }
      if (cmd === 'channels_get_cert_info') {
        return mockCertInfo;
      }
      if (cmd === 'channels_get_config') {
        return mockConfig;
      }
      return {};
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Polling Configuration', () => {
    /**
     * 验证状态轮询间隔为 2000ms
     */
    it('should have status polling interval of 2000ms', () => {
      expect(STATUS_POLLING_INTERVAL_MS).toBe(2000);
    });

    /**
     * 验证视频列表轮询间隔为 1000ms
     */
    it('should have videos polling interval of 1000ms', () => {
      expect(VIDEOS_POLLING_INTERVAL_MS).toBe(1000);
    });
  });

  describe('Initial State', () => {
    /**
     * 测试初始状态（在 API 调用之前）
     */
    it('should have correct initial state', async () => {
      const { result } = renderHook(() => useChannelsSniffer());

      // 初始状态检查（在 useEffect 执行前）
      expect(result.current.state.videos).toEqual([]);
      expect(result.current.state.error).toBeNull();
      
      // 等待初始化完成
      await act(async () => {
        vi.advanceTimersByTime(100);
      });
    });
  });

  describe('State Transitions', () => {
    /**
     * 测试启动嗅探器状态转换
     * Validates: Requirements 1.1
     */
    it('should transition to running state when starting sniffer', async () => {
      let currentStatus = mockStoppedStatus;
      
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          return currentStatus;
        }
        if (cmd === 'channels_start_sniffer') {
          currentStatus = mockRunningStatus;
          return {
            success: true,
            proxy_address: '127.0.0.1:8888',
            error_message: null,
            error_code: null,
          };
        }
        if (cmd === 'channels_get_videos') {
          return mockVideos;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      // 等待初始化
      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      // 启动嗅探器
      await act(async () => {
        await result.current.startSniffer();
        vi.advanceTimersByTime(100);
      });

      expect(result.current.state.status?.state).toBe('running');
    });

    /**
     * 测试停止嗅探器状态转换
     * Validates: Requirements 1.5
     */
    it('should transition to stopped state when stopping sniffer', async () => {
      let currentStatus = mockRunningStatus;
      
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          return currentStatus;
        }
        if (cmd === 'channels_stop_sniffer') {
          currentStatus = mockStoppedStatus;
          return { success: true, message: '嗅探器已停止' };
        }
        if (cmd === 'channels_get_videos') {
          return [];
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      // 等待初始化
      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      // 停止嗅探器
      await act(async () => {
        await result.current.stopSniffer();
        vi.advanceTimersByTime(100);
      });

      expect(result.current.state.status?.state).toBe('stopped');
    });
  });

  describe('Video List Management', () => {
    /**
     * 测试获取视频列表
     * Validates: Requirements 2.5
     */
    it('should fetch and update video list', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          return mockRunningStatus;
        }
        if (cmd === 'channels_get_videos') {
          return mockVideos;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      // 等待初始化
      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      // 手动获取视频列表
      await act(async () => {
        await result.current.fetchVideos();
      });

      expect(result.current.state.videos).toEqual(mockVideos);
      expect(result.current.state.videos.length).toBe(2);
    });

    /**
     * 测试清空视频列表
     */
    it('should clear video list', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_videos') {
          return mockVideos;
        }
        if (cmd === 'channels_clear_videos') {
          return { success: true, message: '视频列表已清空' };
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      // 等待初始化
      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      // 先获取视频
      await act(async () => {
        await result.current.fetchVideos();
      });

      expect(result.current.state.videos.length).toBe(2);

      // 清空视频列表
      await act(async () => {
        await result.current.clearVideos();
      });

      expect(result.current.state.videos).toEqual([]);
    });
  });

  describe('Download Operations', () => {
    /**
     * 测试下载视频
     */
    it('should download video successfully', async () => {
      const downloadResponse = {
        success: true,
        file_path: '/downloads/video.mp4',
        file_size: 10485760,
        error: null,
        error_code: null,
        task_id: 'task-123',
      };

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_download_video') {
          return downloadResponse;
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      let response;
      await act(async () => {
        response = await result.current.downloadVideo({
          url: 'https://finder.video.qq.com/video.mp4',
          quality: 'best',
        });
      });

      expect(response).toEqual(downloadResponse);
      expect(response.success).toBe(true);
      expect(response.file_path).toBe('/downloads/video.mp4');
    });

    /**
     * 测试取消下载
     */
    it('should cancel download', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_cancel_download') {
          return { success: true, message: '下载已取消' };
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.cancelDownload('task-123');
      });

      expect(mockInvoke).toHaveBeenCalledWith('channels_cancel_download', { task_id: 'task-123' });
    });
  });

  describe('Certificate Management', () => {
    /**
     * 测试获取证书信息
     */
    it('should fetch certificate info', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.fetchCertInfo();
      });

      expect(result.current.state.certInfo).toEqual(mockCertInfo);
      expect(result.current.state.certInfo?.valid).toBe(true);
    });

    /**
     * 测试生成证书
     */
    it('should generate certificate', async () => {
      const generateResponse = {
        success: true,
        cert_path: '/path/to/new-cert.pem',
        error_message: null,
      };

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_generate_cert') {
          return generateResponse;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      let response;
      await act(async () => {
        response = await result.current.generateCert();
      });

      expect(response).toEqual(generateResponse);
      expect(response.success).toBe(true);
    });
  });

  describe('Configuration Management', () => {
    /**
     * 测试获取配置
     */
    it('should fetch configuration', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.fetchConfig();
      });

      expect(result.current.state.config).toEqual(mockConfig);
      expect(result.current.state.config?.proxy_port).toBe(8888);
    });

    /**
     * 测试更新配置
     */
    it('should update configuration', async () => {
      const updatedConfig = { ...mockConfig, proxy_port: 9999 };

      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_update_config') {
          return { success: true, message: '配置已更新' };
        }
        if (cmd === 'channels_get_config') {
          return updatedConfig;
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.updateConfig({ proxy_port: 9999 });
      });

      expect(result.current.state.config?.proxy_port).toBe(9999);
    });
  });

  describe('Error Handling', () => {
    /**
     * 测试启动嗅探器失败
     */
    it('should handle start sniffer error', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_start_sniffer') {
          return {
            success: false,
            proxy_address: null,
            error_message: '端口已被占用',
            error_code: 'PORT_IN_USE',
          };
        }
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      await act(async () => {
        await result.current.startSniffer();
      });

      expect(result.current.state.error).toBeTruthy();
    });

    /**
     * 测试网络错误处理
     */
    it('should handle network error', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          throw new Error('网络连接失败');
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.fetchStatus();
      });

      expect(result.current.state.error).toBe('网络连接失败');
    });
  });

  describe('Computed Properties', () => {
    /**
     * 测试计算属性
     */
    it('should compute isRunning correctly', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          return mockRunningStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.fetchStatus();
      });

      expect(result.current.isRunning).toBe(true);
      expect(result.current.isStopped).toBe(false);
    });

    it('should compute isStopped correctly', async () => {
      mockInvoke.mockImplementation(async (cmd: string) => {
        if (cmd === 'channels_get_status') {
          return mockStoppedStatus;
        }
        if (cmd === 'channels_get_cert_info') {
          return mockCertInfo;
        }
        if (cmd === 'channels_get_config') {
          return mockConfig;
        }
        return {};
      });

      const { result } = renderHook(() => useChannelsSniffer());

      await act(async () => {
        await result.current.fetchStatus();
      });

      expect(result.current.isStopped).toBe(true);
      expect(result.current.isRunning).toBe(false);
    });
  });
});
