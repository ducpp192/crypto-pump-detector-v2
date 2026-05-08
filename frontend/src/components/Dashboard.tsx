import React, { useState, useMemo } from "react";
import { FilterState } from "../types";
import { useRealtimeSignals, WsStatus } from "../hooks/useRealtimeSignals";
import { StatCard } from "./StatCard";
import { FilterPanel } from "./FilterPanel";
import { TokenTable } from "./TokenTable";

// ── WS Status Dot ─────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<WsStatus, { color: string; label: string; dot: boolean }> = {
  connected:    { color: "#3fb950", label: "LIVE",          dot: true  },
  connecting:   { color: "#d29922", label: "connecting…",   dot: false },
  disconnected: { color: "#f85149", label: "reconnecting…", dot: false },
};

function WsStatusBadge({ status }: { status: WsStatus }) {
  const s = STATUS_STYLES[status];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {s.dot
        ? <span className="dot-live" />
        : <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.color, display: "inline-block" }} />
      }
      <span style={{ color: s.color, fontSize: 11, fontWeight: 600 }}>{s.label}</span>
    </div>
  );
}

// ── Default filter state ──────────────────────────────────────────────────────

const DEFAULT_FILTERS: FilterState = {
  minScore:    0,
  maxScore:    100,
  signalType:  "all",
  squeezeOnly: false,
  searchQuery: "",
  oiSpike:     false,
  highOiRatio: false,
  oiSignal:    "all",
};

// ── Dashboard ─────────────────────────────────────────────────────────────────

export function Dashboard() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const { signals, meta, status } = useRealtimeSignals(filters);

  // Stats — computed only when signals array changes
  const stats = useMemo(() => {
    const pumpCount  = signals.filter(s => s.signal === "PUMP").length;
    const dumpCount  = signals.filter(s => s.signal === "DUMP").length;
    const sqzCount   = signals.filter(s => s.short_squeeze || s.long_squeeze).length;
    const pumpActive = signals.filter(s => s.pump_detected).length;
    const validRatio = signals.filter(s => s.buy_ratio > 0);
    const avgBuy     = validRatio.length > 0
      ? validRatio.reduce((acc, s) => acc + s.buy_ratio, 0) / validRatio.length * 100
      : 50;
    const buyColor   = avgBuy > 55 ? "#3fb950" : avgBuy < 45 ? "#f85149" : "#d29922";
    const crimeCoins = signals.filter(s => s.crime_level === "CRIME_COIN" || s.crime_level === "MM_ACTIVE").length;
    return { pumpCount, dumpCount, sqzCount, pumpActive, avgBuy, buyColor, crimeCoins };
  }, [signals]);

  const lastUpdated = meta?.last_updated
    ? new Date(meta.last_updated).toLocaleTimeString()
    : "—";

  return (
    <div style={{ minHeight: "100vh", background: "#0d1117", padding: "0 0 40px" }}>
      {/* Header */}
      <div style={{
        background: "#161b22",
        borderBottom: "1px solid #30363d",
        padding: "10px 20px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        flexWrap: "wrap" as const,
      }}>
        <div>
          <div style={{ color: "#e6edf3", fontWeight: 700, fontSize: 15, letterSpacing: "0.03em" }}>
            🔍 Crypto Pump Detector <span style={{ color: "#8b949e", fontSize: 12 }}>v2</span>
          </div>
          <div style={{ color: "#8b949e", fontSize: 11 }}>Mid-cap · Binance Spot + Futures + WS</div>
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
          {meta && (
            <>
              <span style={{ color: "#8b949e", fontSize: 11 }}>
                {meta.total_scanned} tokens · updated {lastUpdated}
              </span>
              {meta.alerts_triggered > 0 && (
                <span style={{ color: "#d29922", fontSize: 11 }}>
                  🔔 {meta.alerts_triggered} alert{meta.alerts_triggered !== 1 ? "s" : ""}
                </span>
              )}
            </>
          )}
          <WsStatusBadge status={status} />
        </div>
      </div>

      <div style={{ padding: "14px 20px", display: "flex", flexDirection: "column" as const, gap: 12 }}>
        {/* Stat cards */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" as const }}>
          <StatCard title="🚀 PUMP" value={stats.pumpCount} valueColor="#3fb950" />
          <StatCard title="🔴 DUMP" value={stats.dumpCount} valueColor="#f85149" />
          <StatCard title="⚡ SQUEEZE" value={stats.sqzCount} valueColor="#d29922" />
          <StatCard title="⚡ WS CONFIRMED" value={stats.pumpActive} subtitle="pump_detected"
            valueColor={stats.pumpActive > 0 ? "#3fb950" : "#8b949e"} />
          <StatCard
            title="📊 MARKET BIAS"
            value={`${stats.avgBuy.toFixed(1)}% buy`}
            subtitle={stats.avgBuy > 55 ? "Bullish" : stats.avgBuy < 45 ? "Bearish" : "Neutral"}
            valueColor={stats.buyColor}
          />
          <StatCard title="⚠ CRIME COINS" value={stats.crimeCoins}
            subtitle="CRIME / MM_ACTIVE"
            valueColor={stats.crimeCoins > 0 ? "#f85149" : "#8b949e"} />
          <StatCard title="📡 TRACKED" value={meta?.total_scanned ?? 0}
            subtitle="mid-cap tokens" valueColor="#58a6ff" />
        </div>

        {/* Filter panel */}
        <FilterPanel filters={filters} onChange={setFilters} />

        {/* Token table */}
        <TokenTable signals={signals} />
      </div>
    </div>
  );
}
