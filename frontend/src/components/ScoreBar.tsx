import React from "react";

interface ScoreBarProps {
  score: number;
  width?: number;
}

function scoreColor(score: number): string {
  if (score >= 65) return "#3fb950";
  if (score <= 35) return "#f85149";
  return "#d29922";
}

export const ScoreBar = React.memo(function ScoreBar({ score, width = 80 }: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const color   = scoreColor(clamped);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width,
        height: 6,
        background: "#30363d",
        borderRadius: 3,
        overflow: "hidden",
        flexShrink: 0,
      }}>
        <div style={{
          width: `${clamped}%`,
          height: "100%",
          background: color,
          borderRadius: 3,
          transition: "width 0.3s ease",
        }} />
      </div>
      <span style={{ color, fontSize: 11, fontWeight: 600, minWidth: 28, textAlign: "right" }}>
        {clamped.toFixed(0)}
      </span>
    </div>
  );
});
