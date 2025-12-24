/**
 * 全局设置上下文 - 与后端配置同步
 */
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { invoke } from '../components/TauriIntegration';

export interface Settings {
  downloadPath: string;
  defaultQuality: string;
  defaultFormat: string;
  maxConcurrentDownloads: number;
  autoSubtitle: boolean;
  autoTranslate: boolean;
  theme: string;
  language: string;
  notifications: boolean;
  autoUpdate: boolean;
  saveHistory: boolean;
}

const defaultSettings: Settings = {
  downloadPath: '',
  defaultQuality: '1080p',
  defaultFormat: 'mp4',
  maxConcurrentDownloads: 3,
  autoSubtitle: false,
  autoTranslate: false,
  theme: 'light',
  language: 'zh-CN',
  notifications: true,
  autoUpdate: true,
  saveHistory: true
};

interface SettingsContextType {
  settings: Settings;
  updateSettings: (newSettings: Partial<Settings>) => Promise<void>;
  resetSettings: () => Promise<void>;
  loading: boolean;
}

const SettingsContext = createContext<SettingsContextType>({
  settings: defaultSettings,
  updateSettings: async () => {},
  resetSettings: async () => {},
  loading: true
});

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [loading, setLoading] = useState(true);

  // 从后端加载配置
  const loadSettingsFromBackend = async () => {
    try {
      setLoading(true);
      const response = await invoke('get_config');
      
      if (response && response.status === 'success') {
        const backendConfig = response.config;
        
        // 将后端配置转换为前端格式
        const frontendSettings: Settings = {
          downloadPath: backendConfig.download?.default_path || '',
          defaultQuality: backendConfig.download?.default_quality || '1080p',
          defaultFormat: backendConfig.download?.default_format || 'mp4',
          maxConcurrentDownloads: backendConfig.download?.max_concurrent || 3,
          autoSubtitle: backendConfig.download?.auto_subtitle || false,
          autoTranslate: backendConfig.download?.auto_translate || false,
          theme: backendConfig.app?.theme || 'light',
          language: backendConfig.app?.language || 'zh-CN',
          notifications: backendConfig.advanced?.notifications !== false,
          autoUpdate: backendConfig.advanced?.auto_update !== false,
          saveHistory: backendConfig.advanced?.save_history !== false,
        };
        
        setSettings(frontendSettings);
        console.log('✅ 设置已从后端加载:', frontendSettings);
      }
    } catch (error) {
      console.error('❌ 从后端加载设置失败，使用默认设置:', error);
      setSettings(defaultSettings);
    } finally {
      setLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    loadSettingsFromBackend();
  }, []);

  // 应用主题设置
  useEffect(() => {
    const root = document.documentElement;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    let transitionTimeout: number | undefined;

    const withThemeTransition = (fn: () => void) => {
      root.classList.add('theme-transition');

      if (transitionTimeout !== undefined) {
        window.clearTimeout(transitionTimeout);
      }

      transitionTimeout = window.setTimeout(() => {
        root.classList.remove('theme-transition');
        transitionTimeout = undefined;
      }, 250);

      fn();
    };

    const applyTheme = () => {
      if (settings.theme === 'dark') {
        root.classList.add('dark');
        return;
      }
      if (settings.theme === 'light') {
        root.classList.remove('dark');
        return;
      }

      // auto 模式根据系统
      if (mediaQuery.matches) {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
    };

    const handleSystemThemeChange = () => {
      if (settings.theme === 'auto') {
        withThemeTransition(applyTheme);
      }
    };

    withThemeTransition(applyTheme);
    mediaQuery.addEventListener('change', handleSystemThemeChange);
    return () => {
      mediaQuery.removeEventListener('change', handleSystemThemeChange);
      if (transitionTimeout !== undefined) {
        window.clearTimeout(transitionTimeout);
      }
      root.classList.remove('theme-transition');
    };
  }, [settings.theme]);

  // 更新设置（保存到后端）
  const updateSettings = async (newSettings: Partial<Settings>) => {
    const previousSettings = settings;
    const merged = { ...settings, ...newSettings };

    const normalizedDownloadPath =
      merged.downloadPath && merged.downloadPath.trim() ? merged.downloadPath : settings.downloadPath;

    const updated: Settings = {
      ...merged,
      downloadPath: normalizedDownloadPath,
    };

    if (!updated.downloadPath || !updated.downloadPath.trim()) {
      throw new Error('下载保存路径不能为空');
    }

    if (updated.maxConcurrentDownloads < 1 || updated.maxConcurrentDownloads > 10) {
      throw new Error('最大并发下载数必须在 1-10 之间');
    }

    const rollbackBackendConfig = {
      download: {
        default_path: previousSettings.downloadPath,
        default_quality: previousSettings.defaultQuality,
        default_format: previousSettings.defaultFormat,
        max_concurrent: previousSettings.maxConcurrentDownloads,
        auto_subtitle: previousSettings.autoSubtitle,
        auto_translate: previousSettings.autoTranslate,
      },
      app: {
        theme: previousSettings.theme,
        language: previousSettings.language,
      },
      advanced: {
        notifications: previousSettings.notifications,
        auto_update: previousSettings.autoUpdate,
        save_history: previousSettings.saveHistory,
      },
    };

    // 转换为后端格式
    const backendConfig = {
      download: {
        default_path: updated.downloadPath,
        default_quality: updated.defaultQuality,
        default_format: updated.defaultFormat,
        max_concurrent: updated.maxConcurrentDownloads,
        auto_subtitle: updated.autoSubtitle,
        auto_translate: updated.autoTranslate,
      },
      app: {
        theme: updated.theme,
        language: updated.language,
      },
      advanced: {
        notifications: updated.notifications,
        auto_update: updated.autoUpdate,
        save_history: updated.saveHistory,
      }
    };

    let configUpdated = false;
    try {
      await invoke('update_config', { updates: backendConfig });
      configUpdated = true;

      if (updated.maxConcurrentDownloads !== previousSettings.maxConcurrentDownloads) {
        await invoke('update_queue_config', {
          max_concurrent: updated.maxConcurrentDownloads
        });
      }

      setSettings(updated);
      console.log('✅ 设置已保存到后端');
    } catch (error) {
      console.error('❌ 保存设置到后端失败:', error);

      if (configUpdated) {
        try {
          await invoke('update_config', { updates: rollbackBackendConfig });

          if (updated.maxConcurrentDownloads !== previousSettings.maxConcurrentDownloads) {
            await invoke('update_queue_config', {
              max_concurrent: previousSettings.maxConcurrentDownloads,
            });
          }
        } catch (rollbackError) {
          console.error('❌ 回滚设置失败:', rollbackError);
        }
      }

      await loadSettingsFromBackend();
      throw error;
    }
  };

  // 重置设置
  const resetSettings = async () => {
    try {
      await invoke('reset_config');
      
      // 重新加载配置
      await loadSettingsFromBackend();
      
      console.log('✅ 设置已重置');
    } catch (error) {
      console.error('❌ 重置设置失败:', error);
      throw error;
    }
  };

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, resetSettings, loading }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within SettingsProvider');
  }
  return context;
}
