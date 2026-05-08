/**
 * DOCX Audit Generator — crypto-pump-detector-v2
 * Reads all source files from disk and produces a comprehensive audit document.
 * Run: node generate_audit_docx.js
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  PageOrientation, PageBreak, LevelFormat,
} = require('docx');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const OUT  = path.join(ROOT, 'crypto_pump_detector_audit.docx');

// ── Colour palette ────────────────────────────────────────────────────────────
const C = {
  white:     'FFFFFF',
  dark:      '0D1117',
  headerBg:  '161B22',
  codeBg:    '1A1F2E',
  accent:    '58A6FF',
  green:     '3FB950',
  red:       'F85149',
  yellow:    'D29922',
  muted:     '8B949E',
  border:    '30363D',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function readFile(relPath) {
  try {
    return fs.readFileSync(path.join(ROOT, relPath), 'utf8');
  } catch {
    return `[FILE NOT FOUND: ${relPath}]`;
  }
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 160 },
    children: [new TextRun({ text, bold: true, size: 36, color: C.white, font: 'Consolas' })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: C.accent, space: 4 } },
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, size: 28, color: C.accent, font: 'Consolas' })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 180, after: 80 },
    children: [new TextRun({ text, bold: true, size: 24, color: C.yellow, font: 'Consolas' })],
  });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 80, after: 80 },
    children: [new TextRun({ text, size: 20, color: C.white, font: 'Arial', ...opts })],
  });
}

function note(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    indent: { left: 360 },
    children: [new TextRun({ text: `ℹ  ${text}`, size: 18, color: C.muted, font: 'Arial', italics: true })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, size: 20, color: C.white, font: 'Arial' })],
  });
}

function codeLine(line) {
  return new Paragraph({
    spacing: { before: 0, after: 0, line: 240, lineRule: 'auto' },
    children: [new TextRun({ text: line || ' ', size: 16, color: 'C9D1D9', font: 'Consolas' })],
  });
}

function filePathPara(relPath) {
  return new Paragraph({
    spacing: { before: 160, after: 60 },
    children: [new TextRun({ text: relPath, size: 22, color: C.green, font: 'Consolas', bold: true })],
  });
}

function codeBlock(content) {
  const lines = content.split('\n');
  // Trim trailing empty lines
  while (lines.length && lines[lines.length - 1].trim() === '') lines.pop();

  const border = { style: BorderStyle.SINGLE, size: 1, color: C.border };
  const borders = { top: border, bottom: border, left: border, right: border };

  return new Table({
    width: { size: 14400, type: WidthType.DXA },
    columnWidths: [14400],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders,
            width: { size: 14400, type: WidthType.DXA },
            shading: { fill: '0D1117', type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: lines.map(codeLine),
          }),
        ],
      }),
    ],
  });
}

function hr() {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.border, space: 1 } },
    children: [new TextRun({ text: '' })],
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// ── File section builder ──────────────────────────────────────────────────────

function fileSection(relPath, description) {
  const content = readFile(relPath);
  const blocks = [
    filePathPara(relPath),
    para(description, { color: C.muted }),
    new Paragraph({ spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '' })] }),
    codeBlock(content),
    hr(),
  ];
  return blocks;
}

// ── Build document ────────────────────────────────────────────────────────────

const children = [];

// ── Cover Page ────────────────────────────────────────────────────────────────
children.push(
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 1440, after: 240 },
    children: [new TextRun({ text: 'CRYPTO PUMP DETECTOR v2', size: 56, bold: true, color: C.accent, font: 'Consolas' })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 240 },
    children: [new TextRun({ text: 'Source Code Audit Document', size: 32, color: C.muted, font: 'Arial' })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 80 },
    children: [new TextRun({ text: `Generated: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC`, size: 22, color: C.muted, font: 'Consolas' })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 480 },
    children: [new TextRun({ text: `Root: ${ROOT}`, size: 18, color: C.border, font: 'Consolas' })],
  }),

  // Quick summary table
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3120, 6240],
    rows: [
      ['Backend', 'FastAPI + Python 3.11 · asyncio · WebSocket · SQLite'],
      ['Frontend', 'React 18 + TypeScript · WebSocket client · CSS-in-JS'],
      ['Data sources', 'Binance REST (spot klines, orderbook, ticker) + Binance Futures REST + Binance WS trade stream'],
      ['Scoring', '7-factor weighted model (0–100 scale) + pump/dump boost + squeeze detection'],
      ['History', 'SQLite signal log with 4h/24h price outcome auto-tracking'],
      ['Token universe', 'CoinMarketCap Top-N filtered by market cap ($1M–$500M), min volume $500K/day'],
    ].map(([k, v]) => {
      const border = { style: BorderStyle.SINGLE, size: 1, color: C.border };
      const borders = { top: border, bottom: border, left: border, right: border };
      return new TableRow({
        children: [
          new TableCell({
            borders,
            width: { size: 3120, type: WidthType.DXA },
            shading: { fill: C.headerBg, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({ children: [new TextRun({ text: k, size: 18, bold: true, color: C.yellow, font: 'Consolas' })] })],
          }),
          new TableCell({
            borders,
            width: { size: 6240, type: WidthType.DXA },
            shading: { fill: '161B22', type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({ children: [new TextRun({ text: v, size: 18, color: C.white, font: 'Arial' })] })],
          }),
        ],
      });
    }),
  }),
  pageBreak(),
);

// ── 1. Architecture Overview ──────────────────────────────────────────────────
children.push(
  h1('1. Architecture Overview'),

  h2('1.1 System Design'),
  para('Crypto Pump Detector v2 is a real-time market scanner that monitors up to 120 altcoins simultaneously for pump/dump signals, squeeze setups, and volume anomalies. It uses a multi-layered data pipeline:'),
  bullet('CoinMarketCap API — refreshes token universe every 5 minutes (top 500, filter by market cap & volume)'),
  bullet('Binance REST — enriches each token every 45s: 1m/5m/15m klines, orderbook depth, 24h ticker'),
  bullet('Binance Futures REST — enriches every 30s: funding rate, open interest history (10 x 5m candles)'),
  bullet('Binance WebSocket — receives real-time trade stream for all tokens simultaneously (chunked into 200-sym connections)'),
  bullet('Signal Engine — scores every 5s using 7-factor weighted model, detects pump/dump/squeeze'),
  bullet('FastAPI WebSocket — broadcasts delta updates to connected dashboards with ~50ms batch latency'),
  bullet('SQLite History — saves qualifying signals (score >= 75) and auto-tracks 4h/24h price outcomes'),
  new Paragraph({ spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '' })] }),

  h2('1.2 Scoring Pipeline'),
  para('The 7-factor model produces a 0-100 score for each token every 5 seconds:'),
  new Paragraph({ spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '' })] }),

  new Table({
    width: { size: 14400, type: WidthType.DXA },
    columnWidths: [2400, 1440, 4800, 5760],
    rows: [
      ['Factor', 'Weight', 'Source', 'Description'],
      ['Spot Momentum', '22%', 'Binance REST 15m klines', 'EMA(5/9/21) alignment + RSI(9) + price breakout above 12-candle high + 5m momentum'],
      ['Volume Spike', '18%', 'Binance REST 1m klines', '5-candle recent avg vs 60-candle baseline (1h). Ratio >= 2.5x = score 100'],
      ['Order Book', '13%', 'Binance REST depth', 'Bid/ask volume imbalance ratio. Bullish >= 2.0, Bearish <= 0.5'],
      ['Trade Flow', '12%', 'Binance WebSocket trades', 'Buy ratio from last 50 WS trades + trade frequency boost/penalty'],
      ['Funding Rate', '12%', 'Binance Futures REST', 'FR > +0.1% (crowded longs, bearish) / FR < -0.1% (crowded shorts, bullish)'],
      ['Open Interest', '12%', 'Binance Futures REST', 'OI up + price up = bullish confirmation. OI down + price up = short squeeze signal'],
      ['Liquidation', '11%', 'Derived from OI + price', 'OI drop > 3% + price move > 2%: estimated liquidation event (no allForceOrders call)'],
    ].map((row, i) => {
      const isHeader = i === 0;
      const border = { style: BorderStyle.SINGLE, size: 1, color: C.border };
      const borders = { top: border, bottom: border, left: border, right: border };
      const widths = [2400, 1440, 4800, 5760];
      return new TableRow({
        children: row.map((cell, ci) => new TableCell({
          borders,
          width: { size: widths[ci], type: WidthType.DXA },
          shading: { fill: isHeader ? C.headerBg : '0D1117', type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
          children: [new Paragraph({ children: [new TextRun({ text: cell, size: isHeader ? 18 : 17, bold: isHeader, color: isHeader ? C.yellow : C.white, font: isHeader ? 'Consolas' : 'Arial' })] })],
        })),
      });
    }),
  }),
  new Paragraph({ spacing: { before: 120, after: 80 }, children: [new TextRun({ text: '' })] }),

  h2('1.3 Signal Labels'),
  bullet('PUMP  (score >= 72) — strong bullish momentum, high buy ratio, volume spike'),
  bullet('DUMP  (score <= 28) — strong bearish momentum, low buy ratio, selling pressure'),
  bullet('SHORT_SQUEEZE — FR < -0.1% AND 1h price > +1.5% AND (short liquidation OR OI drop < -2%)'),
  bullet('LONG_SQUEEZE  — FR > +0.1% AND 1h price < -1.5% AND (long  liquidation OR OI drop < -2%)'),
  bullet('NEUTRAL — everything else (28 < score < 72 and no squeeze condition)'),

  h2('1.4 WebSocket Protocol (server → client)'),
  bullet('snapshot  — full token list on first connect'),
  bullet('delta     — only tokens whose key fields changed (MD5 hash: price, score, signal, buy_ratio, pump_detected, dump_detected, short/long_squeeze, volume_spike_pct, momentum_score, trade_flow_score)'),
  bullet('heartbeat — keepalive every 15 seconds'),
  note('Delta latency: ~50ms. Batch window = 50ms. Queue depth = 128 (oldest dropped on overflow).'),

  h2('1.5 Signal History'),
  para('All PUMP/DUMP/SHORT_SQUEEZE/LONG_SQUEEZE signals with score >= 75 are saved to SQLite (data/signal_history.db). A 15-minute per-symbol+signal cooldown prevents duplicate saves. A background task checks every 5 minutes for records >= 3h50m old (4h outcome) and >= 23h50m old (24h outcome) and fetches the current Binance price to compute PnL%.'),

  h2('1.6 Quality Filters (pre-scoring)'),
  bullet('price = 0 → skip'),
  bullet('volume_24h < $500K → skip (low liquidity)'),
  bullet('spread > 0.5% → skip (wide bid/ask)'),
  bullet('|price_change_1h| > 12% → skip (late entry, already pumped)'),

  pageBreak(),
);

// ── 2. Project Structure ──────────────────────────────────────────────────────
children.push(
  h1('2. Project Structure'),
  codeBlock(`crypto-pump-detector-v2/
├── backend/
│   ├── main.py                    # FastAPI app, lifespan, routers
│   ├── config.py                  # All constants and tuning parameters
│   ├── models.py                  # Pydantic response models (TokenSignal, DashboardState)
│   ├── models/
│   │   └── token_state.py         # TokenState dataclass (mutable, locked)
│   ├── routers/
│   │   ├── signals.py             # GET /api/signals, GET /api/status
│   │   ├── ws.py                  # WebSocket /ws/signals
│   │   └── history.py             # GET /api/history, GET /api/history/stats
│   ├── services/
│   │   ├── scanner.py             # Main scan loop: CMC + REST + Futures + WS + scoring
│   │   ├── signal_engine.py       # 7-factor scoring, squeeze detection
│   │   ├── pump_detector.py       # WS-trade based pump/dump detection
│   │   ├── binance_rest.py        # Spot klines, orderbook, ticker enrichment
│   │   ├── binance_futures.py     # Funding rate, OI, liquidation estimation
│   │   ├── binance_ws.py          # Trade stream WebSocket manager
│   │   ├── ws_manager.py          # WS broadcast manager (delta + heartbeat)
│   │   ├── signal_history.py      # SQLite signal log + outcome tracker
│   │   ├── cmc_service.py         # CoinMarketCap token universe
│   │   ├── alert_service.py       # Telegram alert sender
│   │   └── rate_limiter.py        # Token-bucket rate limiter (10 req/s)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── types/index.ts         # All TypeScript interfaces
│       ├── hooks/
│       │   └── useRealtimeSignals.ts  # WS hook (snapshot+delta, rAF batching)
│       └── components/
│           ├── Dashboard.tsx      # Root component, tab switcher (Live/History)
│           ├── TokenTable.tsx     # Live signals table (React.memo, 14-field equality)
│           ├── HistoryTable.tsx   # History tab with stats bar and expandable rows
│           ├── FilterPanel.tsx    # Signal type + score range + search filters
│           ├── SignalBadge.tsx    # Colored PUMP/DUMP/SQUEEZE badges
│           ├── ScoreBar.tsx       # Animated progress bar 0-100
│           └── StatCard.tsx       # Summary stat cards in header
└── data/
    └── signal_history.db          # SQLite database (auto-created)`),
  pageBreak(),
);

// ── 3. Dependencies ───────────────────────────────────────────────────────────
children.push(
  h1('3. Dependencies'),
  h2('3.1 Backend (requirements.txt)'),
  ...fileSection('backend/requirements.txt',
    'Python package dependencies. Key: fastapi + uvicorn (ASGI server), aiohttp (Futures REST), httpx (Spot REST with connection pooling), websockets (Binance WS), pydantic v2 (data validation), numpy (EMA/RSI calculations), aiosqlite (async SQLite for history).'),
  pageBreak(),
);

// ── 4. Backend Source Files ───────────────────────────────────────────────────
children.push(h1('4. Backend Source Files'));

// config.py
children.push(
  h2('4.1 config.py'),
  para('Central configuration file. All constants, thresholds, weights, and intervals are defined here — no magic numbers anywhere else in the codebase. Key design decisions:'),
  bullet('MAX_TOKENS = 120 — limits token universe to stay within 10 req/s rate limit (120 tokens x 5 endpoints = 600 req / 60s cycle)'),
  bullet('CANDLES_1M = 70 — 70 one-minute candles = 1h10m of data. Needed for: 60-candle baseline (1h) + 5-candle recent window + 1 forming candle = 66 minimum. Extra margin for edge cases.'),
  bullet('VOLUME_SPIKE_RECENT_CANDLES = 5 / VOLUME_SPIKE_BASELINE_CANDLES = 60 — non-overlapping windows for volume spike ratio. Recent = last 5 complete candles (~5 min). Baseline = 60 prior candles (1h). Avoids self-referential bias.'),
  bullet('WEIGHTS sum to 1.0 — spot_momentum 0.22, volume_spike 0.18, order_book 0.13, trade_flow 0.12, funding_rate 0.12, open_interest 0.12, liquidation 0.11'),
  bullet('PUMP_SCORE_THRESHOLD = 72 / DUMP_SCORE_THRESHOLD = 28 — asymmetric around 50 to reduce false positives on both sides'),
  ...fileSection('backend/config.py', ''),
  pageBreak(),
);

// main.py
children.push(
  h2('4.2 main.py'),
  para('FastAPI application entry point. Uses asyncio contextmanager lifespan to start/stop background tasks. Starts: scanner loop, WS broadcast manager, Binance WS trade streams, history outcome tracker. Includes CORS for frontend dev. Routes: /api/signals, /api/status, /api/history, /ws/signals.'),
  ...fileSection('backend/main.py', ''),
  pageBreak(),
);

// models.py
children.push(
  h2('4.3 models.py'),
  para('Pydantic v2 response models for API serialization. TokenSignal is the main DTO containing all 40+ fields that flow from TokenState through the API to the frontend. DashboardState wraps a list of TokenSignal with metadata. These are read-only snapshots; the mutable source of truth is TokenState.'),
  ...fileSection('backend/models.py', ''),
  pageBreak(),
);

// models/token_state.py
children.push(
  h2('4.4 models/token_state.py'),
  para('Mutable per-token state object. Each token has exactly one TokenState that is shared between all background tasks. Protected by asyncio.Lock for concurrent read/write. Fields are updated incrementally: WS trades append to recent_trades deque (maxlen=200), REST fields are refreshed every 45s, futures fields every 30s. The Trade NamedTuple represents a single WebSocket trade event.'),
  note('recent_trades is a deque(maxlen=200) — automatically drops oldest trades. Pump detector uses the last 50 trades for buy ratio analysis.'),
  ...fileSection('backend/models/token_state.py', ''),
  pageBreak(),
);

// routers/signals.py
children.push(
  h2('4.5 routers/signals.py'),
  para('REST endpoints for the dashboard. GET /api/signals returns all tracked tokens sorted by score (PUMP first, then DUMP, then rest by score). GET /api/status returns signal counts by type. These endpoints are used as fallback when WebSocket is unavailable; the primary real-time path is /ws/signals.'),
  ...fileSection('backend/routers/signals.py', ''),
  pageBreak(),
);

// routers/ws.py
children.push(
  h2('4.6 routers/ws.py'),
  para('WebSocket endpoint /ws/signals. Accepts query parameters for initial filter state (signal_filter, min_score, max_score, squeeze_only). On connect, sends a full snapshot immediately. Listens for filter-update messages from client. Disconnects are handled gracefully.'),
  ...fileSection('backend/routers/ws.py', ''),
  pageBreak(),
);

// routers/history.py
children.push(
  h2('4.7 routers/history.py'),
  para('REST endpoints for signal history. GET /api/history returns paginated list with filters (signal_type, min_score, has_outcome). GET /api/history/stats returns win-rate and average PnL statistics grouped by signal type. Both delegate to signal_history.py service functions.'),
  ...fileSection('backend/routers/history.py', ''),
  pageBreak(),
);

// services/scanner.py
children.push(
  h2('4.8 services/scanner.py'),
  para('Main orchestration loop. Three independent async cycles run in parallel: (1) CMC refresh every 300s — fetches new token universe, merges into states dict, restarts WS subscriptions on symbol changes. (2) REST enrich every 45s — batches 10 tokens at a time through BinanceRestClient (spot klines + OB + ticker), respects semaphore rate limit. (3) Futures enrich every 30s — same batching pattern for funding rate + OI. (4) Signal task every 5s — scores all tokens, broadcasts delta to WS clients, saves qualifying signals to history.'),
  note('Tokens are processed in REST_CONCURRENCY=10 batches with REST_BATCH_DELAY=1s between batches to maintain exactly 10 req/s.'),
  ...fileSection('backend/services/scanner.py', ''),
  pageBreak(),
);

// services/signal_engine.py
children.push(
  h2('4.9 services/signal_engine.py'),
  para('Core scoring logic. Takes a TokenState and writes all score fields back onto it. Steps: (1) Quality filter — skip tokens with bad spread, zero price, late entry, low volume. (2) Compute 7 factor scores. (3) Apply pump/dump boost (+/-2 integer boost from WS analysis, multiplied by 3.0). (4) Weighted sum to final 0-100 score. (5) Squeeze detection overrides score-based label.'),
  note('Volume spike comment: avg_volume_1m = avg of 60 baseline 1m candles (prior hour). recent_volume = avg of 5 most recent complete 1m candles (~5 min). Ratio >= 2.5x (VOLUME_SPIKE_MULT) maps to score 100.'),
  ...fileSection('backend/services/signal_engine.py', ''),
  pageBreak(),
);

// services/pump_detector.py
children.push(
  h2('4.10 services/pump_detector.py'),
  para('Analyzes recent WebSocket trade data for pump/dump patterns. Uses three metrics from the last N trades: (1) buy_ratio — fraction of buy-side trades (buyer_maker=False). (2) trade_freq — trades per second over a rolling time window. (3) price_trend_pct — price change % from oldest to newest trade in window. Pump = buy_ratio >= 0.70 AND (freq >= 2.0/s OR price rising). Dump = buy_ratio < 0.30 AND (freq >= 2.0/s OR price falling). Returns boolean + reason list for display.'),
  ...fileSection('backend/services/pump_detector.py', ''),
  pageBreak(),
);

// services/binance_rest.py
children.push(
  h2('4.11 services/binance_rest.py'),
  para('Spot market data enrichment via Binance REST API. Fetches 5 endpoints in parallel per token: 1m klines (70 candles), 5m klines (12 candles), 15m klines (30 candles), orderbook depth (20 levels), 24h ticker. Parse helpers extract: volume spike windows (5m recent vs 60m baseline, non-overlapping), EMA(5/9/21) and RSI(9) from 15m klines, breakout flag (close > max of last 12 highs), order book imbalance (bid_vol / ask_vol), best bid/ask, spread %.'),
  note('Volume spike fix: _parse_klines_1m uses non-overlapping slice. recent_vols = volumes[-R-1:-1] (5 candles). baseline_vols = volumes[-R-B-1:-R-1] (60 candles before the recent window). This ensures the baseline is never contaminated by a current pump event.'),
  ...fileSection('backend/services/binance_rest.py', ''),
  pageBreak(),
);

// services/binance_futures.py
children.push(
  h2('4.12 services/binance_futures.py'),
  para('Futures market data enrichment. Loads perpetual USDT pairs from /fapi/v1/exchangeInfo once on startup. For each futures-listed token: fetches lastFundingRate from /fapi/v1/premiumIndex and 10 x 5m OI history from /futures/data/openInterestHist. Estimates liquidation events from OI drop > 3% combined with price direction (avoids allForceOrders endpoint which costs weight=20/call — too expensive for bulk scanning). Score helpers: compute_funding_score, compute_oi_score, compute_liquidation_score map raw values to 0-100 range.'),
  ...fileSection('backend/services/binance_futures.py', ''),
  pageBreak(),
);

// services/binance_ws.py
children.push(
  h2('4.13 services/binance_ws.py'),
  para('Manages Binance trade stream WebSocket connections. Symbols are chunked into groups of WS_MAX_PER_CONN=200, each getting a persistent connection with exponential backoff reconnect (3s → 6s → 12s … → 60s). Each trade message updates TokenState.recent_trades (deque, maxlen=200) and live price. Every 5 trades per symbol, runs early pump/dump detection — if the pump_detected flag flips, pushes an immediate delta to all WS clients (bypassing the 5s scoring cycle for <250ms latency on pump events).'),
  note('Early pump alert architecture: BinanceWSManager.broadcast_manager reference is set by scanner.py. If no clients connected, early detection is skipped entirely to save CPU.'),
  ...fileSection('backend/services/binance_ws.py', ''),
  pageBreak(),
);

// services/ws_manager.py
children.push(
  h2('4.14 services/ws_manager.py'),
  para('Central WebSocket broadcast hub. Singleton (broadcast_manager module-level instance). Per-client state tracks signal_filter, min_score, max_score, squeeze_only preferences. Delta detection: MD5 hash of 11 volatile fields per token — only tokens whose hash changed are queued. Batching: asyncio.Queue (maxsize=128) flushed every 50ms. Fan-out: filtered per client in O(n) before send. Heartbeat loop every 15s to detect dead connections. enqueue_immediate() is the hot path for early pump alerts from BinanceWSManager.'),
  ...fileSection('backend/services/ws_manager.py', ''),
  pageBreak(),
);

// services/signal_history.py
children.push(
  h2('4.15 services/signal_history.py'),
  para('SQLite-based signal history service. Schema has 40+ columns covering all token metrics at signal time. Dedup logic: in-memory dict tracks last save time per symbol+signal — no saves within 15 minutes of the previous one. Outcome tracker: background task running every 5 minutes queries for records ready for 4h/24h outcome (using time-based SQL). Fetches current Binance price via aiohttp and computes PnL%. Query helper get_history() supports filtering by signal type, min score, outcome status with pagination. get_stats() returns win-rate and avg PnL per signal type.'),
  ...fileSection('backend/services/signal_history.py', ''),
  pageBreak(),
);

// services/cmc_service.py
children.push(
  h2('4.16 services/cmc_service.py'),
  para('CoinMarketCap token universe service. Fetches top CMC_TOP_N=500 tokens by market cap, filters by: not a stablecoin (STABLECOINS set), market cap $1M–$500M, listed on Binance spot (USDT pair). Returns up to MAX_TOKENS=120 symbols sorted by market cap descending. Result is cached and refreshed every CMC_REFRESH_SECONDS=300.'),
  ...fileSection('backend/services/cmc_service.py', ''),
  pageBreak(),
);

// services/alert_service.py
children.push(
  h2('4.17 services/alert_service.py'),
  para('Telegram alert service. Sends formatted messages for PUMP/DUMP/SHORT_SQUEEZE/LONG_SQUEEZE signals via Telegram Bot API. Uses httpx for async HTTP. Per-symbol cooldown (ALERT_COOLDOWN_SECONDS=300) prevents alert spam. Message format includes: signal type emoji, symbol, score, price, 1h%, key metrics (buy_ratio, volume_spike_pct, funding rate, OI change), and pump/squeeze reasons.'),
  ...fileSection('backend/services/alert_service.py', ''),
  pageBreak(),
);

// services/rate_limiter.py
children.push(
  h2('4.18 services/rate_limiter.py'),
  para('Token-bucket rate limiter shared across all Binance API requests (spot REST + futures REST). Configured for 10 req/s. Uses asyncio.Lock for thread safety in async context. Each acquire() call waits until a token is available. Prevents Binance 429 rate limit errors from parallel REST enrichment tasks. Both BinanceRestClient and binance_futures.py call _rl_acquire() before each request.'),
  ...fileSection('backend/services/rate_limiter.py', ''),
  pageBreak(),
);

// ── 5. Frontend Source Files ──────────────────────────────────────────────────
children.push(h1('5. Frontend Source Files'));

// types/index.ts
children.push(
  h2('5.1 types/index.ts'),
  para('Central TypeScript type definitions. TokenSignal mirrors the backend Pydantic model exactly. WsMessage is a discriminated union (snapshot | delta | heartbeat). SignalHistory extends TokenSignal with outcome fields. HistoryStats and HistoryStatEntry are for win-rate statistics. FilterState holds the current dashboard filter UI state.'),
  ...fileSection('frontend/src/types/index.ts', ''),
  pageBreak(),
);

// hooks/useRealtimeSignals.ts
children.push(
  h2('5.2 hooks/useRealtimeSignals.ts'),
  para('Primary data hook. Maintains a Map<symbol, TokenSignal> as a ref (no re-render on mutation). On snapshot message: replaces entire map. On delta message: merges only changed tokens into map. State update is batched via requestAnimationFrame (~60fps cap) — avoids flooding React with dozens of state updates per second. Reconnects with exponential backoff (1s → 2s → 4s → ... → 30s). Filters are applied client-side on every flush (not requiring a new WS subscription).'),
  ...fileSection('frontend/src/hooks/useRealtimeSignals.ts', ''),
  pageBreak(),
);

// Dashboard.tsx
children.push(
  h2('5.3 Dashboard.tsx'),
  para('Root React component. Manages: (1) activeTab state ("live" | "history"). (2) Single call to useRealtimeSignals hook for all live data. (3) Stats derived with useMemo to avoid recomputing on every 1s tick. (4) 1s setInterval for "X s ago" display only — does not cause data re-fetches. Live tab shows StatCards + FilterPanel + TokenTable. History tab shows HistoryTable. A WS status indicator dot changes color (yellow=connecting, green=live, red=disconnected).'),
  ...fileSection('frontend/src/components/Dashboard.tsx', ''),
  pageBreak(),
);

// TokenTable.tsx
children.push(
  h2('5.4 TokenTable.tsx'),
  para('High-performance live signals table. Performance techniques: (1) TokenRow wrapped in React.memo with 14-field custom equality — only the row whose data changed re-renders. (2) SectionTable is also memoized. (3) onToggle callback is stable via useCallback. (4) "All Tracked" section capped at DEFAULT_SHOW=50 rows with "Show all" toggle. (5) Style objects are module-level constants (zero GC pressure per render). Sections: BUY Signals | SELL Signals | Squeeze Setups | All Tracked.'),
  ...fileSection('frontend/src/components/TokenTable.tsx', ''),
  pageBreak(),
);

// HistoryTable.tsx
children.push(
  h2('5.5 HistoryTable.tsx'),
  para('Signal history browser. Shows a StatsBar with per-signal-type win rates and avg PnL, a filter toolbar (signal type dropdown, outcome filter, min score, refresh button), and a paginated table. PnlCell component renders PnL% with color coding: green > 2%, light green > 0%, orange between 0 and -2%, red below -2%. Rows are expandable to show 7 sub-scores and signal reasons. Data is fetched via REST (not WebSocket) since history does not need real-time updates.'),
  ...fileSection('frontend/src/components/HistoryTable.tsx', ''),
  pageBreak(),
);

// FilterPanel.tsx
children.push(
  h2('5.6 FilterPanel.tsx'),
  para('Dashboard filter controls for the Live tab. Provides signal type filter tabs (All / BUY / SELL / Short Sqz / Long Sqz / All Squeeze), symbol search input, and score range min/max inputs. All filters are applied client-side in the useRealtimeSignals hook via applyFilters(). The "squeeze" tab sets squeezeOnly=true which filters by short_squeeze OR long_squeeze fields (not by signal label, since squeeze tokens can have any score).'),
  ...fileSection('frontend/src/components/FilterPanel.tsx', ''),
  pageBreak(),
);

// SignalBadge.tsx
children.push(
  h2('5.7 SignalBadge.tsx'),
  para('Small colored badge component mapping signal types to display labels: PUMP="BUY" (green), DUMP="SELL" (red), NEUTRAL="IGNORE" (blue), SHORT_SQUEEZE="⚡ SHORT SQZ" (dark green), LONG_SQUEEZE="🔥 LONG SQZ" (dark red). Used in both TokenTable and HistoryTable.'),
  ...fileSection('frontend/src/components/SignalBadge.tsx', ''),
  pageBreak(),
);

// ScoreBar.tsx
children.push(
  h2('5.8 ScoreBar.tsx'),
  para('Animated score bar. Maps 0-100 float to a colored progress bar + label. Score >= 72 shows green "+N" label (PUMP range). Score <= 28 shows red "-N" label (distance from 100, so "-72" means score=28). Neutral shows yellow score number. Bar width transitions smoothly (CSS transition: width 0.5s) for real-time updates.'),
  ...fileSection('frontend/src/components/ScoreBar.tsx', ''),
  pageBreak(),
);

// StatCard.tsx
children.push(
  h2('5.9 StatCard.tsx'),
  para('Simple stat card used in the Dashboard header grid. Accepts label, value, optional sub-label, and color variant (green/red/yellow/blue/purple/default). Used for: tracking count, BUY signals count, SELL signals count, pump active count, squeeze count, avg buy ratio, last updated time.'),
  ...fileSection('frontend/src/components/StatCard.tsx', ''),
  pageBreak(),
);

// ── 6. Key Algorithms ─────────────────────────────────────────────────────────
children.push(
  h1('6. Key Algorithms & Design Notes'),

  h2('6.1 Volume Spike Algorithm'),
  para('The volume spike detector was redesigned to fix three bugs in the original implementation:'),
  bullet('BUG 1 (self-referential): Original used volumes[:-1] as baseline which included the recent candles themselves. A pump already underway elevated its own baseline.'),
  bullet('BUG 2 (too short): Original used only 24 candles (24 min baseline). Too short — a 20-minute pump already elevated the average.'),
  bullet('BUG 3 (single-candle noise): Original compared a single recent candle. Noisy due to random volume spikes in individual minutes.'),
  bullet('FIX: CANDLES_1M increased from 25 to 70. Non-overlapping slices: recent=volumes[-6:-1] (5 candles), baseline=volumes[-66:-6] (60 candles). The 5-candle recent window averages out noise. The 60-candle baseline represents a full hour of normal activity and can never be contaminated by the current pump.'),

  h2('6.2 EMA / RSI Calculation'),
  para('Computed from 15m klines (30 candles) using numpy for performance. EMA uses standard formula with k=2/(period+1). RSI(9) uses simple average of gains and losses from last 9 delta values (not Wilder smoothing). Breakout flag is true when latest close > max high of prior 12 candles. These three indicators feed into the spot_momentum_score (22% weight).'),

  h2('6.3 Funding Rate Score'),
  para('Funding rate is clamped to [-0.3%, +0.3%] range then linearly mapped: FR=+0.3% maps to score=0 (extremely bearish, crowded longs will be liquidated), FR=-0.3% maps to score=100 (extremely bullish, crowded shorts getting squeezed), FR=0 maps to score=50 (neutral).'),

  h2('6.4 OI Score Matrix'),
  para('4-quadrant classification: (OI up + price up) = 80 (new longs entering, bullish). (OI up + price down) = 25 (new shorts entering, bearish). (OI down + price up) = 90 (short liquidations = short squeeze). (OI down + price down) = 10 (long liquidations = panic). OI flat = 50.'),

  h2('6.5 Delta Detection Hash'),
  para('MD5 of 11 concatenated fields: price (8 decimal), score (1 decimal), signal, buy_ratio (3 decimal), pump_detected, dump_detected, short_squeeze, long_squeeze, volume_spike_pct (1 decimal), spot_momentum_score (1 decimal), trade_flow_score (1 decimal). Only first 8 hex chars used (good enough for change detection, 1-in-16M collision probability). Timestamp is intentionally excluded — only substantive changes trigger a broadcast.'),

  h2('6.6 Rate Limiting'),
  para('Token bucket: capacity=10, refill_rate=10/s. Each API call calls acquire() which async-waits if bucket is empty. This applies globally to all Binance requests (spot REST + futures REST combined). With 120 tokens x 5 spot endpoints = 600 req, and 120 x 3 futures endpoints = 360 req per cycle, the total throughput is approximately 10 req/s, meaning a full cycle takes ~60s for spot and ~36s for futures.'),

  pageBreak(),

  h1('7. Configuration Reference'),
  codeBlock(`SIGNAL THRESHOLDS
  PUMP_SCORE_THRESHOLD     = 72      # score >= 72 → PUMP signal
  DUMP_SCORE_THRESHOLD     = 28      # score <= 28 → DUMP signal
  PRICE_SKIP_THRESHOLD     = 0.12    # skip if |1h change| > 12% (late entry)
  SPREAD_MAX_PCT           = 0.5     # skip if bid/ask spread > 0.5%
  MIN_VOLUME_24H           = 500_000 # skip if 24h volume < $500K

SCORING WEIGHTS (sum = 1.0)
  spot_momentum  0.22   volume_spike  0.18   order_book   0.13
  trade_flow     0.12   funding_rate  0.12   open_interest 0.12
  liquidation    0.11

PUMP DETECTOR (WS trades)
  PUMP_BUY_RATIO           = 0.70    # >= 70% buys → pump signal
  PUMP_FREQ_WINDOW_SECS    = 30.0    # trade frequency window
  VOLUME_SPIKE_MULT        = 2.5     # vol ratio >= 2.5x → score 100

SQUEEZE DETECTION
  SQUEEZE_PRICE_MOVE_PCT   = 1.5     # 1h price move threshold
  SQUEEZE_OI_DROP_PCT      = -2.0    # OI drop threshold
  FUNDING_BULLISH_THRESHOLD= -0.001  # FR < -0.1% → bullish (short squeeze)
  FUNDING_BEARISH_THRESHOLD=  0.001  # FR > +0.1% → bearish (long squeeze)

TASK INTERVALS (seconds)
  CMC_REFRESH_SECONDS      = 300     # token universe refresh
  REST_ENRICH_SECONDS      = 45      # spot REST cycle
  FUTURES_ENRICH_SECONDS   = 30      # futures REST cycle
  SIGNAL_SCORE_SECONDS     = 5       # scoring + WS broadcast cycle

WS BROADCAST
  BATCH_MS                 = 50      # flush queue every 50ms
  HEARTBEAT_S              = 15      # keepalive interval
  QUEUE_MAX                = 1024    # merge-on-overflow (was 128, drop-oldest)

HISTORY
  SAVE_COOLDOWN            = 900     # 15 min per symbol+signal dedup
  SCORE_THRESHOLD          = 60.0    # minimum score to save (was 75 — survivorship bias)
  VALID_SIGNALS            = PUMP, DUMP, SHORT_SQUEEZE, LONG_SQUEEZE

TOKEN UNIVERSE
  MIDCAP_MIN_USD           = 1_000_000    # $1M minimum market cap
  MIDCAP_MAX_USD           = 500_000_000  # $500M maximum market cap
  CMC_TOP_N                = 500          # fetch top 500 from CMC
  MAX_TOKENS               = 120          # limit final list`),
);

// ── 8. Audit Findings & Fixes ─────────────────────────────────────────────────
children.push(
  h1('8. Audit Findings & Fixes'),
  para('The following issues were identified during code audit and fixed in this version. All changes are reflected in the source code sections above.', { color: C.muted }),

  // ── 8.1 Volume Spike threshold ───────────────────────────────────────────
  h2('8.1 VOLUME_SPIKE_MULT: 2.5 → 5.0  [FIXED]'),
  para('Severity: High  |  Files: config.py, services/signal_engine.py'),

  new Table({
    width: { size: 14400, type: WidthType.DXA },
    columnWidths: [2400, 5700, 6300],
    rows: [
      ['', 'Before', 'After'],
      ['Threshold', 'ratio >= 2.5x → score 100', 'ratio >= 5.0x → score 100'],
      ['1.0x volume', 'score = 50 (neutral!)', 'score ≈ 30 (below avg, penalised)'],
      ['1.5x volume', 'score = 62.5', 'score = 45 (near-neutral)'],
      ['2.0x volume', 'score = 75', 'score = 55 (slightly elevated)'],
      ['3.0x volume', 'score = 100', 'score = 75 (warning zone)'],
      ['5.0x volume', 'score = 100 (same)', 'score = 100 (real pump)'],
    ].map((row, i) => {
      const isH = i === 0;
      const b = { style: BorderStyle.SINGLE, size: 1, color: C.border };
      const borders = { top: b, bottom: b, left: b, right: b };
      const ws = [2400, 5700, 6300];
      return new TableRow({ children: row.map((cell, ci) => new TableCell({
        borders, width: { size: ws[ci], type: WidthType.DXA },
        shading: { fill: isH ? C.headerBg : (i % 2 === 0 ? '0D1117' : '111820'), type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: [new TextRun({ text: cell, size: isH ? 18 : 17, bold: isH, color: isH ? C.yellow : (ci === 1 ? C.red : (ci === 2 ? C.green : C.white)), font: 'Consolas' })] })],
      })) });
    }),
  }),
  new Paragraph({ spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '' })] }),
  para('Root cause: At 2.5x threshold, any coin with routine volume spike (lunch-time, news) scored 100 on this factor. With weight=18%, even a 1.5x volume bump added ~11 points to final score — significant noise. The new 5-tier curve penalises below-average volume and only rewards clear anomalies.'),
  hr(),

  // ── 8.2 recent_trades maxlen ─────────────────────────────────────────────
  h2('8.2 recent_trades maxlen: 200 → 500  [FIXED]'),
  para('Severity: Medium  |  File: models/token_state.py'),
  para('Problem: For high-frequency coins (PEPE, BNB, SOL), 200 trades can represent only 3–5 seconds of data at 40–60 trades/second. The pump detector uses a 30-second frequency window (PUMP_FREQ_WINDOW_SECS=30) and acceleration detection uses a 30-second lookback. With maxlen=200, those time windows may have no data at all, making the detector blind.'),
  note('At 10 trades/s (typical mid-cap): 500 trades = 50 seconds of context. At 40 trades/s (high-cap): 500 trades = 12.5 seconds — still limited. Consider making deque size dynamic or time-based for very high-freq tokens in a future version.'),
  hr(),

  // ── 8.3 Volume-weighted buy ratio ────────────────────────────────────────
  h2('8.3 Buy Ratio: Count-based → Volume-weighted  [FIXED]'),
  para('Severity: High  |  File: services/pump_detector.py'),
  para('Problem: The original compute_buy_ratio() counted trades (1 small trade = 1 large trade in weight). A bot placing 40 micro $5 buy orders could push buy_ratio to 0.80 while actual buy volume might be only $200 vs $10,000 sell volume. This made the pump detector trivially fakeable.'),
  codeBlock(`# BEFORE — count-based (bot-friendly)
buys = sum(1 for t in recent if not t.is_buyer_maker)
return buys / len(recent)

# AFTER — volume-weighted USD (whale-sensitive)
meaningful = [t for t in trades if t.qty * t.price >= MIN_TRADE_USDT][-window:]
buy_vol  = sum(t.qty * t.price for t in meaningful if not t.is_buyer_maker)
sell_vol = sum(t.qty * t.price for t in meaningful if t.is_buyer_maker)
return buy_vol / (buy_vol + sell_vol) if (buy_vol + sell_vol) > 0 else 0.5`),
  para('Also added: MIN_TRADE_USDT=10.0 filter removes micro trades from analysis. A $5 bot trade is ignored; only real market participants counted.'),
  hr(),

  // ── 8.4 Whale detection ───────────────────────────────────────────────────
  h2('8.4 Whale Detection  [NEW]'),
  para('Severity: Enhancement  |  File: services/pump_detector.py'),
  para('New functions: detect_whale_buy() / detect_whale_sell(). A single trade >= WHALE_BUY_USDT=$10,000 in the last 50 trades is flagged as a whale event. Effects: (1) Whale buy relaxes the buy_ratio threshold by 0.05 — smart money entering is a stronger signal than retail buy count. (2) When organic_volume=False (bot pattern detected), a whale buy is REQUIRED to confirm pump — bot spam alone is not enough. (3) Whale reason appears in signal reasons list on the dashboard.'),
  hr(),

  // ── 8.5 Trade acceleration ────────────────────────────────────────────────
  h2('8.5 Trade Acceleration Detection  [NEW]'),
  para('Severity: Enhancement  |  File: services/pump_detector.py'),
  para('compute_trade_acceleration() computes: trades/s in last 10s ÷ trades/s in prior 10–30s. Ratio >= TRADE_ACCEL_RATIO=3.0 means trade frequency tripled — a burst/spike. This substitutes for freq_ok in the pump detection gate, meaning a sudden trade acceleration (even if base frequency was low) can trigger the detector. Acceleration is more reliable than absolute frequency because it is relative to the token\'s own baseline.'),
  hr(),

  // ── 8.6 Organic volume check ──────────────────────────────────────────────
  h2('8.6 Bot Pattern Detection (Organic Volume Check)  [NEW]'),
  para('Severity: Enhancement  |  File: services/pump_detector.py'),
  para('is_organic_volume() computes the Coefficient of Variation (CV = std_dev / mean) of buy trade quantities. Bot farms typically place orders of identical or near-identical size (low variance). Real organic buying has high variance — small retail buys mixed with larger buys. If CV < 0.3, the volume pattern is flagged as suspicious. When bot_pattern is detected, the pump confirmation requires BOTH the normal conditions AND a whale_buy. This prevents bot-orchestrated wash trading from triggering pump signals.'),
  codeBlock(`# CV < 0.3 = suspiciously uniform = likely bot
variance = sum((q - mean)**2 for q in qtys) / len(qtys)
cv = variance**0.5 / mean
return cv > 0.3  # True = organic, False = bot-like`),
  hr(),

  // ── 8.7 Funding rate context ──────────────────────────────────────────────
  h2('8.7 Funding Rate: Naive → Context-Aware  [FIXED]'),
  para('Severity: High  |  File: services/binance_futures.py'),
  para('Problem: The original formula treated any positive funding rate as bearish (score < 50). This is wrong during real pumps: when a token pumps strongly, futures traders rush to open leveraged longs, which pushes FR positive. The old formula would actually penalise tokens that are actively pumping.'),

  new Table({
    width: { size: 14400, type: WidthType.DXA },
    columnWidths: [3600, 3600, 3600, 3600],
    rows: [
      ['Scenario', 'FR value', 'Old score', 'New score'],
      ['Strong pump (price +3%, FR +0.15%)', 'FR = +0.0015', '~33 (bearish!)', '~60 (confirmation)'],
      ['FR high + price flat', 'FR = +0.0015', '~33', '~33 (correctly bearish)'],
      ['Short squeeze setup (FR -0.2%)', 'FR = -0.002', '~83', '~83 (unchanged)'],
      ['Neutral FR', 'FR ≈ 0', '50', '50 (unchanged)'],
    ].map((row, i) => {
      const isH = i === 0;
      const b = { style: BorderStyle.SINGLE, size: 1, color: C.border };
      const borders = { top: b, bottom: b, left: b, right: b };
      const ws = [3600, 3600, 3600, 3600];
      return new TableRow({ children: row.map((cell, ci) => new TableCell({
        borders, width: { size: ws[ci], type: WidthType.DXA },
        shading: { fill: isH ? C.headerBg : '0D1117', type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: [new TextRun({
          text: cell, size: isH ? 18 : 17, bold: isH,
          color: isH ? C.yellow : (ci === 2 ? C.red : ci === 3 ? C.green : C.white),
          font: 'Consolas',
        })] })],
      })) });
    }),
  }),
  new Paragraph({ spacing: { before: 80, after: 80 }, children: [new TextRun({ text: '' })] }),
  hr(),

  // ── 8.8 Queue overflow ────────────────────────────────────────────────────
  h2('8.8 WS Queue Overflow: Drop-oldest → Merge  [FIXED]'),
  para('Severity: Medium  |  File: services/ws_manager.py'),
  para('Problem: QUEUE_MAX=128 with drop-oldest strategy meant that during a market-wide event (all 120 tokens changing simultaneously across multiple scoring passes), the oldest updates were silently discarded. Clients could miss signal transitions.'),
  para('Fix: QUEUE_MAX raised to 1024. On overflow, the entire queue is drained, all updates are merged symbol-by-symbol (newest value per symbol wins), and re-queued as a single consolidated entry. Result: zero signal loss at the cost of a single merge operation. This is O(n_queue × n_tokens) on overflow — acceptable given overflow is rare.'),
  codeBlock(`# BEFORE — drop oldest (signal loss)
if self._queue.full():
    self._queue.get_nowait()  # discard
self._queue.put_nowait(entry)

# AFTER — merge on overflow (zero loss)
if self._queue.full():
    merged = {}
    while not self._queue.empty():
        old_updates, _ = self._queue.get_nowait()
        for u in old_updates: merged[u["symbol"]] = u
    for u in changed: merged[u["symbol"]] = u  # new wins
    self._queue.put_nowait((list(merged.values()), meta))
    return
self._queue.put_nowait(entry)`),
  hr(),

  // ── 8.9 Survivorship bias ─────────────────────────────────────────────────
  h2('8.9 Signal History Survivorship Bias: threshold 75 → 60  [FIXED]'),
  para('Severity: Medium  |  File: services/signal_history.py'),
  para('Problem: Only saving score >= 75 means the history dataset is biased. You cannot answer: "Would score 65 tokens have been profitable?" You cannot optimise the threshold without data below the threshold. Stats computed from this dataset overestimate model performance.'),
  para('Fix: SCORE_THRESHOLD lowered to 60. Records are tagged with score_tier (HIGH=≥80, MED=70–79, LOW=60–69). The get_stats() API now returns a tier breakdown, allowing comparison of win-rate by tier. Existing databases are automatically migrated via ALTER TABLE (non-destructive).'),

  new Table({
    width: { size: 10800, type: WidthType.DXA },
    columnWidths: [2700, 2700, 2700, 2700],
    rows: [
      ['Tier', 'Score range', 'Expected volume', 'Purpose'],
      ['HIGH', '>= 80', 'Low (strong signals)', 'High-confidence signals'],
      ['MED',  '70–79', 'Medium',               'Mid-quality, compare to HIGH'],
      ['LOW',  '60–69', 'High (more noise)',     'Baseline — see if threshold matters'],
    ].map((row, i) => {
      const isH = i === 0;
      const colors = ['', C.green, C.yellow, C.muted];
      const b = { style: BorderStyle.SINGLE, size: 1, color: C.border };
      const borders = { top: b, bottom: b, left: b, right: b };
      return new TableRow({ children: row.map((cell, ci) => new TableCell({
        borders, width: { size: 2700, type: WidthType.DXA },
        shading: { fill: isH ? C.headerBg : '0D1117', type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: [new TextRun({
          text: cell, size: isH ? 18 : 17, bold: isH || ci === 0,
          color: isH ? C.yellow : (ci === 0 && !isH ? colors[i] : C.white),
          font: 'Consolas',
        })] })],
      })) });
    }),
  }),
  new Paragraph({ spacing: { before: 120, after: 80 }, children: [new TextRun({ text: '' })] }),

  // Summary table
  h2('8.10 Summary of All Changes'),
  new Table({
    width: { size: 14400, type: WidthType.DXA },
    columnWidths: [3200, 2200, 4200, 4800],
    rows: [
      ['File', 'Severity', 'Issue', 'Fix'],
      ['config.py', 'HIGH', 'VOLUME_SPIKE_MULT=2.5 too low → noise', '5-tier curve, threshold raised to 5.0x'],
      ['signal_engine.py', 'HIGH', 'Flat scoring: 1x vol = 50 score', 'New curve: <1.5x penalised, >5x = 100'],
      ['signal_engine.py', 'HIGH', 'FR score ignores price direction', 'Pass price_change_1h to funding scorer'],
      ['pump_detector.py', 'HIGH', 'Count-based buy_ratio → bot-fakeable', 'Volume-weighted USD ratio + $10 min filter'],
      ['pump_detector.py', 'MED', 'No whale detection', 'detect_whale_buy/sell >= $10K'],
      ['pump_detector.py', 'MED', 'No acceleration detection', 'compute_trade_acceleration(): 10s vs 30s'],
      ['pump_detector.py', 'MED', 'No bot pattern detection', 'is_organic_volume(): CV < 0.3 = suspect'],
      ['binance_futures.py', 'HIGH', 'FR+ always bearish → misses real pumps', 'FR+ + price rising = 55–70 (confirmation)'],
      ['ws_manager.py', 'MED', 'Queue overflow → signal loss', 'QUEUE_MAX 128→1024, merge-on-overflow'],
      ['models/token_state.py', 'MED', 'recent_trades maxlen=200 (few secs)', 'Raised to 500 → 50s context @ 10t/s'],
      ['signal_history.py', 'MED', 'SCORE_THRESHOLD=75 → survivorship bias', 'Lowered to 60, added score_tier column'],
    ].map((row, i) => {
      const isH = i === 0;
      const sevColor = row[1] === 'HIGH' ? C.red : row[1] === 'MED' ? C.yellow : C.muted;
      const b = { style: BorderStyle.SINGLE, size: 1, color: C.border };
      const borders = { top: b, bottom: b, left: b, right: b };
      const ws = [3200, 2200, 4200, 4800];
      return new TableRow({ children: row.map((cell, ci) => new TableCell({
        borders, width: { size: ws[ci], type: WidthType.DXA },
        shading: { fill: isH ? C.headerBg : (i % 2 === 0 ? '0D1117' : '0a0f18'), type: ShadingType.CLEAR },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ children: [new TextRun({
          text: cell, size: isH ? 18 : 16, bold: isH,
          color: isH ? C.yellow : (ci === 1 && !isH ? sevColor : C.white),
          font: ci === 0 ? 'Consolas' : 'Arial',
        })] })],
      })) });
    }),
  }),
  pageBreak(),
);

// ── Build & write ─────────────────────────────────────────────────────────────

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Arial', size: 20, color: C.white } },
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Consolas', color: C.white },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Consolas', color: C.accent },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Consolas', color: C.yellow },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 480, hanging: 240 } }, run: { font: 'Arial' } },
      }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 16838, height: 11906, orientation: PageOrientation.LANDSCAPE },
        margin: { top: 720, right: 720, bottom: 720, left: 720 },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`\nDOCX written: ${OUT}`);
  console.log(`Size: ${(buf.length / 1024).toFixed(1)} KB`);
}).catch(err => {
  console.error('ERROR:', err);
  process.exit(1);
});
