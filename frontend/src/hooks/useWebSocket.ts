/**
 * Custom hook for resilient native WebSocket connection with auto-reconnect.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { WS_URL } from '../services/api';
import type { WebSocketMessage } from '../types/metrics';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  enabled?: boolean;
}

export function useWebSocket({
  onMessage,
  onStatusChange,
  enabled = true,
}: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const onMessageRef = useRef(onMessage);
  const onStatusChangeRef = useRef(onStatusChange);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onStatusChangeRef.current = onStatusChange;
  });

  const updateStatus = useCallback((newStatus: ConnectionStatus) => {
    setStatus(newStatus);
    onStatusChangeRef.current?.(newStatus);
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    // Avoid duplicate connections
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    updateStatus('connecting');

    try {
      const ws = new WebSocket(WS_URL);
      socketRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptRef.current = 0;
        updateStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as WebSocketMessage;
          setLastMessage(parsed);
          onMessageRef.current?.(parsed);
        } catch {
          // Ignore invalid JSON payloads
        }
      };

      ws.onerror = () => {
        updateStatus('error');
      };

      ws.onclose = () => {
        updateStatus('disconnected');
        socketRef.current = null;

        if (enabled) {
          // Exponential backoff reconnect: 1s, 2s, 4s, max 8s
          const delay = Math.min(1000 * Math.pow(1.5, reconnectAttemptRef.current), 8000);
          reconnectAttemptRef.current += 1;
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch {
      updateStatus('error');
    }
  }, [enabled, updateStatus]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    updateStatus('disconnected');
  }, [updateStatus]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    status,
    lastMessage,
    reconnect: connect,
    disconnect,
  };
}
