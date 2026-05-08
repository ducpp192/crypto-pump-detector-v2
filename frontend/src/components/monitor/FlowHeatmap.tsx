import React, { useMemo } from "react";
import { MonitorToken } from "../../types/monitor";

interface Props {
  tokens: MonitorToken[];
}

function scoreToColor(score: number): string {
  if (score >= 75) return "#0a3a0a";
  if (score >= 65) return "#0f2a0f";
  if (score >= 55) return "#1a2a0a";
  if (score >= 45) return "#1a1a1a";
  if (score >= 35) return "#2a1a0a";
  if (score >= 25) return "#2a0f0f";
  return "#3a0a0a";
}

function scoreToBorder(score: number): string {
  if (score >= 70) return "#3fb950";
  if (score >= 60) return "#58a6ff";
  if (score >= 50) return "#30363d";
  if (score >= 40) return "#e3771a";
  return "#f85149";
}

function scoreToText(score: number): string {
  if (score >= 70) return "#3fb950";
  if (score >= 60) return "#58a6ff";
  if (score >= 50) return "#8b949e";
  if (score >= 40) return "#e3771a";
  return "#f85149";
}

function fmtPct(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

export const FlowHeatmap = React.memo(function FlowHeatmap({ tokens }: Props) {
  const items = useMemo(
    () => tokens.slice(0, 120).sort((a, b) => b.flow_score_5m - a.flow_score_5m),
    [tokens],
  );

  if (items.length === 0) {
    return (
      <div style={{
        textAlign: "center", padding: "40px 20px",
        color: "#8b949e", background: "#0d1117",
        borderRadius: 8, border: "1px solid #21262d",
      }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>🗺️</div>
        <div style={{ fontSize: 13 }}>Waiting for data…</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{
        padding: "6px 12px", borderRadius: "6px 6px 0 0",
        background: "#161b22", borderBottom: "2px solid #58a6ff",
        display: "flex", alignItems: "center", gap: 12, marginBottom: 0,
      }}>
        <span style={{ color: "#58a6ff", fontWeight: 700, fontSize: 12 }}>🗺️ FLOW HEATMAP</span>
        <span style={{ color: "#8b949e", fontSize: 11 }}>top 120 tokens · colored by Flow Score 5m</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          {[["≥70", "#3fb950"], ["55–70", "#58a6ff"], ["45–55", "#8b949e"], ["30–45", "#e3771a"], ["≤30", "#f85149"]].map(
            ([label, color]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 3 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: color as string }} />
                <span style={{ color: "#8b949e", fontSize: 9 }}>{label}</span>
              </div>
            ),
          )}
        </div>
      </div>
      <div style={{
        background: "#0d1117",
        border: "1px solid #21262d",
        borderTop: "none",
        borderRadius: "0 0 6px 6px",
        padding: 12,
        display: "flex",
        flexWrap: "wrap",
        gap: 4,
      }}>
        {items.map(t => (
          <div
            key={t.symbol}
            title={`${t.symbol}\nFlow: ${t.flow_score_5m}\n5m: ${fmtPct(t.price_change_5m)}\nBuy: ${(t.buy_ratio * 100).toFixed(0)}%\n${t.smart_signals.join(", ") || "—"}`}
            style={{
              padding: "4px 7px",
              borderRadius: 4,
              background: scoreToColor(t.flow_score_5m),
              border: `1px solid ${scoreToBorder(t.flow_score_5m)}`,
              cursor: "default",
              minWidth: 52,
              textAlign: "center",
            }}
          >
            <div style={{ color: "#e6edf3", fontSize: 10, fontWeight: 700 }}>{t.symbol}</div>
            <div style={{ color: scoreToText(t.flow_score_5m), fontSize: 9, marginTop: 1 }}>
              {t.flow_score_5m.toFixed(0)}
            </div>
            <div style={{
              color: t.price_change_5m >= 0 ? "#3fb950" : "#f85149",
              fontSize: 9,
            }}>
              {fmtPct(t.price_change_5m)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});
