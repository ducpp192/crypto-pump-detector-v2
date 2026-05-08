import React, { useMemo } from "react";
import { MonitorToken, SmartSignal } from "../../types/monitor";
import { SmartSignalBadge } from "./SmartSignalBadge";

interface Props {
  tokens: MonitorToken[];
}

function fmtPct(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

export function AlertFeed({ tokens }: Props) {
  const alerts = useMemo(() => {
    const list = tokens.filter(t =>
      t.flow_score_5m >= 70 ||
      t.flow_score_5m <= 30 ||
      t.smart_signals.length > 0,
    );
    list.sort((a, b) => {
      const sa = Math.abs(a.flow_score_5m - 50) + a.smart_signals.length * 5;
      const sb = Math.abs(b.flow_score_5m - 50) + b.smart_signals.length * 5;
      return sb - sa;
    });
    return list.slice(0, 50);
  }, [tokens]);

  if (alerts.length === 0) {
    return (
      <div style={{
        textAlign: "center", padding: "40px 20px",
        color: "#8b949e", background: "#0d1117",
        borderRadius: 8, border: "1px solid #21262d",
      }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>🔔</div>
        <div style={{ fontSize: 13 }}>No active alerts</div>
        <div style={{ fontSize: 11, marginTop: 4 }}>Alerts appear when Flow Score ≥ 70 or ≤ 30</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{
        padding: "6px 12px", borderRadius: "6px 6px 0 0",
        background: "#161b22", borderBottom: "2px solid #d29922",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ color: "#d29922", fontWeight: 700, fontSize: 12 }}>🔔 FLOW ALERTS</span>
        <span style={{ color: "#8b949e", fontSize: 11 }}>({alerts.length} active)</span>
      </div>
      <div style={{
        background: "#0d1117",
        border: "1px solid #21262d",
        borderTop: "none",
        borderRadius: "0 0 6px 6px",
        overflow: "hidden",
      }}>
        {alerts.map((t, i) => {
          const isInflow  = t.flow_score_5m >= 60;
          const isOutflow = t.flow_score_5m <= 40;
          const accentColor = isInflow ? "#3fb950" : isOutflow ? "#f85149" : "#d29922";

          return (
            <div
              key={t.symbol}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: "8px 12px",
                borderBottom: i < alerts.length - 1 ? "1px solid #161b22" : "none",
                background: i % 2 === 0 ? "transparent" : "#0a0e14",
              }}
            >
              {/* Color bar */}
              <div style={{
                width: 3, alignSelf: "stretch", borderRadius: 2,
                background: accentColor, flexShrink: 0,
              }} />

              {/* Symbol + name */}
              <div style={{ minWidth: 80, flexShrink: 0 }}>
                <div style={{ color: "#e6edf3", fontWeight: 700, fontSize: 13 }}>{t.symbol}</div>
                <div style={{ color: "#8b949e", fontSize: 10 }}>{t.name}</div>
              </div>

              {/* Flow score */}
              <div style={{ minWidth: 54, flexShrink: 0, textAlign: "center" }}>
                <div style={{ color: accentColor, fontWeight: 700, fontSize: 18, lineHeight: 1 }}>
                  {t.flow_score_5m.toFixed(0)}
                </div>
                <div style={{ color: "#8b949e", fontSize: 9 }}>flow</div>
              </div>

              {/* Price changes */}
              <div style={{ minWidth: 70, flexShrink: 0 }}>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {[
                    { label: "5m", v: t.price_change_5m },
                    { label: "1h", v: t.price_change_1h },
                    { label: "24h", v: t.price_change_24h },
                  ].map(({ label, v }) => (
                    <div key={label} style={{ textAlign: "center" }}>
                      <div style={{ color: v >= 0 ? "#3fb950" : "#f85149", fontSize: 10, fontWeight: 600 }}>
                        {fmtPct(v)}
                      </div>
                      <div style={{ color: "#8b949e", fontSize: 9 }}>{label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Smart signals */}
              <div style={{ flex: 1, display: "flex", flexWrap: "wrap", gap: 3, alignItems: "center" }}>
                {t.smart_signals.map(s => (
                  <SmartSignalBadge key={s} signal={s as SmartSignal} />
                ))}
                {t.oi_spike && (
                  <span style={{ color: "#e3771a", fontSize: 9, fontWeight: 600 }}>🔥 OI Spike</span>
                )}
              </div>

              {/* Buy ratio */}
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div style={{
                  color: t.buy_ratio >= 0.6 ? "#3fb950" : t.buy_ratio <= 0.4 ? "#f85149" : "#d29922",
                  fontSize: 11, fontWeight: 600,
                }}>
                  {(t.buy_ratio * 100).toFixed(0)}% buy
                </div>
                <div style={{ color: "#8b949e", fontSize: 9 }}>
                  {t.has_futures ? "futures" : "spot only"}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
