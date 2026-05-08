import React, { useEffect, useState } from "react";

interface FundFlowRow {
  ts: number;
  time: string;
  score: number;
  price: number;
  flow_5m:  number;
  flow_15m: number;
  flow_30m: number;
  flow_1h:  number;
  flow_4h:  number;
  flow_1d:  number;
}

interface Props {
  symbol: string;
  onClose: () => void;
}

const API = process.env.REACT_APP_API_URL ?? "http://localhost:8002";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtFlow(v: number): string {
  const abs = Math.abs(v);
  const sign = v >= 0 ? "+" : "-";
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(0)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

function flowCellStyle(v: number): React.CSSProperties {
  if (v === 0) return { color: "#8b949e", background: "transparent" };
  const intensity = Math.min(1, Math.abs(v) / 5_000_000);
  const alpha = 0.1 + intensity * 0.35;
  if (v > 0) return {
    color: `rgba(63,185,80,${0.7 + intensity * 0.3})`,
    background: `rgba(63,185,80,${alpha})`,
  };
  return {
    color: `rgba(248,81,73,${0.7 + intensity * 0.3})`,
    background: `rgba(248,81,73,${alpha})`,
  };
}

function scoreDot(score: number) {
  const color = score >= 65 ? "#3fb950" : score <= 35 ? "#f85149" : "#d29922";
  return (
    <span style={{
      display: "inline-block", width: 7, height: 7, borderRadius: "50%",
      background: color, marginRight: 4, verticalAlign: "middle",
    }} />
  );
}

// ── Column header ─────────────────────────────────────────────────────────────

const COLS = ["5m", "15m", "30m", "1h", "4h", "1d"] as const;

// ── FundFlowPanel ─────────────────────────────────────────────────────────────

export function FundFlowPanel({ symbol, onClose }: Props) {
  const [rows, setRows]       = useState<FundFlowRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [limit, setLimit]     = useState(24);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`${API}/api/monitor/fund-flow/${symbol}?limit=${limit}`)
      .then(r => r.json())
      .then(d => { setRows(d.rows ?? []); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [symbol, limit]);

  const colKey = (tf: string): keyof FundFlowRow =>
    `flow_${tf}` as keyof FundFlowRow;

  const cellStyle: React.CSSProperties = {
    padding: "5px 10px",
    textAlign: "right",
    fontSize: 12,
    fontWeight: 600,
    borderBottom: "1px solid #161b22",
    whiteSpace: "nowrap",
    fontVariantNumeric: "tabular-nums",
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.7)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "#161b22",
        border: "1px solid #30363d",
        borderRadius: 10,
        width: "min(860px, 95vw)",
        maxHeight: "85vh",
        display: "flex", flexDirection: "column",
        boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
      }}>
        {/* Header */}
        <div style={{
          padding: "12px 18px",
          borderBottom: "1px solid #30363d",
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <div>
            <div style={{ color: "#e6edf3", fontWeight: 700, fontSize: 15 }}>
              {symbol} — Net Inflow History
            </div>
            <div style={{ color: "#8b949e", fontSize: 11, marginTop: 2 }}>
              5-minute snapshots · rolling cumulative net flow (USD)
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
            {[12, 24, 48, 96].map(n => (
              <button
                key={n}
                style={{
                  padding: "3px 9px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 600,
                  border: `1px solid ${limit === n ? "#58a6ff" : "#30363d"}`,
                  background: limit === n ? "#1c2e4a" : "#0d1117",
                  color: limit === n ? "#58a6ff" : "#8b949e",
                }}
                onClick={() => setLimit(n)}
              >
                {n}
              </button>
            ))}
            <button
              style={{
                marginLeft: 8, padding: "3px 10px", borderRadius: 4,
                border: "1px solid #30363d", background: "#21262d",
                color: "#8b949e", cursor: "pointer", fontSize: 13,
              }}
              onClick={onClose}
            >✕</button>
          </div>
        </div>

        {/* Legend */}
        <div style={{
          padding: "6px 18px", display: "flex", gap: 16, alignItems: "center",
          borderBottom: "1px solid #21262d", fontSize: 10, color: "#8b949e",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 10, height: 10, background: "rgba(63,185,80,0.4)", borderRadius: 2 }} />
            Net Inflow (buy pressure)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 10, height: 10, background: "rgba(248,81,73,0.4)", borderRadius: 2 }} />
            Net Outflow (sell pressure)
          </div>
          <span>· Columns = cumulative rolling windows</span>
        </div>

        {/* Table */}
        <div style={{ overflowY: "auto", flex: 1 }}>
          {loading && (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#8b949e" }}>
              Loading…
            </div>
          )}
          {error && (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#f85149", fontSize: 12 }}>
              {error}
            </div>
          )}
          {!loading && !error && rows.length === 0 && (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#8b949e" }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>⏳</div>
              <div>No snapshots yet — data saves every 5 minutes.</div>
              <div style={{ fontSize: 11, marginTop: 4, color: "#484f58" }}>
                First snapshot in ~{5} min after backend start.
              </div>
            </div>
          )}
          {!loading && rows.length > 0 && (
            <table style={{
              width: "100%", borderCollapse: "collapse",
              background: "#0d1117", fontSize: 12,
            }}>
              <thead>
                <tr style={{ position: "sticky", top: 0, background: "#161b22", zIndex: 1 }}>
                  <th style={{
                    ...cellStyle, textAlign: "left", color: "#8b949e",
                    fontWeight: 600, fontSize: 10, textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}>Time</th>
                  {COLS.map(tf => (
                    <th key={tf} style={{
                      ...cellStyle, color: "#8b949e", fontWeight: 600,
                      fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em",
                    }}>{tf}</th>
                  ))}
                  <th style={{
                    ...cellStyle, color: "#8b949e", fontWeight: 600,
                    fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em",
                  }}>Score</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={row.ts} style={{ background: i % 2 === 0 ? "transparent" : "#0a0e14" }}>
                    <td style={{ ...cellStyle, textAlign: "left", color: "#8b949e" }}>
                      {row.time}
                    </td>
                    {COLS.map(tf => {
                      const v = row[colKey(tf)] as number;
                      const s = flowCellStyle(v);
                      return (
                        <td key={tf} style={{ ...cellStyle, ...s, borderRadius: 0 }}>
                          {fmtFlow(v)}
                        </td>
                      );
                    })}
                    <td style={{ ...cellStyle, color: "#e6edf3" }}>
                      {scoreDot(row.score)}{row.score}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
