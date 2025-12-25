import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { toast } from 'sonner';
import {
  AlertCircle,
  CheckCircle2,
  Info,
  Download,
  ExternalLink,
  Loader2,
  RefreshCw,
  Zap
} from 'lucide-react';
import { Alert, AlertDescription } from './ui/alert';
import { getApiBaseUrl } from './TauriIntegration';
import { AIToolsCard } from './AIToolsCard';
import { useInstallProgress } from '../contexts/InstallProgressContext';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from './ui/alert-dialog';

interface ToolInfo {
  id: string;
  name: string;
  description: string;
  installed: boolean;
  version: string | null;
  path: string | null;
  required: boolean;
  official_url: string;
  compatible?: boolean;
  incompatible_reason?: string | null;
  bundled?: boolean;  // 是否为内置工具
}

interface GPUInstallGuide {
  title: string;
  description: string;
  benefits: string[];
  requirements: string[];
  steps: Array<{
    step: number;
    title: string;
    description: string;
    action: string;
  }>;
  manual_install: {
    title: string;
    command: string;
    note: string;
  };
}

interface GPUInfo {
  gpu_available: boolean;
  gpu_enabled: boolean;
  device_name?: string | null;
  cuda_version?: string | null;
  can_install: boolean;
  install_guide?: GPUInstallGuide | null;
  installing?: boolean;
}

export function ToolsConfig() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [gpuInfo, setGpuInfo] = useState<GPUInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState<string | null>(null);

  // 使用全局安装进度状态
  const { installProgress } = useInstallProgress();

  // AI 工具状态
  const [aiToolsStatus, setAiToolsStatus] = useState<{
    installed: boolean;
    faster_whisper: boolean;
    torch: boolean;
    version: string | null;
    device: string;
  } | null>(null);

  // AI 版本选择 - 从 localStorage 读取用户上次的选择
  const [aiVersion, setAiVersion] = useState<'cpu' | 'cuda'>(() => {
    try {
      const platform = window.electron?.platform;
      if (platform === 'darwin') return 'cpu';
      const saved = localStorage.getItem('vidflow_ai_version');
      return (saved === 'cuda' || saved === 'cpu') ? saved : 'cpu';
    } catch {
      return 'cpu';
    }
  });

  const [installingAI, setInstallingAI] = useState(false);
  const [uninstallingAI, setUninstallingAI] = useState(false);
  const [showUninstallConfirm, setShowUninstallConfirm] = useState(false);

  // 当用户更改 AI 版本时，保存到 localStorage
  const handleAIVersionChange = useCallback((version: 'cpu' | 'cuda') => {
    const platform = window.electron?.platform;
    const resolvedVersion = (platform === 'darwin' && version === 'cuda') ? 'cpu' : version;
    setAiVersion(resolvedVersion);
    try {
      localStorage.setItem('vidflow_ai_version', resolvedVersion);
    } catch (error) {
      console.error('Failed to save AI version to localStorage:', error);
    }
  }, []);

  // 获取工具状态
  const fetchToolsStatus = useCallback(async () => {
    try {
      const apiUrl = getApiBaseUrl();
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 增加到10秒

      const response = await fetch(`${apiUrl}/api/v1/system/tools/status`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        setTools(data);
      } else {
        console.error('获取工具状态失败:', response.status);
      }
    } catch (error) {
      // 静默处理超时错误，避免控制台噪音
      if (error instanceof Error && error.name === 'AbortError') {
        console.warn('[ToolsConfig] 工具状态请求超时，将在下次轮询时重试');
      } else {
        console.error('[ToolsConfig] Failed to fetch tools status:', error);
      }
    }
  }, []);

  // 获取 GPU 状态
  const fetchGPUStatus = useCallback(async () => {
    try {
      const apiUrl = getApiBaseUrl();
      console.log('[GPU] Fetching GPU status from:', `${apiUrl}/api/v1/system/gpu/status`);
      const response = await fetch(`${apiUrl}/api/v1/system/gpu/status`);
      console.log('[GPU] Response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('[GPU] Received GPU data:', data);
        setGpuInfo(data?.data ?? data);
      } else {
        console.error('[GPU] Failed to fetch GPU status:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('[GPU] Failed to fetch GPU status:', error);
    }
  }, []);

  // 获取 AI 工具状态
  const fetchAIToolsStatus = useCallback(async () => {
    try {
      const apiUrl = getApiBaseUrl();
      const controller = new AbortController();
      // AI工具状态接口可能需要加载torch，增加到20秒超时
      const timeoutId = setTimeout(() => controller.abort(), 20000);

      const response = await fetch(`${apiUrl}/api/v1/system/tools/ai/status`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        setAiToolsStatus(data);
      }
    } catch (error) {
      // 静默处理超时错误，避免控制台噪音和影响其他状态
      if (error instanceof Error && error.name === 'AbortError') {
        console.warn('[ToolsConfig] AI 工具状态请求超时（20秒），使用缓存数据，将在下次轮询时重试');
        // 超时时保持当前状态，不清空数据
      } else {
        console.error('[ToolsConfig] Failed to fetch AI tools status:', error);
      }
    }
  }, []);

  // 监听安装进度变化
  useEffect(() => {
    console.log('[ToolsConfig] installProgress changed:', installProgress);
    console.log('[ToolsConfig] State:', { installing, installingAI, uninstallingAI });

    // 同步状态到 ref，供定时器使用
    installingAIRef.current = installingAI;
    uninstallingAIRef.current = uninstallingAI;

    const clearUninstallTimeout = () => {
      if (uninstallTimeoutRef.current) {
        clearTimeout(uninstallTimeoutRef.current);
        uninstallTimeoutRef.current = null;
      }
    };

    // 检查 AI 工具安装完成
    const aiProgress = installProgress['ai-tools'];
    if (aiProgress && aiProgress.progress === 100 && installingAI) {
      console.log('[ToolsConfig] AI installation complete:', aiProgress);
      setTimeout(() => {
        fetchAIToolsStatus();
        fetchToolsStatus();
        fetchGPUStatus();
        setInstallingAI(false);

        const message = aiProgress.message || 'AI 工具安装完成';
        if (message.includes('失败') || message.includes('错误') || message.toLowerCase().includes('error')) {
          toast.error('AI 工具安装失败', { description: message });
        } else {
          toast.success(message);
        }
      }, 1000);
    }

    // 检查 AI 工具卸载完成
    const aiUninstallProgress = installProgress['ai-tools-uninstall'];
    if (aiUninstallProgress && aiUninstallProgress.progress === 100 && uninstallingAI) {
      console.log('[ToolsConfig] AI uninstallation complete:', aiUninstallProgress);
      clearUninstallTimeout();
      setTimeout(async () => {
        // 等待后端完成收尾工作后再刷新状态（增加到5秒）
        await new Promise(resolve => setTimeout(resolve, 5000));

        // 重试机制：最多尝试3次，每次间隔2秒
        let retries = 3;
        while (retries > 0) {
          await fetchAIToolsStatus();
          await fetchToolsStatus();

          // 等待状态更新
          await new Promise(resolve => setTimeout(resolve, 500));

          // 检查是否真的卸载了（通过检查 aiToolsStatus）
          // 如果还显示已安装，继续重试
          retries--;
          if (retries > 0) {
            console.log(`[ToolsConfig] Retrying status fetch, ${retries} attempts left`);
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        }

        setUninstallingAI(false);

        const message = aiUninstallProgress.message || 'AI 工具卸载完成';
        if (message.includes('失败') || message.includes('错误') || message.toLowerCase().includes('error')) {
          toast.error('AI 工具卸载失败', { description: message });
        } else {
          toast.success(message);
        }
      }, 1200);
    }

    // 检查其他工具安装完成
    if (installing && installProgress[installing]) {
      const progress = installProgress[installing];
      if (progress.progress === 100) {
        setTimeout(() => {
          fetchToolsStatus();
          setInstalling(null);
        }, 1000);
      }
    }
    return () => {
      clearUninstallTimeout();
    };
  }, [installProgress, installing, installingAI, uninstallingAI, fetchAIToolsStatus, fetchGPUStatus, fetchToolsStatus]);

  // 安装工具
  const handleInstall = async (toolId: string, toolName: string) => {
    setInstalling(toolId);
    try {
      const apiUrl = getApiBaseUrl();
      const endpoint = toolId === 'faster-whisper' ? 'whisper' : toolId;
      const response = await fetch(
        `${apiUrl}/api/v1/system/tools/install/${endpoint}`,
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();

        if (data && Object.prototype.hasOwnProperty.call(data, 'updated') && data.updated === false) {
          toast.success(data.message || `${toolName} 已是最新版本`);
          setInstalling(null);
          await fetchToolsStatus();
          return;
        }
      } else {
        const error = await response.json();
        toast.error(`${toolName} 安装失败`, {
          description: error.detail || '请检查网络连接'
        });
        setInstalling(null);
      }
    } catch (error) {
      console.error('Install failed:', error);
      toast.error('安装失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
      setInstalling(null);
    }
  };

  // 打开官网
  const handleOpenUrl = (url: string) => {
    window.open(url, '_blank');
  };

  // 恢复 yt-dlp 到内置版本
  const handleReset = async (toolId: string) => {
    if (toolId !== 'ytdlp') {
      toast.error('仅支持恢复 yt-dlp');
      return;
    }

    try {
      const apiUrl = getApiBaseUrl();
      const response = await fetch(
        `${apiUrl}/api/v1/system/tools/ytdlp/downloaded`,
        { method: 'DELETE' }
      );
      
      if (response.ok) {
        const result = await response.json();
        toast.success(result.message || '恢复成功');
        await fetchToolsStatus(); // 刷新状态
      } else {
        const error = await response.json();
        toast.error('恢复失败', {
          description: error.detail || '未知错误'
        });
      }
    } catch (error) {
      console.error('Reset failed:', error);
      toast.error('恢复失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  const hasInitialized = useRef(false);
  const isMountedRef = useRef(true);
  const uninstallTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const installingAIRef = useRef(false);
  const uninstallingAIRef = useRef(false);

  // 失败重试计数器和限流机制
  const failureCountRef = useRef(0);
  const lastToastTimeRef = useRef(0);
  const MAX_FAILURES = 3; // 最多连续失败3次后降低频率

  const refreshAll = useCallback(
    async (options?: { skipDelay?: boolean }) => {
      if (!isMountedRef.current) return;
      setLoading(true);

      // 首次进入时等待端口初始化，后续跳过
      if (!hasInitialized.current && !options?.skipDelay) {
        await new Promise(resolve => setTimeout(resolve, 300));
        hasInitialized.current = true;
      }

      if (!isMountedRef.current) return;

      try {
        // 核心接口：必须成功，失败才提示（10秒超时）
        const coreTimeoutPromise = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Core request timeout')), 10000)
        );

        await Promise.race([
          Promise.all([
            fetchToolsStatus().catch(err => {
              console.error('[ToolsConfig] Failed to fetch tools status:', err);
            }),
            fetchGPUStatus().catch(err => {
              console.error('[ToolsConfig] Failed to fetch GPU status:', err);
            })
          ]),
          coreTimeoutPromise
        ]);

        // 成功时重置失败计数
        failureCountRef.current = 0;

        // AI接口：完全异步非阻塞，超时静默，不影响其他状态
        // 即使超时也不触发任何Toast，仅打印debug日志
        (async () => {
          try {
            await fetchAIToolsStatus();
          } catch (err) {
            // AI接口超时/失败：完全静默，仅debug日志
            if (err instanceof Error && err.name === 'AbortError') {
              console.debug('[ToolsConfig] AI接口超时（静默处理，不影响体验）');
            } else {
              console.debug('[ToolsConfig] AI接口请求失败（静默处理）:', err);
            }
            // 沿用上次的AI状态，不更新也不清空
          }
        })();

      } catch (error) {
        failureCountRef.current += 1;

        // 限流：连续失败时减少日志和 toast 频率
        const shouldShowToast = Date.now() - lastToastTimeRef.current > 30000; // 30秒内最多显示1次toast

        if (failureCountRef.current <= MAX_FAILURES) {
          console.warn(`[ToolsConfig] 核心工具状态请求失败 (${failureCountRef.current}/${MAX_FAILURES})，将在下次轮询时重试`);
        }

        if (error instanceof Error && error.message === 'Core request timeout') {
          if (shouldShowToast && failureCountRef.current === 1) {
            // 第一次失败：温和的info提示
            toast.info('工具基础状态加载中，请稍候...', {
              duration: 3000
            });
            lastToastTimeRef.current = Date.now();
          }
        } else if (failureCountRef.current === MAX_FAILURES && shouldShowToast) {
          // 连续失败3次才显示错误提示
          console.error('[ToolsConfig] Failed to refresh:', error);
          toast.error('核心工具状态加载失败', {
            description: '请检查后端服务是否正常运行'
          });
          lastToastTimeRef.current = Date.now();
        }
      } finally {
        if (isMountedRef.current) {
          setLoading(false);
        }
      }
    },
    [fetchAIToolsStatus, fetchGPUStatus, fetchToolsStatus]
  );

  useEffect(() => {
    isMountedRef.current = true;

    const runInitial = async () => {
      // 初始化防抖：延迟1秒触发，给后端缓冲时间
      // 避免页面刚加载就立即触发超时
      await new Promise(resolve => setTimeout(resolve, 1000));
      if (isMountedRef.current) {
        await refreshAll();
      }
    };

    runInitial();

    const onVisibilityChange = () => {
      // 只有在没有进行安装/卸载操作且连续失败次数少于阈值时才刷新
      if (!document.hidden && !installingAIRef.current && !uninstallingAIRef.current) {
        // 如果已经连续失败多次，延迟触发避免雪崩
        if (failureCountRef.current >= MAX_FAILURES) {
          setTimeout(() => refreshAll({ skipDelay: true }), 3000);
        } else {
          refreshAll({ skipDelay: true });
        }
      }
    };

    // 动态轮询间隔：失败时延长间隔
    const getPollingInterval = () => {
      if (failureCountRef.current === 0) return 30000; // 30秒（正常）
      if (failureCountRef.current < MAX_FAILURES) return 45000; // 45秒（有失败）
      return 60000; // 60秒（连续失败）
    };

    let pollingTimer: ReturnType<typeof setTimeout>;
    const schedulePoll = () => {
      const interval = getPollingInterval();
      pollingTimer = setTimeout(() => {
        // 在安装或卸载 AI 工具时，跳过自动刷新，避免打断用户体验
        if (!document.hidden && !installingAIRef.current && !uninstallingAIRef.current) {
          refreshAll({ skipDelay: true });
        }
        schedulePoll(); // 递归调度下次轮询
      }, interval);
    };

    schedulePoll(); // 启动动态轮询

    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      isMountedRef.current = false;
      clearTimeout(pollingTimer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [refreshAll]); // 依赖 refreshAll（已 useCallback）

  // 安装 AI 工具
  const handleInstallAI = async () => {
    setInstallingAI(true);
    try {
      const apiUrl = getApiBaseUrl();
      const response = await fetch(
        `${apiUrl}/api/v1/system/tools/ai/install?version=${aiVersion}`,
        { method: 'POST' }
      );
      
      if (response.ok) {
        await response.json(); // 获取响应但不需要使用
        toast.info('AI 工具安装已启动', {
          description: '安装将在后台进行，请耐心等待（约5-10分钟）'
        });
        // 不立即设置 setInstallingAI(false)，等待 WebSocket 进度更新
      } else {
        const error = await response.json();
        setInstallingAI(false);
        toast.error('AI 工具安装失败', {
          description: error.detail || '请检查网络连接和 Python 版本'
        });
      }
    } catch (error) {
      console.error('Install AI tools failed:', error);
      setInstallingAI(false);
      toast.error('安装失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  // 卸载 AI 工具
  const handleUninstallAI = () => {
    setShowUninstallConfirm(true);
  };

  const confirmUninstallAI = async () => {
    setShowUninstallConfirm(false);
    setUninstallingAI(true);
    if (uninstallTimeoutRef.current) {
      clearTimeout(uninstallTimeoutRef.current);
    }
    uninstallTimeoutRef.current = setTimeout(() => {
      if (!isMountedRef.current) return;
      if (uninstallingAI) {
        toast.warning('卸载时间较长', {
          description: '卸载仍在进行中，请继续等待。如果超过 5 分钟无响应，请刷新页面重试。',
          duration: 15000
        });
      }
    }, 120000);
    toast.info('正在卸载 AI 工具...', {
      description: '这可能需要 10-30 秒，请耐心等待',
      duration: 30000
    });
    try {
      const apiUrl = getApiBaseUrl();
      const response = await fetch(
        `${apiUrl}/api/v1/system/tools/ai/uninstall`,
        { method: 'POST' }
      );
      
      if (response.ok) {
        toast.info('卸载已开始', {
          description: '请稍等，进度将实时更新'
        });
      } else {
        const error = await response.json();
        toast.error('卸载失败', {
          description: error.detail
        });
        setUninstallingAI(false);
        if (uninstallTimeoutRef.current) {
          clearTimeout(uninstallTimeoutRef.current);
          uninstallTimeoutRef.current = null;
        }
      }
    } catch (error) {
      console.error('Uninstall AI tools failed:', error);
      toast.error('卸载失败');
      setUninstallingAI(false);
      if (uninstallTimeoutRef.current) {
        clearTimeout(uninstallTimeoutRef.current);
        uninstallTimeoutRef.current = null;
      }
    }
  };

  // 分组工具
  const externalTools = tools.filter(t => t.id === 'ffmpeg' || t.id === 'ytdlp');

  // Loading 状态
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">工具配置</h2>
          <p className="text-muted-foreground mt-1">
            管理 VidFlow 依赖的外部工具
          </p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => {
              fetchToolsStatus();
              fetchAIToolsStatus();
              fetchGPUStatus();
            }}
            disabled={loading}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新状态
          </Button>
        </div>
      </div>

      {/* AI 功能 */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">AI 功能</h3>
        
        {/* AI 工具卡片（新的独立组件） */}
        <AIToolsCard
          status={aiToolsStatus}
          version={aiVersion}
          installing={installingAI}
          uninstalling={uninstallingAI}
          progress={installProgress['ai-tools']}
          uninstallProgress={installProgress['ai-tools-uninstall']}
          onVersionChange={handleAIVersionChange}
          onInstall={handleInstallAI}
          onUninstall={handleUninstallAI}
        />
        
        {/* GPU 加速状态 */}
        {gpuInfo && aiToolsStatus?.installed && (
          <GPUStatusCard gpuInfo={gpuInfo} onRefresh={fetchGPUStatus} />
        )}
      </div>

      {/* 外部工具 */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">外部工具</h3>
        {externalTools.map((tool) => (
          <ToolCard
            key={tool.id}
            tool={tool}
            installing={installing === tool.id}
            progress={installProgress[tool.id]}
            onInstall={() => handleInstall(tool.id, tool.name)}
            onReset={() => handleReset(tool.id)}
            onOpenUrl={() => handleOpenUrl(tool.official_url)}
          />
        ))}
      </div>

      {/* 卸载确认对话框 */}
      <AlertDialog open={showUninstallConfirm} onOpenChange={setShowUninstallConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认卸载 AI 工具</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>将删除以下组件：</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>faster-whisper</li>
                  <li>PyTorch（torch、torchvision、torchaudio）</li>
                  <li>ctranslate2</li>
                  <li>onnxruntime</li>
                </ul>
                <p className="text-destructive">
                  此操作不可撤销，卸载后需要重新安装才能使用 AI 字幕功能。
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={uninstallingAI}>取消</AlertDialogCancel>
            <AlertDialogAction onClick={confirmUninstallAI} className="bg-destructive" disabled={uninstallingAI}>
              确认卸载
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// 工具卡片组件
function ToolCard({
  tool,
  installing,
  progress,
  onInstall,
  onReset,
  onOpenUrl
}: {
  tool: ToolInfo;
  installing: boolean;
  progress?: { progress: number; message: string };
  onInstall: () => void;
  onReset?: () => void;
  onOpenUrl: () => void;
}) {
  const getStatusIcon = () => {
    if (tool.bundled) {
      return <CheckCircle2 className="w-5 h-5 text-blue-500" />;
    }
    if (tool.installed) {
      return <CheckCircle2 className="w-5 h-5 text-green-500" />;
    }
    if (tool.required) {
      return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
    return <Info className="w-5 h-5 text-blue-500" />;
  };

  const getStatusText = () => {
    if (tool.bundled) return '应用内置';
    if (tool.installed) return '已安装';
    return '未安装';
  };

  const getStatusBadge = () => {
    if (tool.bundled) {
      return <Badge variant="secondary" className="text-xs bg-blue-500/10 text-blue-600 border-blue-200">内置</Badge>;
    }
    if (tool.required) {
      return <Badge variant="destructive" className="text-xs">必需</Badge>;
    }
    return <Badge variant="secondary" className="text-xs">可选</Badge>;
  };

  const showInstallButton = !tool.installed && (tool.compatible !== false);
  const showIncompatibleWarning = tool.compatible === false;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            {getStatusIcon()}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg">{tool.name}</CardTitle>
                {getStatusBadge()}
              </div>
              <CardDescription className="mt-1">
                {tool.description}
              </CardDescription>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onOpenUrl}
            className="ml-2"
          >
            <ExternalLink className="w-4 h-4" />
            <span className="ml-1 text-xs">官网</span>
          </Button>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* 状态信息 */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">状态</span>
            <div className="font-medium mt-1">{getStatusText()}</div>
          </div>
          <div>
            <span className="text-muted-foreground">版本</span>
            <div className="font-medium mt-1">
              {tool.version || 'N/A'}
            </div>
          </div>
        </div>

        {/* 路径信息 */}
        {tool.path && (
          <div className="text-sm">
            <span className="text-muted-foreground">路径</span>
            <div className="font-mono text-xs mt-1 p-2 bg-muted rounded">
              {tool.path}
            </div>
          </div>
        )}

        {/* 提示信息 */}
        {tool.bundled ? (
          <Alert className="border-blue-200 bg-blue-50/50">
            <CheckCircle2 className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-blue-900">
              <span className="font-medium">应用内置工具</span>
              <br />
              {tool.id === 'ytdlp' ? (
                <>
                  {tool.name} 已预装在应用中。由于视频网站频繁更新，建议定期检查更新以获得最佳兼容性。
                </>
              ) : (
                <>
                  {tool.name} 已预装在应用中，无需手动安装，开箱即用。
                </>
              )}
            </AlertDescription>
          </Alert>
        ) : (
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              {tool.required ? (
                <>
                  <span className="font-medium">必需组件</span>
                  <br />
                  {tool.name} 用于{tool.description === '视频处理工具' ? '视频下载、格式转换等核心功能' : '解析和下载各大视频网站的视频'}。
                </>
              ) : (
                <>
                  <span className="font-medium">可选组件</span>
                  <br />
                  {tool.name} 用于 AI 字幕生成功能。需要兼容 CUDA 支持（推荐），不影响大部分核心功能。
                </>
              )}
            </AlertDescription>
          </Alert>
        )}

        {/* 不兼容警告 */}
        {showIncompatibleWarning && tool.incompatible_reason && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <span className="font-medium">兼容性问题</span>
              <br />
              {tool.incompatible_reason}
            </AlertDescription>
          </Alert>
        )}

        {/* 安装进度 */}
        {progress && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{progress.message}</span>
              <span className="font-medium">{progress.progress.toFixed(1)}%</span>
            </div>
            <Progress value={progress.progress} className="h-2" />
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex flex-wrap gap-2">
          {/* FFmpeg 内置工具：不显示操作按钮 */}
          {tool.bundled && tool.id === 'ffmpeg' && (
            <p className="text-sm text-muted-foreground py-2">
              内置工具版本随应用更新而更新
            </p>
          )}

          {tool.id === 'ffmpeg' && tool.installed && !tool.bundled && (
            <Button
              onClick={onInstall}
              disabled={installing}
              variant="outline"
              className="flex-1"
            >
              {installing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  更新中...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  检查更新
                </>
              )}
            </Button>
          )}

          {/* yt-dlp：无论是否内置，都提供检查更新；内置额外提供恢复默认 */}
          {tool.id === 'ytdlp' && tool.installed && (
            <>
              <Button
                onClick={onInstall}
                disabled={installing}
                variant="outline"
                className="flex-1"
              >
                {installing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    更新中...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    检查更新
                  </>
                )}
              </Button>
              {tool.bundled && (
                <Button
                  onClick={onReset}
                  disabled={installing}
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground"
                >
                  恢复默认
                </Button>
              )}
            </>
          )}
          
          {/* 未安装工具：显示安装按钮 */}
          {!tool.bundled && !tool.installed && showInstallButton && (
            <Button
              onClick={onInstall}
              disabled={installing}
              className="flex-1"
            >
              {installing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  安装中...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  自动安装
                </>
              )}
            </Button>
          )}
          
          {/* 查看说明按钮（所有非内置工具） */}
          {!tool.bundled && (
            <Button
              variant="outline"
              onClick={onOpenUrl}
              disabled={installing}
            >
              查看说明
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// GPU 加速状态卡片
function GPUStatusCard({ gpuInfo, onRefresh }: { gpuInfo: GPUInfo; onRefresh: () => void }) {
  const { installProgress } = useInstallProgress();
  const gpuProgress = installProgress['gpu'];

  const [showInstallConfirm, setShowInstallConfirm] = useState(false);
  const [startingInstall, setStartingInstall] = useState(false);
  const handledCompletionRef = useRef(false);

  const statusText = gpuInfo.gpu_enabled
    ? '已启用'
    : gpuInfo.gpu_available
      ? '未启用'
      : '未检测到 GPU';

  const isInstalling = Boolean(gpuProgress?.installing) || Boolean(gpuInfo.installing) || startingInstall;
  const canInstall = gpuInfo.can_install && !gpuInfo.gpu_enabled;

  useEffect(() => {
    if (!gpuProgress) return;

    if (gpuProgress.progress < 100) {
      handledCompletionRef.current = false;
      return;
    }

    if (handledCompletionRef.current) return;
    handledCompletionRef.current = true;
    setStartingInstall(false);

    const message = gpuProgress.message || 'GPU 加速包安装完成';
    if (message.includes('失败') || message.includes('错误') || message.toLowerCase().includes('error')) {
      toast.error('GPU 加速包安装失败', { description: message });
    } else {
      toast.success(message);
    }

    setTimeout(() => {
      onRefresh();
    }, 1500);
  }, [gpuProgress, onRefresh]);

  const startInstall = async () => {
    setShowInstallConfirm(false);
    setStartingInstall(true);

    try {
      const apiUrl = getApiBaseUrl();
      const response = await fetch(`${apiUrl}/api/v1/system/gpu/install`, { method: 'POST' });

      if (response.ok) {
        toast.info('GPU 加速包安装已启动', {
          description: '安装将在后台进行，请耐心等待（约5-10分钟，完成后需重启软件）'
        });

        setTimeout(() => {
          onRefresh();
        }, 800);
        return;
      }

      const error = await response.json();
      setStartingInstall(false);
      toast.error('启动 GPU 安装失败', {
        description: error?.detail || '请检查网络连接'
      });
    } catch (error) {
      setStartingInstall(false);
      toast.error('启动 GPU 安装失败', {
        description: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  const getStatusIcon = () => {
    if (gpuInfo.gpu_enabled) {
      return <Zap className="w-5 h-5 text-green-500" />;
    }
    if (gpuInfo.gpu_available) {
      return <AlertCircle className="w-5 h-5 text-yellow-500" />;
    }
    return <Info className="w-5 h-5 text-gray-500" />;
  };

  const getStatusBadge = () => {
    if (gpuInfo.gpu_enabled) {
      return <Badge className="text-xs bg-green-500/10 text-green-600 border-green-200">已启用</Badge>;
    }
    if (gpuInfo.gpu_available) {
      return <Badge variant="secondary" className="text-xs bg-yellow-500/10 text-yellow-600 border-yellow-200">未启用</Badge>;
    }
    return <Badge variant="secondary" className="text-xs">未启用</Badge>;
  };

  const shouldShowProgress = Boolean(gpuProgress) || isInstalling;
  const effectiveProgress =
    gpuProgress || (isInstalling ? { progress: 0, message: '正在安装 GPU 加速包...' } : null);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            {getStatusIcon()}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg">GPU 加速</CardTitle>
                {getStatusBadge()}
              </div>
              <CardDescription className="mt-1">
                AI 字幕处理加速
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">状态</span>
            <div className="font-medium mt-1">{statusText}</div>
          </div>
          <div>
            <span className="text-muted-foreground">GPU</span>
            <div className="font-medium mt-1">{gpuInfo.device_name || 'N/A'}</div>
          </div>
          {gpuInfo.cuda_version && (
            <div>
              <span className="text-muted-foreground">CUDA 版本</span>
              <div className="font-medium mt-1">{gpuInfo.cuda_version}</div>
            </div>
          )}
        </div>

        {shouldShowProgress && effectiveProgress && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{effectiveProgress.message}</span>
              <span className="font-medium">{effectiveProgress.progress.toFixed(1)}%</span>
            </div>
            <Progress value={effectiveProgress.progress} className="h-2" />
          </div>
        )}

        {gpuInfo.gpu_enabled ? (
          <Alert className="border-green-200 bg-green-50/50">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-900">
              GPU 加速已启用
            </AlertDescription>
          </Alert>
        ) : canInstall ? (
          <Alert className="border-yellow-200 bg-yellow-50/50">
            <AlertCircle className="h-4 w-4 text-yellow-600" />
            <AlertDescription className="text-yellow-900">
              {gpuInfo.install_guide?.description || '检测到 NVIDIA GPU，可安装 GPU 加速包提升速度'}
            </AlertDescription>
          </Alert>
        ) : (
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              未检测到可用的 GPU 加速环境
            </AlertDescription>
          </Alert>
        )}

        {canInstall && (
          <div className="flex gap-2">
            <Button
              onClick={() => setShowInstallConfirm(true)}
              disabled={isInstalling}
              className="flex-1"
            >
              {isInstalling ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  安装中...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  安装 GPU 加速包
                </>
              )}
            </Button>
          </div>
        )}

        <AlertDialog open={showInstallConfirm} onOpenChange={setShowInstallConfirm}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>确认安装 GPU 加速包</AlertDialogTitle>
              <AlertDialogDescription>
                安装需要下载约 3GB 数据，耗时 5-10 分钟。安装完成后需要重启软件。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isInstalling}>取消</AlertDialogCancel>
              <AlertDialogAction onClick={startInstall} disabled={isInstalling}>
                确认安装
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}
