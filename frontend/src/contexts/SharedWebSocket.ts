import { getApiBaseUrl } from '../components/TauriIntegration';

type Listener = (data: any) => void;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<Listener>();
let connected = false;

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
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[SharedWS] Received message:', data);
        notify(data);
      } catch (err) {
        console.warn('[SharedWS] parse error', err);
      }
    };

    ws.onclose = () => {
      connected = false;
      if (listeners.size > 0) {
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
