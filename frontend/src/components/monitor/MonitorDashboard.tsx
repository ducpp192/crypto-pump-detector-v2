import React, { useMemo, useState } from "react";
import { MonitorFilters } from "../../types/monitor";
import { useMonitorData, MonitorStatus } from "../../hooks/useMonitorData";
import { MonitorFilterPanel } from "./MonitorFilterPanel";
import { FlowTable } from "./FlowTable";
import { FlowHeatmap } from "./FlowHeatmap";
import { AlertFeed } from "./AlertFeed";
import { FlowHistoryTab } from "./FlowHistoryTab";

// ── WS status badge ───────────────────────────────────────────────────────────

const STATUS_STYLES: Record<MonitorStatus, { color: string; label: string; dot: boolean }> = {
  connected:    { color: "#3fb950", label: "LIVE",          dot: true  },
  connecting:   { color: "#d29922", label: "connecting…",   dot: false },
  disconnected: { color: "#f85149", label: "reconnecting…", dot: false },
};

function WsStatusBadge({ status }: { status: MonitorStatus }) {
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

// ── Stat card ─────────────────────────────────────────────────────────────────

function MonitorStatCard({
  title, value, subtitle, valueColor = "#e6edf3",
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  valueColor?: string;
}) {
  return (
    <div style={{
      background: "#161b22",
      border: "1px solid #30363d",
      borderRadius: 8,
      padding: "8px 14px",
      minWidth: 100,
      flex: "0 0 auto",
    }}>
      <div style={{ color: "#8b949e", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {title}
      </div>
      <div style={{ color: valueColor, fontSize: 20, fontWeight: 700, lineHeight: 1.2, marginTop: 2 }}>
        {value}
      </div>
      {subtitle && <div style={{ color: "#8b949e", fontSize: 10, marginTop: 1 }}>{subtitle}</div>}
    </div>
  );
}

// ── Tab navigation ────────────────────────────────────────────────────────────

type SubTab = "table" | "heatmap" | "alerts" | "history";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "table",   label: "📋 Flow Ranking" },
  { key: "heatmap", label: "🗺️ Heatmap" },
  { key: "alerts",  label: "🔔 Alerts" },
  { key: "history", label: "📈 History" },
];

// ── Default filters ───────────────────────────────────────────────────────────

const DEFAULT_FILTERS: MonitorFilters = {
  minScore:    0,
  maxScore:    100,
  direction:   "all",
  signal:      "all",
  searchQuery: "",
  timeframe:   "5m",
  hasFutures:  "all",
};

// ── MonitorDashboard ──────────────────────────────────────────────────────────

export function MonitorDashboard() {
  const [filters, setFilters]   = useState<MonitorFilters>(DEFAULT_FILTERS);
  const [subTab, setSubTab]     = useState<SubTab>("table");
  const { tokens, status, lastUpdated } = useMonitorData();

  const stats = useMemo(() => {
    const inflow  = tokens.filter(t => t.flow_score_5m >= 60).length;
    const outflow = tokens.filter(t => t.flow_score_5m <= 40).length;
    const alerts  = tokens.filter(t => t.flow_score_5m >= 70 || t.flow_score_5m <= 30).length;
    const withSig = tokens.filter(t => t.smart_signals.length > 0).length;
    const avgScore = tokens.length > 0
      ? tokens.reduce((acc, t) => acc + t.flow_score_5m, 0) / tokens.length
      : 50;
    const topInflow = [...tokens].sort((a, b) => b.flow_score_5m - a.flow_score_5m)[0];
    return { inflow, outflow, alerts, withSig, avgScore, topInflow };
  }, [tokens]);

  const lastUpdatedStr = lastUpdated ? lastUpdated.toLocaleTimeString() : "—";

  const tabBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: "5px 14px",
    borderRadius: "4px 4px 0 0",
    border: `1px solid ${active ? "#58a6ff" : "#30363d"}`,
    borderBottom: active ? "1px solid #0d1117" : "1px solid #30363d",
    background: active ? "#0d1117" : "#161b22",
    color: active ? "#58a6ff" : "#8b949e",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    marginBottom: -1,
  });

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
            💸 Money Flow Monitor <span style={{ color: "#8b949e", fontSize: 12 }}>v2</span>
          </div>
          <div style={{ color: "#8b949e", fontSize: 11 }}>
            FLOW_SCORE = Vol·0.25 + OI·0.25 + Momentum·0.20 + Funding·0.15 + Liquidation·0.10 + RelVol·0.05
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ color: "#8b949e", fontSize: 11 }}>
            {tokens.length} tokens · updated {lastUpdatedStr}
          </span>
          {stats.alerts > 0 && (
            <span style={{ color: "#d29922", fontSize: 11 }}>🔔 {stats.alerts} alerts</span>
          )}
          <WsStatusBadge status={status} />
        </div>
      </div>

      <div style={{ padding: "14px 20px", display: "flex", flexDirection: "column" as const, gap: 12 }}>
        {/* Stat cards */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" as const }}>
          <MonitorStatCard title="▲ INFLOW"  value={stats.inflow}  valueColor="#3fb950" subtitle="flow_score ≥ 60" />
          <MonitorStatCard title="▼ OUTFLOW" value={stats.outflow} valueColor="#f85149" subtitle="flow_score ≤ 40" />
          <MonitorStatCard title="🔔 ALERTS"  value={stats.alerts}  valueColor="#d29922" subtitle="extreme flow" />
          <MonitorStatCard title="⚡ SIGNALS" value={stats.withSig} valueColor="#58a6ff" subtitle="smart signals" />
          <MonitorStatCard
            title="📊 AVG FLOW"
            value={stats.avgScore.toFixed(1)}
            valueColor={stats.avgScore > 55 ? "#3fb950" : stats.avgScore < 45 ? "#f85149" : "#d29922"}
            subtitle={stats.avgScore > 55 ? "Market bullish" : stats.avgScore < 45 ? "Market bearish" : "Market neutral"}
          />
          {stats.topInflow && (
            <MonitorStatCard
              title="🏆 TOP INFLOW"
              value={stats.topInflow.symbol}
              valueColor="#3fb950"
              subtitle={`Score ${stats.topInflow.flow_score_5m.toFixed(0)}`}
            />
          )}
          <MonitorStatCard title="📡 TRACKED" value={tokens.length} subtitle="mid-cap tokens" valueColor="#58a6ff" />
        </div>

        {/* Filter panel */}
        <MonitorFilterPanel filters={filters} onChange={setFilters} totalTokens={tokens.length} />

        {/* Sub-tab navigation */}
        <div style={{ display: "flex", gap: 2, borderBottom: "1px solid #30363d" }}>
          {SUB_TABS.map(t => (
            <button key={t.key} style={tabBtnStyle(subTab === t.key)} onClick={() => setSubTab(t.key)}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Sub-tab content */}
        <div style={{ position: "relative" }}>
          {subTab === "table"   && <FlowTable      tokens={tokens} filters={filters} />}
          {subTab === "heatmap" && <FlowHeatmap   tokens={tokens} />}
          {subTab === "alerts"  && <AlertFeed     tokens={tokens} />}
          {subTab === "history" && <FlowHistoryTab />}
        </div>
      </div>
    </div>
  );
}
