/**
 * 微信视频号嗅探器状态管理 Hook
 * 实现嗅探器的状态管理、视频列表轮询和下载操作
 * 支持透明捕获模式
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { invoke, getApiBaseUrl } from '../components/TauriIntegration';
import {
  ChannelsSnifferState,
  SnifferStatusResponse,
  SnifferStartResponse,
  SnifferStopResponse,
  DetectedVideo,
  DownloadRequest,
  DownloadResponse,
  CertInfoResponse,
  CertGenerateResponse,
  CertInstallResponse,
  ChannelsConfigResponse,
  ChannelsConfigUpdateRequest,
  CaptureMode,
  DriverStatusResponse,
  DriverInstallResponse,
  CaptureConfigResponse,
  CaptureConfigUpdateRequest,
  CaptureStatistics,
  CaptureState,
  getErrorMessage,
  // 深度优化相关类型（Task 19.1）
  ProxyInfo,
  DiagnosticInfo,
  MultiCaptureMode,
  CaptureModesResponse,
  SwitchModeResponse,
  QUICStatusResponse,
  MultiModeConfigResponse,
  MultiModeConfigUpdateRequest,
} from '../types/channels';

/** 状态轮询间隔（毫秒） */
const STATUS_POLLING_INTERVAL_MS = 2000;

/** 视频列表轮询间隔（毫秒）- 从 1s 调整到 2s */
const VIDEOS_POLLING_INTERVAL_MS = 2000;

/** 连续失败熔断阈值 */
const MAX_CONSECUTIVE_FAILURES = 5;

/** 熔断后的等待时间（毫秒） */
const CIRCUIT_BREAKER_COOLDOWN_MS = 15000;

/**
 * 初始状态
 */
const initialState: ChannelsSnifferState = {
  status: null,
  videos: [],
  certInfo: null,
  config: null,
  isLoading: false,
  error: null,
};

/**
 * 微信视频号嗅探器 Hook
 */
export function useChannelsSniffer() {
  const [state, setState] = useState<ChannelsSnifferState>(initialState);
  const [driverStatus, setDriverStatus] = useState<DriverStatusResponse | null>(null);
  const [captureConfig, setCaptureConfig] = useState<CaptureConfigResponse | null>(null);
  const [captureStatistics, setCaptureStatistics] = useState<CaptureStatistics | null>(null);
  const [captureState, setCaptureState] = useState<CaptureState>('stopped');
  const [captureStartedAt, setCaptureStartedAt] = useState<string | null>(null);

  // 深度优化相关状态（Task 19.1）
  const [proxyInfo, setProxyInfo] = useState<ProxyInfo | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticInfo | null>(null);
  const [captureModes, setCaptureModes] = useState<CaptureModesResponse | null>(null);
  const [quicStatus, setQuicStatus] = useState<QUICStatusResponse | null>(null);
  const [multiModeConfig, setMultiModeConfig] = useState<MultiModeConfigResponse | null>(null);

  const statusPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const videosPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);
  const fetchVideosRef = useRef<() => Promise<void>>(async () => {});

  // 熔断器状态
  const statusFailureCountRef = useRef(0);
  const videosFailureCountRef = useRef(0);
  const statusCircuitOpenRef = useRef(false);
  const videosCircuitOpenRef = useRef(false);

  /**
   * 安全更新状态
   */
  const safeSetState = useCallback((updater: Partial<ChannelsSnifferState> | ((prev: ChannelsSnifferState) => ChannelsSnifferState)) => {
    if (isMountedRef.current) {
      if (typeof updater === 'function') {
        setState(updater);
      } else {
        setState(prev => ({ ...prev, ...updater }));
      }
    }
  }, []);

  /**
   * 清理状态轮询
   */
  const clearStatusPolling = useCallback(() => {
    if (statusPollingRef.current) {
      clearInterval(statusPollingRef.current);
      statusPollingRef.current = null;
    }
  }, []);

  /**
   * 清理视频列表轮询
   */
  const clearVideosPolling = useCallback(() => {
    if (videosPollingRef.current) {
      clearInterval(videosPollingRef.current);
      videosPollingRef.current = null;
    }
  }, []);

  /**
   * 清理所有轮询
   */
  const clearAllPolling = useCallback(() => {
    clearStatusPolling();
    clearVideosPolling();
  }, [clearStatusPolling, clearVideosPolling]);

  /**
   * 获取嗅探器状态（带熔断机制）
   */
  const fetchStatus = useCallback(async () => {
    // 熔断器打开时跳过请求
    if (statusCircuitOpenRef.current) {
      return;
    }

    try {
      const response = await invoke('channels_get_status', {}) as SnifferStatusResponse;
      if (!isMountedRef.current) return;

      // 请求成功，重置失败计数
      statusFailureCountRef.current = 0;

      safeSetState({ status: response, error: null });

      // 更新捕获统计
      if (response.statistics) {
        setCaptureStatistics(response.statistics);
      }
      setCaptureState(response.capture_state);
      setCaptureStartedAt(response.capture_started_at || null);

      // If sniffer is running, make sure videos polling is active.
      if (response.state === 'running' && !videosPollingRef.current) {
        clearVideosPolling();
        void fetchVideosRef.current();
        videosPollingRef.current = setInterval(() => {
          void fetchVideosRef.current();
        }, VIDEOS_POLLING_INTERVAL_MS);
      } else if (response.state !== 'running') {
        clearVideosPolling();
      }
    } catch (error: any) {
      if (!isMountedRef.current) return;
      console.error('Failed to fetch sniffer status:', error);

      // 增加失败计数
      statusFailureCountRef.current++;

      // 达到熔断阈值，打开熔断器
      if (statusFailureCountRef.current >= MAX_CONSECUTIVE_FAILURES) {
        console.warn(`Status polling circuit breaker opened after ${MAX_CONSECUTIVE_FAILURES} failures`);
        statusCircuitOpenRef.current = true;
        safeSetState({ error: '后端连接失败，正在重试...' });

        // 冷却后重置熔断器
        setTimeout(() => {
          if (isMountedRef.current) {
            console.log('Status polling circuit breaker reset');
            statusCircuitOpenRef.current = false;
            statusFailureCountRef.current = 0;
          }
        }, CIRCUIT_BREAKER_COOLDOWN_MS);
      } else {
        safeSetState({ error: error.message || '获取状态失败' });
      }
    }
  }, [safeSetState, clearVideosPolling]);

  /**
   * 获取检测到的视频列表（带熔断机制）
   */
  const fetchVideos = useCallback(async () => {
    // 熔断器打开时跳过请求
    if (videosCircuitOpenRef.current) {
      return;
    }

    try {
      const videos = await invoke('channels_get_videos', {}) as DetectedVideo[];
      if (!isMountedRef.current) return;

      // 请求成功，重置失败计数
      videosFailureCountRef.current = 0;

      // 调试：打印视频信息
      if (videos.length > 0) {
        console.log('[Channels] Fetched videos:', videos.map(v => ({
          id: v.id,
          title: v.title,
          thumbnail: v.thumbnail,
          url: v.url.substring(0, 50) + '...'
        })));
      }

      safeSetState({ videos });
    } catch (error: any) {
      if (!isMountedRef.current) return;
      console.error('Failed to fetch videos:', error);

      // 增加失败计数
      videosFailureCountRef.current++;

      // 达到熔断阈值，打开熔断器
      if (videosFailureCountRef.current >= MAX_CONSECUTIVE_FAILURES) {
        console.warn(`Videos polling circuit breaker opened after ${MAX_CONSECUTIVE_FAILURES} failures`);
        videosCircuitOpenRef.current = true;

        // 冷却后重置熔断器
        setTimeout(() => {
          if (isMountedRef.current) {
            console.log('Videos polling circuit breaker reset');
            videosCircuitOpenRef.current = false;
            videosFailureCountRef.current = 0;
          }
        }, CIRCUIT_BREAKER_COOLDOWN_MS);
      }
    }
  }, [safeSetState]);
  fetchVideosRef.current = fetchVideos;

  /**
   * 开始状态轮询
   */
  const startStatusPolling = useCallback(() => {
    clearStatusPolling();
    fetchStatus();
    statusPollingRef.current = setInterval(fetchStatus, STATUS_POLLING_INTERVAL_MS);
  }, [fetchStatus, clearStatusPolling]);

  /**
   * 开始视频列表轮询
   */
  const startVideosPolling = useCallback(() => {
    clearVideosPolling();
    fetchVideos();
    videosPollingRef.current = setInterval(fetchVideos, VIDEOS_POLLING_INTERVAL_MS);
  }, [fetchVideos, clearVideosPolling]);

  /**
   * 启动嗅探器
   */
  const startSniffer = useCallback(async (port?: number, captureMode?: CaptureMode): Promise<SnifferStartResponse> => {
    safeSetState({ isLoading: true, error: null });

    try {
      const response = await invoke('channels_start_sniffer', {
        port,
        capture_mode: captureMode,
      }) as SnifferStartResponse;

      if (!isMountedRef.current) return response;

      if (response.proxy_info !== undefined) {
        setProxyInfo(response.proxy_info ?? null);
      }

      if (response.success) {
        // 启动成功，开始轮询
        startStatusPolling();
        startVideosPolling();
      } else {
        safeSetState({
          error: response.error_message || getErrorMessage(response.error_code)
        });
      }

      safeSetState({ isLoading: false });
      return response;
    } catch (error: any) {
      if (!isMountedRef.current) throw error;

      const errorMessage = error.message || '启动嗅探器失败';
      safeSetState({ isLoading: false, error: errorMessage });
      throw error;
    }
  }, [safeSetState, startStatusPolling, startVideosPolling]);

  /**
   * 停止嗅探器
   */
  const stopSniffer = useCallback(async (): Promise<SnifferStopResponse> => {
    safeSetState({ isLoading: true, error: null });

    try {
      const response = await invoke('channels_stop_sniffer', {}) as SnifferStopResponse;

      if (!isMountedRef.current) return response;

      if (response.success) {
        clearVideosPolling();
      }

      safeSetState({ isLoading: false });
      await fetchStatus();
      return response;
    } catch (error: any) {
      if (!isMountedRef.current) throw error;

      const errorMessage = error.message || '停止嗅探器失败';
      safeSetState({ isLoading: false, error: errorMessage });
      throw error;
    }
  }, [safeSetState, clearVideosPolling, fetchStatus]);

  /**
   * 清空视频列表
   */
  const clearVideos = useCallback(async () => {
    try {
      await invoke('channels_clear_videos', {});
      safeSetState({ videos: [] });
    } catch (error: any) {
      console.error('Failed to clear videos:', error);
      safeSetState({ error: error.message || '清空视频列表失败' });
    }
  }, [safeSetState]);

  /**
   * 手动添加视频 URL
   */
  const addVideoManually = useCallback(async (url: string, title?: string) => {
    try {
      const response = await invoke('channels_add_video', { url, title }) as {
        success: boolean;
        video: DetectedVideo | null;
        error_message: string | null;
      };

      if (response.success && response.video) {
        // 刷新视频列表
        await fetchVideos();
      }

      return response;
    } catch (error: any) {
      console.error('Failed to add video manually:', error);
      throw error;
    }
  }, [fetchVideos]);

  /**
   * 下载视频
   */
  const downloadVideo = useCallback(async (request: DownloadRequest): Promise<DownloadResponse> => {
    try {
      const response = await invoke('channels_download_video', request) as DownloadResponse;
      return response;
    } catch (error: any) {
      console.error('Failed to download video:', error);
      throw error;
    }
  }, []);

  /**
   * 取消下载
   */
  const cancelDownload = useCallback(async (taskId: string) => {
    try {
      await invoke('channels_cancel_download', { task_id: taskId });
    } catch (error: any) {
      console.error('Failed to cancel download:', error);
      throw error;
    }
  }, []);

  /**
   * 获取证书信息
   */
  const fetchCertInfo = useCallback(async () => {
    try {
      const certInfo = await invoke('channels_get_cert_info', {}) as CertInfoResponse;
      if (!isMountedRef.current) return;

      safeSetState({ certInfo });
    } catch (error: any) {
      console.error('Failed to fetch cert info:', error);
    }
  }, [safeSetState]);

  /**
   * 生成证书
   */
  const generateCert = useCallback(async (): Promise<CertGenerateResponse> => {
    safeSetState({ isLoading: true });

    try {
      const response = await invoke('channels_generate_cert', {}) as CertGenerateResponse;

      if (!isMountedRef.current) return response;

      if (response.success) {
        await fetchCertInfo();
      }

      safeSetState({ isLoading: false });
      return response;
    } catch (error: any) {
      if (!isMountedRef.current) throw error;

      safeSetState({ isLoading: false, error: error.message || '生成证书失败' });
      throw error;
    }
  }, [safeSetState, fetchCertInfo]);

  /**
   * 导出证书
   */
  const exportCert = useCallback(async (exportPath: string, format: 'cer' | 'p12' = 'cer') => {
    try {
      const response = await invoke('channels_export_cert', { export_path: exportPath, format });
      return response;
    } catch (error: any) {
      console.error('Failed to export cert:', error);
      throw error;
    }
  }, []);

  /**
   * 下载证书（等待 API 初始化）
   */
  const downloadCert = useCallback(async (format: 'cer' | 'p12' = 'p12') => {
    try {
      const apiBaseUrl = getApiBaseUrl();

      // 检查 API_BASE 是否已初始化
      if (!apiBaseUrl) {
        safeSetState({ error: '后端未就绪，请稍后重试' });
        throw new Error('后端未就绪，请稍后重试');
      }

      window.open(`${apiBaseUrl}/api/channels/certificate/download?format=${format}`, '_blank');
    } catch (error: any) {
      console.error('Failed to download cert:', error);
      throw error;
    }
  }, [safeSetState]);

  /**
   * 安装系统根证书
   */
  const installRootCert = useCallback(async (): Promise<CertInstallResponse> => {
    safeSetState({ isLoading: true });

    try {
      const response = await invoke('channels_install_root_cert', {}) as CertInstallResponse;
      if (response.success) {
        await fetchCertInfo();
      }
      safeSetState({ isLoading: false });
      return response;
    } catch (error: any) {
      safeSetState({ isLoading: false, error: error.message || '安装系统根证书失败' });
      throw error;
    }
  }, [fetchCertInfo, safeSetState]);

  /**
   * 导入微信兼容 P12
   */
  const installWechatP12 = useCallback(async (): Promise<CertInstallResponse> => {
    safeSetState({ isLoading: true });

    try {
      const response = await invoke('channels_install_wechat_p12', {}) as CertInstallResponse;
      if (response.success) {
        await fetchCertInfo();
      }
      safeSetState({ isLoading: false });
      return response;
    } catch (error: any) {
      safeSetState({ isLoading: false, error: error.message || '导入微信兼容 P12 失败' });
      throw error;
    }
  }, [fetchCertInfo, safeSetState]);

  /**
   * 获取证书安装说明
   */
  const getCertInstructions = useCallback(async (): Promise<string> => {
    try {
      const response = await invoke('channels_get_cert_instructions', {}) as { instructions: string };
      return response.instructions;
    } catch (error: any) {
      console.error('Failed to get cert instructions:', error);
      return '获取说明失败';
    }
  }, []);

  /**
   * 获取配置
   */
  const fetchConfig = useCallback(async () => {
    try {
      const config = await invoke('channels_get_config', {}) as ChannelsConfigResponse;
      if (!isMountedRef.current) return;

      safeSetState({ config });
    } catch (error: any) {
      console.error('Failed to fetch config:', error);
    }
  }, [safeSetState]);

  /**
   * 更新配置
   */
  const updateConfig = useCallback(async (updates: ChannelsConfigUpdateRequest) => {
    try {
      await invoke('channels_update_config', updates);
      await fetchConfig();
    } catch (error: any) {
      console.error('Failed to update config:', error);
      throw error;
    }
  }, [fetchConfig]);

  // ============ 透明捕获相关方法 ============

  /**
   * 获取驱动状态
   */
  const fetchDriverStatus = useCallback(async () => {
    try {
      const status = await invoke('channels_get_driver_status', {}) as DriverStatusResponse;
      if (!isMountedRef.current) return;

      setDriverStatus(status);
    } catch (error: any) {
      console.error('Failed to fetch driver status:', error);
    }
  }, []);

  /**
   * 安装驱动
   */
  const installDriver = useCallback(async (): Promise<DriverInstallResponse> => {
    safeSetState({ isLoading: true });

    try {
      const response = await invoke('channels_install_driver', {}) as DriverInstallResponse;

      if (!isMountedRef.current) return response;

      if (response.success) {
        await fetchDriverStatus();
      }

      safeSetState({ isLoading: false });
      return response;
    } catch (error: any) {
      if (!isMountedRef.current) throw error;

      safeSetState({ isLoading: false, error: error.message || '安装驱动失败' });
      throw error;
    }
  }, [safeSetState, fetchDriverStatus]);

  /**
   * 请求管理员权限重启
   */
  const requestAdminRestart = useCallback(async () => {
    try {
      await invoke('channels_request_admin_restart', {});
    } catch (error: any) {
      console.error('Failed to request admin restart:', error);
      throw error;
    }
  }, []);

  /**
   * 获取捕获配置
   */
  const fetchCaptureConfig = useCallback(async () => {
    try {
      const config = await invoke('channels_get_capture_config', {}) as CaptureConfigResponse;
      if (!isMountedRef.current) return;

      setCaptureConfig(config);
    } catch (error: any) {
      console.error('Failed to fetch capture config:', error);
    }
  }, []);

  /**
   * 更新捕获配置
   */
  const updateCaptureConfig = useCallback(async (updates: CaptureConfigUpdateRequest) => {
    try {
      await invoke('channels_update_capture_config', updates);
      await fetchCaptureConfig();
    } catch (error: any) {
      console.error('Failed to update capture config:', error);
      throw error;
    }
  }, [fetchCaptureConfig]);

  /**
   * 获取捕获统计
   */
  const fetchCaptureStatistics = useCallback(async () => {
    try {
      const response = await invoke('channels_get_capture_statistics', {}) as {
        state: CaptureState;
        statistics: CaptureStatistics;
        started_at: string | null;
      };
      if (!isMountedRef.current) return;

      setCaptureStatistics(response.statistics);
      setCaptureState(response.state);
      setCaptureStartedAt(response.started_at);
    } catch (error: any) {
      console.error('Failed to fetch capture statistics:', error);
    }
  }, []);

  // ============ 深度优化相关方法（Task 19.1）============

  /**
   * 检测代理软件
   */
  const detectProxy = useCallback(async () => {
    try {
      const info = await invoke('channels_detect_proxy', {}) as ProxyInfo;
      if (!isMountedRef.current) return info;

      setProxyInfo(info);
      return info;
    } catch (error: any) {
      console.error('Failed to detect proxy:', error);
      return null;
    }
  }, []);

  /**
   * 获取诊断信息
   */
  const fetchDiagnostics = useCallback(async () => {
    try {
      const info = await invoke('channels_get_diagnostics', {}) as DiagnosticInfo;
      if (!isMountedRef.current) return info;

      setDiagnostics(info);
      return info;
    } catch (error: any) {
      console.error('Failed to fetch diagnostics:', error);
      return null;
    }
  }, []);

  /**
   * 获取可用捕获模式
   */
  const fetchCaptureModes = useCallback(async () => {
    try {
      const modes = await invoke('channels_get_modes', {}) as CaptureModesResponse;
      if (!isMountedRef.current) return modes;

      setCaptureModes(modes);
      return modes;
    } catch (error: any) {
      console.error('Failed to fetch capture modes:', error);
      return null;
    }
  }, []);

  /**
   * 切换捕获模式
   */
  const switchCaptureMode = useCallback(async (mode: MultiCaptureMode): Promise<SwitchModeResponse | null> => {
    try {
      const response = await invoke('channels_switch_mode', { mode }) as SwitchModeResponse;
      if (!isMountedRef.current) return response;

      if (response.success) {
        // 刷新模式列表
        await fetchCaptureModes();
      }

      return response;
    } catch (error: any) {
      console.error('Failed to switch capture mode:', error);
      return null;
    }
  }, [fetchCaptureModes]);

  /**
   * 获取QUIC状态
   */
  const fetchQUICStatus = useCallback(async () => {
    try {
      const status = await invoke('channels_get_quic_status', {}) as QUICStatusResponse;
      if (!isMountedRef.current) return status;

      setQuicStatus(status);
      return status;
    } catch (error: any) {
      console.error('Failed to fetch QUIC status:', error);
      return null;
    }
  }, []);

  /**
   * 切换QUIC阻止状态
   */
  const toggleQUICBlocking = useCallback(async (enabled: boolean): Promise<QUICStatusResponse | null> => {
    try {
      const status = await invoke('channels_toggle_quic', { enabled }) as QUICStatusResponse;
      if (!isMountedRef.current) return status;

      setQuicStatus(status);
      return status;
    } catch (error: any) {
      console.error('Failed to toggle QUIC blocking:', error);
      return null;
    }
  }, []);

  /**
   * 获取多模式配置
   */
  const fetchMultiModeConfig = useCallback(async () => {
    try {
      const config = await invoke('channels_get_multi_mode_config', {}) as MultiModeConfigResponse;
      if (!isMountedRef.current) return config;

      setMultiModeConfig(config);
      return config;
    } catch (error: any) {
      console.error('Failed to fetch multi-mode config:', error);
      return null;
    }
  }, []);

  /**
   * 更新多模式配置
   */
  const updateMultiModeConfig = useCallback(async (updates: MultiModeConfigUpdateRequest): Promise<MultiModeConfigResponse | null> => {
    try {
      const config = await invoke('channels_update_multi_mode_config', updates) as MultiModeConfigResponse;
      if (!isMountedRef.current) return config;

      setMultiModeConfig(config);
      return config;
    } catch (error: any) {
      console.error('Failed to update multi-mode config:', error);
      return null;
    }
  }, []);

  /**
   * 重置多模式配置
   */
  const resetMultiModeConfig = useCallback(async (): Promise<boolean> => {
    try {
      const response = await invoke('channels_reset_multi_mode_config', {}) as { success: boolean };
      if (!isMountedRef.current) return response.success;

      if (response.success) {
        await fetchMultiModeConfig();
      }

      return response.success;
    } catch (error: any) {
      console.error('Failed to reset multi-mode config:', error);
      return false;
    }
  }, [fetchMultiModeConfig]);

  /**
   * 导出多模式配置
   */
  const exportMultiModeConfig = useCallback(async (exportPath: string): Promise<boolean> => {
    try {
      const response = await invoke('channels_export_multi_mode_config', { export_path: exportPath }) as { success: boolean };
      return response.success;
    } catch (error: any) {
      console.error('Failed to export multi-mode config:', error);
      return false;
    }
  }, []);

  /**
   * 导入多模式配置
   */
  const importMultiModeConfig = useCallback(async (importPath: string): Promise<boolean> => {
    try {
      const response = await invoke('channels_import_multi_mode_config', { import_path: importPath }) as { success: boolean };
      if (!isMountedRef.current) return response.success;

      if (response.success) {
        await fetchMultiModeConfig();
      }

      return response.success;
    } catch (error: any) {
      console.error('Failed to import multi-mode config:', error);
      return false;
    }
  }, [fetchMultiModeConfig]);

  /**
   * 初始化
   */
  const initialize = useCallback(async () => {
    safeSetState({ isLoading: true });

    try {
      await Promise.all([
        fetchStatus(),
        fetchCertInfo(),
        fetchConfig(),
        fetchDriverStatus(),
        fetchCaptureConfig(),
        fetchCaptureStatistics(),
        // 深度优化相关初始化（Task 19.1）
        detectProxy(),
        fetchCaptureModes(),
        fetchQUICStatus(),
        fetchMultiModeConfig(),
      ]);
    } catch (error: any) {
      console.error('Failed to initialize:', error);
    } finally {
      safeSetState({ isLoading: false });
    }
  }, [fetchStatus, fetchCertInfo, fetchConfig, fetchDriverStatus, fetchCaptureConfig, fetchCaptureStatistics, detectProxy, fetchCaptureModes, fetchQUICStatus, fetchMultiModeConfig, safeSetState]);

  /**
   * 组件挂载时初始化
   * 优化：先等待初始化完成，再启动轮询
   */
  useEffect(() => {
    isMountedRef.current = true;

    // 先初始化，完成后再启动状态轮询
    initialize().then(() => {
      if (isMountedRef.current) {
        startStatusPolling();
      }
    });

    return () => {
      isMountedRef.current = false;
      clearAllPolling();
    };
  }, []);

  return {
    // 状态
    state,
    isRunning: state.status?.state === 'running',
    isStopped: state.status?.state === 'stopped',
    isStarting: state.status?.state === 'starting',
    isStopping: state.status?.state === 'stopping',
    hasError: state.status?.state === 'error',

    // 嗅探器操作
    startSniffer,
    stopSniffer,
    fetchStatus,

    // 视频操作
    fetchVideos,
    clearVideos,
    addVideoManually,
    downloadVideo,
    cancelDownload,

    // 证书操作
    fetchCertInfo,
    generateCert,
    exportCert,
    downloadCert,
    installRootCert,
    installWechatP12,
    getCertInstructions,

    // 配置操作
    fetchConfig,
    updateConfig,

    // 透明捕获相关
    driverStatus,
    captureConfig,
    captureStatistics,
    captureState,
    captureStartedAt,
    fetchDriverStatus,
    installDriver,
    requestAdminRestart,
    fetchCaptureConfig,
    updateCaptureConfig,
    fetchCaptureStatistics,

    // 深度优化相关（Task 19.1）
    proxyInfo,
    diagnostics,
    captureModes,
    quicStatus,
    multiModeConfig,
    detectProxy,
    fetchDiagnostics,
    fetchCaptureModes,
    switchCaptureMode,
    fetchQUICStatus,
    toggleQUICBlocking,
    fetchMultiModeConfig,
    updateMultiModeConfig,
    resetMultiModeConfig,
    exportMultiModeConfig,
    importMultiModeConfig,

    // 初始化
    initialize,
  };
}

export { STATUS_POLLING_INTERVAL_MS, VIDEOS_POLLING_INTERVAL_MS, MAX_CONSECUTIVE_FAILURES, CIRCUIT_BREAKER_COOLDOWN_MS };
