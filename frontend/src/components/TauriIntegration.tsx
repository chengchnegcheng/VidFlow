/**
 * Tauri Integration Adapter for Electron
 * 将 Tauri API 适配为 Electron + REST API
 */
import { createContext, useContext, ReactNode, useState, useEffect } from 'react';
import axios from 'axios';

// 开发模式标志
const isDev = import.meta.env.DEV;

// 动态获取后端端口
let API_BASE = ''; // 将由 initializeBackendPort 动态设置
let portInitialized = false;
let initializationInProgress = false; // 防止并发初始化
let initializationAttempts = 0;
const MAX_INIT_ATTEMPTS = 10;

const api = axios.create({ 
  baseURL: API_BASE,
  timeout: 60000,
  withCredentials: true,
});

// 初始化后端端口配置（带重试）
async function initializeBackendPort(): Promise<boolean> {
  if (portInitialized) return true;
  if (initializationInProgress) {
    // 如果正在初始化，等待一下
    await new Promise(resolve => setTimeout(resolve, 100));
    return portInitialized;
  }
  
  initializationInProgress = true;
  initializationAttempts++;
  
  if (window.electron) {
    try {
      console.log(`🔄 [Attempt ${initializationAttempts}/${MAX_INIT_ATTEMPTS}] Requesting backend port from Electron...`);
      const config = await window.electron.invoke('get-backend-port');
      console.log('📡 Backend config received:', config);
      
      if (config && config.port && config.ready) {
        API_BASE = `http://${config.host}:${config.port}`;
        api.defaults.baseURL = API_BASE;
        
        // 验证后端真的可以响应
        console.log('🔍 Verifying backend health...');
        try {
          // 使用正确的健康检查端点 /health
          const healthCheck = await api.get('/health', { timeout: 5000 });
          if (healthCheck.status === 200) {
            portInitialized = true;
            initializationInProgress = false;
            console.log('✅ Backend API URL initialized and verified:', API_BASE);
            console.log('✅ Backend health check passed:', healthCheck.data);
            return true;
          } else {
            console.warn('⚠️ Backend health check failed, status:', healthCheck.status);
          }
        } catch (healthError) {
          console.error('❌ Backend health check failed:', healthError);
          console.warn('⚠️ Port received but backend not responding, will retry...');
        }
      } else if (config && config.port && !config.ready) {
        console.warn('⚠️ Backend port received but backend not ready yet, will retry...');
      } else {
        console.warn('⚠️ Backend port not available yet, will retry...');
      }
    } catch (error) {
      console.error('❌ Failed to get backend port:', error);
    }
  } else {
    console.warn('⚠️ window.electron not available, using default port');
    // 如果不是 Electron 环境，使用默认端口
    portInitialized = true;
    initializationInProgress = false;
    return true;
  }
  
  initializationInProgress = false;
  return false;
}

// 启动时持续尝试初始化，直到成功
async function startPortInitialization() {
  for (let i = 0; i < MAX_INIT_ATTEMPTS; i++) {
    const success = await initializeBackendPort();
    if (success) {
      console.log('✅ Port initialization completed successfully');
      return;
    }
    // 等待后再重试
    console.log(`⏳ Waiting 2 seconds before retry...`);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  console.error('❌ Failed to initialize backend port after maximum attempts');
  console.error('⚠️ Frontend will continue with default port, but API calls may fail');
}

// 立即开始初始化
console.log('🚀 TauriIntegration.tsx loaded, starting port initialization...');
console.log('🔍 window.electron exists:', !!window.electron);
console.log('🔍 window.electron.invoke exists:', !!(window.electron && window.electron.invoke));
startPortInitialization();

// 请求拦截器 - 确保使用最新的端口
api.interceptors.request.use(
  async (config) => {
    // 只在完全未初始化且没有正在初始化时才尝试
    if (!portInitialized && !initializationInProgress) {
      console.log('🔄 Port not initialized, waiting for initialization...');
      // 等待初始化完成，最多等待5秒
      for (let i = 0; i < 50; i++) {
        if (portInitialized) break;
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
    
    // 总是使用最新的 API_BASE（已初始化或为空）
    config.baseURL = API_BASE;
    
    if (isDev) {
      console.log(`📡 API Request: ${config.method?.toUpperCase()} ${config.baseURL || 'pending'}${config.url}`);
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('❌ API Error:', error.message);

    // 打印后端返回的详细错误信息
    if (error.response?.data) {
      console.error('❌ Backend Error Details:', error.response.data);
    }

    if (error.code === 'ERR_NETWORK' || error.code === 'ECONNREFUSED') {
      console.error('❌ Backend connection refused. Backend might not be ready yet.');
    }

    // 如果后端返回了详细错误信息,将其附加到 error.message
    if (error.response?.data?.detail) {
      error.message = error.response.data.detail;
    }

    return Promise.reject(error);
  }
);

interface TauriContextType {
  isDesktop: boolean;
  version: string;
  isOnline: boolean;
  minimize: () => void;
  maximize: () => void;
  close: () => void;
}

const TauriContext = createContext<TauriContextType>({
  isDesktop: true,
  version: '1.0.0',
  isOnline: true,
  minimize: () => {},
  maximize: () => {},
  close: () => {},
});

export function TauriProvider({ children }: { children: ReactNode }) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const value: TauriContextType = {
    isDesktop: true, // Electron 环境
    version: '1.0.0',
    isOnline,
    minimize: () => {
      // Electron IPC 调用（如果需要）
      console.log('Minimize window');
    },
    maximize: () => {
      console.log('Maximize window');
    },
    close: () => {
      console.log('Close window');
    },
  };

  return (
    <TauriContext.Provider value={value}>
      {children}
    </TauriContext.Provider>
  );
}

export function useTauri() {
  return useContext(TauriContext);
}

export function useDesktopFeatures() {
  return {
    openDownloadFolder: async () => {
      console.log('Open download folder');
      // 可以通过 Electron IPC 或打开文件管理器
    },
    selectDirectory: async (): Promise<string | null> => {
      // 使用 HTML5 file API 或 Electron dialog
      return null;
    },
  };
}

type StructuredErrorPayload = {
  code?: string;
  message?: string;
  hint?: string;
};

function normalizeStructuredErrorPayload(value: unknown): StructuredErrorPayload | null {
  if (!value) return null;

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return normalizeStructuredErrorPayload(parsed);
    } catch {
      return null;
    }
  }

  if (typeof value === 'object') {
    const payload = value as Record<string, unknown>;
    const message = payload.message;
    if (typeof message === 'string' && message.trim()) {
      const hint = payload.hint;
      const code = payload.code;
      return {
        code: typeof code === 'string' ? code : undefined,
        message: message,
        hint: typeof hint === 'string' ? hint : undefined,
      };
    }
  }

  return null;
}

function formatBackendErrorMessage(detail: unknown, fallback: string): string {
  const structured = normalizeStructuredErrorPayload(detail);
  if (structured?.message) {
    if (structured.hint) {
      return `${structured.message}（${structured.hint}）`;
    }
    return structured.message;
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

function getAxiosErrorMessage(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail ?? error?.response?.data?.error;
  if (detail !== undefined) {
    return formatBackendErrorMessage(detail, fallback);
  }
  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

/**
 * 模拟 Tauri 的 invoke 函数
 * 将 Tauri 命令转换为 REST API 调用
 */
export async function invoke(command: string, args?: any): Promise<any> {
  // 减少日志噪音：仅在开发环境或首次调用时打印
  if (import.meta.env.DEV) {
    console.debug(`[invoke] ${command}`, args);
  }

  if (!portInitialized) {
    await initializeBackendPort();
    for (let i = 0; i < 50; i++) {
      if (API_BASE) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  if (!API_BASE && window.electron) {
    throw new Error('后端未就绪，请稍后重试（后端端口/健康检查未通过）');
  }

  const commandMap: Record<string, () => Promise<any>> = {
    // 视频信息
    'get_video_info': async () => {
      const res = await api.post('/api/v1/downloads/info', { url: args?.url });
      return res.data.data;
    },

    // 开始下载
    'start_download': async () => {
      const res = await api.post('/api/v1/downloads/start', {
        url: args?.url,
        quality: args?.quality,
        format_id: args?.format_id,
        output_path: args?.output_path,
      });
      return res.data;
    },

    // 获取下载任务列表
    'get_download_tasks': async () => {
      try {
        const res = await api.get('/api/v1/downloads/tasks');
        console.log('[DEBUG] get_download_tasks response:', res.data);
        const tasks = res.data?.tasks || [];
        return tasks;
      } catch (error) {
        console.error('[ERROR] Failed to get download tasks:', error);
        return [];
      }
    },

    // 获取单个任务状态
    'get_task_status': async () => {
      const res = await api.get(`/api/v1/downloads/tasks/${args?.task_id}`);
      return res.data.task;
    },

    // 删除任务
    'delete_download_task': async () => {
      await api.delete(`/api/v1/downloads/tasks/${args?.task_id}`);
      return { success: true };
    },

    // 取消任务
    'cancel_download_task': async () => {
      await api.post(`/api/v1/downloads/tasks/${args?.task_id}/cancel`);
      return { success: true };
    },

    // 暂停任务
    'pause_download_task': async () => {
      await api.post(`/api/v1/downloads/tasks/${args?.task_id}/pause`);
      return { success: true };
    },

    // 恢复任务
    'resume_download_task': async () => {
      await api.post(`/api/v1/downloads/tasks/${args?.task_id}/resume`);
      return { success: true };
    },

    // 系统信息
    'get_system_info': async () => {
      try {
        const res = await api.get('/api/v1/system/info');
        return res.data;
      } catch (error) {
        // 降级到模拟数据
        return {
          cpu_usage: Math.random() * 30 + 10,
          memory_usage: Math.random() * 40 + 20,
          disk_usage: Math.random() * 50 + 30,
          network_speed: { download: 0, upload: 0 },
          active_tasks: 0,
          queue_size: 0,
          total_downloads: 0,
          backend_status: 'online',
          uptime: '0h 0m'
        };
      }
    },

    // 队列状态 (模拟)
    'get_queue_status': async () => {
      try {
        const tasks = await api.get('/api/v1/downloads/tasks');
        console.log('[DEBUG] get_queue_status response:', tasks.data);
        const downloading = tasks.data?.tasks?.filter((t: any) => 
          t.status === 'downloading' || t.status === 'pending'
        ).length || 0;
        return [downloading];
      } catch (error) {
        console.error('[ERROR] Failed to get queue status:', error);
        return [0];
      }
    },

    // 工具状态检测
    'check_tool_status': async () => {
      try {
        const res = await api.get('/api/v1/system/tools/status');
        return res.data;
      } catch (error) {
        // 降级到模拟数据
        return [
          { name: 'FFmpeg', installed: false, required: true },
          { name: 'yt-dlp', installed: false, required: true },
          { name: 'Python', installed: true, version: '3.14.0', required: true },
          { name: 'faster-whisper', installed: false, required: false }
        ];
      }
    },

    // 获取下载文件夹路径
    'get_downloads_path': async () => {
      try {
        const res = await api.get('/api/v1/system/downloads-path');
        return res.data?.path || '';
      } catch (error) {
        console.error('Failed to get downloads path:', error);
        return '';
      }
    },

    // 打开外部链接
    'open_external': async () => {
      window.open(args?.url, '_blank');
      return { success: true };
    },

    // 选择目录 (使用 HTML5)
    'select_directory': async () => {
      // 在浏览器环境中使用 input[type=file]
      return null;
    },

    // 安装 FFmpeg（需要下载，超时时间 5 分钟）
    'install_ffmpeg': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/install/ffmpeg', {}, {
          timeout: 300000 // 5 分钟
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '安装失败');
      }
    },

    // 安装 yt-dlp（需要下载，超时时间 5 分钟）
    'install_ytdlp': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/install/ytdlp', {}, {
          timeout: 300000 // 5 分钟
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '安装失败');
      }
    },

    // 安装 faster-whisper（需要下载大模型，超时时间 10 分钟）
    'install_whisper': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/install/whisper', {}, {
          timeout: 600000 // 10 分钟
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '安装失败');
      }
    },

    // 一键安装所有工具（可能需要很长时间，超时时间 15 分钟）
    'install_all_tools': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/install/all', {}, {
          timeout: 900000 // 15 分钟
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '安装失败');
      }
    },

    // 更新依赖包（可能需要较长时间，超时时间 5 分钟）
    'update_dependencies': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/update/dependencies', {}, {
          timeout: 300000 // 5 分钟
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '更新失败');
      }
    },

    // 打开终端
    'open_terminal': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/terminal');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '打开终端失败');
      }
    },

    // 获取Python环境信息
    'get_python_info': async () => {
      try {
        const res = await api.get('/api/v1/system/tools/python-info');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取信息失败');
      }
    },

    // 获取日志
    'get_logs': async () => {
      try {
        const res = await api.get('/api/v1/logs/', { params: args });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取日志失败');
      }
    },

    // 获取日志统计
    'get_log_stats': async () => {
      try {
        const res = await api.get('/api/v1/logs/stats');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取统计失败');
      }
    },

    // 清空日志
    'clear_logs': async () => {
      try {
        const res = await api.delete('/api/v1/logs/clear');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '清空日志失败');
      }
    },

    // 下载日志
    'download_logs': async () => {
      try {
        const res = await api.get('/api/v1/logs/download', {
          responseType: 'blob'
        });
        // 创建下载链接
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `vidflow_logs_${new Date().toISOString().split('T')[0]}.log`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        return { success: true };
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '下载失败');
      }
    },

    // 获取日志路径
    'get_log_path': async () => {
      try {
        const res = await api.get('/api/v1/logs/path');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取日志路径失败');
      }
    },

    // 获取存储信息
    'get_storage_info': async () => {
      try {
        const res = await api.get('/api/v1/system/storage');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取存储信息失败');
      }
    },

    // 清理缓存
    'clear_cache': async () => {
      try {
        const res = await api.post('/api/v1/system/cache/clear');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '清理缓存失败');
      }
    },

    // 创建字幕生成任务
    'generate_subtitle': async () => {
      try {
        const res = await api.post('/api/v1/subtitle/generate', args);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '创建任务失败'));
      }
    },

    // 获取字幕任务列表
    'get_subtitle_tasks': async () => {
      try {
        const res = await api.get('/api/v1/subtitle/tasks');
        return res.data?.tasks || [];
      } catch (error: any) {
        console.error('Failed to get subtitle tasks:', error);
        return [];
      }
    },

    // 获取单个字幕任务
    'get_subtitle_task': async () => {
      try {
        const res = await api.get(`/api/v1/subtitle/tasks/${args?.task_id}`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '获取任务失败'));
      }
    },

    // 删除字幕任务
    'delete_subtitle_task': async () => {
      try {
        await api.delete(`/api/v1/subtitle/tasks/${args?.task_id}`);
        return { success: true };
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '删除失败'));
      }
    },

    'cancel_subtitle_task': async () => {
      try {
        const res = await api.post(`/api/v1/subtitle/tasks/${args?.task_id}/cancel`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '取消任务失败'));
      }
    },

    // 暂停字幕任务
    'pause_subtitle_task': async () => {
      try {
        const res = await api.post(`/api/v1/subtitle/tasks/${args?.task_id}/pause`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '暂停任务失败'));
      }
    },

    // 恢复字幕任务
    'resume_subtitle_task': async () => {
      try {
        const res = await api.post(`/api/v1/subtitle/tasks/${args?.task_id}/resume`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '恢复任务失败'));
      }
    },

    // 获取可用模型
    'get_subtitle_models': async () => {
      try {
        const res = await api.get('/api/v1/subtitle/models');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取模型失败');
      }
    },

    // 获取支持的语言
    'get_subtitle_languages': async () => {
      try {
        const res = await api.get('/api/v1/subtitle/languages');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取语言失败');
      }
    },

    // 检测代理是否可用
    'check_proxy': async () => {
      try {
        const res = await api.get('/api/v1/system/network/proxy-check');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '代理检测失败');
      }
    },

    // 打开文件夹
    'open_folder': async () => {
      try {
        const res = await api.post('/api/v1/system/open-folder', {
          path: args?.path
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '打开文件夹失败');
      }
    },

    // 烧录字幕到视频
    'burn_subtitle': async () => {
      try {
        const res = await api.post('/api/v1/subtitle/burn-subtitle', {
          video_path: args?.video_path,
          subtitle_path: args?.subtitle_path,
          output_path: args?.output_path
        });
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '字幕烧录失败'));
      }
    },

    // 选择文件
    'select_file': async () => {
      try {
        const res = await api.post('/api/v1/system/select-file', {
          filters: args?.filters
        });
        return res.data?.path;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '选择文件失败');
      }
    },

    // 保存文件对话框
    'save_file': async () => {
      try {
        const res = await api.post('/api/v1/system/save-file', {
          default_path: args?.defaultPath,
          filters: args?.filters
        });
        return res.data?.path;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '保存文件失败');
      }
    },

    // ==================== 烧录字幕任务管理 ====================
    
    // 创建烧录字幕任务
    'create_burn_subtitle_task': async () => {
      try {
        const res = await api.post('/api/v1/subtitle/burn-subtitle-task', {
          video_path: args?.video_path,
          subtitle_path: args?.subtitle_path,
          output_path: args?.output_path,
          video_title: args?.video_title
        });
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '创建烧录任务失败'));
      }
    },

    // 获取烧录字幕任务列表
    'get_burn_subtitle_tasks': async () => {
      try {
        const res = await api.get('/api/v1/subtitle/burn-subtitle-tasks');
        return res.data || [];
      } catch (error: any) {
        console.error('Failed to get burn subtitle tasks:', error);
        return [];
      }
    },

    // 删除烧录字幕任务
    'delete_burn_subtitle_task': async () => {
      try {
        await api.delete(`/api/v1/subtitle/burn-subtitle-tasks/${args?.task_id}`);
        return { success: true };
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '删除烧录任务失败'));
      }
    },

    // 取消烧录字幕任务
    'cancel_burn_subtitle_task': async () => {
      try {
        const res = await api.post(`/api/v1/subtitle/burn-subtitle-tasks/${args?.task_id}/cancel`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '取消烧录任务失败'));
      }
    },

    // 暂停烧录字幕任务
    'pause_burn_subtitle_task': async () => {
      try {
        const res = await api.post(`/api/v1/subtitle/burn-subtitle-tasks/${args?.task_id}/pause`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '暂停烧录任务失败'));
      }
    },

    // 恢复烧录字幕任务
    'resume_burn_subtitle_task': async () => {
      try {
        const res = await api.post(`/api/v1/subtitle/burn-subtitle-tasks/${args?.task_id}/resume`);
        return res.data;
      } catch (error: any) {
        throw new Error(getAxiosErrorMessage(error, '恢复烧录任务失败'));
      }
    },

    // ==================== GPU 加速管理 ====================
    
    // 获取GPU状态
    'get_gpu_status': async () => {
      try {
        const res = await api.get('/api/v1/system/gpu/status');
        return res.data?.data ?? res.data;
      } catch (error: any) {
        console.error('Failed to get GPU status:', error);
        return {
          gpu_available: false,
          gpu_enabled: false,
          can_install: false,
          installing: false
        };
      }
    },

    // 安装GPU加速包
    'install_gpu_package': async () => {
      try {
        const res = await api.post('/api/v1/system/gpu/install');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '启动GPU安装失败');
      }
    },

    // ==================== 工具状态检查 ====================
    
    // 检查工具安装状态
    'check_tools_status': async () => {
      try {
        const res = await api.get('/api/v1/system/tools/status');
        return res.data || [];
      } catch (error: any) {
        console.error('Failed to check tools status:', error);
        return [];
      }
    },

    // 下载/更新 yt-dlp
    'download_ytdlp': async () => {
      try {
        const res = await api.post('/api/v1/system/tools/ytdlp/download');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '下载 yt-dlp 失败');
      }
    },

    // ==================== 配置管理 ====================
    
    // 获取完整配置
    'get_config': async () => {
      try {
        const res = await api.get('/api/v1/config');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取配置失败');
      }
    },

    // 获取单个配置项
    'get_config_value': async () => {
      try {
        const res = await api.get(`/api/v1/config/${args?.key}`);
        return res.data?.value;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取配置项失败');
      }
    },

    // 更新配置
    'update_config': async () => {
      try {
        const res = await api.post('/api/v1/config/update', {
          updates: args?.updates
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '更新配置失败');
      }
    },

    // 重置配置
    'reset_config': async () => {
      try {
        const res = await api.post('/api/v1/config/reset');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '重置配置失败');
      }
    },

    // 更新队列并发数
    'update_queue_config': async () => {
      try {
        const res = await api.post('/api/v1/downloads/queue/config', null, {
          params: { max_concurrent: args?.max_concurrent }
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '更新队列配置失败');
      }
    },

    // ==================== Cookie 管理 ====================
    
    // 获取所有平台的Cookie状态
    'get_cookies_status': async () => {
      try {
        const res = await api.get('/api/v1/system/cookies/status');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取Cookie状态失败');
      }
    },

    // 获取指定平台的Cookie内容
    'get_cookie_content': async () => {
      try {
        const res = await api.get(`/api/v1/system/cookies/${args?.platform}`);
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取Cookie内容失败');
      }
    },

    // 保存指定平台的Cookie
    'save_cookie_content': async () => {
      try {
        const res = await api.post(`/api/v1/system/cookies/${args?.platform}`, {
          content: args?.content
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '保存Cookie失败');
      }
    },

    // 删除指定平台的Cookie
    'delete_cookie': async () => {
      try {
        const res = await api.delete(`/api/v1/system/cookies/${args?.platform}`);
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '删除Cookie失败');
      }
    },

    // 打开Cookie文件夹
    'open_cookies_folder': async () => {
      try {
        const res = await api.get('/api/v1/system/cookies/open-folder');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '打开Cookie文件夹失败');
      }
    },

    // ==================== Cookie 自动获取 ====================
    
    // 检查Selenium状态
    'check_selenium_status': async () => {
      try {
        const res = await api.get('/api/v1/system/cookies/auto/selenium-status');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '检查Selenium状态失败');
      }
    },

    // 启动受控浏览器
    'start_cookie_browser': async () => {
      try {
        const res = await api.post('/api/v1/system/cookies/auto/start-browser', {
          platform: args?.platform,
          browser: args?.browser
        });

        // ✅ 检查业务状态，将业务错误转换为异常
        if (res.data?.status === 'error') {
          throw new Error(res.data.error || '启动浏览器失败');
        }

        return res.data;
      } catch (error: any) {
        // 如果是我们自己抛出的错误，直接重新抛出
        if (error.message && !error.response) {
          throw error;
        }
        throw new Error(error.response?.data?.detail || '启动浏览器失败');
      }
    },

    // 提取Cookie
    'extract_cookies': async () => {
      try {
        const res = await api.post('/api/v1/system/cookies/auto/extract');

        // ✅ 检查业务状态，将业务错误转换为异常
        if (res.data?.status === 'error') {
          throw new Error(res.data.error || '提取Cookie失败');
        }

        return res.data;
      } catch (error: any) {
        // 如果是我们自己抛出的错误，直接重新抛出
        if (error.message && !error.response) {
          throw error;
        }
        throw new Error(error.response?.data?.detail || '提取Cookie失败');
      }
    },

    // 关闭浏览器
    'close_cookie_browser': async () => {
      try {
        const res = await api.post('/api/v1/system/cookies/auto/close-browser');

        // ✅ 检查业务状态，将业务错误转换为异常
        if (res.data?.status === 'error') {
          throw new Error(res.data.error || '关闭浏览器失败');
        }

        return res.data;
      } catch (error: any) {
        // 如果是我们自己抛出的错误，直接重新抛出
        if (error.message && !error.response) {
          throw error;
        }
        throw new Error(error.response?.data?.detail || '关闭浏览器失败');
      }
    },

    // 从已安装的浏览器提取Cookie（最可靠的方法）
    'extract_cookies_from_browser': async () => {
      try {
        // 确保参数存在
        if (!args?.platform) {
          throw new Error('缺少 platform 参数');
        }

        const requestBody = {
          platform: args.platform,
          browser: args.browser || 'chrome'
        };

        console.log('[DEBUG] extract_cookies_from_browser request:', requestBody);

        const res = await api.post('/api/v1/system/cookies/from-browser', requestBody, {
          headers: {
            'Content-Type': 'application/json'
          }
        });

        console.log('[DEBUG] extract_cookies_from_browser response:', res.data);

        // ✅ 检查业务状态，将业务错误转换为异常
        if (res.data?.status === 'error') {
          throw new Error(res.data.error || '从浏览器提取Cookie失败');
        }

        return res.data;
      } catch (error: any) {
        console.error('[DEBUG] extract_cookies_from_browser error:', error);
        // 如果是我们自己抛出的错误，直接重新抛出
        if (error.message && !error.response) {
          throw error;
        }
        // 422错误通常是请求体验证失败
        if (error.response?.status === 422) {
          throw new Error('请求参数验证失败，请检查浏览器和平台参数是否正确');
        }
        throw new Error(error.response?.data?.detail || error.response?.data?.error || '从浏览器提取Cookie失败');
      }
    },

    // ==================== Cookie/CORS 测试 ====================
    'auth_test_login': async () => {
      try {
        const res = await api.post('/api/v1/system/auth/test/login');
        const data = res.data;
        if (data?.session) {
          const expiresAt = Date.now() + 7 * 24 * 3600 * 1000;
          const payload = { value: data.session, expiresAt };
          try {
            localStorage.setItem('vidflow_session', JSON.stringify(payload));
          } catch (err) {
            console.warn('Failed to persist session to localStorage:', err);
          }
        }
        return data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '测试登录失败');
      }
    },
    'auth_test_check': async () => {
      try {
        const res = await api.get('/api/v1/system/auth/test/check');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '检测 Cookie 失败');
      }
    },

    // 恢复 yt-dlp 到内置版本
    'reset_ytdlp': async () => {
      try {
        const res = await api.delete('/api/v1/system/tools/ytdlp/downloaded');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '恢复失败');
      }
    },

    // ==================== QR 扫码登录 ====================
    
    // 获取支持扫码登录的平台列表
    'qr_login_get_supported_platforms': async () => {
      try {
        const res = await api.get('/api/v1/admin/cookies/qr/supported');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取支持平台列表失败');
      }
    },

    // 获取平台登录二维码
    'qr_login_get_qrcode': async () => {
      try {
        const res = await api.get(`/api/v1/admin/cookies/qr/${args?.platformId}/qrcode`);
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取二维码失败');
      }
    },

    // 检查扫码状态
    'qr_login_check_status': async () => {
      try {
        const res = await api.post(`/api/v1/admin/cookies/qr/${args?.platformId}/qrcode/check`);
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '检查扫码状态失败');
      }
    },

    // 取消扫码登录
    'qr_login_cancel': async () => {
      try {
        const res = await api.post(`/api/v1/admin/cookies/qr/${args?.platformId}/qrcode/cancel`);
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '取消扫码登录失败');
      }
    },

    // 启用/禁用平台扫码登录
    'qr_login_set_enabled': async () => {
      try {
        const res = await api.post(`/api/v1/admin/cookies/qr/${args?.platformId}/enable`, {
          enabled: args?.enabled
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '设置平台状态失败');
      }
    },

    // ==================== 微信视频号 API ====================

    // 获取嗅探器状态
    'channels_get_status': async () => {
      try {
        // 使用较短的超时时间，这是高频轮询接口
        const res = await api.get('/api/channels/sniffer/status', {
          timeout: 5000  // 5 秒超时
        });
        return res.data;
      } catch (error: any) {
        // 超时或网络错误时返回默认状态
        if (error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK') {
          console.warn('Failed to get sniffer status (timeout/network), returning stopped status');
          return {
            state: 'stopped',
            proxy_port: 8888,
            videos_detected: 0,
            capture_mode: 'transparent',
            capture_state: 'stopped'
          };
        }
        throw new Error(error.response?.data?.detail || '获取嗅探器状态失败');
      }
    },

    // 启动嗅探器
    'channels_start_sniffer': async () => {
      try {
        const res = await api.post('/api/channels/sniffer/start', {
          port: args?.port,
          capture_mode: args?.capture_mode
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '启动嗅探器失败');
      }
    },

    // 停止嗅探器
    'channels_stop_sniffer': async () => {
      try {
        const res = await api.post('/api/channels/sniffer/stop');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '停止嗅探器失败');
      }
    },

    // 获取检测到的视频列表
    'channels_get_videos': async () => {
      try {
        // 使用较短的超时时间，避免阻塞 UI
        const res = await api.get('/api/channels/videos', {
          timeout: 5000  // 5 秒超时
        });
        return res.data;
      } catch (error: any) {
        // 超时或网络错误时返回空数组，不抛出异常
        if (error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK') {
          console.warn('Failed to get videos (timeout/network), returning empty list');
          return [];
        }
        throw new Error(error.response?.data?.detail || '获取视频列表失败');
      }
    },

    // 清空视频列表
    'channels_clear_videos': async () => {
      try {
        const res = await api.delete('/api/channels/videos');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '清空视频列表失败');
      }
    },

    // 手动添加视频 URL
    'channels_add_video': async () => {
      try {
        const res = await api.post('/api/channels/videos/add', {
          url: args?.url,
          title: args?.title
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '添加视频失败');
      }
    },

    // 下载视频
    'channels_download_video': async () => {
      try {
        const res = await api.post('/api/channels/download', {
          url: args?.url,
          quality: args?.quality,
          output_path: args?.output_path,
          auto_decrypt: args?.auto_decrypt,
          decryption_key: args?.decryption_key  // 传递解密密钥
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '下载视频失败');
      }
    },

    // 取消下载
    'channels_cancel_download': async () => {
      try {
        const res = await api.post('/api/channels/download/cancel', {
          task_id: args?.task_id
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '取消下载失败');
      }
    },

    // 获取下载任务列表
    'channels_get_download_tasks': async () => {
      try {
        const res = await api.get('/api/channels/download/tasks');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取下载任务失败');
      }
    },

    // 删除下载任务
    'channels_delete_download_task': async () => {
      try {
        const res = await api.delete(`/api/channels/download/tasks/${args?.task_id}`);
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '删除任务失败');
      }
    },

    // 获取证书信息
    'channels_get_cert_info': async () => {
      try {
        const res = await api.get('/api/channels/certificate');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取证书信息失败');
      }
    },

    // 生成证书
    'channels_generate_cert': async () => {
      try {
        const res = await api.post('/api/channels/certificate/generate');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '生成证书失败');
      }
    },

    // 导出证书
    'channels_export_cert': async () => {
      try {
        const res = await api.post('/api/channels/certificate/export', {
          export_path: args?.export_path
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '导出证书失败');
      }
    },

    // 获取证书安装说明
    'channels_get_cert_instructions': async () => {
      try {
        const res = await api.get('/api/channels/certificate/instructions');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取证书说明失败');
      }
    },

    // 获取配置
    'channels_get_config': async () => {
      try {
        const res = await api.get('/api/channels/config');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取配置失败');
      }
    },

    // 更新配置
    'channels_update_config': async () => {
      try {
        const res = await api.put('/api/channels/config', {
          proxy_port: args?.proxy_port,
          download_dir: args?.download_dir,
          auto_decrypt: args?.auto_decrypt,
          quality_preference: args?.quality_preference,
          clear_on_exit: args?.clear_on_exit
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '更新配置失败');
      }
    },

    // ==================== 透明捕获 API ====================

    // 获取驱动状态
    'channels_get_driver_status': async () => {
      try {
        const res = await api.get('/api/channels/driver/status');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取驱动状态失败');
      }
    },

    // 安装驱动
    'channels_install_driver': async () => {
      try {
        const res = await api.post('/api/channels/driver/install');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '安装驱动失败');
      }
    },

    // 请求管理员权限重启
    'channels_request_admin_restart': async () => {
      try {
        const res = await api.post('/api/channels/driver/request-admin');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '请求管理员权限失败');
      }
    },

    // 获取捕获配置
    'channels_get_capture_config': async () => {
      try {
        const res = await api.get('/api/channels/capture/config');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取捕获配置失败');
      }
    },

    // 更新捕获配置
    'channels_update_capture_config': async () => {
      try {
        const res = await api.put('/api/channels/capture/config', {
          capture_mode: args?.capture_mode,
          use_windivert: args?.use_windivert,
          target_processes: args?.target_processes,
          no_detection_timeout: args?.no_detection_timeout,
          log_unrecognized_domains: args?.log_unrecognized_domains
        });
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '更新捕获配置失败');
      }
    },

    // 获取捕获统计
    'channels_get_capture_statistics': async () => {
      try {
        const res = await api.get('/api/channels/capture/statistics');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '获取捕获统计失败');
      }
    },

    // 系统诊断
    'channels_diagnose': async () => {
      try {
        const res = await api.get('/api/channels/diagnose');
        return res.data;
      } catch (error: any) {
        throw new Error(error.response?.data?.detail || '系统诊断失败');
      }
    },

  };

  const handler = commandMap[command];
  if (!handler) {
    // 减少日志噪音：仅在开发环境打印未知命令
    if (import.meta.env.DEV) {
      console.debug(`[invoke] Unknown command: ${command}`);
    }
    // 返回安全的默认值而不是抛出错误
    return null;
  }

  try {
    return await handler();
  } catch (error) {
    console.error(`Error executing command ${command}:`, error);
    // 根据命令类型返回合适的默认值
    if (command.includes('get_') && command.includes('tasks')) {
      return [];
    }
    // ⚠️ 对于其他命令，重新抛出错误而不是返回 null
    // 这样上层可以捕获到真实的错误信息
    throw error;
  }
}

/**
 * 模拟 Tauri 事件监听
 */
export function listen(event: string, _callback: (data: any) => void): Promise<() => void> {
  console.log(`[listen] ${event}`);
  
  // 可以使用 WebSocket 实现实时事件
  // 或者使用轮询
  
  const unlisten = () => {
    console.log(`[unlisten] ${event}`);
  };

  return Promise.resolve(unlisten);
}

/**
 * 获取当前的 API Base URL（包含动态端口）
 * 用于需要直接构造 API URL 的场景（如图片代理）
 */
export function getApiBaseUrl(): string {
  return API_BASE;
}

// 导出兼容 Tauri 的 API
export const tauri = {
  invoke,
  event: { listen },
};
