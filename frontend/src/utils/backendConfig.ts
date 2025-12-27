/**
 * 统一的后端配置管理
 * 所有与后端端口相关的逻辑集中在这里，避免多处初始化导致的竞态条件
 */

type BackendStatus = 'starting' | 'ready' | 'failed' | 'disconnected';

interface BackendConfig {
  port: number | null;
  host: string;
  ready: boolean;
  status: BackendStatus;
  error: string | null;
}

class BackendConfigManager {
  private config: BackendConfig = {
    port: null,
    host: '127.0.0.1',
    ready: false,
    status: 'starting',
    error: null,
  };

  private initialized = false;
  private initializing = false;
  private initAttempts = 0;
  private readonly MAX_ATTEMPTS = 10;
  private listeners: Array<(config: BackendConfig) => void> = [];

  /**
   * 获取当前后端配置
   */
  getConfig(): BackendConfig {
    return { ...this.config };
  }

  /**
   * 获取 API Base URL
   */
  getApiBaseUrl(): string {
    if (!this.config.port) {
      return '';
    }
    return `http://${this.config.host}:${this.config.port}`;
  }

  /**
   * 检查后端是否就绪
   */
  isReady(): boolean {
    return this.config.ready && this.config.port !== null;
  }

  /**
   * 初始化后端配置
   */
  async initialize(): Promise<boolean> {
    if (this.initialized) return true;
    if (this.initializing) {
      // 等待初始化完成
      for (let i = 0; i < 50; i++) {
        if (this.initialized) return true;
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      return this.initialized;
    }

    this.initializing = true;
    this.initAttempts++;

    if (window.electron) {
      try {
        console.log(`🔄 [Attempt ${this.initAttempts}/${this.MAX_ATTEMPTS}] Requesting backend config from Electron...`);
        const electronConfig = await window.electron.invoke('get-backend-port');
        console.log('📡 Backend config received:', electronConfig);

        // 更新配置
        this.updateConfig({
          port: electronConfig.port,
          host: electronConfig.host || '127.0.0.1',
          ready: electronConfig.ready,
          status: electronConfig.status || (electronConfig.ready ? 'ready' : 'starting'),
          error: electronConfig.error || null,
        });

        if (this.config.ready && this.config.port) {
          // 验证后端健康
          try {
            const axios = (await import('axios')).default;
            const healthUrl = `${this.getApiBaseUrl()}/api/v1/system/health`;
            console.log('🔍 Verifying backend health:', healthUrl);

            const response = await axios.get(healthUrl, { timeout: 3000 });
            if (response.status === 200) {
              this.initialized = true;
              this.initializing = false;
              console.log('✅ Backend initialization successful');
              this.notifyListeners();
              return true;
            }
          } catch (healthError: any) {
            console.error('❌ Backend health check failed:', healthError.message);
            this.updateConfig({
              ready: false,
              status: 'failed',
              error: '后端健康检查失败',
            });
          }
        } else if (electronConfig.status === 'failed') {
          console.error('❌ Backend startup failed:', electronConfig.error);
          this.initializing = false;
          return false;
        } else {
          console.warn('⚠️ Backend not ready yet, will retry...');
        }
      } catch (error: any) {
        console.error('❌ Failed to get backend config:', error);
        this.updateConfig({
          status: 'failed',
          error: error.message || '无法获取后端配置',
        });
      }
    } else {
      console.warn('⚠️ window.electron not available');
      this.initialized = true;
      this.initializing = false;
      return true;
    }

    this.initializing = false;
    return false;
  }

  /**
   * 持续尝试初始化直到成功
   */
  async startInitialization(): Promise<void> {
    // 监听后端就绪事件
    if (window.electron) {
      window.electron.on('backend-ready', (data: { port: number }) => {
        console.log('📢 Received backend-ready event:', data);
        this.updateConfig({
          port: data.port,
          ready: true,
          status: 'ready',
          error: null,
        });
        this.initialized = true;
        this.notifyListeners();
      });

      window.electron.on('backend-error', (data: { message: string }) => {
        console.error('📢 Received backend-error event:', data);
        this.updateConfig({
          ready: false,
          status: 'failed',
          error: data.message,
        });
        this.notifyListeners();
      });

      window.electron.on('backend-disconnected', (data: { code: number; message: string }) => {
        console.warn('📢 Received backend-disconnected event:', data);
        this.updateConfig({
          ready: false,
          status: 'disconnected',
          error: data.message,
        });
        this.initialized = false;
        this.notifyListeners();
      });
    }

    // 主动轮询初始化
    for (let i = 0; i < this.MAX_ATTEMPTS; i++) {
      const success = await this.initialize();
      if (success) {
        console.log('✅ Backend configuration initialized successfully');
        return;
      }
      console.log(`⏳ Waiting 2 seconds before retry (${i + 1}/${this.MAX_ATTEMPTS})...`);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    console.error('❌ Failed to initialize backend config after maximum attempts');
    this.updateConfig({
      status: 'failed',
      error: '后端初始化超时',
    });
  }

  /**
   * 更新配置并通知监听器
   */
  private updateConfig(updates: Partial<BackendConfig>): void {
    this.config = { ...this.config, ...updates };
    this.notifyListeners();
  }

  /**
   * 添加配置变化监听器
   */
  addListener(listener: (config: BackendConfig) => void): () => void {
    this.listeners.push(listener);
    // 返回取消监听的函数
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  /**
   * 通知所有监听器
   */
  private notifyListeners(): void {
    this.listeners.forEach(listener => {
      try {
        listener(this.getConfig());
      } catch (error) {
        console.error('Error in backend config listener:', error);
      }
    });
  }

  /**
   * 重置配置（用于测试或重启）
   */
  reset(): void {
    this.config = {
      port: null,
      host: '127.0.0.1',
      ready: false,
      status: 'starting',
      error: null,
    };
    this.initialized = false;
    this.initializing = false;
    this.initAttempts = 0;
    this.notifyListeners();
  }
}

// 单例实例
const backendConfigManager = new BackendConfigManager();

// 启动初始化
console.log('🚀 Starting backend configuration initialization...');
backendConfigManager.startInitialization();

export default backendConfigManager;
