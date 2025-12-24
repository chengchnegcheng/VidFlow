/**
 * Electron API 类型定义
 */

interface ElectronAPI {
  // 事件监听
  on(channel: string, callback: (...args: any[]) => void): void;
  
  // 调用主进程方法
  invoke(channel: string, ...args: any[]): Promise<any>;
}

interface Window {
  electron: ElectronAPI;
}
