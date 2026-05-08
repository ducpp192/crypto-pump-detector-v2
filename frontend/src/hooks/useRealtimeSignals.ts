/**
 * useRealtimeSignals — WebSocket hook replacing the polling useSignals hook.
 *
 * Architecture:
 *   1. Opens a single WebSocket to /ws/signals
 *   2. On "snapshot" message → replaces entire tokenMap
 *   3. On "delta" message    → merges only changed tokens into tokenMap
 *   4. Batches React state updates via requestAnimationFrame (~60fps cap)
 *   5. Reconnects with exponential backoff (1s → 2s → 4s … → 30s)
 *
 * Why this is fast:
 *   - No 10s polling latency; updates arrive within ~50ms of the scoring pass
 *   - tokenMap is a ref (not state), so merging deltas costs zero renders
 *   - React state update is scheduled once per animation frame even if many
 *     deltas arrive in the same flush window
 *   - Only changed tokens cause re-renders (via React.memo in TokenRow)
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { FilterState, TokenSignal } from "../types";

// ── WS message types ──────────────────────────────────────────────────────────

interface Meta {
  total_scanned: number;
  last_updated: string;
  alerts_triggered: number;
}

type WsMessage =
  | { type: "snapshot"; signals: TokenSignal[]; meta: Meta }
  | { type: "delta";    updates: TokenSignal[]; meta: Meta }
  | { type: "heartbeat"; ts: number };

export type WsStatus = "connecting" | "connected" | "disconnected";

// ── Hook return type ──────────────────────────────────────────────────────────

export interface RealtimeSignalsResult {
  signals:  TokenSignal[];
  meta:     Meta | null;
  status:   WsStatus;
}

// ── Client-side filter ────────────────────────────────────────────────────────

function applyFilters(tokens: TokenSignal[], f: FilterState): TokenSignal[] {
  let out = tokens;

  // OI-specific quick filters (checked first — most selective)
  if (f.oiSpike) {
    out = out.filter(s => s.oi_spike);
  }
  if (f.highOiRatio) {
    out = out.filter(s => s.oi_market_cap_ratio != null && s.oi_market_cap_ratio > 0.3);
  }
  if (f.oiSignal && f.oiSignal !== "all") {
    out = out.filter(s => s.oi_signal_type === f.oiSignal);
  }

  // Signal-type / squeeze filters
  if (f.squeezeOnly) {
    out = out.filter(s => s.short_squeeze || s.long_squeeze);
  } else if (f.signalType !== "all") {
    out = out.filter(s => s.signal === f.signalType);
  }

  // Score range
  if (f.minScore > 0 || f.maxScore < 100) {
    out = out.filter(s => s.score >= f.minScore && s.score <= f.maxScore);
  }

  // Symbol search
  if (f.searchQuery) {
    const q = f.searchQuery.toUpperCase();
    out = out.filter(s => s.symbol.includes(q));
  }

  return out;
}

// ── Build WS URL ──────────────────────────────────────────────────────────────

function buildWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Pump-detector backend runs on port 8002 (token-analyzer uses 8000)
  const base = process.env.REACT_APP_API_WS_URL
    ?? `${proto}//${window.location.hostname}:8002`;
  return `${base}/ws/signals`;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useRealtimeSignals(filters: FilterState): RealtimeSignalsResult {
  // tokenMap is a ref — mutations don't trigger renders
  const tokenMapRef = useRef<Map<string, TokenSignal>>(new Map());

  const [signals, setSignals] = useState<TokenSignal[]>([]);
  const [meta,    setMeta]    = useState<Meta | null>(null);
  const [status,  setStatus]  = useState<WsStatus>("connecting");

  // rAF handle — we batch state updates into animation frames
  const rafRef     = useRef<number | null>(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;   // always up-to-date without re-subscribing

  // Re-derive signals array from tokenMap + current filters
  const flushToReact = useCallback(() => {
    rafRef.current = null;
    const all = Array.from(tokenMapRef.current.values());
    const filtered = applyFilters(all, filtersRef.current);
    // Sort: score descending (matches backend order)
    filtered.sort((a, b) => b.score - a.score);
    setSignals(filtered);
  }, []);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current !== null) return;  // already scheduled this frame
    rafRef.current = requestAnimationFrame(flushToReact);
  }, [flushToReact]);

  // Re-apply filters when they change (no WS reconnect needed)
  useEffect(() => {
    scheduleFlush();
  }, [filters, scheduleFlush]);

  // Connect to WS once on mount; reconnect with backoff on disconnect
  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryDelay = 1_000;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let alive = true;

    function connect() {
      if (!alive) return;
      setStatus("connecting");

      ws = new WebSocket(buildWsUrl());

      ws.onopen = () => {
        if (!alive) { ws?.close(); return; }
        setStatus("connected");
        retryDelay = 1_000;   // reset backoff on successful connect
      };

      ws.onmessage = (evt: MessageEvent) => {
        if (!alive) return;
        let msg: WsMessage;
        try {
          msg = JSON.parse(evt.data as string);
        } catch {
          return;
        }

        if (msg.type === "snapshot") {
          // Full replace
          const newMap = new Map<string, TokenSignal>();
          for (const s of msg.signals) newMap.set(s.symbol, s);
          tokenMapRef.current = newMap;
          setMeta(msg.meta);
          scheduleFlush();

        } else if (msg.type === "delta") {
          // Incremental merge — only changed tokens
          for (const update of msg.updates) {
            const existing = tokenMapRef.current.get(update.symbol);
            // Merge: preserve fields not included in the delta
            tokenMapRef.current.set(update.symbol, existing
              ? { ...existing, ...update }
              : update
            );
          }
          setMeta(msg.meta);
          scheduleFlush();

        }
        // heartbeat: ignored (just proves connection is alive)
      };

      ws.onclose = () => {
        if (!alive) return;
        setStatus("disconnected");
        retryTimer = setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, 30_000);
          connect();
        }, retryDelay);
      };

      ws.onerror = () => {
        ws?.close();
      };
    }

    connect();

    return () => {
      alive = false;
      if (retryTimer) clearTimeout(retryTimer);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;   // reset so scheduleFlush can fire again on remount
      }
      ws?.close();
    };
  }, [scheduleFlush]); // stable ref — won't re-run

  return { signals, meta, status };
}
