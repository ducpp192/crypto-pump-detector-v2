import React, { useMemo, useState } from "react";
import { MonitorToken, MonitorFilters, SmartSignal } from "../../types/monitor";
import { FlowScoreBar } from "./FlowScoreBar";
import { SmartSignalBadge } from "./SmartSignalBadge";
import { FundFlowPanel } from "./FundFlowPanel";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtPrice(p: number): string {
  if (p >= 1000) return p.toFixed(2);
  if (p >= 1)    return p.toFixed(4);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
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

function pctColor(v: number): string {
  return v >= 0 ? "#3fb950" : "#f85149";
}

function directionBadge(d: string) {
  if (d === "INFLOW")  return { label: "▲ INFLOW",  color: "#3fb950", bg: "#0a2d0a" };
  if (d === "OUTFLOW") return { label: "▼ OUTFLOW", color: "#f85149", bg: "#2d0a0a" };
  return { label: "— NEUTRAL", color: "#8b949e", bg: "transparent" };
}

// ── Sort types ────────────────────────────────────────────────────────────────

type SortKey =
  | "flow_score_5m" | "flow_score_15m" | "flow_score_1h" | "flow_score_1d"
  | "price_change_5m" | "price_change_15m" | "price_change_1h" | "price_change_24h"
  | "volume_spike_pct" | "market_cap" | "volume_24h"
  | "oi_change_5m" | "oi_change_15m" | "oi_usd" | "oi_market_cap_ratio"
  | "buy_ratio" | "funding_rate" | "trade_freq"
  | "crime_score";

function getSortValue(t: MonitorToken, key: SortKey): number {
  const v = t[key as keyof MonitorToken];
  if (v == null) return -Infinity;
  return v as number;
}

// ── Column header ─────────────────────────────────────────────────────────────

interface THProps {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
  sortKey?: SortKey;
  currentSort?: SortKey;
  sortDir?: "asc" | "desc";
  onSort?: (k: SortKey) => void;
}

function TH({ children, align = "left", sortKey, currentSort, sortDir, onSort }: THProps) {
  const isActive = !!sortKey && sortKey === currentSort;
  return (
    <th
      style={{
        padding: "6px 8px",
        color: isActive ? "#e6edf3" : "#8b949e",
        fontSize: 10,
        fontWeight: 600,
        textAlign: align,
        borderBottom: "1px solid #21262d",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        whiteSpace: "nowrap",
        cursor: sortKey ? "pointer" : "default",
        userSelect: "none",
        background: isActive ? "#161b22" : "transparent",
      }}
      onClick={sortKey && onSort ? () => onSort(sortKey) : undefined}
    >
      {children}
      {sortKey && (
        <span style={{ marginLeft: 3, opacity: isActive ? 1 : 0.3, fontSize: 9 }}>
          {isActive ? (sortDir === "desc" ? "▼" : "▲") : "⇅"}
        </span>
      )}
    </th>
  );
}

// ── Token row ─────────────────────────────────────────────────────────────────

interface TokenRowProps {
  token: MonitorToken;
  tf: string;
  onFundFlow: (sym: string) => void;
}

const TokenRow = React.memo(function TokenRow({ token: t, tf, onFundFlow }: TokenRowProps) {
  const fsKey  = `flow_score_${tf}` as keyof MonitorToken;
  const pcKey  = `price_change_${tf}` as keyof MonitorToken;
  const fs = (t[fsKey] as number) ?? t.flow_score_5m;
  const pc = (t[pcKey] as number) ?? t.price_change_5m;
  const dir = directionBadge(t.flow_direction);

  const cell: React.CSSProperties = {
    padding: "5px 8px",
    borderBottom: "1px solid #161b22",
    whiteSpace: "nowrap",
    verticalAlign: "middle",
    fontSize: 12,
  };

  return (
    <tr
      style={{ background: "transparent", cursor: "pointer" }}
      onClick={() => onFundFlow(t.symbol)}
      title="Click to view fund flow history"
    >
      {/* Symbol */}
      <td style={cell}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ color: "#e6edf3", fontWeight: 600 }}>{t.symbol}</span>
          {t.oi_spike && <span title="OI Spike" style={{ color: "#e3771a", fontSize: 10 }}>🔥</span>}
        </div>
        <div style={{ color: "#8b949e", fontSize: 10 }}>{t.name}</div>
      </td>
      {/* Price / tf change */}
      <td style={{ ...cell, textAlign: "right" }}>
        <div style={{ color: "#e6edf3" }}>${fmtPrice(t.price)}</div>
        <div style={{ color: pctColor(pc), fontSize: 10 }}>{fmtPct(pc)}</div>
      </td>
      {/* 24h */}
      <td style={{ ...cell, textAlign: "right", color: pctColor(t.price_change_24h) }}>
        {fmtPct(t.price_change_24h)}
      </td>
      {/* Flow score */}
      <td style={cell}>
        <FlowScoreBar score={fs} width={72} />
      </td>
      {/* Direction */}
      <td style={{ ...cell, textAlign: "center" }}>
        <span style={{
          padding: "2px 6px", borderRadius: 4,
          background: dir.bg, color: dir.color,
          fontSize: 10, fontWeight: 700,
        }}>
          {dir.label}
        </span>
      </td>
      {/* Smart signals */}
      <td style={{ ...cell, maxWidth: 180 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
          {t.smart_signals.map(s => <SmartSignalBadge key={s} signal={s as SmartSignal} />)}
        </div>
      </td>
      {/* Buy% */}
      <td style={{
        ...cell, textAlign: "right",
        color: t.buy_ratio >= 0.6 ? "#3fb950" : t.buy_ratio <= 0.4 ? "#f85149" : "#d29922",
      }}>
        {(t.buy_ratio * 100).toFixed(1)}%
      </td>
      {/* Vol spike */}
      <td style={{ ...cell, textAlign: "right", color: t.volume_spike_pct > 200 ? "#e3771a" : "#8b949e" }}>
        {t.volume_spike_pct > 0 ? `+${t.volume_spike_pct.toFixed(0)}%` : "—"}
      </td>
      {/* Funding */}
      <td style={{
        ...cell, textAlign: "right",
        color: (t.funding_rate ?? 0) < -0.0001 ? "#3fb950" : (t.funding_rate ?? 0) > 0.0001 ? "#f85149" : "#8b949e",
      }}>
        {fmtFR(t.funding_rate)}
      </td>
      {/* OI 5m */}
      <td style={{
        ...cell, textAlign: "right",
        color: (t.oi_change_5m ?? 0) > 0 ? "#3fb950" : (t.oi_change_5m ?? 0) < 0 ? "#f85149" : "#8b949e",
      }}>
        {t.oi_change_5m != null ? fmtPct(t.oi_change_5m) : "—"}
      </td>
      {/* OI USD */}
      <td style={{ ...cell, textAlign: "right", color: "#8b949e" }}>
        {fmtVol(t.oi_usd)}
      </td>
      {/* Trade freq */}
      <td style={{ ...cell, textAlign: "right", color: "#8b949e" }}>
        {t.trade_freq > 0 ? `${t.trade_freq.toFixed(1)}/s` : "—"}
      </td>
      {/* Market cap */}
      <td style={{ ...cell, textAlign: "right", color: "#8b949e" }}>
        {fmtVol(t.market_cap)}
      </td>
    </tr>
  );
});

// ── FlowTable ─────────────────────────────────────────────────────────────────

interface Props {
  tokens: MonitorToken[];
  filters: MonitorFilters;
}

export function FlowTable({ tokens, filters }: Props) {
  const [sortKey, setSortKey]   = useState<SortKey>("flow_score_5m");
  const [sortDir, setSortDir]   = useState<"asc" | "desc">("desc");
  const [expanded, setExpanded] = useState(false);
  const [fundFlowSym, setFundFlowSym] = useState<string | null>(null);

  const tf = filters.timeframe;

  function handleSort(k: SortKey) {
    if (k === sortKey) {
      setSortDir(d => d === "desc" ? "asc" : "desc");
    } else {
      setSortKey(k);
      setSortDir("desc");
    }
  }

  const filtered = useMemo(() => {
    let list = tokens;

    if (filters.searchQuery) {
      const q = filters.searchQuery.toUpperCase();
      list = list.filter(t => t.symbol.includes(q) || t.name.toUpperCase().includes(q));
    }
    if (filters.direction !== "all") {
      list = list.filter(t => t.flow_direction === filters.direction);
    }
    if (filters.signal !== "all" && filters.signal !== "") {
      list = list.filter(t => t.smart_signals.includes(filters.signal as SmartSignal));
    }
    if (filters.hasFutures === "yes") {
      list = list.filter(t => t.has_futures);
    } else if (filters.hasFutures === "no") {
      list = list.filter(t => !t.has_futures);
    }

    const fsKey = `flow_score_${tf}` as keyof MonitorToken;
    list = list.filter(t => {
      const s = (t[fsKey] as number) ?? t.flow_score_5m;
      return s >= filters.minScore && s <= filters.maxScore;
    });

    return [...list].sort((a, b) => {
      const va = getSortValue(a, sortKey);
      const vb = getSortValue(b, sortKey);
      return sortDir === "desc" ? vb - va : va - vb;
    });
  }, [tokens, filters, sortKey, sortDir, tf]);

  const CAP     = 60;
  const visible = expanded ? filtered : filtered.slice(0, CAP);
  const hidden  = filtered.length - CAP;

  // Shared sort props spread into each TH — uses currentSort not sortKey to avoid name collision
  const sh = { currentSort: sortKey, sortDir: sortDir as "asc" | "desc", onSort: handleSort } as const;

  if (filtered.length === 0) {
    return (
      <div style={{
        textAlign: "center", padding: "40px 20px",
        color: "#8b949e", background: "#0d1117",
        borderRadius: 8, border: "1px solid #21262d",
      }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>📡</div>
        <div style={{ fontSize: 13 }}>No tokens match current filters</div>
      </div>
    );
  }

  const tfLabel = tf;

  return (
    <div>
      {fundFlowSym && (
        <FundFlowPanel symbol={fundFlowSym} onClose={() => setFundFlowSym(null)} />
      )}

      {/* Section header */}
      <div style={{
        padding: "6px 12px", borderRadius: "6px 6px 0 0",
        background: "#161b22", borderBottom: "2px solid #58a6ff",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ color: "#58a6ff", fontWeight: 700, fontSize: 12 }}>
          💸 MONEY FLOW RANKING
        </span>
        <span style={{ color: "#8b949e", fontSize: 11 }}>
          ({filtered.length} tokens · sorted by {sortKey} {sortDir === "desc" ? "↓" : "↑"})
        </span>
        <span style={{ color: "#484f58", fontSize: 10, marginLeft: 4 }}>
          Click row → Fund Flow History
        </span>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: "#0d1117", fontSize: 12 }}>
          <thead>
            <tr>
              <TH>Symbol</TH>
              <TH align="right" sortKey={`price_change_${tf}` as SortKey} {...sh}>
                Price / {tfLabel}
              </TH>
              <TH align="right" sortKey="price_change_24h" {...sh}>24h</TH>
              <TH sortKey={`flow_score_${tf}` as SortKey} {...sh}>
                Flow {tfLabel}
              </TH>
              <TH align="center">Direction</TH>
              <TH>Signals</TH>
              <TH align="right" sortKey="buy_ratio" {...sh}>Buy%</TH>
              <TH align="right" sortKey="volume_spike_pct" {...sh}>Vol Spike</TH>
              <TH align="right" sortKey="funding_rate" {...sh}>Funding</TH>
              <TH align="right" sortKey="oi_change_5m" {...sh}>OI 5m</TH>
              <TH align="right" sortKey="oi_usd" {...sh}>OI USD</TH>
              <TH align="right" sortKey="trade_freq" {...sh}>Freq</TH>
              <TH align="right" sortKey="market_cap" {...sh}>Mktcap</TH>
            </tr>
          </thead>
          <tbody>
            {visible.map(t => (
              <TokenRow
                key={t.symbol}
                token={t}
                tf={tf}
                onFundFlow={setFundFlowSym}
              />
            ))}
          </tbody>
        </table>
      </div>

      {!expanded && hidden > 0 && (
        <button
          style={{
            width: "100%", padding: "6px",
            background: "#161b22", border: "1px solid #30363d",
            borderTop: "none", color: "#58a6ff", cursor: "pointer",
            fontSize: 11, borderRadius: "0 0 6px 6px",
          }}
          onClick={() => setExpanded(true)}
        >
          Show all {filtered.length} tokens (+{hidden} more)
        </button>
      )}
    </div>
  );
}
