import React from "react";
import { SmartSignal } from "../../types/monitor";

const SIGNAL_META: Record<SmartSignal, { label: string; color: string; bg: string }> = {
  ABNORMAL_VOLUME:      { label: "🔊 Vol",     color: "#e3771a", bg: "#2d1a0a" },
  SHORT_SQUEEZE_LIKELY: { label: "⚡ Short Sqz",color: "#d29922", bg: "#2d260a" },
  LONG_SQUEEZE_LIKELY:  { label: "⚡ Long Sqz", color: "#f85149", bg: "#2d0a0a" },
  LEVERAGE_BUILDUP:     { label: "📈 Leverage", color: "#58a6ff", bg: "#0a1a2d" },
  SPOT_LED_RALLY:       { label: "🚀 Spot",     color: "#3fb950", bg: "#0a2d0a" },
  FUTURES_LED_RALLY:    { label: "📊 Futures",  color: "#a371f7", bg: "#1a0a2d" },
  LOW_CAP_SPECULATION:  { label: "🎯 LowCap",   color: "#ffa657", bg: "#2d1a0a" },
  HIGH_OI_RATIO:        { label: "🔥 OI/MC",    color: "#e3771a", bg: "#2d1a0a" },
};

interface Props {
  signal: SmartSignal;
}

export function SmartSignalBadge({ signal }: Props) {
  const meta = SIGNAL_META[signal];
  if (!meta) return null;
  return (
    <span style={{
      display: "inline-block",
      padding: "1px 5px",
      borderRadius: 3,
      background: meta.bg,
      color: meta.color,
      fontSize: 9,
      fontWeight: 700,
      border: `1px solid ${meta.color}33`,
      whiteSpace: "nowrap",
    }}>
      {meta.label}
    </span>
  );
}
