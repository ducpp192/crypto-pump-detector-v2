import React from "react";
import { SignalType } from "../types";

const SIGNAL_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  PUMP:          { bg: "#1a3a1a", color: "#3fb950", label: "PUMP" },
  DUMP:          { bg: "#3a1a1a", color: "#f85149", label: "DUMP" },
  SHORT_SQUEEZE: { bg: "#3a2a00", color: "#d29922", label: "SQ↑" },
  LONG_SQUEEZE:  { bg: "#2a1a00", color: "#e3771a", label: "SQ↓" },
  NEUTRAL:       { bg: "#1c2128", color: "#8b949e", label: "—" },
};

interface SignalBadgeProps {
  signal: SignalType;
  pumpDetected?: boolean;
  dumpDetected?: boolean;
}

export const SignalBadge = React.memo(function SignalBadge({
  signal,
  pumpDetected,
  dumpDetected,
}: SignalBadgeProps) {
  const s = SIGNAL_STYLES[signal] ?? SIGNAL_STYLES.NEUTRAL;
  const isWsConfirmed = (signal === "PUMP" && pumpDetected) || (signal === "DUMP" && dumpDetected);
  return (
    <span style={{
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.color}44`,
      borderRadius: 4,
      padding: "2px 7px",
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: "0.05em",
      whiteSpace: "nowrap",
      boxShadow: isWsConfirmed ? `0 0 6px ${s.color}88` : "none",
    }}>
      {isWsConfirmed ? "⚡" : ""}{s.label}
    </span>
  );
});
