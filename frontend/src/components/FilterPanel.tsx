import React from "react";
import { FilterState } from "../types";

interface FilterPanelProps {
  filters: FilterState;
  onChange: (f: FilterState) => void;
}

const SIGNAL_TABS = [
  { key: "all",            label: "ALL" },
  { key: "PUMP",           label: "🚀 PUMP" },
  { key: "DUMP",           label: "🔴 DUMP" },
  { key: "SHORT_SQUEEZE",  label: "⚡ SHORT SQZ" },
  { key: "LONG_SQUEEZE",   label: "⚡ LONG SQZ" },
  { key: "NEUTRAL",        label: "NEUTRAL" },
];

const OI_SIGNAL_TABS = [
  { key: "all",            label: "All" },
  { key: "SHORT_SQUEEZE",  label: "Short Sqz" },
  { key: "LONG_LIQ",       label: "Long Liq" },
  { key: "TRAP",           label: "Trap" },
  { key: "DIVERGENCE",     label: "Divergence" },
];

export const FilterPanel = React.memo(function FilterPanel({ filters, onChange }: FilterPanelProps) {
  function set<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  const tabBtnStyle = (active: boolean) => ({
    padding: "4px 10px",
    borderRadius: 4,
    border: `1px solid ${active ? "#58a6ff" : "#30363d"}`,
    background: active ? "#1c2e4a" : "#0d1117",
    color: active ? "#58a6ff" : "#8b949e",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
  });

  const inputStyle = {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: 4,
    color: "#e6edf3",
    fontSize: 12,
    padding: "4px 8px",
    width: 56,
    outline: "none",
  };

  const checkStyle = {
    accentColor: "#58a6ff",
    cursor: "pointer",
    width: 14,
    height: 14,
  };

  return (
    <div style={{
      background: "#161b22",
      border: "1px solid #30363d",
      borderRadius: 8,
      padding: "10px 14px",
      display: "flex",
      flexWrap: "wrap" as const,
      gap: 10,
      alignItems: "center",
    }}>
      {/* Signal type tabs */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" as const }}>
        {SIGNAL_TABS.map(tab => (
          <button
            key={tab.key}
            style={tabBtnStyle(filters.signalType === tab.key && !filters.squeezeOnly)}
            onClick={() => onChange({ ...filters, signalType: tab.key, squeezeOnly: false })}
          >
            {tab.label}
          </button>
        ))}
        <button
          style={tabBtnStyle(filters.squeezeOnly)}
          onClick={() => set("squeezeOnly", !filters.squeezeOnly)}
        >
          🔥 Any Squeeze
        </button>
      </div>

      {/* Separator */}
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
          style={inputStyle}
          min={0}
          max={100}
          value={filters.minScore}
          onChange={e => set("minScore", Math.max(0, Math.min(100, Number(e.target.value))))}
        />
        <span style={{ color: "#8b949e", fontSize: 11 }}>–</span>
        <input
          type="number"
          style={inputStyle}
          min={0}
          max={100}
          value={filters.maxScore}
          onChange={e => set("maxScore", Math.max(0, Math.min(100, Number(e.target.value))))}
        />
      </div>

      {/* Separator */}
      <div style={{ width: 1, height: 20, background: "#30363d", flexShrink: 0 }} />

      {/* OI quick filters */}
      <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
        <input
          type="checkbox"
          style={checkStyle}
          checked={filters.oiSpike}
          onChange={e => set("oiSpike", e.target.checked)}
        />
        <span style={{ color: "#e3771a", fontSize: 11 }}>🔥 OI Spike</span>
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
        <input
          type="checkbox"
          style={checkStyle}
          checked={filters.highOiRatio}
          onChange={e => set("highOiRatio", e.target.checked)}
        />
        <span style={{ color: "#d29922", fontSize: 11 }}>📊 High OI/MC</span>
      </label>

      {/* OI signal type */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" as const }}>
        {OI_SIGNAL_TABS.map(tab => (
          <button
            key={tab.key}
            style={tabBtnStyle(filters.oiSignal === tab.key)}
            onClick={() => set("oiSignal", tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
});
