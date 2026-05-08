import React from "react";

interface Props {
  score: number;
  width?: number;
}

export const FlowScoreBar = React.memo(function FlowScoreBar({ score, width = 80 }: Props) {
  const color =
    score >= 65 ? "#3fb950" :
    score >= 55 ? "#58a6ff" :
    score <= 35 ? "#f85149" :
    score <= 45 ? "#e3771a" :
    "#d29922";

  const pct = Math.max(0, Math.min(100, score));

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{
        width,
        height: 5,
        background: "#21262d",
        borderRadius: 3,
        overflow: "hidden",
      }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          background: color,
          borderRadius: 3,
          transition: "width 0.3s ease",
        }} />
      </div>
      <span style={{ color, fontSize: 11, fontWeight: 600, minWidth: 28 }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
});
