import React from "react";
import { MonitorFilters } from "../../types/monitor";

interface Props {
  filters: MonitorFilters;
  onChange: (f: MonitorFilters) => void;
  totalTokens: number;
}

const DIRECTION_TABS = [
  { key: "all",     label: "ALL" },
  { key: "INFLOW",  label: "▲ INFLOW" },
  { key: "NEUTRAL", label: "— NEUTRAL" },
  { key: "OUTFLOW", label: "▼ OUTFLOW" },
];

const SIGNAL_OPTS = [
  { key: "all",                 label: "All Signals" },
  { key: "ABNORMAL_VOLUME",     label: "🔊 Abnormal Vol" },
  { key: "SHORT_SQUEEZE_LIKELY",label: "⚡ Short Squeeze" },
  { key: "LONG_SQUEEZE_LIKELY", label: "⚡ Long Squeeze" },
  { key: "LEVERAGE_BUILDUP",    label: "📈 Leverage" },
  { key: "SPOT_LED_RALLY",      label: "🚀 Spot Rally" },
  { key: "FUTURES_LED_RALLY",   label: "📊 Futures Rally" },
  { key: "LOW_CAP_SPECULATION", label: "🎯 Low Cap Spec" },
  { key: "HIGH_OI_RATIO",       label: "🔥 High OI/MC" },
];

const TF_TABS = [
  { key: "5m",  label: "5m" },
  { key: "15m", label: "15m" },
  { key: "1h",  label: "1h" },
  { key: "1d",  label: "1d" },
];

export const MonitorFilterPanel = React.memo(function MonitorFilterPanel({ filters, onChange, totalTokens }: Props) {
  function set<K extends keyof MonitorFilters>(key: K, value: MonitorFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  const tabStyle = (active: boolean, activeColor = "#58a6ff"): React.CSSProperties => ({
    padding: "4px 10px",
    borderRadius: 4,
    border: `1px solid ${active ? activeColor : "#30363d"}`,
    background: active ? "#1c2e4a" : "#0d1117",
    color: active ? activeColor : "#8b949e",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    whiteSpace: "nowrap",
  });

  const inputStyle: React.CSSProperties = {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: 4,
    color: "#e6edf3",
    fontSize: 12,
    padding: "4px 8px",
    outline: "none",
  };

  return (
    <div style={{
      background: "#161b22",
      border: "1px solid #30363d",
      borderRadius: 8,
      padding: "10px 14px",
      display: "flex",
      flexWrap: "wrap",
      gap: 10,
      alignItems: "center",
    }}>
      {/* Timeframe tabs */}
      <div style={{ display: "flex", gap: 4 }}>
        <span style={{ color: "#8b949e", fontSize: 10, alignSelf: "center", marginRight: 2 }}>TF:</span>
        {TF_TABS.map(t => (
          <button key={t.key} style={tabStyle(filters.timeframe === t.key)} onClick={() => set("timeframe", t.key as MonitorFilters["timeframe"])}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ width: 1, height: 20, background: "#30363d", flexShrink: 0 }} />

      {/* Direction tabs */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {DIRECTION_TABS.map(d => (
          <button
            key={d.key}
            style={tabStyle(
              filters.direction === d.key,
              d.key === "INFLOW" ? "#3fb950" : d.key === "OUTFLOW" ? "#f85149" : "#58a6ff",
            )}
            onClick={() => set("direction", d.key as MonitorFilters["direction"])}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div style={{ width: 1, height: 20, background: "#30363d", flexShrink: 0 }} />

      {/* Signal filter */}
      <select
        value={filters.signal}
        onChange={e => set("signal", e.target.value)}
        style={{ ...inputStyle, cursor: "pointer" }}
      >
        {SIGNAL_OPTS.map(o => (
          <option key={o.key} value={o.key}>{o.label}</option>
        ))}
      </select>

      {/* Futures filter */}
      <select
        value={filters.hasFutures}
        onChange={e => set("hasFutures", e.target.value as MonitorFilters["hasFutures"])}
        style={{ ...inputStyle, cursor: "pointer" }}
      >
        <option value="all">All Markets</option>
        <option value="yes">Has Futures</option>
        <option value="no">Spot Only</option>
      </select>

      <div style={{ width: 1, height: 20, background: "#30363d", flexShrink: 0 }} />

      {/* Search */}
      <input
        style={{ ...inputStyle, width: 100 }}
        placeholder="Symbol…"
        value={filters.searchQuery}
        onChange={e => set("searchQuery", e.target.value)}
      />

      {/* Score range */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ color: "#8b949e", fontSize: 11 }}>Score</span>
        <input
          type="number"
          style={{ ...inputStyle, width: 52 }}
          min={0} max={100}
          value={filters.minScore}
          onChange={e => set("minScore", Math.max(0, Math.min(100, Number(e.target.value))))}
        />
        <span style={{ color: "#8b949e", fontSize: 11 }}>–</span>
        <input
          type="number"
          style={{ ...inputStyle, width: 52 }}
          min={0} max={100}
          value={filters.maxScore}
          onChange={e => set("maxScore", Math.max(0, Math.min(100, Number(e.target.value))))}
        />
      </div>

      {/* Token count */}
      <div style={{ marginLeft: "auto", color: "#8b949e", fontSize: 11 }}>
        {totalTokens} tokens tracked
      </div>
    </div>
  );
});
