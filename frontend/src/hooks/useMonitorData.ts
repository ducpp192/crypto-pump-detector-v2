import { useCallback, useEffect, useRef, useState } from "react";
import { MonitorToken } from "../types/monitor";

export type MonitorStatus = "connected" | "connecting" | "disconnected";

const WS_URL =
  (process.env.REACT_APP_API_WS_URL ?? "ws://localhost:8002") + "/api/monitor/ws/monitor";

export function useMonitorData() {
  const [tokens, setTokens] = useState<MonitorToken[]>([]);
  const [status, setStatus] = useState<MonitorStatus>("connecting");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setStatus("connected");
      reconnectDelay.current = 1000;
    };

    ws.onmessage = (e) => {
      if (!mountedRef.current) return;
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "snapshot") {
          setTokens(msg.tokens ?? []);
          setLastUpdated(new Date());
        }
      } catch {}
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus("disconnected");
      const delay = reconnectDelay.current;
      reconnectDelay.current = Math.min(delay * 2, 30000);
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { tokens, status, lastUpdated };
}
