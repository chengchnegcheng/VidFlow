import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';

interface UpdateInfo {
  has_update: boolean;
  latest_version: string;
  release_notes: string;
  file_size: number;
  is_mandatory: boolean;
  download_url: string;
  rollout_blocked?: boolean;
  rollout_message?: string;
}

interface DownloadProgress {
  percent: number;
  bytesPerSecond: number;
  transferred: number;
  total: number;
}

export function CustomUpdateNotification() {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [updateDownloaded, setUpdateDownloaded] = useState(false);

  useEffect(() => {
    // 监听更新事件
    if (window.electron) {
      // 检查更新中
      window.electron.on('update-checking', () => {
        console.log('Checking for updates...');
      });

      // 发现更新
      window.electron.on('update-available', (info: UpdateInfo) => {
        console.log('Update available:', info);
        setUpdateInfo(info);
        
        // 如果被灰度阻止
        if (info.rollout_blocked) {
          toast.info('新版本发布中', {
            description: info.rollout_message || '您的设备暂未进入更新名单，请稍后再试'
          });
        } else {
          setShowModal(true);
          toast.info(`发现新版本 ${info.latest_version}`);
        }
      });

      // 没有更新
      window.electron.on('update-not-available', () => {
        console.log('No update available');
      });

      // 下载进度
      window.electron.on('download-progress', (progress: DownloadProgress) => {
        setDownloadProgress(progress);
      });

      // 更新已下载
      window.electron.on('update-downloaded', () => {
        setDownloading(false);
        setUpdateDownloaded(true);
        toast.success('更新下载完成', {
          description: '准备安装新版本',
          action: {
            label: '立即安装',
            onClick: handleInstall
          }
        });
      });

      // 更新错误
      window.electron.on('update-error', (error: string) => {
        setDownloading(false);
        toast.error('更新失败', {
          description: error
        });
      });
    }

    // 清理
    return () => {
      // 移除监听器（如果 electron API 支持）
    };
  }, []);

  const handleDownload = async () => {
    if (!updateInfo || updateInfo.rollout_blocked) {
      return;
    }

    setDownloading(true);
    try {
      const result = await window.electron.invoke('custom-update-download');
      if (!result.success) {
        toast.error('下载失败', { description: result.error });
        setDownloading(false);
      }
    } catch (error) {
      toast.error('下载失败', { description: String(error) });
      setDownloading(false);
    }
  };

  const handleInstall = async () => {
    try {
      await window.electron.invoke('custom-update-install');
    } catch (error) {
      toast.error('安装失败', { description: String(error) });
    }
  };

  const handleClose = () => {
    if (!updateInfo?.is_mandatory) {
      setShowModal(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatSpeed = (bytesPerSecond: number) => {
    return formatBytes(bytesPerSecond) + '/s';
  };

  if (!showModal || !updateInfo) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
        {/* 头部 */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              发现新版本
            </h2>
            {!updateInfo.is_mandatory && !downloading && (
              <button
                onClick={handleClose}
                className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* 内容 */}
        <div className="px-6 py-4">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">版本</span>
              <span className="font-semibold text-gray-900 dark:text-white">
                {updateInfo.latest_version}
              </span>
            </div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">大小</span>
              <span className="text-sm text-gray-900 dark:text-white">
                {formatBytes(updateInfo.file_size)}
              </span>
            </div>
            {updateInfo.is_mandatory && (
              <div className="flex items-center gap-2 p-2 bg-amber-50 dark:bg-amber-900/20 rounded-md">
                <svg className="w-5 h-5 text-amber-600 dark:text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="text-sm text-amber-800 dark:text-amber-200">
                  这是一个强制更新
                </span>
              </div>
            )}
          </div>

          {/* 更新说明 */}
          {updateInfo.release_notes && (
            <div className="mb-4">
              <h3 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                更新内容
              </h3>
              <div className="prose prose-sm dark:prose-invert max-h-48 overflow-y-auto bg-gray-50 dark:bg-gray-900 rounded-md p-3">
                <div dangerouslySetInnerHTML={{ __html: updateInfo.release_notes }} />
              </div>
            </div>
          )}

          {/* 下载进度 */}
          {downloading && downloadProgress && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600 dark:text-gray-400">下载进度</span>
                <span className="text-sm text-gray-900 dark:text-white">
                  {downloadProgress.percent}%
                </span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${downloadProgress.percent}%` }}
                />
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {formatBytes(downloadProgress.transferred)} / {formatBytes(downloadProgress.total)}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {formatSpeed(downloadProgress.bytesPerSecond)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900 flex gap-3">
          {!downloading && !updateDownloaded && (
            <>
              {!updateInfo.is_mandatory && (
                <button
                  onClick={handleClose}
                  className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  稍后提醒
                </button>
              )}
              <button
                onClick={handleDownload}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
              >
                立即下载
              </button>
            </>
          )}

          {downloading && (
            <button
              disabled
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md opacity-75 cursor-not-allowed"
            >
              下载中...
            </button>
          )}

          {updateDownloaded && (
            <button
              onClick={handleInstall}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700"
            >
              重启并安装
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
