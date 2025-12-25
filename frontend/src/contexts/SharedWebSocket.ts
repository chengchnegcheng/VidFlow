import { getApiBaseUrl } from '../components/TauriIntegration';

type Listener = (data: any) => void;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<Listener>();
let connected = false;
let lastLoggedMessages: { [key: string]: any } = {}; // 缓存上次日志的消息

const notify = (data: any) => {
  listeners.forEach(listener => {
    try {
      listener(data);
    } catch (error) {
      console.error('[SharedWS] listener error', error);
    }
  });
};

const scheduleReconnect = (delayMs: number) => {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, delayMs);
};

const connect = () => {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const apiUrl = getApiBaseUrl();
  if (!apiUrl) {
    scheduleReconnect(1500);
    return;
  }

  const wsUrl = apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');

  try {
    ws = new WebSocket(`${wsUrl}/api/v1/system/ws`);

    ws.onopen = () => {
      connected = true;
      console.log('[SharedWS] Connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // 只在消息实际变化时打印日志(避免重复进度消息导致日志爆炸)
        if (data?.type === 'tool_install_progress') {
          const key = `${data.type}_${data.tool_id}`;
          const lastMsg = lastLoggedMessages[key];
          // 只在进度变化时打印
          if (!lastMsg || lastMsg.progress !== data.progress) {
            console.log(`[SharedWS] ${data.tool_id}: ${data.progress}% - ${data.message}`);
            lastLoggedMessages[key] = data;
          }
        } else {
          // 非进度消息，正常打印
          console.log('[SharedWS] Received:', data);
        }

        notify(data);
      } catch (err) {
        console.warn('[SharedWS] parse error', err);
      }
    };

    ws.onclose = () => {
      connected = false;
      if (listeners.size > 0) {
        console.log('[SharedWS] Disconnected, reconnecting...');
        scheduleReconnect(3000);
      }
    };

    ws.onerror = () => {
      connected = false;
      ws?.close();
    };
  } catch (error) {
    console.error('[SharedWS] failed to create WebSocket', error);
    connected = false;
    scheduleReconnect(3000);
  }
};

const ensureConnected = () => {
  if (!ws || ws.readyState === WebSocket.CLOSED) {
    connect();
  }
};

export function subscribeSharedWebSocket(listener: Listener) {
  listeners.add(listener);
  ensureConnected();

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        ws.close();
        ws = null;
        connected = false;
      }
    }
  };
}

export function isSharedWebSocketConnected() {
  return connected && ws?.readyState === WebSocket.OPEN;
}
