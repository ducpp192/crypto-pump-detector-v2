import { useState, useEffect, useCallback, useRef } from "react";
import { DashboardResponse, FilterState, TokenSignal } from "../types";

const POLL_INTERVAL = 10_000; // 10 seconds

function buildQueryString(filters: FilterState): string {
  const params = new URLSearchParams({
    min_score: String(filters.minScore),
    max_score: String(filters.maxScore),
    squeeze_only: String(filters.squeezeOnly),
    limit: "200",
  });
  if (filters.signalType !== "all") {
    params.set("signal_type", filters.signalType);
  }
  return params.toString();
}

export function useSignals(filters: FilterState) {
  const [signals, setSignals] = useState<TokenSignal[]>([]);
  const [meta, setMeta] = useState<Omit<DashboardResponse, "signals"> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSignals = useCallback(async () => {
    try {
      const qs = buildQueryString(filters);
      const res = await fetch(`/api/signals?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DashboardResponse = await res.json();

      let filtered = data.signals;
      if (filters.searchQuery) {
        const q = filters.searchQuery.toUpperCase();
        filtered = filtered.filter((s) => s.symbol.includes(q));
      }

      setSignals(filtered);
      setMeta({
        last_updated: data.last_updated,
        total_scanned: data.total_scanned,
        alerts_triggered: data.alerts_triggered,
      });
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchSignals();
    timerRef.current = setInterval(fetchSignals, POLL_INTERVAL);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchSignals]);

  return { signals, meta, loading, error, refetch: fetchSignals };
}
