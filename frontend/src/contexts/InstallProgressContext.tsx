import { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { subscribeSharedWebSocket } from './SharedWebSocket';

interface InstallProgress {
  [toolId: string]: {
    progress: number;
    message: string;
    installing: boolean;
  };
}

interface InstallProgressContextType {
  installProgress: InstallProgress;
  setToolProgress: (toolId: string, progress: number, message: string) => void;
  setToolInstalling: (toolId: string, installing: boolean) => void;
  clearToolProgress: (toolId: string) => void;
}

const InstallProgressContext = createContext<InstallProgressContextType | undefined>(undefined);

export function InstallProgressProvider({ children }: { children: ReactNode }) {
  const [installProgress, setInstallProgress] = useState<InstallProgress>({});
  const isMountedRef = useRef(true);
  const lastProgressRef = useRef<{ [key: string]: number }>({});

  // WebSocket 连接（共享通道）
  useEffect(() => {
    isMountedRef.current = true;

    const unsubscribe = subscribeSharedWebSocket((data) => {
      if (!isMountedRef.current) return;

      if (data?.type === 'tool_install_progress') {
        const toolId = data.tool_id;
        const currentProgress = data.progress;
        const lastProgress = lastProgressRef.current[toolId];

        // 只在进度实际变化时打印日志(避免日志爆炸)
        if (lastProgress !== currentProgress) {
          console.log('[InstallProgressContext] Progress update:', {
            tool_id: toolId,
            progress: currentProgress,
            message: data.message
          });
          lastProgressRef.current[toolId] = currentProgress;
        }

        setInstallProgress(prev => ({
          ...prev,
          [toolId]: {
            progress: currentProgress,
            message: data.message,
            installing: currentProgress < 100
          }
        }));

        // 安装完成后清理进度
        if (currentProgress === 100) {
          setTimeout(() => {
            setInstallProgress(prev => {
              const newProgress = { ...prev };
              delete newProgress[toolId];
              return newProgress;
            });
            // 清理进度记录
            delete lastProgressRef.current[toolId];
          }, 3000);
        }
      }

      if (data?.type === 'tool_install_error') {
        console.log('[InstallProgressContext] Install error:', {
          tool_id: data.tool_id,
          error: data.error
        });

        setInstallProgress(prev => ({
          ...prev,
          [data.tool_id]: {
            progress: 100,
            message: data.error || '安装失败',
            installing: false
          }
        }));

        setTimeout(() => {
          setInstallProgress(prev => {
            const newProgress = { ...prev };
            delete newProgress[data.tool_id];
            return newProgress;
          });
        }, 3000);
      }
    });

    return () => {
      isMountedRef.current = false;
      unsubscribe();
    };
  }, []);

  const setToolProgress = (toolId: string, progress: number, message: string) => {
    setInstallProgress(prev => ({
      ...prev,
      [toolId]: {
        progress,
        message,
        installing: progress < 100
      }
    }));
  };

  const setToolInstalling = (toolId: string, installing: boolean) => {
    setInstallProgress(prev => ({
      ...prev,
      [toolId]: {
        ...prev[toolId],
        installing
      }
    }));
  };

  const clearToolProgress = (toolId: string) => {
    setInstallProgress(prev => {
      const newProgress = { ...prev };
      delete newProgress[toolId];
      return newProgress;
    });
  };

  return (
    <InstallProgressContext.Provider
      value={{
        installProgress,
        setToolProgress,
        setToolInstalling,
        clearToolProgress
      }}
    >
      {children}
    </InstallProgressContext.Provider>
  );
}

export function useInstallProgress() {
  const context = useContext(InstallProgressContext);
  if (context === undefined) {
    throw new Error('useInstallProgress must be used within an InstallProgressProvider');
  }
  return context;
}
