export type SignalType = "PUMP" | "DUMP" | "NEUTRAL" | "SHORT_SQUEEZE" | "LONG_SQUEEZE";
export type OISignalType = "SHORT_SQUEEZE" | "LONG_LIQ" | "TRAP" | "DIVERGENCE";
export type OITrend = "UP" | "DOWN" | "SIDEWAYS";
export type FRDivergence = "LONG_DANGER" | "SHORT_DANGER";

// ── WebSocket message types ───────────────────────────────────────────────────

export interface WsMeta {
  total_scanned: number;
  last_updated: string;
  alerts_triggered: number;
}

export type WsMessage =
  | { type: "snapshot"; signals: TokenSignal[]; meta: WsMeta }
  | { type: "delta";    updates: TokenSignal[]; meta: WsMeta }
  | { type: "heartbeat"; ts: number };

export type WsStatus = "connecting" | "connected" | "disconnected";

export interface TokenSignal {
  symbol: string;
  name: string;
  price: number;
  price_change_1h: number;
  price_change_24h: number;
  market_cap: number;
  volume_24h: number;

  spot_momentum_score: number;
  volume_spike_score: number;
  order_book_score: number;
  trade_flow_score: number;
  funding_rate_score: number;
  open_interest_score: number;
  liquidation_score: number;

  score: number;
  signal: SignalType;

  // Derivatives (base)
  funding_rate: number | null;
  oi_change_pct: number | null;    // 5m % change (back-compat)
  oi_usd: number | null;
  volume_spike_pct: number;

  short_squeeze: boolean;
  long_squeeze: boolean;
  liquidation_detected: boolean;
  liquidation_side: "long" | "short" | null;

  // ── OI Enhanced Metrics ───────────────────────────────────────────
  oi_change_1m:  number | null;
  oi_change_5m:  number | null;
  oi_change_15m: number | null;
  oi_trend:      OITrend;
  oi_spike:      boolean;
  oi_spike_score: number;          // 0–100
  oi_market_cap_ratio: number | null;

  /** Mảng oi_usd 30 điểm gần nhất để render sparkline */
  oi_sparkline: number[];

  /** OI manipulation pattern detected by oi_tracker */
  oi_signal_type:       OISignalType | null;
  oi_signal_confidence: number;    // 0–100

  /** Funding-rate vs price divergence */
  oi_fr_divergence: FRDivergence | null;

  // ── Crime Coin Score ──────────────────────────────────────────────
  crime_score:      number;   // 0–100
  crime_level:      "NORMAL" | "WARNING" | "SUSPICIOUS" | "CRIME_COIN" | "MM_ACTIVE";
  crime_signals:    string[];
  crime_oi_mc:      number;   // 0–20
  crime_funding:    number;   // 0–15
  crime_oi_change:  number;   // 0–15
  crime_divergence: number;   // 0–15
  crime_flow:       number;   // 0–10
  crime_liquidity:  number;   // 0–10
  crime_exchange:   number;   // 0–10
  crime_volatility: number;   // 0–5

  // WS live metrics
  buy_ratio: number;
  trade_freq: number;
  price_trend_10s: number;
  pump_detected: boolean;
  dump_detected: boolean;
  boost: number;
  reasons: string[];

  timestamp: string;
}

export interface DashboardResponse {
  signals: TokenSignal[];
  last_updated: string;
  total_scanned: number;
  alerts_triggered: number;
}

export interface StatusResponse {
  last_updated: string;
  total_scanned: number;
  signal_counts: {
    PUMP: number;
    DUMP: number;
    SHORT_SQUEEZE: number;
    LONG_SQUEEZE: number;
    NEUTRAL: number;
  };
}

// ── Signal History ────────────────────────────────────────────────────────────

export interface SignalHistory {
  id: number;
  saved_at: string;
  symbol: string;
  name: string;
  price: number;
  price_change_1h: number;
  price_change_24h: number;
  market_cap: number;
  volume_24h: number;
  volume_spike_pct: number;
  spot_momentum_score: number;
  volume_spike_score: number;
  order_book_score: number;
  trade_flow_score: number;
  funding_rate_score: number;
  open_interest_score: number;
  liquidation_score: number;
  score: number;
  signal: SignalType;
  funding_rate: number | null;
  oi_change_pct: number | null;
  oi_usd: number | null;
  short_squeeze: number;       // SQLite 0/1
  long_squeeze: number;
  liquidation_detected: number;
  liquidation_side: string | null;
  buy_ratio: number;
  trade_freq: number;
  price_trend_10s: number;
  pump_detected: number;
  dump_detected: number;
  boost: number;
  reasons: string[];
  // Outcome
  price_4h: number | null;
  price_24h: number | null;
  pnl_4h_pct: number | null;
  pnl_24h_pct: number | null;
  outcome_4h_at: string | null;
  outcome_24h_at: string | null;
}

export interface HistoryStatEntry {
  total: number;
  checked_4h: number;
  checked_24h: number;
  avg_pnl_4h: number | null;
  avg_pnl_24h: number | null;
  win_4h: number;
  win_24h: number;
  win_rate_4h: number | null;
  win_rate_24h: number | null;
}

export interface HistoryStats {
  PUMP?: HistoryStatEntry;
  DUMP?: HistoryStatEntry;
  SHORT_SQUEEZE?: HistoryStatEntry;
  LONG_SQUEEZE?: HistoryStatEntry;
}

export interface FilterState {
  minScore: number;
  maxScore: number;
  signalType: string;
  squeezeOnly: boolean;
  searchQuery: string;
  // OI-specific quick filters
  oiSpike:       boolean;  // only show tokens with oi_spike = true
  highOiRatio:   boolean;  // only show oi_market_cap_ratio > 0.3
  oiSignal:      string;   // "all" | "SHORT_SQUEEZE" | "LONG_LIQ" | "TRAP" | "DIVERGENCE"
}

// ── Dòng Tiền (Money Flow Scanner) ───────────────────────────────────────────

export type DongTienSignalType = "ACCUMULATION" | "SQUEEZE_SETUP" | "BREAKOUT_READY" | "WATCH";

export interface DongTienAlert {
  symbol: string;
  name: string;
  price: number;
  price_change_1h: number;
  market_cap: number;

  // Absolute price delta (dollars, not %)
  price_delta_5m:  number;
  price_delta_15m: number;
  price_delta_1h:  number;

  fund_inflow_usd: number;
  fund_outflow_usd: number;
  fund_net_usd: number;
  flow_ratio_pct: number;
  flow_consistency_pct: number;

  big_holder_long_ratio: number;
  big_holder_short_ratio: number;
  retail_long_ratio: number;
  retail_short_ratio: number;
  squeeze_setup: boolean;

  funding_rate: number | null;

  score: number;
  flow_ratio_score: number;
  consistency_score: number;
  smart_money_score: number;
  squeeze_score: number;
  funding_score: number;
  price_quiet_score: number;

  signal_type: DongTienSignalType;
  alert_reasons: string[];
  timestamp: string;
}

export interface DongTienMeta {
  total: number;
  last_updated: string | null;
  data_sources: string[];
  coinank_available: boolean;
  cache_fresh?: boolean;
  error?: string;
}

export interface DongTienResponse {
  alerts: DongTienAlert[];
  meta: DongTienMeta;
}
