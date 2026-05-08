import React, { useState, useMemo } from "react";
import { TokenSignal, SignalType } from "../types";
import { SignalBadge } from "./SignalBadge";
import { ScoreBar } from "./ScoreBar";

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtPrice(p: number): string {
  if (p >= 1000) return p.toFixed(2);
  if (p >= 1)    return p.toFixed(4);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}

function fmtPct(v: number | null | undefined, plus = true): string {
  if (v == null) return "—";
  const sign = plus && v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function fmtVol(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function fmtFR(v: number | null): string {
  if (v == null) return "—";
  const pct = v * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(4)}%`;
}

function frColor(v: number | null): string {
  if (v == null) return "#8b949e";
  if (v < -0.001) return "#3fb950";
  if (v > 0.001)  return "#f85149";
  return "#8b949e";
}

// ── Column header ─────────────────────────────────────────────────────────────

const TH: React.FC<{ children: React.ReactNode; align?: "left" | "right" | "center" }> = ({
  children, align = "left",
}) => (
  <th style={{
    padding: "6px 8px",
    color: "#8b949e",
    fontSize: 10,
    fontWeight: 600,
    textAlign: align,
    borderBottom: "1px solid #21262d",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    whiteSpace: "nowrap",
  }}>{children}</th>
);

// ── Token row ─────────────────────────────────────────────────────────────────

interface TokenRowProps { token: TokenSignal; }

function rowEqual(a: TokenRowProps, b: TokenRowProps): boolean {
  const p = a.token, q = b.token;
  return (
    p.symbol === q.symbol &&
    p.price === q.price &&
    p.score === q.score &&
    p.signal === q.signal &&
    p.buy_ratio === q.buy_ratio &&
    p.pump_detected === q.pump_detected &&
    p.dump_detected === q.dump_detected &&
    p.short_squeeze === q.short_squeeze &&
    p.long_squeeze === q.long_squeeze &&
    p.volume_spike_pct === q.volume_spike_pct &&
    p.spot_momentum_score === q.spot_momentum_score &&
    p.trade_flow_score === q.trade_flow_score &&
    p.oi_spike === q.oi_spike &&
    p.crime_level === q.crime_level
  );
}

const CRIME_COLORS: Record<string, string> = {
  MM_ACTIVE:  "#f85149",
  CRIME_COIN: "#e3771a",
  SUSPICIOUS: "#d29922",
  WARNING:    "#8b949e",
  NORMAL:     "transparent",
};

const TokenRow = React.memo(function TokenRow({ token: t }: TokenRowProps) {
  const chg1hColor = (t.price_change_1h ?? 0) >= 0 ? "#3fb950" : "#f85149";
  const chg24hColor = (t.price_change_24h ?? 0) >= 0 ? "#3fb950" : "#f85149";
  const buyColor = t.buy_ratio >= 0.6 ? "#3fb950" : t.buy_ratio <= 0.4 ? "#f85149" : "#d29922";
  const crimeColor = CRIME_COLORS[t.crime_level] ?? "transparent";
  const hasOiAlert = t.oi_spike || t.oi_signal_type != null;

  const cellStyle: React.CSSProperties = {
    padding: "5px 8px",
    borderBottom: "1px solid #161b22",
    whiteSpace: "nowrap",
    verticalAlign: "middle",
    fontSize: 12,
  };

  return (
    <tr style={{ background: "transparent" }}>
      {/* Symbol */}
      <td style={cellStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          {crimeColor !== "transparent" && t.crime_level !== "NORMAL" && (
            <span title={`Crime: ${t.crime_level} (${t.crime_score.toFixed(0)})`}
              style={{ color: crimeColor, fontSize: 10 }}>⚠</span>
          )}
          <span style={{ color: "#e6edf3", fontWeight: 600 }}>{t.symbol}</span>
          {hasOiAlert && (
            <span title={`OI: ${t.oi_signal_type ?? "spike"}`}
              style={{ color: "#e3771a", fontSize: 10 }}>🔥</span>
          )}
        </div>
        <div style={{ color: "#8b949e", fontSize: 10 }}>{t.name}</div>
      </td>
      {/* Price */}
      <td style={{ ...cellStyle, textAlign: "right" }}>
        <div style={{ color: "#e6edf3" }}>${fmtPrice(t.price)}</div>
        <div style={{ color: chg1hColor, fontSize: 10 }}>{fmtPct(t.price_change_1h)}</div>
      </td>
      {/* 24h */}
      <td style={{ ...cellStyle, textAlign: "right", color: chg24hColor }}>
        {fmtPct(t.price_change_24h)}
      </td>
      {/* Score */}
      <td style={cellStyle}>
        <ScoreBar score={t.score} width={72} />
      </td>
      {/* Signal */}
      <td style={{ ...cellStyle, textAlign: "center" }}>
        <SignalBadge
          signal={t.signal as SignalType}
          pumpDetected={t.pump_detected}
          dumpDetected={t.dump_detected}
        />
      </td>
      {/* Buy ratio */}
      <td style={{ ...cellStyle, textAlign: "right", color: buyColor }}>
        {(t.buy_ratio * 100).toFixed(1)}%
      </td>
      {/* Vol spike */}
      <td style={{ ...cellStyle, textAlign: "right", color: t.volume_spike_pct > 200 ? "#e3771a" : "#8b949e" }}>
        {t.volume_spike_pct > 0 ? `+${t.volume_spike_pct.toFixed(0)}%` : "—"}
      </td>
      {/* Funding rate */}
      <td style={{ ...cellStyle, textAlign: "right", color: frColor(t.funding_rate) }}>
        {fmtFR(t.funding_rate)}
      </td>
      {/* OI change 5m */}
      <td style={{ ...cellStyle, textAlign: "right", color: (t.oi_change_5m ?? 0) > 0 ? "#3fb950" : (t.oi_change_5m ?? 0) < 0 ? "#f85149" : "#8b949e" }}>
        {t.oi_change_5m != null ? fmtPct(t.oi_change_5m) : "—"}
      </td>
      {/* OI USD */}
      <td style={{ ...cellStyle, textAlign: "right", color: "#8b949e" }}>
        {fmtVol(t.oi_usd)}
      </td>
      {/* Trade freq */}
      <td style={{ ...cellStyle, textAlign: "right", color: "#8b949e" }}>
        {t.trade_freq > 0 ? `${t.trade_freq.toFixed(1)}/s` : "—"}
      </td>
      {/* MC */}
      <td style={{ ...cellStyle, textAlign: "right", color: "#8b949e" }}>
        {fmtVol(t.market_cap)}
      </td>
    </tr>
  );
}, rowEqual);

// ── Section table ─────────────────────────────────────────────────────────────

const CAP = 50;

interface SectionTableProps {
  title: string;
  color: string;
  tokens: TokenSignal[];
}

function SectionTable({ title, color, tokens }: SectionTableProps) {
  const [expanded, setExpanded] = useState(false);

  if (tokens.length === 0) return null;

  const visible = expanded ? tokens : tokens.slice(0, CAP);
  const hidden  = tokens.length - CAP;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        padding: "6px 12px",
        borderRadius: "6px 6px 0 0",
        background: "#161b22",
        borderBottom: `2px solid ${color}`,
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}>
        <span style={{ color, fontWeight: 700, fontSize: 12 }}>{title}</span>
        <span style={{ color: "#8b949e", fontSize: 11 }}>({tokens.length})</span>
      </div>
      <div style={{ overflowX: "auto" as const }}>
        <table style={{
          width: "100%",
          borderCollapse: "collapse",
          background: "#0d1117",
          fontSize: 12,
        }}>
          <thead>
            <tr>
              <TH>Symbol</TH>
              <TH align="right">Price / 1h</TH>
              <TH align="right">24h</TH>
              <TH>Score</TH>
              <TH align="center">Signal</TH>
              <TH align="right">Buy%</TH>
              <TH align="right">Vol Spike</TH>
              <TH align="right">Funding</TH>
              <TH align="right">OI 5m</TH>
              <TH align="right">OI USD</TH>
              <TH align="right">Freq</TH>
              <TH align="right">Mktcap</TH>
            </tr>
          </thead>
          <tbody>
            {visible.map(t => <TokenRow key={t.symbol} token={t} />)}
          </tbody>
        </table>
      </div>
      {!expanded && hidden > 0 && (
        <button
          style={{
            width: "100%",
            padding: "6px",
            background: "#161b22",
            border: "1px solid #30363d",
            borderTop: "none",
            color: "#58a6ff",
            cursor: "pointer",
            fontSize: 11,
            borderRadius: "0 0 6px 6px",
          }}
          onClick={() => setExpanded(true)}
        >
          Show all {tokens.length} tokens (+{hidden} more)
        </button>
      )}
    </div>
  );
}

// ── Main TokenTable ───────────────────────────────────────────────────────────

interface TokenTableProps {
  signals: TokenSignal[];
}

export function TokenTable({ signals }: TokenTableProps) {
  const pumpSignals = useMemo(() => signals.filter(s => s.signal === "PUMP"), [signals]);
  const dumpSignals = useMemo(() => signals.filter(s => s.signal === "DUMP"), [signals]);
  const sqzSignals  = useMemo(() => signals.filter(s => s.short_squeeze || s.long_squeeze), [signals]);
  const otherSignals = useMemo(() =>
    signals.filter(s => s.signal === "NEUTRAL" && !s.short_squeeze && !s.long_squeeze),
    [signals],
  );

  if (signals.length === 0) {
    return (
      <div style={{
        textAlign: "center",
        padding: "60px 20px",
        color: "#8b949e",
        background: "#0d1117",
        borderRadius: 8,
        border: "1px solid #21262d",
      }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>📡</div>
        <div style={{ fontSize: 14 }}>Waiting for data…</div>
        <div style={{ fontSize: 12, marginTop: 6 }}>Backend is scanning — first results appear in ~30s</div>
      </div>
    );
  }

  return (
    <div>
      <SectionTable title="🚀 PUMP"    color="#3fb950" tokens={pumpSignals} />
      <SectionTable title="🔴 DUMP"    color="#f85149" tokens={dumpSignals} />
      <SectionTable title="⚡ SQUEEZE" color="#d29922" tokens={sqzSignals} />
      <SectionTable title="NEUTRAL"    color="#484f58" tokens={otherSignals} />
    </div>
  );
}
