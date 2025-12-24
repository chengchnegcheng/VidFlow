/**
 * 后端连接状态管理 Context
 */
import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { invoke } from '../components/TauriIntegration';

export type BackendStatus = 'initializing' | 'ready' | 'failed';

export interface BackendState {
  status: BackendStatus;
  error?: string;
  retryCount: number;
  lastRetryTime?: number;
}

interface BackendContextType {
  state: BackendState;
  retry: () => Promise<void>;
}

const BackendContext = createContext<BackendContextType | undefined>(undefined);

const MAX_RETRIES = 10;
const RETRY_DELAY = 2000; // 2秒

export function BackendProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<BackendState>({
    status: 'initializing',
    retryCount: 0,
  });

  const checkBackend = useCallback(async () => {
    try {
      // 尝试调用健康检查
      const response = await invoke('get_system_info');

      if (response) {
        setState({
          status: 'ready',
          retryCount: 0,
        });
        console.log('✅ Backend connection established');
        return true;
      }

      throw new Error('Backend health check failed');
    } catch (error) {
      console.error('❌ Backend connection check failed:', error);
      return false;
    }
  }, []);

  const retry = useCallback(async () => {
    if (state.status === 'initializing') {
      console.log('⏳ Backend is already initializing, please wait...');
      return;
    }

    setState(prev => ({
      ...prev,
      status: 'initializing',
      lastRetryTime: Date.now(),
    }));

    // 执行重试
    for (let i = 0; i < MAX_RETRIES; i++) {
      console.log(`🔄 Retry attempt ${i + 1}/${MAX_RETRIES}...`);

      const success = await checkBackend();

      if (success) {
        return;
      }

      setState(prev => ({
        ...prev,
        retryCount: i + 1,
      }));

      if (i < MAX_RETRIES - 1) {
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      }
    }

    // 所有重试都失败
    setState({
      status: 'failed',
      error: '后端连接失败，请检查后端服务是否正常运行',
      retryCount: MAX_RETRIES,
      lastRetryTime: Date.now(),
    });
  }, [checkBackend, state.status]);

  // 初始化时检查后端
  useEffect(() => {
    retry();
  }, []);

  return (
    <BackendContext.Provider value={{ state, retry }}>
      {children}
    </BackendContext.Provider>
  );
}

export function useBackend() {
  const context = useContext(BackendContext);
  if (!context) {
    throw new Error('useBackend must be used within BackendProvider');
  }
  return context;
}
