import React, { useCallback, useEffect, useState } from "react";
import { SmartSignal } from "../../types/monitor";
import { SmartSignalBadge } from "./SmartSignalBadge";
import { FundFlowPanel } from "./FundFlowPanel";

interface HistorySignal {
  symbol: string;
  ts: number;
  time: string;
  score: number;
  direction: "INFLOW" | "OUTFLOW";
  price: number;
  net_flow: number;
  smart_signals: SmartSignal[];
}

const API = process.env.REACT_APP_API_URL ?? "http://localhost:8002";

function fmtFlow(v: number): string {
  const abs = Math.abs(v);
  const sign = v >= 0 ? "+" : "-";
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(0)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

function fmtPrice(p: number): string {
  if (p >= 1000) return p.toFixed(2);
  if (p >= 1)    return p.toFixed(4);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}

export function FlowHistoryTab() {
  const [signals, setSignals]     = useState<HistorySignal[]>([]);
  const [loading, setLoading]     = useState(true);
  const [direction, setDirection] = useState<"all" | "INFLOW" | "OUTFLOW">("all");
  const [search, setSearch]       = useState("");
  const [fundFlowSym, setFundFlowSym] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    const qs = direction !== "all" ? `?direction=${direction}&limit=200` : "?limit=200";
    fetch(`${API}/api/monitor/history${qs}`)
      .then(r => r.json())
      .then(d => { setSignals(d.signals ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [direction]);

  useEffect(() => { load(); }, [load]);

  const filtered = search
    ? signals.filter(s => s.symbol.toUpperCase().includes(search.toUpperCase()))
    : signals;

  const cell: React.CSSProperties = {
    padding: "5px 10px",
    borderBottom: "1px solid #161b22",
    fontSize: 12,
    whiteSpace: "nowrap",
    verticalAlign: "middle",
  };

  return (
    <div>
      {fundFlowSym && (
        <FundFlowPanel symbol={fundFlowSym} onClose={() => setFundFlowSym(null)} />
      )}

      {/* Controls */}
      <div style={{
        background: "#161b22", border: "1px solid #30363d",
        borderRadius: 8, padding: "10px 14px",
        display: "flex", gap: 10, alignItems: "center",
        flexWrap: "wrap", marginBottom: 12,
      }}>
        <span style={{ color: "#8b949e", fontSize: 11, fontWeight: 600 }}>DIRECTION:</span>
        {(["all", "INFLOW", "OUTFLOW"] as const).map(d => (
          <button
            key={d}
            style={{
              padding: "4px 12px", borderRadius: 4, cursor: "pointer",
              fontSize: 11, fontWeight: 600,
              border: `1px solid ${direction === d
                ? d === "INFLOW" ? "#3fb950" : d === "OUTFLOW" ? "#f85149" : "#58a6ff"
                : "#30363d"}`,
              background: direction === d ? "#1c2e4a" : "#0d1117",
              color: direction === d
                ? d === "INFLOW" ? "#3fb950" : d === "OUTFLOW" ? "#f85149" : "#58a6ff"
                : "#8b949e",
            }}
            onClick={() => setDirection(d)}
          >
            {d === "all" ? "ALL" : d === "INFLOW" ? "▲ INFLOW" : "▼ OUTFLOW"}
          </button>
        ))}
        <input
          style={{
            background: "#0d1117", border: "1px solid #30363d", borderRadius: 4,
            color: "#e6edf3", fontSize: 12, padding: "4px 8px", width: 110, outline: "none",
          }}
          placeholder="Symbol…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button
          style={{
            marginLeft: "auto", padding: "4px 12px", borderRadius: 4, cursor: "pointer",
            border: "1px solid #30363d", background: "#21262d",
            color: "#8b949e", fontSize: 11,
          }}
          onClick={load}
        >
          ↻ Refresh
        </button>
        <span style={{ color: "#8b949e", fontSize: 11 }}>{filtered.length} records</span>
      </div>

      {/* Header */}
      <div style={{
        padding: "6px 12px", borderRadius: "6px 6px 0 0",
        background: "#161b22", borderBottom: "2px solid #d29922",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ color: "#d29922", fontWeight: 700, fontSize: 12 }}>
          📈 SIGNAL HISTORY — score &gt;75 (INFLOW) · score &lt;25 (OUTFLOW)
        </span>
        <span style={{ color: "#8b949e", fontSize: 11 }}>kept 30 days</span>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: "#0d1117", fontSize: 12 }}>
          <thead>
            <tr>
              {["Time", "Symbol", "Direction", "Score", "Price", "Net Flow 5m", "Signals"].map((h, i) => (
                <th key={h} style={{
                  padding: "6px 10px", color: "#8b949e", fontSize: 10, fontWeight: 600,
                  textAlign: i <= 1 ? "left" : "right",
                  borderBottom: "1px solid #21262d",
                  textTransform: "uppercase", letterSpacing: "0.06em",
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} style={{ ...cell, textAlign: "center", color: "#8b949e", padding: "40px" }}>Loading…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={7} style={{ ...cell, textAlign: "center", color: "#8b949e", padding: "40px" }}>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>📭</div>
                  <div>No signals yet — strong signals are saved every 5 minutes when score &gt;75 or &lt;25.</div>
                </td>
              </tr>
            )}
            {!loading && filtered.map((s, i) => {
              const isIn = s.direction === "INFLOW";
              return (
                <tr
                  key={`${s.symbol}-${s.ts}`}
                  style={{ background: i % 2 === 0 ? "transparent" : "#0a0e14", cursor: "pointer" }}
                  onClick={() => setFundFlowSym(s.symbol)}
                  title="Click to view fund flow history"
                >
                  <td style={{ ...cell, color: "#8b949e" }}>{s.time}</td>
                  <td style={{ ...cell }}>
                    <span style={{ color: "#e6edf3", fontWeight: 700 }}>{s.symbol}</span>
                  </td>
                  <td style={{ ...cell, textAlign: "right" }}>
                    <span style={{
                      padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700,
                      background: isIn ? "#0a2d0a" : "#2d0a0a",
                      color: isIn ? "#3fb950" : "#f85149",
                    }}>
                      {isIn ? "▲ INFLOW" : "▼ OUTFLOW"}
                    </span>
                  </td>
                  <td style={{
                    ...cell, textAlign: "right", fontWeight: 700,
                    color: s.score >= 65 ? "#3fb950" : s.score <= 35 ? "#f85149" : "#d29922",
                  }}>
                    {s.score.toFixed(1)}
                  </td>
                  <td style={{ ...cell, textAlign: "right", color: "#e6edf3" }}>
                    ${fmtPrice(s.price)}
                  </td>
                  <td style={{
                    ...cell, textAlign: "right", fontWeight: 600,
                    color: s.net_flow >= 0 ? "#3fb950" : "#f85149",
                  }}>
                    {fmtFlow(s.net_flow)}
                  </td>
                  <td style={{ ...cell, textAlign: "right", maxWidth: 200 }}>
                    <div style={{ display: "flex", gap: 3, flexWrap: "wrap", justifyContent: "flex-end" }}>
                      {s.smart_signals.map(sig => (
                        <SmartSignalBadge key={sig} signal={sig} />
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
