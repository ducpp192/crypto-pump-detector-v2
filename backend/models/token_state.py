"""
TokenState — unified per-token container for all data sources.

Sources:
  CMC   → market_cap, volume_24h
  REST  → price history, klines, orderbook, funding rate, OI
  WS    → live trades (real-time)
  ENGINE→ score, signal, squeeze flags
  OI    → oi_history, oi_change_*, oi_trend, oi_spike, oi_signal_*
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, NamedTuple, Optional


class Trade(NamedTuple):
    """Single exchange trade from WebSocket stream.

    is_buyer_maker=True  → seller was aggressor (sell trade)
    is_buyer_maker=False → buyer was aggressor (buy trade)
    """
    price: float
    qty: float
    is_buyer_maker: bool
    timestamp: float


class OISnapshot(NamedTuple):
    """Single OI data point stored in the rolling history deque."""
    timestamp: float        # Unix seconds
    oi_usd: float           # Open interest in USD
    source: str             # "binance" | "bybit"


@dataclass
class TokenState:
    """All runtime data for a single tracked token."""

    # ── Identity / CMC ────────────────────────────────────────────────
    symbol: str
    name: str = ""
    market_cap: float = 0.0
    volume_24h: float = 0.0

    # ── Price (REST + WS) ─────────────────────────────────────────────
    price: float = 0.0
    price_1m_ago: float = 0.0
    price_5m_ago: float = 0.0
    price_15m_ago: float = 0.0
    price_1h_ago: float = 0.0
    price_change_24h_pct: float = 0.0

    # ── Range / kline metrics (REST) ──────────────────────────────────
    high_20: float = 0.0
    low_20: float = 0.0
    avg_volume_1m: float = 0.0
    recent_volume: float = 0.0
    momentum_1m: float = 0.0
    momentum_5m: float = 0.0

    # ── Orderbook (REST) ──────────────────────────────────────────────
    imbalance: float = 1.0       # bid_vol / ask_vol
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread_pct: float = 0.0

    # ── Live trades (WS) ──────────────────────────────────────────────
    recent_trades: Deque[Trade] = field(
        default_factory=lambda: deque(maxlen=500)
    )

    # ── Derivatives (REST - Futures) ──────────────────────────────────
    has_futures: bool = False
    funding_rate: Optional[float] = None     # e.g. 0.0012
    oi_usd: Optional[float] = None
    oi_change_pct: Optional[float] = None   # 5m change (back-compat)
    liquidation_detected: bool = False
    liquidation_side: Optional[str] = None   # "long" | "short"

    # ── OI History & rolling analytics ───────────────────────────────
    # Stores up to 200 snapshots (200 × 30s = ~100 min of history)
    oi_history: Deque[OISnapshot] = field(
        default_factory=lambda: deque(maxlen=200)
    )
    # Funding rate history: (timestamp, rate) — used for divergence detection
    funding_history: Deque[tuple] = field(
        default_factory=lambda: deque(maxlen=50)
    )

    # Computed OI metrics (updated by oi_tracker.compute_oi_metrics)
    oi_change_1m:  Optional[float] = None
    oi_change_5m:  Optional[float] = None
    oi_change_15m: Optional[float] = None
    oi_trend:      str = "SIDEWAYS"          # "UP" | "DOWN" | "SIDEWAYS"
    oi_spike:      bool = False
    oi_spike_score: int = 0                  # 0–100

    # OI / Market-cap ratio
    oi_market_cap_ratio: Optional[float] = None

    # OI manipulation signals (set by oi_tracker)
    oi_signal_type:       Optional[str] = None  # SHORT_SQUEEZE|LONG_LIQ|TRAP|DIVERGENCE
    oi_signal_confidence: int = 0               # 0–100

    # Funding-rate divergence (set by oi_tracker)
    oi_fr_divergence: Optional[str] = None  # "LONG_DANGER" | "SHORT_DANGER" | None

    # ── Pump/dump analytics (ENGINE) ─────────────────────────────────
    buy_ratio: float = 0.5
    trade_freq: float = 0.0
    price_trend_10s: float = 0.0
    pump_detected: bool = False
    dump_detected: bool = False

    # ── Final signal (ENGINE) ─────────────────────────────────────────
    score: float = 50.0            # 0–100 weighted
    boost: int = 0                 # integer pump/dump bonus from WS
    signal: str = "NEUTRAL"        # PUMP|DUMP|NEUTRAL|SHORT_SQUEEZE|LONG_SQUEEZE
    short_squeeze: bool = False
    long_squeeze: bool = False

    # Sub-scores (0–100)
    spot_momentum_score: float = 50.0
    volume_spike_score: float = 50.0
    order_book_score: float = 50.0
    trade_flow_score: float = 50.0
    funding_rate_score: float = 50.0
    open_interest_score: float = 50.0
    liquidation_score: float = 50.0
    volume_spike_pct: float = 0.0

    reasons: List[str] = field(default_factory=list)

    # ── Crime Coin Score ──────────────────────────────────────────────
    crime_score: float = 0.0
    crime_level: str = "NORMAL"
    crime_signals: list = field(default_factory=list)

    # ── Timestamps ────────────────────────────────────────────────────
    last_rest_update: float = field(default_factory=time.time)
    last_futures_update: float = 0.0
    last_ws_trade_time: float = 0.0
    last_signal_time: float = 0.0

    # ── Concurrency ───────────────────────────────────────────────────
    lock: asyncio.Lock = field(
        default_factory=asyncio.Lock, repr=False, compare=False
    )

    # ── Properties ───────────────────────────────────────────────────

    @property
    def price_change_5m_pct(self) -> float:
        if self.price_5m_ago <= 0:
            return 0.0
        return (self.price - self.price_5m_ago) / self.price_5m_ago * 100.0

    @property
    def price_change_15m_pct(self) -> float:
        if self.price_15m_ago <= 0:
            return 0.0
        return (self.price - self.price_15m_ago) / self.price_15m_ago * 100.0

    @property
    def price_change_1h_pct(self) -> float:
        if self.price_1h_ago <= 0:
            return 0.0
        return (self.price - self.price_1h_ago) / self.price_1h_ago * 100.0

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.last_rest_update) > 120.0

    def reset_signal(self) -> None:
        self.score = 50.0
        self.boost = 0
        self.signal = "NEUTRAL"
        self.short_squeeze = False
        self.long_squeeze = False
        self.pump_detected = False
        self.dump_detected = False
        self.buy_ratio = 0.5
        self.trade_freq = 0.0
        self.price_trend_10s = 0.0
        self.reasons = []

    def __repr__(self) -> str:
        return (
            f"TokenState(symbol={self.symbol!r}, price={self.price:.6g}, "
            f"score={self.score:.1f}, signal={self.signal!r}, "
            f"pump={self.pump_detected}, dump={self.dump_detected})"
        )
