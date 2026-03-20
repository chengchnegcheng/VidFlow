import { useState, useEffect } from 'react';

/**
 * 视频缩略图 Hook
 * 优先使用本地视频文件生成缩略图，如果失败则回退到在线缩略图
 */
export function useVideoThumbnail(
  filePath: string | undefined | null,
  onlineThumbnail: string | undefined | null
): string | null {
  const [thumbnail, setThumbnail] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const loadThumbnail = async () => {
      // 如果没有文件路径，直接使用在线缩略图
      if (!filePath) {
        setThumbnail(onlineThumbnail || null);
        return;
      }

      // 检查是否在 Electron 环境
      if (!window.electron?.isElectron || !window.electron?.generateVideoThumbnail) {
        setThumbnail(onlineThumbnail || null);
        return;
      }

      try {
        // 检查文件是否存在
        const exists = await window.electron.fileExists(filePath);
        if (!exists) {
          if (mounted) {
            setThumbnail(onlineThumbnail || null);
          }
          return;
        }

        // 生成本地缩略图
        const localThumbnail = await window.electron.generateVideoThumbnail(filePath);

        if (mounted) {
          if (localThumbnail) {
            setThumbnail(localThumbnail);
          } else {
            // 生成失败，回退到在线缩略图
            setThumbnail(onlineThumbnail || null);
          }
        }
      } catch (error) {
        console.error('Failed to generate thumbnail:', error);
        if (mounted) {
          setThumbnail(onlineThumbnail || null);
        }
      }
    };

    loadThumbnail();

    return () => {
      mounted = false;
    };
  }, [filePath, onlineThumbnail]);

  return thumbnail;
}
