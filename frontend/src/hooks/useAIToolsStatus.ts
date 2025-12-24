import { useState, useEffect, useRef } from 'react';
import { getApiBaseUrl } from '../components/TauriIntegration';

export interface AIToolsStatus {
  installed: boolean;
  faster_whisper: boolean;
  torch: boolean;
  version: string | null;
  torch_version: string | null;
  device: string;
  python_compatible: boolean;
  error?: string;
}

export function useAIToolsStatus() {
  const [status, setStatus] = useState<AIToolsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    let retryTimer: number;

    const fetchStatus = async () => {
      try {
        setLoading(true);
        const apiUrl = getApiBaseUrl();
        if (!apiUrl) {
          retryTimer = window.setTimeout(fetchStatus, 1200);
          return;
        }

        const response = await fetch(`${apiUrl}/api/v1/system/tools/ai/status`);

        if (!isMountedRef.current) return;

        if (response.ok) {
          const data = await response.json();
          setStatus(data);
          setError(null);
        } else {
          setError('无法获取 AI 工具状态');
        }
      } catch (err) {
        if (isMountedRef.current) {
          setError(err instanceof Error ? err.message : '未知错误');
        }
      } finally {
        if (isMountedRef.current) {
          setLoading(false);
        }
      }
    };

    fetchStatus();

    return () => {
      isMountedRef.current = false;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, []);

  const refresh = async () => {
    try {
      setLoading(true);
      const apiUrl = getApiBaseUrl();
      if (!apiUrl) return;

      const response = await fetch(`${apiUrl}/api/v1/system/tools/ai/status`);

      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        setError(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  return {
    status,
    loading,
    error,
    refresh
  };
}
