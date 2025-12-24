import { useEffect, useRef, useState, useCallback } from 'react';

// WebSocket 重连默认策略
const RECONNECT_BASE_INTERVAL_MS = 1000;        // 初始 1s
const RECONNECT_MAX_INTERVAL_MS = 10000;        // 上限 10s
const RECONNECT_BACKOFF_FACTOR = 2;             // 指数退避
const RECONNECT_MAX_ATTEMPTS = 5;

export interface WebSocketMessage {
  type: string;
  data?: any;
  message?: string;
  timestamp: string;
}

export interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    url,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    autoConnect = true,
    reconnectInterval = RECONNECT_BASE_INTERVAL_MS,
    maxReconnectAttempts = RECONNECT_MAX_ATTEMPTS
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  // in browser, setTimeout returns number (not NodeJS.Timeout)
  const reconnectTimeoutRef = useRef<number>();
  
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('[WebSocket] Message received:', message.type);
          setLastMessage(message);
          onMessage?.(message);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        onError?.(error);
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        wsRef.current = null;
        onDisconnect?.();

        // 尝试重连
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          console.log(
            `[WebSocket] Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
          );
          const backoffDelay = Math.min(
            reconnectInterval * Math.pow(RECONNECT_BACKOFF_FACTOR, reconnectAttemptsRef.current - 1),
            RECONNECT_MAX_INTERVAL_MS
          );
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, backoffDelay);
        } else {
          console.log('[WebSocket] Max reconnect attempts reached');
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
    }
  }, [url, onConnect, onMessage, onDisconnect, onError, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current !== undefined) {
      window.clearTimeout(reconnectTimeoutRef.current);
    }
    reconnectAttemptsRef.current = maxReconnectAttempts; // 防止自动重连
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, [maxReconnectAttempts]);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const data = typeof message === 'string' ? message : JSON.stringify(message);
      wsRef.current.send(data);
      console.log('[WebSocket] Message sent:', message);
      return true;
    }
    console.warn('[WebSocket] Cannot send message, not connected');
    return false;
  }, []);

  const sendPing = useCallback(() => {
    sendMessage({ type: 'ping' });
  }, [sendMessage]);

  const subscribe = useCallback((events: string[]) => {
    sendMessage({ type: 'subscribe', events });
  }, [sendMessage]);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect]); // 只在 mount/unmount 时执行

  return {
    isConnected,
    lastMessage,
    connect,
    disconnect,
    sendMessage,
    sendPing,
    subscribe
  };
}
