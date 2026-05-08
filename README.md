# 🔍 Crypto Pump Detector v2

A real-time mid-cap cryptocurrency signal engine and money flow monitor built with **FastAPI + React + WebSocket**.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![React](https://img.shields.io/badge/React-18-61dafb) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green) ![License](https://img.shields.io/badge/license-MIT-brightgreen)

---

## ✨ Features

### 🚀 Pump Detector Tab
- **Real-time signal engine** scanning 140+ mid-cap tokens (market cap $1M–$500M)
- **WebSocket delta protocol** — MD5 hash-based change detection, 50ms batch flush
- **7 concurrent background tasks**: CMC refresh, REST enrichment, WS stream, Futures, Scoring, Outcome tracker, Money flow
- **Signal types**: PUMP · DUMP · SHORT_SQUEEZE · LONG_SQUEEZE · NEUTRAL
- **Crime Coin Score** — 8-component market manipulation detection (0–100)
- **OI Analytics** — open interest change 1m/5m/15m, trend, spike score, signal type
- **Dòng Tiền (Money Flow)** — Coinank + Bybit L/S ratio composite scoring
- **Signal history** — SQLite with 4h/24h PnL outcome tracking

### 💸 Money Flow Monitor Tab
- **FLOW_SCORE** composite across 5 timeframes (5m · 15m · 1h · 4h · 1d):
  ```
  FLOW_SCORE = (volume_delta × 0.25) + (oi_delta × 0.25) + (price_momentum × 0.20)
             + (funding_divergence × 0.15) + (liquidation_pressure × 0.10) + (relative_volume × 0.05)
  ```
- **Smart signals**: ABNORMAL_VOLUME · SHORT_SQUEEZE_LIKELY · LONG_SQUEEZE_LIKELY · LEVERAGE_BUILDUP · SPOT_LED_RALLY · FUTURES_LED_RALLY · LOW_CAP_SPECULATION · HIGH_OI_RATIO
- **Flow Heatmap** — top 120 tokens colored by inflow/outflow intensity
- **Fund Flow History** (Coinank-style) — click any token to see net inflow table: 5m · 15m · 30m · 1h · 4h · 1d rolling cumulative USD flow
- **History tab** — all strong signals (score >75 or <25) stored in SQLite, kept 30 days
- **Sort on all columns** — click any column header to sort ascending/descending

---

## 🏗️ Architecture

```
crypto-pump-detector-v2/
├── backend/                    # FastAPI + Python
│   ├── main.py                 # App entry point, 8 background tasks
│   ├── config.py               # Thresholds, weights, API endpoints
│   ├── models/
│   │   ├── __init__.py         # TokenSignal Pydantic model
│   │   └── token_state.py      # TokenState runtime dataclass
│   ├── routers/
│   │   ├── signals.py          # GET /api/signals
│   │   ├── ws.py               # WS  /ws/signals (delta stream)
│   │   ├── oi.py               # GET /api/oi/*
│   │   ├── dong_tien.py        # GET /api/dong-tien/*
│   │   ├── monitor.py          # GET /api/monitor/* + WS /ws/monitor
│   │   └── history.py          # GET /api/history/*
│   └── services/
│       ├── scanner.py          # 6-task orchestrator + shared _states
│       ├── signal_engine.py    # Weighted scoring (0–100)
│       ├── monitor_service.py  # FLOW_SCORE engine
│       ├── flow_history.py     # SQLite snapshots + alert history
│       ├── crime_score.py      # Manipulation detection
│       ├── oi_tracker.py       # OI analytics & signals
│       ├── binance_rest.py     # Klines, orderbook, funding rate
│       ├── binance_futures.py  # OI, liquidations
│       ├── binance_ws.py       # Live trade stream
│       ├── cmc_service.py      # CoinMarketCap mid-cap universe
│       └── dong_tien_service.py# Coinank + Bybit money flow
└── frontend/                   # React 18 + TypeScript
    └── src/
        ├── App.tsx             # Tab navigation (Pump Detector / Monitor)
        ├── components/
        │   ├── Dashboard.tsx   # Pump detector main view
        │   ├── TokenTable.tsx  # Sortable signal table
        │   ├── FilterPanel.tsx # Signal/OI filters
        │   └── monitor/
        │       ├── MonitorDashboard.tsx
        │       ├── FlowTable.tsx       # Full-sort flow ranking
        │       ├── FlowHeatmap.tsx     # Color-coded grid
        │       ├── FundFlowPanel.tsx   # Coinank-style inflow modal
        │       ├── FlowHistoryTab.tsx  # Historical strong signals
        │       └── AlertFeed.tsx
        └── hooks/
            ├── useRealtimeSignals.ts   # WS delta + RAF batching
            └── useMonitorData.ts       # Monitor WS
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- CoinMarketCap API key (free tier works)

### 1. Backend setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your CMC_API_KEY
```

### 2. Frontend setup
```bash
cd frontend
npm install
```

### 3. Run everything
```bash
# Windows — double-click or run:
START.bat
```
- Backend: http://localhost:8002
- Frontend: http://localhost:3001
- API docs: http://localhost:8002/docs

---

## ⚙️ Configuration

Edit `backend/.env`:
```env
CMC_API_KEY=your_coinmarketcap_api_key
TELEGRAM_BOT_TOKEN=optional_for_alerts
TELEGRAM_CHAT_ID=optional_for_alerts
```

Key thresholds in `backend/config.py`:
```python
MIDCAP_MIN_USD   = 1_000_000    # Min market cap
MIDCAP_MAX_USD   = 500_000_000  # Max market cap
PUMP_SCORE_THRESHOLD = 65       # Score ≥ 65 → PUMP signal
DUMP_SCORE_THRESHOLD = 35       # Score ≤ 35 → DUMP signal
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/signals` | Current token signals |
| WS | `/ws/signals` | Real-time delta stream |
| GET | `/api/monitor/snapshot` | Flow scores snapshot |
| WS | `/api/monitor/ws/monitor` | Real-time flow stream |
| GET | `/api/monitor/fund-flow/{symbol}` | Coinank-style inflow history |
| GET | `/api/monitor/history` | Strong signal alert history |
| GET | `/api/monitor/heatmap` | Compact heatmap data |
| GET | `/api/oi/{symbol}` | OI history + analytics |
| GET | `/api/dong-tien/scan` | Money flow scan |
| GET | `/health` | Health check |

---

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.10, FastAPI, Uvicorn, aiohttp, aiosqlite |
| Frontend | React 18, TypeScript, Create React App |
| Data | Binance Spot + Futures API, CoinMarketCap, Coinank |
| Storage | SQLite (signal history, flow snapshots) |
| Realtime | WebSocket (delta protocol, RAF-batched renders) |

---

## 📄 License

MIT — free to use, modify, and share.

---

> Built with ❤️ for crypto traders who want more signal, less noise.
