import React from "react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  valueColor?: string;
}

export const StatCard = React.memo(function StatCard({
  title,
  value,
  subtitle,
  valueColor = "#e6edf3",
}: StatCardProps) {
  return (
    <div style={{
      background: "#161b22",
      border: "1px solid #30363d",
      borderRadius: 8,
      padding: "12px 16px",
      minWidth: 120,
      flex: 1,
    }}>
      <div style={{ color: "#8b949e", fontSize: 11, marginBottom: 4 }}>{title}</div>
      <div style={{ color: valueColor, fontSize: 22, fontWeight: 700, lineHeight: 1.2 }}>{value}</div>
      {subtitle && (
        <div style={{ color: "#8b949e", fontSize: 11, marginTop: 2 }}>{subtitle}</div>
      )}
    </div>
  );
});
