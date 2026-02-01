// Electron API 类型定义

// 更新相关类型
interface UpdateInfo {
  has_update: boolean;
  latest_version: string;
  release_notes: string;
  file_size: number;
  is_mandatory: boolean;
  download_url: string;
  file_name: string;
  file_hash: string;
  rollout_blocked?: boolean;
  rollout_message?: string;
}

interface DownloadProgress {
  percent: number;
  bytesPerSecond: number;
  transferred: number;
  total: number;
}

interface ElectronAPI {
  // 通用 IPC 调用
  invoke: (channel: string, ...args: any[]) => Promise<any>;
  
  // 文件选择
  selectDirectory: () => Promise<string | undefined>;
  selectVideoFile: () => Promise<string | undefined>;
  selectFiles: () => Promise<string[]>;
  
  // 文件操作
  showItemInFolder: (filePath: string) => Promise<void>;
  openFolder: (folderPath: string) => Promise<void>;
  fileExists: (filePath: string) => Promise<boolean>;
  getFileInfo: (filePath: string) => Promise<{
    size: number;
    created: Date;
    modified: Date;
    isFile: boolean;
    isDirectory: boolean;
  } | null>;
  generateVideoThumbnail: (videoPath: string) => Promise<string | null>;
  
  // 应用信息
  getAppVersion: () => Promise<string>;
  openExternal: (url: string) => Promise<void>;
  
  // 后端配置
  getBackendPort: () => Promise<{
    port: number | null;
    ready: boolean;
    host: string;
  }>;
  
  // 桌面通知
  showNotification: (options: {
    title: string;
    body: string;
    icon?: string;
    silent?: boolean;
  }) => Promise<{ success: boolean; error?: string }>;
  
  // 窗口控制
  minimize: () => Promise<void>;
  maximize: () => Promise<void>;
  close: () => Promise<void>;
  
  // 更新相关
  on: (channel: string, callback: (...args: any[]) => void) => void;
  off: (channel: string, callback: (...args: any[]) => void) => void;
  checkForUpdates: () => Promise<{ success: boolean; data?: UpdateInfo; error?: string }>;
  downloadUpdate: () => Promise<{ success: boolean; error?: string }>;
  installUpdate: () => Promise<{ success: boolean; error?: string }>;
  cleanUpdateFiles: () => Promise<{ success: boolean; message?: string; count?: number; size?: number; error?: string }>;
  
  // 平台信息
  platform: string;
  arch: string;
  isElectron: boolean;
}

declare global {
  interface Window {
    electron?: ElectronAPI;
  }
}

export {};
