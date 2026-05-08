import React, { useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { MonitorDashboard } from "./components/monitor/MonitorDashboard";

type AppTab = "pump" | "monitor";

const TABS: { key: AppTab; label: string }[] = [
  { key: "pump",    label: "🔍 Pump Detector" },
  { key: "monitor", label: "💸 Monitor Crypto" },
];

function App() {
  const [tab, setTab] = useState<AppTab>("pump");

  return (
    <div style={{ minHeight: "100vh", background: "#0d1117" }}>
      {/* Top-level tab bar */}
      <div style={{
        background: "#010409",
        borderBottom: "1px solid #30363d",
        display: "flex",
        padding: "0 20px",
        gap: 2,
      }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "10px 18px",
              border: "none",
              borderBottom: `2px solid ${tab === t.key ? "#58a6ff" : "transparent"}`,
              background: "transparent",
              color: tab === t.key ? "#e6edf3" : "#8b949e",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: tab === t.key ? 700 : 500,
              letterSpacing: "0.02em",
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "pump"    && <Dashboard />}
      {tab === "monitor" && <MonitorDashboard />}
    </div>
  );
}

export default App;
