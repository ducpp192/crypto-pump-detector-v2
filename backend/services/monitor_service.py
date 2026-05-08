"""
Monitor Service — FLOW_SCORE multi-timeframe computation.

FLOW_SCORE = (volume_delta * 0.25) + (oi_delta * 0.25) + (price_momentum * 0.20)
           + (funding_divergence * 0.15) + (liquidation_pressure * 0.10) + (relative_volume * 0.05)

Each component is [0, 100]. 50 = neutral, >50 = bullish inflow, <50 = bearish outflow.
"""
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from models.token_state import TokenState


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _pct_to_score(pct: float, scale: float = 5.0) -> float:
    """Map percentage change to [0, 100]: 0% → 50, +scale% → 100, -scale% → 0."""
    return _clamp(50.0 + (pct / scale) * 50.0)


# ── Component computations ────────────────────────────────────────────────────

def _volume_delta(state: TokenState) -> float:
    if state.avg_volume_1m <= 0:
        return 50.0
    ratio = state.recent_volume / state.avg_volume_1m
    return _clamp((ratio / 3.0) * 100.0)


def _oi_delta(state: TokenState, tf: str) -> float:
    oi_change: Optional[float] = None
    if tf in ("5m", "1d"):
        oi_change = state.oi_change_5m
    elif tf == "15m":
        oi_change = state.oi_change_15m
    elif tf in ("1h", "4h"):
        # Use 15m change as best available proxy
        oi_change = state.oi_change_15m
    if oi_change is None:
        return 50.0
    return _pct_to_score(oi_change, scale=3.0)


def _price_momentum(state: TokenState, tf: str) -> float:
    pct = 0.0
    if tf == "5m":
        pct = state.price_change_5m_pct
    elif tf == "15m":
        pct = state.price_change_15m_pct
    elif tf in ("1h", "4h"):
        pct = state.price_change_1h_pct
    elif tf == "1d":
        pct = state.price_change_24h_pct
    return _pct_to_score(pct, scale=5.0)


def _funding_divergence(state: TokenState) -> float:
    fr = state.funding_rate
    if fr is None:
        return 50.0
    # Negative FR = shorts heavily funded = potential short squeeze = bullish → score > 50
    # Positive FR = over-leveraged longs = risky → score < 50
    return _clamp(50.0 - (fr / 0.003) * 30.0)


def _liquidation_pressure(state: TokenState) -> float:
    if not state.liquidation_detected:
        return 50.0
    if state.liquidation_side == "short":
        return 85.0
    if state.liquidation_side == "long":
        return 15.0
    return 50.0


def _relative_volume(state: TokenState) -> float:
    vsp = state.volume_spike_pct
    if vsp <= 0:
        return 50.0
    return _clamp(50.0 + (vsp / 300.0) * 50.0)


# ── FLOW_SCORE weights ────────────────────────────────────────────────────────

_WEIGHTS = {
    "volume_delta":         0.25,
    "oi_delta":             0.25,
    "price_momentum":       0.20,
    "funding_divergence":   0.15,
    "liquidation_pressure": 0.10,
    "relative_volume":      0.05,
}


def compute_flow_score(state: TokenState, tf: str = "5m") -> Dict[str, float]:
    comps = {
        "volume_delta":         _volume_delta(state),
        "oi_delta":             _oi_delta(state, tf),
        "price_momentum":       _price_momentum(state, tf),
        "funding_divergence":   _funding_divergence(state),
        "liquidation_pressure": _liquidation_pressure(state),
        "relative_volume":      _relative_volume(state),
    }
    score = sum(comps[k] * _WEIGHTS[k] for k in comps)
    return {"flow_score": round(score, 2), **{k: round(v, 2) for k, v in comps.items()}}


# ── Smart signal detection ────────────────────────────────────────────────────

def detect_smart_signals(state: TokenState) -> List[str]:
    signals: List[str] = []

    if state.volume_spike_pct > 200:
        signals.append("ABNORMAL_VOLUME")

    short_sqz = (
        state.oi_signal_type == "SHORT_SQUEEZE"
        or (
            state.oi_trend == "UP"
            and state.buy_ratio > 0.62
            and (state.funding_rate or 0.0) < -0.0002
        )
    )
    if short_sqz:
        signals.append("SHORT_SQUEEZE_LIKELY")

    long_sqz = (
        state.oi_signal_type == "LONG_LIQ"
        or (
            state.oi_trend == "DOWN"
            and state.buy_ratio < 0.38
            and (state.funding_rate or 0.0) > 0.0002
        )
    )
    if long_sqz:
        signals.append("LONG_SQUEEZE_LIKELY")

    if (
        state.oi_trend == "UP"
        and abs(state.price_change_5m_pct) < 1.0
        and (state.funding_rate or 0.0) > 0.0005
    ):
        signals.append("LEVERAGE_BUILDUP")

    if (
        state.buy_ratio > 0.65
        and state.price_change_5m_pct > 1.0
        and (state.oi_change_5m or 0.0) < 1.0
    ):
        signals.append("SPOT_LED_RALLY")

    if (
        (state.oi_change_5m or 0.0) > 3.0
        and state.price_change_5m_pct > 1.5
    ):
        signals.append("FUTURES_LED_RALLY")

    if (
        0 < state.market_cap < 50_000_000
        and state.volume_spike_pct > 300
    ):
        signals.append("LOW_CAP_SPECULATION")

    if state.oi_market_cap_ratio is not None and state.oi_market_cap_ratio > 0.5:
        signals.append("HIGH_OI_RATIO")

    return signals


# ── Build full monitor token payload ─────────────────────────────────────────

def build_monitor_token(state: TokenState) -> Dict[str, Any]:
    s5m  = compute_flow_score(state, "5m")
    s15m = compute_flow_score(state, "15m")
    s1h  = compute_flow_score(state, "1h")
    s1d  = compute_flow_score(state, "1d")

    fs = s5m["flow_score"]
    direction = "INFLOW" if fs > 60 else "OUTFLOW" if fs < 40 else "NEUTRAL"

    return {
        "symbol":       state.symbol,
        "name":         state.name,
        "price":        state.price,
        "market_cap":   state.market_cap,
        "volume_24h":   state.volume_24h,

        "price_change_5m":  round(state.price_change_5m_pct, 4),
        "price_change_15m": round(state.price_change_15m_pct, 4),
        "price_change_1h":  round(state.price_change_1h_pct, 4),
        "price_change_24h": round(state.price_change_24h_pct, 4),

        "flow_score_5m":  s5m["flow_score"],
        "flow_score_15m": s15m["flow_score"],
        "flow_score_1h":  s1h["flow_score"],
        "flow_score_1d":  s1d["flow_score"],
        "flow_direction": direction,

        "volume_delta":         s5m["volume_delta"],
        "oi_delta":             s5m["oi_delta"],
        "price_momentum":       s5m["price_momentum"],
        "funding_divergence":   s5m["funding_divergence"],
        "liquidation_pressure": s5m["liquidation_pressure"],
        "relative_volume":      s5m["relative_volume"],

        "funding_rate":        state.funding_rate,
        "oi_usd":              state.oi_usd,
        "oi_change_5m":        state.oi_change_5m,
        "oi_change_15m":       state.oi_change_15m,
        "oi_trend":            state.oi_trend,
        "oi_spike":            state.oi_spike,
        "oi_market_cap_ratio": state.oi_market_cap_ratio,
        "has_futures":         state.has_futures,

        "buy_ratio":        state.buy_ratio,
        "volume_spike_pct": state.volume_spike_pct,
        "trade_freq":       state.trade_freq,

        "crime_score": state.crime_score,
        "crime_level": state.crime_level,

        "smart_signals": detect_smart_signals(state),
        "last_updated":  time.time(),
    }


def get_monitor_snapshot(states: Dict[str, TokenState]) -> List[Dict[str, Any]]:
    """All tracked tokens sorted by flow_score_5m descending."""
    tokens: List[Dict[str, Any]] = []
    for sym, state in states.items():
        if state.price <= 0:
            continue
        try:
            tokens.append(build_monitor_token(state))
        except Exception:
            pass
    tokens.sort(key=lambda t: t["flow_score_5m"], reverse=True)
    return tokens
