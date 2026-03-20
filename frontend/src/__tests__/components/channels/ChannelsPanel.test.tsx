import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChannelsPanel } from '../../../components/channels/ChannelsPanel';

const startSnifferMock = vi.fn();
const stopSnifferMock = vi.fn();
const clearVideosMock = vi.fn();
const addVideoManuallyMock = vi.fn();
const downloadVideoMock = vi.fn();
const updateConfigMock = vi.fn();
const initializeMock = vi.fn();
const fetchCertInfoMock = vi.fn();
const generateCertMock = vi.fn();
const downloadCertMock = vi.fn();
const installRootCertMock = vi.fn();
const installWechatP12Mock = vi.fn();
const getCertInstructionsMock = vi.fn();
const fetchDriverStatusMock = vi.fn();
const installDriverMock = vi.fn();
const requestAdminRestartMock = vi.fn();
const updateCaptureConfigMock = vi.fn();
const toggleQUICBlockingMock = vi.fn();

let snifferControlProps: any = null;

vi.mock('../../../hooks/useChannelsSniffer', () => ({
  useChannelsSniffer: () => ({
    state: {
      status: {
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
      },
      videos: [],
      certInfo: null,
      config: {
        proxy_port: 8888,
        download_dir: '',
        auto_decrypt: true,
        auto_clean_wechat_cache: true,
        quality_preference: 'best',
        clear_on_exit: false,
      },
      isLoading: false,
      error: null,
    },
    isRunning: false,
    startSniffer: startSnifferMock,
    stopSniffer: stopSnifferMock,
    clearVideos: clearVideosMock,
    addVideoManually: addVideoManuallyMock,
    downloadVideo: downloadVideoMock,
    updateConfig: updateConfigMock,
    initialize: initializeMock,
    driverStatus: {
      state: 'installed',
      version: '2.2.2',
      path: 'C:\\tools\\WinDivert.dll',
      error_message: null,
      is_admin: true,
    },
    captureConfig: {
      capture_mode: 'transparent',
      use_windivert: true,
      quic_blocking_enabled: false,
      target_processes: ['WeChatAppEx.exe'],
      no_detection_timeout: 60,
      log_unrecognized_domains: true,
    },
    captureStatistics: null,
    captureState: 'stopped',
    captureStartedAt: null,
    fetchCertInfo: fetchCertInfoMock,
    generateCert: generateCertMock,
    downloadCert: downloadCertMock,
    installRootCert: installRootCertMock,
    installWechatP12: installWechatP12Mock,
    getCertInstructions: getCertInstructionsMock,
    proxyInfo: null,
    quicStatus: {
      blocking_enabled: false,
      packets_blocked: 0,
      packets_allowed: 0,
      target_processes: ['WeChatAppEx.exe'],
    },
    fetchDriverStatus: fetchDriverStatusMock,
    installDriver: installDriverMock,
    requestAdminRestart: requestAdminRestartMock,
    updateCaptureConfig: updateCaptureConfigMock,
    toggleQUICBlocking: toggleQUICBlockingMock,
  }),
}));

vi.mock('../../../components/TauriIntegration', () => ({
  invoke: vi.fn(async (command: string) => {
    if (command === 'channels_get_download_tasks') {
      return [];
    }
    return null;
  }),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('../../../components/channels/SnifferControl', () => ({
  SnifferControl: (props: any) => {
    snifferControlProps = props;
    return (
      <button onClick={() => props.onStart()} type="button">
        start-sniffer
      </button>
    );
  },
}));

vi.mock('../../../components/channels/VideoList', () => ({
  VideoList: () => <div>video-list</div>,
}));

vi.mock('../../../components/channels/DownloadTaskList', () => ({
  DownloadTaskList: () => <div>download-task-list</div>,
}));

vi.mock('../../../components/channels/DriverInstallDialog', () => ({
  DriverInstallDialog: () => null,
}));

vi.mock('../../../components/channels/CertificateDialog', () => ({
  CertificateDialog: () => null,
}));

vi.mock('../../../components/channels/ProcessSelector', () => ({
  ProcessSelector: () => <div>process-selector</div>,
}));

vi.mock('../../../components/channels/CaptureStatus', () => ({
  CaptureStatus: () => <div>capture-status</div>,
}));

vi.mock('../../../components/channels/DiagnosticPanel', () => ({
  DiagnosticPanel: () => <div>diagnostic-panel</div>,
}));

describe('ChannelsPanel', () => {
  beforeEach(() => {
    snifferControlProps = null;
    startSnifferMock.mockReset();
    startSnifferMock.mockResolvedValue({ success: true, capture_mode: 'transparent' });
  });

  it('starts the sniffer with the configured transparent mode', async () => {
    render(<ChannelsPanel />);

    expect(snifferControlProps?.captureMode).toBe('transparent');

    fireEvent.click(screen.getByRole('button', { name: 'start-sniffer' }));

    expect(startSnifferMock).toHaveBeenCalledWith(undefined, 'transparent');
  });
});
