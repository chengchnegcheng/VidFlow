/**
 * API 客户端
 */
import axios from 'axios';

// 动态获取后端端口
let API_BASE_URL = ''; // 将由 initializeBackendPort 动态设置
let backendPort: number | null = null;
let portInitialized = false;
let initializationInProgress = false;

// 初始化后端端口配置
async function initializeBackendPort() {
  if (portInitialized) return true;
  if (initializationInProgress) {
    // 等待初始化完成
    for (let i = 0; i < 50; i++) {
      if (portInitialized) return true;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return portInitialized;
  }

  initializationInProgress = true;

  if (window.electron) {
    try {
      const config = await window.electron.invoke('get-backend-port');
      if (config && config.port) {
        backendPort = config.port;
        API_BASE_URL = `http://${config.host}:${config.port}`;
        api.defaults.baseURL = API_BASE_URL;
        portInitialized = true;
        console.log('✅ Backend API URL initialized:', API_BASE_URL);
        initializationInProgress = false;
        return true;
      }
    } catch (error) {
      console.error('❌ Failed to get backend port:', error);
    }
  }

  initializationInProgress = false;
  return false;
}

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
});

// 后台异步初始化端口
initializeBackendPort();

// 请求拦截器 - 确保使用最新的端口
api.interceptors.request.use(
  async (config) => {
    // 如果还没有初始化端口，先初始化
    if (!portInitialized) {
      console.log('🔄 Port not initialized, initializing now...');
      await initializeBackendPort();
    }

    // 如果已经有端口，使用最新的 baseURL
    if (backendPort) {
      config.baseURL = API_BASE_URL;
      console.log(`📡 API Request: ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    } else {
      console.warn('⚠️ Backend port not available, using default:', config.baseURL);
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

// 导出获取当前 API URL 的方法
export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getBackendPort(): number | null {
  return backendPort;
}

// 类型定义
export interface VideoInfo {
  title: string;
  duration: number;
  thumbnail: string;
  description?: string;
  uploader?: string;
  upload_date?: string;
  view_count?: number;
  platform: string;
  formats: VideoFormat[];
  url: string;
}

export interface VideoFormat {
  format_id: string;
  ext: string;
  quality: string;
  filesize: number;
  vcodec: string;
  acodec: string;
  height: number;
  width: number;
  fps: number;
}

export interface DownloadTask {
  id: number;
  task_id: string;
  url: string;
  title?: string;
  platform?: string;
  thumbnail?: string;
  duration?: number;
  quality: string;
  format_id?: string;
  output_path?: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed: number;
  eta: number;
  filename?: string;
  filesize?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

// API 方法
export const apiClient = {
  /**
   * 获取视频信息
   */
  async getVideoInfo(url: string): Promise<VideoInfo> {
    const response = await api.post('/api/v1/downloads/info', { url });
    return response.data.data;
  },

  /**
   * 开始下载
   */
  async startDownload(
    url: string,
    quality: string = 'best',
    outputPath?: string,
    formatId?: string
  ): Promise<{ task_id: string; video_info: VideoInfo }> {
    const response = await api.post('/api/v1/downloads/start', {
      url,
      quality,
      output_path: outputPath,
      format_id: formatId,
    });
    return response.data;
  },

  /**
   * 获取所有任务
   */
  async getTasks(
    limit: number = 50,
    offset: number = 0,
    status?: string
  ): Promise<{ tasks: DownloadTask[]; total: number }> {
    const params: any = { limit, offset };
    if (status) params.status = status;

    const response = await api.get('/api/v1/downloads/tasks', { params });
    return response.data;
  },

  /**
   * 获取任务状态
   */
  async getTaskStatus(taskId: string): Promise<DownloadTask> {
    const response = await api.get(`/api/v1/downloads/tasks/${taskId}`);
    return response.data.task;
  },

  /**
   * 删除任务
   */
  async deleteTask(taskId: string): Promise<void> {
    await api.delete(`/api/v1/downloads/tasks/${taskId}`);
  },

  /**
   * 健康检查
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await api.get('/health');
    return response.data;
  },
};

export default apiClient;
