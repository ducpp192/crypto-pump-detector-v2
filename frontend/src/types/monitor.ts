export type FlowDirection = "INFLOW" | "OUTFLOW" | "NEUTRAL";

export type SmartSignal =
  | "ABNORMAL_VOLUME"
  | "SHORT_SQUEEZE_LIKELY"
  | "LONG_SQUEEZE_LIKELY"
  | "LEVERAGE_BUILDUP"
  | "SPOT_LED_RALLY"
  | "FUTURES_LED_RALLY"
  | "LOW_CAP_SPECULATION"
  | "HIGH_OI_RATIO";

export interface MonitorToken {
  symbol: string;
  name: string;
  price: number;
  market_cap: number;
  volume_24h: number;

  price_change_5m: number;
  price_change_15m: number;
  price_change_1h: number;
  price_change_24h: number;

  flow_score_5m: number;
  flow_score_15m: number;
  flow_score_1h: number;
  flow_score_1d: number;
  flow_direction: FlowDirection;

  volume_delta: number;
  oi_delta: number;
  price_momentum: number;
  funding_divergence: number;
  liquidation_pressure: number;
  relative_volume: number;

  funding_rate: number | null;
  oi_usd: number | null;
  oi_change_5m: number | null;
  oi_change_15m: number | null;
  oi_trend: string;
  oi_spike: boolean;
  oi_market_cap_ratio: number | null;
  has_futures: boolean;

  buy_ratio: number;
  volume_spike_pct: number;
  trade_freq: number;

  crime_score: number;
  crime_level: string;

  smart_signals: SmartSignal[];
  last_updated: number;
}

export interface MonitorFilters {
  minScore: number;
  maxScore: number;
  direction: "all" | "INFLOW" | "OUTFLOW" | "NEUTRAL";
  signal: string;
  searchQuery: string;
  timeframe: "5m" | "15m" | "1h" | "1d";
  hasFutures: "all" | "yes" | "no";
}
