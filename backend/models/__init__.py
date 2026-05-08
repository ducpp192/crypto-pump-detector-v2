from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime


class TokenSignal(BaseModel):
    symbol: str
    name: str
    price: float
    price_change_1h: float
    price_change_24h: float
    market_cap: float
    volume_24h: float

    spot_momentum_score: float
    volume_spike_score: float
    order_book_score: float
    trade_flow_score: float
    funding_rate_score: float
    open_interest_score: float
    liquidation_score: float

    score: float
    signal: Literal["PUMP", "DUMP", "NEUTRAL", "SHORT_SQUEEZE", "LONG_SQUEEZE"]

    # ── Derivatives (base) ────────────────────────────────────────────
    funding_rate: Optional[float] = None
    oi_change_pct: Optional[float] = None
    oi_usd: Optional[float] = None
    volume_spike_pct: float = 0.0
    short_squeeze: bool = False
    long_squeeze: bool = False
    liquidation_detected: bool = False
    liquidation_side: Optional[Literal["long", "short"]] = None

    # ── OI Enhanced Metrics ───────────────────────────────────────────
    oi_change_1m:         Optional[float] = None
    oi_change_5m:         Optional[float] = None
    oi_change_15m:        Optional[float] = None
    oi_trend:             str = "SIDEWAYS"
    oi_spike:             bool = False
    oi_spike_score:       int = 0
    oi_market_cap_ratio:  Optional[float] = None
    oi_signal_type:       Optional[str] = None
    oi_signal_confidence: int = 0
    oi_fr_divergence:     Optional[str] = None
    oi_sparkline:         List[float] = []

    # ── Crime Coin Score ──────────────────────────────────────────────
    crime_score:       float = 0.0
    crime_level:       str = "NORMAL"   # NORMAL|WARNING|SUSPICIOUS|CRIME_COIN|MM_ACTIVE
    crime_signals:     List[str] = []
    crime_oi_mc:       float = 0.0
    crime_funding:     float = 0.0
    crime_oi_change:   float = 0.0
    crime_divergence:  float = 0.0
    crime_flow:        float = 0.0
    crime_liquidity:   float = 0.0
    crime_exchange:    float = 0.0
    crime_volatility:  float = 0.0

    # ── WS live metrics ───────────────────────────────────────────────
    buy_ratio: float = 0.5
    trade_freq: float = 0.0
    price_trend_10s: float = 0.0
    pump_detected: bool = False
    dump_detected: bool = False
    boost: int = 0
    reasons: List[str] = []

    timestamp: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DashboardState(BaseModel):
    signals: List[TokenSignal]
    last_updated: datetime
    total_scanned: int
    alerts_triggered: int
