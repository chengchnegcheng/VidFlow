import { useState, useEffect } from 'react';
import { invoke } from './TauriIntegration';
import { 
  Zap, 
  Download, 
  CheckCircle, 
  AlertCircle, 
  Loader2,
  Copy,
  Info
} from 'lucide-react';

interface GPUStatus {
  gpu_available: boolean;
  gpu_enabled: boolean;
  device_name?: string;
  cuda_version?: string;
  can_install: boolean;
  install_guide?: {
    title: string;
    description: string;
    benefits: string[];
    requirements: string[];
    manual_install: {
      title: string;
      command: string;
      note: string;
    };
  };
}

export default function GPUSettings() {
  const [gpuStatus, setGpuStatus] = useState<GPUStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadGPUStatus();
  }, []);

  const loadGPUStatus = async () => {
    try {
      setLoading(true);
      const response = await invoke('get_gpu_status');
      setGpuStatus(response?.data ?? response);
    } catch (error) {
      console.error('Failed to load GPU status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async () => {
    if (!window.confirm(
      'GPU加速包安装需要下载约 3GB 数据，耗时 5-10 分钟。\n' +
      '安装完成后需要重启软件。\n\n' +
      '确认安装？'
    )) {
      return;
    }

    try {
      setInstalling(true);
      await invoke('install_gpu_package');
      
      alert(
        '✅ GPU加速包安装已开始！\n\n' +
        '安装需要 5-10 分钟，请勿关闭软件。\n' +
        '完成后请重启软件以启用GPU加速。\n\n' +
        '您可以继续使用软件的其他功能。'
      );
    } catch (error) {
      console.error('Failed to install GPU package:', error);
      alert('安装启动失败，请查看日志或尝试手动安装。');
    } finally {
      setInstalling(false);
    }
  };

  const copyCommand = () => {
    if (gpuStatus?.install_guide?.manual_install.command) {
      navigator.clipboard.writeText(gpuStatus.install_guide.manual_install.command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <span className="ml-3 text-gray-600">检测GPU状态...</span>
      </div>
    );
  }

  if (!gpuStatus) {
    return (
      <div className="p-6 text-center text-gray-500">
        <AlertCircle className="w-12 h-12 mx-auto mb-3 text-gray-400" />
        <p>无法检测GPU状态</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* 标题 */}
      <div className="flex items-center space-x-3">
        <Zap className="w-8 h-8 text-yellow-500" />
        <div>
          <h2 className="text-2xl font-bold text-gray-800">GPU 加速</h2>
          <p className="text-sm text-gray-500">提升字幕处理速度 5-10 倍</p>
        </div>
      </div>

      {/* GPU 状态卡片 */}
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
        <div className="space-y-4">
          {/* GPU 硬件状态 */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-2">
                <span className="text-sm font-medium text-gray-700">GPU 硬件:</span>
                {gpuStatus.gpu_available ? (
                  <span className="flex items-center text-green-600">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    已检测到
                  </span>
                ) : (
                  <span className="flex items-center text-gray-500">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    未检测到
                  </span>
                )}
              </div>
              {gpuStatus.device_name && (
                <div className="text-sm text-gray-600 ml-4">
                  型号: {gpuStatus.device_name}
                </div>
              )}
            </div>
          </div>

          {/* GPU 加速状态 */}
          <div className="flex items-start justify-between pt-4 border-t">
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-2">
                <span className="text-sm font-medium text-gray-700">GPU 加速:</span>
                {gpuStatus.gpu_enabled ? (
                  <span className="flex items-center text-green-600 font-semibold">
                    <CheckCircle className="w-4 h-4 mr-1" />
                    已启用
                  </span>
                ) : (
                  <span className="flex items-center text-gray-500">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    未启用
                  </span>
                )}
              </div>
              {gpuStatus.cuda_version && (
                <div className="text-sm text-gray-600 ml-4">
                  CUDA 版本: {gpuStatus.cuda_version}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 安装提示卡片 */}
      {gpuStatus.can_install && gpuStatus.install_guide && (
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg shadow-md p-6 border border-blue-200">
          <div className="flex items-start space-x-4">
            <div className="flex-shrink-0">
              <Zap className="w-10 h-10 text-blue-600" />
            </div>
            <div className="flex-1 space-y-4">
              <div>
                <h3 className="text-lg font-bold text-gray-800 mb-2">
                  {gpuStatus.install_guide.title}
                </h3>
                <p className="text-gray-700 mb-4">
                  {gpuStatus.install_guide.description}
                </p>
              </div>

              {/* 优势列表 */}
              <div className="bg-white/70 rounded-lg p-4">
                <h4 className="font-semibold text-gray-800 mb-2 flex items-center">
                  <Info className="w-4 h-4 mr-2 text-blue-600" />
                  性能提升
                </h4>
                <ul className="space-y-2">
                  {gpuStatus.install_guide.benefits.map((benefit, index) => (
                    <li key={index} className="flex items-start text-sm text-gray-700">
                      <CheckCircle className="w-4 h-4 mr-2 mt-0.5 text-green-600 flex-shrink-0" />
                      <span>{benefit}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* 需求列表 */}
              <div className="bg-white/70 rounded-lg p-4">
                <h4 className="font-semibold text-gray-800 mb-2 flex items-center">
                  <Info className="w-4 h-4 mr-2 text-blue-600" />
                  安装要求
                </h4>
                <ul className="space-y-2">
                  {gpuStatus.install_guide.requirements.map((req, index) => (
                    <li key={index} className="flex items-start text-sm text-gray-700">
                      <span className="mr-2">•</span>
                      <span>{req}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* 安装按钮 */}
              <div className="flex items-center space-x-3 pt-2">
                <button
                  onClick={handleInstall}
                  disabled={installing}
                  className="flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {installing ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      安装中...
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5 mr-2" />
                      立即安装 GPU 加速包
                    </>
                  )}
                </button>
                <span className="text-xs text-gray-600">
                  下载大小: ~3GB
                </span>
              </div>

              {/* 手动安装 */}
              <details className="bg-white/70 rounded-lg p-4">
                <summary className="font-semibold text-gray-800 cursor-pointer hover:text-blue-600 transition-colors">
                  手动安装（高级用户）
                </summary>
                <div className="mt-3 space-y-2">
                  <p className="text-sm text-gray-600">
                    {gpuStatus.install_guide.manual_install.note}
                  </p>
                  <div className="bg-gray-900 rounded p-3 flex items-center justify-between">
                    <code className="text-xs text-green-400 flex-1 overflow-x-auto">
                      {gpuStatus.install_guide.manual_install.command}
                    </code>
                    <button
                      onClick={copyCommand}
                      className="ml-2 p-2 hover:bg-gray-800 rounded transition-colors"
                      title="复制命令"
                    >
                      {copied ? (
                        <CheckCircle className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4 text-gray-400" />
                      )}
                    </button>
                  </div>
                </div>
              </details>
            </div>
          </div>
        </div>
      )}

      {/* GPU 已启用状态 */}
      {gpuStatus.gpu_enabled && (
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg shadow-md p-6 border border-green-200">
          <div className="flex items-center space-x-4">
            <CheckCircle className="w-12 h-12 text-green-600 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="text-lg font-bold text-gray-800 mb-1">
                🎉 GPU 加速已启用
              </h3>
              <p className="text-gray-700">
                字幕处理速度已提升 5-10 倍，享受更快的处理体验！
              </p>
              {gpuStatus.device_name && (
                <p className="text-sm text-gray-600 mt-2">
                  当前使用: {gpuStatus.device_name}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 无 GPU 提示 */}
      {!gpuStatus.gpu_available && (
        <div className="bg-gray-50 rounded-lg shadow-md p-6 border border-gray-200">
          <div className="flex items-start space-x-4">
            <AlertCircle className="w-8 h-8 text-gray-400 flex-shrink-0" />
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">
                未检测到 NVIDIA GPU
              </h3>
              <p className="text-gray-600 mb-2">
                GPU 加速需要 NVIDIA 显卡支持。您当前的系统将使用 CPU 模式处理字幕。
              </p>
              <p className="text-sm text-gray-500">
                CPU 模式完全可用，但处理速度会较慢。
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
