/**
 * 微信视频号相关类型定义
 */

/**
 * 嗅探器状态枚举
 */
export type SnifferState = 'stopped' | 'starting' | 'running' | 'stopping' | 'error';

/**
 * 加密类型枚举
 */
export type EncryptionType = 'none' | 'xor' | 'aes' | 'unknown';

/**
 * 捕获模式枚举
 */
export type CaptureMode = 'proxy_only' | 'transparent';

/**
 * 驱动状态枚举
 */
export type DriverState = 'not_installed' | 'installed' | 'loading' | 'error';

/**
 * 捕获状态枚举
 */
export type CaptureState = 'stopped' | 'starting' | 'running' | 'stopping' | 'error';

/**
 * 检测到的视频
 */
export interface DetectedVideo {
  id: string;
  url: string;
  title: string | null;
  duration: number | null;
  resolution: string | null;
  filesize: number | null;
  thumbnail: string | null;
  detected_at: string;
  encryption_type: EncryptionType;
  decryption_key: string | null;
  is_placeholder?: boolean;
  placeholder_message?: string;
}

/**
 * 嗅探器状态响应
 */
export interface SnifferStatusResponse {
  state: SnifferState;
  proxy_address: string | null;
  proxy_port: number;
  videos_detected: number;
  started_at: string | null;
  error_message: string | null;
  capture_mode: CaptureMode;
  capture_state: CaptureState;
  capture_started_at: string | null;
  statistics: CaptureStatistics | null;
}

/**
 * 启动嗅探器请求
 */
export interface SnifferStartRequest {
  port?: number;
  capture_mode?: CaptureMode;
}

/**
 * 启动嗅探器响应
 */
export interface SnifferStartResponse {
  success: boolean;
  proxy_address: string | null;
  error_message: string | null;
  error_code: string | null;
  capture_mode: CaptureMode;
}

/**
 * 停止嗅探器响应
 */
export interface SnifferStopResponse {
  success: boolean;
  message: string;
}

/**
 * 下载请求
 */
export interface DownloadRequest {
  url: string;
  quality?: string;
  output_path?: string;
  auto_decrypt?: boolean;
  decryption_key?: string | null;  // 解密密钥（从视频信息中获取）
}

/**
 * 下载响应
 */
export interface DownloadResponse {
  success: boolean;
  file_path: string | null;
  file_size: number | null;
  error: string | null;
  error_code: string | null;
  task_id: string | null;
}

/**
 * 取消下载响应
 */
export interface CancelDownloadResponse {
  success: boolean;
  message: string;
}

/**
 * 证书信息响应
 */
export interface CertInfoResponse {
  exists: boolean;
  valid: boolean;
  expires_at: string | null;
  fingerprint: string | null;
  path: string | null;
}

/**
 * 证书生成响应
 */
export interface CertGenerateResponse {
  success: boolean;
  cert_path: string | null;
  error_message: string | null;
}

/**
 * 证书导出响应
 */
export interface CertExportResponse {
  success: boolean;
  message: string;
  path: string | null;
}

/**
 * 证书安装说明响应
 */
export interface CertInstructionsResponse {
  instructions: string;
}

/**
 * 配置响应
 */
export interface ChannelsConfigResponse {
  proxy_port: number;
  download_dir: string;
  auto_decrypt: boolean;
  quality_preference: string;
  clear_on_exit: boolean;
}

/**
 * 配置更新请求
 */
export interface ChannelsConfigUpdateRequest {
  proxy_port?: number;
  download_dir?: string;
  auto_decrypt?: boolean;
  quality_preference?: string;
  clear_on_exit?: boolean;
}

/**
 * 配置更新响应
 */
export interface ChannelsConfigUpdateResponse {
  success: boolean;
  message: string;
}

/**
 * 清空视频列表响应
 */
export interface ClearVideosResponse {
  success: boolean;
  message: string;
}

/**
 * 手动添加视频请求
 */
export interface AddVideoRequest {
  url: string;
  title?: string;
}

/**
 * 手动添加视频响应
 */
export interface AddVideoResponse {
  success: boolean;
  video: DetectedVideo | null;
  error_message: string | null;
}

/**
 * 视频号 Hook 状态
 */
export interface ChannelsSnifferState {
  status: SnifferStatusResponse | null;
  videos: DetectedVideo[];
  certInfo: CertInfoResponse | null;
  config: ChannelsConfigResponse | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * 错误码枚举
 */
export enum ErrorCode {
  PORT_IN_USE = 'PORT_IN_USE',
  PERMISSION_DENIED = 'PERMISSION_DENIED',
  CERT_MISSING = 'CERT_MISSING',
  CERT_EXPIRED = 'CERT_EXPIRED',
  CERT_INVALID = 'CERT_INVALID',
  NETWORK_ERROR = 'NETWORK_ERROR',
  VIDEO_EXPIRED = 'VIDEO_EXPIRED',
  DOWNLOAD_CANCELLED = 'DOWNLOAD_CANCELLED',
  DECRYPT_FAILED = 'DECRYPT_FAILED',
  UNKNOWN_ENCRYPTION = 'UNKNOWN_ENCRYPTION',
  // 透明捕获相关
  DRIVER_MISSING = 'DRIVER_MISSING',
  DRIVER_LOAD_FAILED = 'DRIVER_LOAD_FAILED',
  ADMIN_REQUIRED = 'ADMIN_REQUIRED',
  PROCESS_NOT_FOUND = 'PROCESS_NOT_FOUND',
  CAPTURE_FAILED = 'CAPTURE_FAILED',
}

/**
 * 错误消息映射
 */
export const ERROR_MESSAGES: Record<string, string> = {
  [ErrorCode.PORT_IN_USE]: '端口已被占用，请更换端口或关闭占用该端口的程序',
  [ErrorCode.PERMISSION_DENIED]: '没有权限启动代理服务，请以管理员身份运行或使用大于 1024 的端口',
  [ErrorCode.CERT_MISSING]: 'CA 证书不存在，请点击"生成证书"按钮',
  [ErrorCode.CERT_EXPIRED]: 'CA 证书已过期，请重新生成证书',
  [ErrorCode.CERT_INVALID]: 'CA 证书无效，请重新生成证书',
  [ErrorCode.NETWORK_ERROR]: '网络连接失败，请检查网络连接',
  [ErrorCode.VIDEO_EXPIRED]: '视频链接已过期，请重新嗅探获取新链接',
  [ErrorCode.DOWNLOAD_CANCELLED]: '下载已取消',
  [ErrorCode.DECRYPT_FAILED]: '视频解密失败，原始文件已保留',
  [ErrorCode.UNKNOWN_ENCRYPTION]: '未知的加密格式，该视频可能使用了新的加密方式',
  // 透明捕获相关
  [ErrorCode.DRIVER_MISSING]: 'WinDivert 驱动未安装，请点击"安装驱动"按钮',
  [ErrorCode.DRIVER_LOAD_FAILED]: 'WinDivert 驱动加载失败，请以管理员身份运行或重新安装驱动',
  [ErrorCode.ADMIN_REQUIRED]: '需要管理员权限，请以管理员身份运行 VidFlow',
  [ErrorCode.PROCESS_NOT_FOUND]: '目标进程未运行，请先启动微信',
  [ErrorCode.CAPTURE_FAILED]: '流量捕获启动失败，请检查防火墙设置或重启应用',
};

/**
 * 获取错误消息
 */
export function getErrorMessage(errorCode: string | null): string {
  if (!errorCode) return '未知错误';
  return ERROR_MESSAGES[errorCode] || errorCode;
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '未知';
  if (bytes === 0) return '0 B';
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${units[i]}`;
}

/**
 * 格式化时长
 */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '未知';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 状态显示文本
 */
export const SNIFFER_STATE_TEXT: Record<SnifferState, string> = {
  stopped: '已停止',
  starting: '正在启动...',
  running: '运行中',
  stopping: '正在停止...',
  error: '错误',
};

/**
 * 获取嗅探器状态文本
 */
export function getSnifferStateText(state: SnifferState): string {
  return SNIFFER_STATE_TEXT[state] || state;
}


// ============ 透明捕获相关类型 ============

/**
 * 捕获统计信息
 */
export interface CaptureStatistics {
  packets_intercepted: number;
  connections_redirected: number;
  videos_detected: number;
  last_detection_at: string | null;
  unrecognized_domains: string[];
}

/**
 * 驱动状态响应
 */
export interface DriverStatusResponse {
  state: DriverState;
  version: string | null;
  path: string | null;
  error_message: string | null;
  is_admin: boolean;
}

/**
 * 驱动安装响应
 */
export interface DriverInstallResponse {
  success: boolean;
  error_code: string | null;
  error_message: string | null;
}

/**
 * 捕获配置响应
 */
export interface CaptureConfigResponse {
  capture_mode: CaptureMode;
  use_windivert: boolean;
  target_processes: string[];
  no_detection_timeout: number;
  log_unrecognized_domains: boolean;
}

/**
 * 捕获配置更新请求
 */
export interface CaptureConfigUpdateRequest {
  capture_mode?: CaptureMode;
  use_windivert?: boolean;
  target_processes?: string[];
  no_detection_timeout?: number;
  log_unrecognized_domains?: boolean;
}

/**
 * 捕获统计响应
 */
export interface CaptureStatisticsResponse {
  state: CaptureState;
  mode: CaptureMode;
  statistics: CaptureStatistics;
  started_at: string | null;
}

/**
 * 扩展的视频号 Hook 状态
 */
export interface ChannelsSnifferStateExtended extends ChannelsSnifferState {
  driverStatus: DriverStatusResponse | null;
  captureConfig: CaptureConfigResponse | null;
  captureStatistics: CaptureStatistics | null;
}

/**
 * 捕获模式显示文本
 */
export const CAPTURE_MODE_TEXT: Record<CaptureMode, string> = {
  proxy_only: '代理模式（已弃用）',
  transparent: '透明捕获 (Windows PC)',
};

/**
 * 驱动状态显示文本
 */
export const DRIVER_STATE_TEXT: Record<DriverState, string> = {
  not_installed: '未安装',
  installed: '已安装',
  loading: '加载中...',
  error: '错误',
};

/**
 * 获取捕获模式文本
 */
export function getCaptureModeText(mode: CaptureMode): string {
  return CAPTURE_MODE_TEXT[mode] || mode;
}

/**
 * 获取驱动状态文本
 */
export function getDriverStateText(state: DriverState): string {
  return DRIVER_STATE_TEXT[state] || state;
}

/**
 * 格式化最后检测时间
 */
export function formatLastDetectionTime(isoString: string | null): string {
  if (!isoString) return '从未';
  
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  
  if (diffSec < 60) return `${diffSec} 秒前`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`;
  
  return date.toLocaleString('zh-CN');
}


// ============ 深度优化相关类型（Task 17.1）============

/**
 * 代理软件类型
 */
export type ProxyType = 
  | 'none' 
  | 'clash' 
  | 'clash_verge' 
  | 'clash_meta' 
  | 'surge' 
  | 'v2ray' 
  | 'shadowsocks' 
  | 'other';

/**
 * 代理工作模式
 */
export type ProxyMode = 
  | 'none' 
  | 'system_proxy' 
  | 'tun' 
  | 'fake_ip' 
  | 'rule';

/**
 * 多模式捕获模式
 */
export type MultiCaptureMode = 
  | 'windivert' 
  | 'clash_api' 
  | 'system_proxy' 
  | 'hybrid';

/**
 * 代理信息
 */
export interface ProxyInfo {
  proxy_type: ProxyType;
  proxy_mode: ProxyMode;
  process_name: string | null;
  process_pid: number | null;
  api_address: string | null;
  is_tun_enabled: boolean;
  is_fake_ip_enabled: boolean;
}

/**
 * 多模式捕获配置
 */
export interface MultiModeCaptureConfig {
  preferred_mode: MultiCaptureMode;
  auto_fallback: boolean;
  clash_api_address: string;
  clash_api_secret: string;
  quic_blocking_enabled: boolean;
  target_processes: string[];
  diagnostic_mode: boolean;
  no_detection_timeout: number;
  max_recovery_attempts: number;
}

/**
 * 诊断信息
 */
export interface DiagnosticInfo {
  detected_snis: string[];
  detected_ips: string[];
  wechat_processes: WeChatProcessInfo[];
  proxy_info: ProxyInfo | null;
  recent_errors: string[];
  capture_log: string[];
  statistics: Record<string, number | string | null>;
}

/**
 * 微信进程信息
 */
export interface WeChatProcessInfo {
  pid: number;
  name: string;
  exe_path: string;
  ports: number[];
  last_seen: string;
}

/**
 * 捕获模式信息
 */
export interface CaptureModeInfo {
  mode: MultiCaptureMode;
  name: string;
  description: string;
  available: boolean;
  recommended: boolean;
}

/**
 * 可用捕获模式响应
 */
export interface CaptureModesResponse {
  modes: CaptureModeInfo[];
  current_mode: MultiCaptureMode;
  recommended_mode: MultiCaptureMode;
}

/**
 * 切换模式请求
 */
export interface SwitchModeRequest {
  mode: MultiCaptureMode;
}

/**
 * 切换模式响应
 */
export interface SwitchModeResponse {
  success: boolean;
  previous_mode: MultiCaptureMode;
  current_mode: MultiCaptureMode;
  error_message: string | null;
}

/**
 * QUIC状态响应
 */
export interface QUICStatusResponse {
  blocking_enabled: boolean;
  packets_blocked: number;
  packets_allowed: number;
  target_processes: string[];
}

/**
 * QUIC开关请求
 */
export interface QUICToggleRequest {
  enabled: boolean;
}

/**
 * 多模式配置响应
 */
export interface MultiModeConfigResponse {
  preferred_mode: MultiCaptureMode;
  auto_fallback: boolean;
  clash_api_address: string;
  clash_api_secret: string;
  quic_blocking_enabled: boolean;
  target_processes: string[];
  diagnostic_mode: boolean;
  no_detection_timeout: number;
  max_recovery_attempts: number;
}

/**
 * 多模式配置更新请求
 */
export interface MultiModeConfigUpdateRequest {
  preferred_mode?: MultiCaptureMode;
  auto_fallback?: boolean;
  clash_api_address?: string;
  clash_api_secret?: string;
  quic_blocking_enabled?: boolean;
  target_processes?: string[];
  diagnostic_mode?: boolean;
  no_detection_timeout?: number;
  max_recovery_attempts?: number;
}

/**
 * 代理类型显示文本
 */
export const PROXY_TYPE_TEXT: Record<ProxyType, string> = {
  none: '无代理',
  clash: 'Clash',
  clash_verge: 'Clash Verge',
  clash_meta: 'Clash Meta',
  surge: 'Surge',
  v2ray: 'V2Ray',
  shadowsocks: 'Shadowsocks',
  other: '其他代理',
};

/**
 * 代理模式显示文本
 */
export const PROXY_MODE_TEXT: Record<ProxyMode, string> = {
  none: '无',
  system_proxy: '系统代理',
  tun: 'TUN模式',
  fake_ip: 'Fake-IP',
  rule: '规则模式',
};

/**
 * 多模式捕获模式显示文本
 */
export const MULTI_CAPTURE_MODE_TEXT: Record<MultiCaptureMode, string> = {
  windivert: 'WinDivert透明捕获',
  clash_api: 'Clash API监控',
  system_proxy: '系统代理拦截',
  hybrid: '混合模式（自动）',
};

/**
 * 获取代理类型文本
 */
export function getProxyTypeText(type: ProxyType): string {
  return PROXY_TYPE_TEXT[type] || type;
}

/**
 * 获取代理模式文本
 */
export function getProxyModeText(mode: ProxyMode): string {
  return PROXY_MODE_TEXT[mode] || mode;
}

/**
 * 获取多模式捕获模式文本
 */
export function getMultiCaptureModeText(mode: MultiCaptureMode): string {
  return MULTI_CAPTURE_MODE_TEXT[mode] || mode;
}

/**
 * 深度优化错误码
 */
export enum DeepOptimizationErrorCode {
  PROXY_TUN_MODE = 'PROXY_TUN_MODE',
  PROXY_FAKE_IP = 'PROXY_FAKE_IP',
  CLASH_API_FAILED = 'CLASH_API_FAILED',
  CLASH_AUTH_FAILED = 'CLASH_AUTH_FAILED',
  ECH_DETECTED = 'ECH_DETECTED',
  NO_VIDEO_DETECTED = 'NO_VIDEO_DETECTED',
  VIDEO_EXPIRED = 'VIDEO_EXPIRED',
  RECOVERY_FAILED = 'RECOVERY_FAILED',
  CONFIG_INVALID = 'CONFIG_INVALID',
}

/**
 * 深度优化错误消息
 */
export const DEEP_OPTIMIZATION_ERROR_MESSAGES: Record<string, string> = {
  [DeepOptimizationErrorCode.PROXY_TUN_MODE]: '检测到代理软件使用TUN模式，请切换到系统代理模式',
  [DeepOptimizationErrorCode.PROXY_FAKE_IP]: '检测到Fake-IP模式，将使用IP识别替代方案',
  [DeepOptimizationErrorCode.CLASH_API_FAILED]: '无法连接到Clash API，请检查Clash是否运行',
  [DeepOptimizationErrorCode.CLASH_AUTH_FAILED]: 'Clash API认证失败，请检查API密钥',
  [DeepOptimizationErrorCode.ECH_DETECTED]: '检测到ECH加密，已切换到IP识别模式',
  [DeepOptimizationErrorCode.NO_VIDEO_DETECTED]: '未检测到视频，请在微信中播放视频',
  [DeepOptimizationErrorCode.VIDEO_EXPIRED]: '视频链接已过期，请重新播放视频',
  [DeepOptimizationErrorCode.RECOVERY_FAILED]: '自动恢复失败，请手动重启捕获功能',
  [DeepOptimizationErrorCode.CONFIG_INVALID]: '配置文件无效，已使用默认配置',
};

/**
 * 获取深度优化错误消息
 */
export function getDeepOptimizationErrorMessage(errorCode: string | null): string {
  if (!errorCode) return '未知错误';
  return DEEP_OPTIMIZATION_ERROR_MESSAGES[errorCode] || ERROR_MESSAGES[errorCode] || errorCode;
}

// ============ 系统诊断相关类型 ============

/**
 * 诊断建议级别
 */
export type DiagnosticLevel = 'error' | 'warning' | 'info' | 'success';

/**
 * 诊断建议
 */
export interface DiagnosticRecommendation {
  level: DiagnosticLevel;
  message: string;
  action: string;
}

/**
 * 系统诊断响应
 */
export interface SystemDiagnosticResponse {
  is_admin: boolean;
  wechat_running: boolean;
  wechat_processes: Array<{
    pid: number;
    name: string;
    exe: string;
  }>;
  sniffer_state: SnifferState;
  videos_detected: number;
  port_8888_available: boolean;
  recommendations: DiagnosticRecommendation[];
}
