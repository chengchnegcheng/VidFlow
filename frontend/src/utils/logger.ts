/**
 * 统一的日志工具
 * 替代 console.log/error/warn，提供更好的日志管理
 */

enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4,
}

interface LogConfig {
  level: LogLevel;
  enableConsole: boolean;
  enableStorage: boolean;
  maxStorageSize: number;
}

class Logger {
  private config: LogConfig;
  private logs: Array<{ level: string; message: string; timestamp: string; data?: any }> = [];

  constructor(config?: Partial<LogConfig>) {
    this.config = {
      level: import.meta.env.DEV ? LogLevel.DEBUG : LogLevel.INFO,
      enableConsole: true,
      enableStorage: false,
      maxStorageSize: 1000,
      ...config,
    };
  }

  /**
   * 调试日志（仅开发环境）
   */
  debug(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.DEBUG) {
      this.log('DEBUG', message, args);
      if (this.config.enableConsole) {
        console.log(`🔍 [DEBUG] ${message}`, ...args);
      }
    }
  }

  /**
   * 信息日志
   */
  info(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.INFO) {
      this.log('INFO', message, args);
      if (this.config.enableConsole) {
        console.log(`ℹ️ [INFO] ${message}`, ...args);
      }
    }
  }

  /**
   * 警告日志
   */
  warn(message: string, ...args: any[]): void {
    if (this.config.level <= LogLevel.WARN) {
      this.log('WARN', message, args);
      if (this.config.enableConsole) {
        console.warn(`⚠️ [WARN] ${message}`, ...args);
      }
    }
  }

  /**
   * 错误日志
   */
  error(message: string, error?: Error | any, ...args: any[]): void {
    if (this.config.level <= LogLevel.ERROR) {
      this.log('ERROR', message, { error, ...args });
      if (this.config.enableConsole) {
        console.error(`❌ [ERROR] ${message}`, error, ...args);
      }
    }
  }

  /**
   * WebSocket 日志
   */
  ws(action: string, data?: any): void {
    this.debug(`[WebSocket] ${action}`, data);
  }

  /**
   * API 日志
   */
  api(method: string, url: string, data?: any): void {
    this.debug(`[API] ${method} ${url}`, data);
  }

  /**
   * 内部日志存储
   */
  private log(level: string, message: string, data?: any): void {
    const logEntry = {
      level,
      message,
      timestamp: new Date().toISOString(),
      data,
    };

    if (this.config.enableStorage) {
      this.logs.push(logEntry);

      // 限制日志大小
      if (this.logs.length > this.config.maxStorageSize) {
        this.logs.shift();
      }
    }
  }

  /**
   * 获取所有日志
   */
  getLogs(): typeof this.logs {
    return [...this.logs];
  }

  /**
   * 清空日志
   */
  clearLogs(): void {
    this.logs = [];
  }

  /**
   * 导出日志（用于调试或报告）
   */
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2);
  }

  /**
   * 设置日志级别
   */
  setLevel(level: LogLevel): void {
    this.config.level = level;
  }

  /**
   * 性能测量
   */
  time(label: string): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.time(`⏱️ ${label}`);
    }
  }

  timeEnd(label: string): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.timeEnd(`⏱️ ${label}`);
    }
  }

  /**
   * 分组日志
   */
  group(label: string): void {
    if (this.config.level <= LogLevel.DEBUG && this.config.enableConsole) {
      console.group(`📂 ${label}`);
    }
  }

  groupEnd(): void {
    if (this.config.level <= LogLevel.DEBUG && this.config.enableConsole) {
      console.groupEnd();
    }
  }
}

// 导出单例实例
export const logger = new Logger();

// 导出 LogLevel 供外部使用
export { LogLevel };

// 开发环境下暴露到 window 对象，方便调试
if (import.meta.env.DEV) {
  (window as any).logger = logger;
}
