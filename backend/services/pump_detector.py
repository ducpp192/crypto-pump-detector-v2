"""
Pump/dump detector — operates on WS trade data in TokenState.

Improvements over v1:
  - Volume-weighted buy ratio (whale-sensitive, bot-resistant)
  - Whale detection: single buy >= WHALE_BUY_USDT
  - Trade acceleration: freq(last 10s) / freq(prior 20s) >= TRADE_ACCEL_RATIO
  - Organic volume check: bot spam has suspiciously uniform trade sizes (low CV)
  - Minimum trade size filter: ignore micro trades < MIN_TRADE_USDT
"""
import time
from collections import deque
from typing import Deque, List, Tuple

from models.token_state import TokenState, Trade
from config import (
    PUMP_BUY_RATIO,
    PUMP_TRADE_WINDOW,
    PUMP_FREQ_WINDOW_SECS,
    MIN_TRADE_USDT,
    WHALE_BUY_USDT,
    TRADE_ACCEL_RATIO,
)


# ── Core helpers ──────────────────────────────────────────────────────────────

def compute_buy_ratio(trades: Deque[Trade], window: int = 50, min_usdt: float = MIN_TRADE_USDT) -> float:
    """
    Volume-weighted buy ratio from last `window` meaningful trades.
    Filters out micro trades (< min_usdt) which are common bot spam.
    Returns fraction of buy-side VOLUME (not count) → whale-sensitive.
    """
    if not trades:
        return 0.5
    # Filter micro trades then take last `window`
    meaningful = [t for t in trades if t.qty * t.price >= min_usdt][-window:]
    if not meaningful:
        return 0.5
    buy_vol  = sum(t.qty * t.price for t in meaningful if not t.is_buyer_maker)
    sell_vol = sum(t.qty * t.price for t in meaningful if t.is_buyer_maker)
    total    = buy_vol + sell_vol
    return buy_vol / total if total > 0 else 0.5


def compute_trade_freq(trades: Deque[Trade], window_secs: float = PUMP_FREQ_WINDOW_SECS) -> float:
    """Trades per second within the last window_secs."""
    if not trades or window_secs <= 0:
        return 0.0
    cutoff = time.time() - window_secs
    count = sum(1 for t in trades if t.timestamp >= cutoff)
    return count / window_secs


def compute_price_trend_pct(trades: Deque[Trade], lookback_secs: float = 10.0) -> float:
    """% price change from oldest to newest trade within lookback_secs."""
    if len(trades) < 2:
        return 0.0
    cutoff = time.time() - lookback_secs
    window = [t for t in trades if t.timestamp >= cutoff]
    if len(window) < 2:
        window = list(trades)
    if len(window) < 2:
        return 0.0
    old, new = window[0].price, window[-1].price
    return (new - old) / old * 100 if old > 0 else 0.0


def compute_volume_30s(trades: Deque[Trade]) -> float:
    """Total USD volume in the last 30 seconds."""
    cutoff = time.time() - 30.0
    return sum(t.price * t.qty for t in trades if t.timestamp >= cutoff)


# ── New detection helpers ─────────────────────────────────────────────────────

def detect_whale_buy(trades: Deque[Trade], min_usdt: float = WHALE_BUY_USDT, window: int = 50) -> bool:
    """True if any single buy trade >= min_usdt in the last `window` trades."""
    recent = list(trades)[-window:]
    return any(
        not t.is_buyer_maker and t.qty * t.price >= min_usdt
        for t in recent
    )


def detect_whale_sell(trades: Deque[Trade], min_usdt: float = WHALE_BUY_USDT, window: int = 50) -> bool:
    """True if any single sell trade >= min_usdt in the last `window` trades."""
    recent = list(trades)[-window:]
    return any(
        t.is_buyer_maker and t.qty * t.price >= min_usdt
        for t in recent
    )


def compute_trade_acceleration(trades: Deque[Trade], window1: float = 10.0, window2: float = 30.0) -> float:
    """
    Ratio of trade/s in last window1 vs the prior (window2 - window1) seconds.
    > 1.0 = accelerating. >= TRADE_ACCEL_RATIO = burst/spike.
    Returns 1.0 when not enough data.
    """
    now = time.time()
    recent_count   = sum(1 for t in trades if now - t.timestamp <= window1)
    previous_count = sum(1 for t in trades if window1 < now - t.timestamp <= window2)
    prior_secs     = window2 - window1

    freq_recent = recent_count / window1
    freq_prior  = previous_count / prior_secs if prior_secs > 0 else 0.0

    if freq_prior == 0:
        return 1.0
    return freq_recent / freq_prior


def is_organic_volume(trades: Deque[Trade], window: int = 50, min_usdt: float = MIN_TRADE_USDT) -> bool:
    """
    Bot spam tends to have suspiciously uniform trade sizes (low coefficient of variation).
    Real organic volume has high variance in trade sizes.
    Returns False if the trade pattern looks bot-like (CV < 0.3).
    """
    recent = [t for t in list(trades)[-window:] if not t.is_buyer_maker and t.qty * t.price >= min_usdt]
    if len(recent) < 8:
        return True  # not enough data → assume organic
    qtys = [t.qty for t in recent]
    mean = sum(qtys) / len(qtys)
    if mean == 0:
        return True
    variance = sum((q - mean) ** 2 for q in qtys) / len(qtys)
    cv = (variance ** 0.5) / mean   # coefficient of variation
    return cv > 0.3                  # cv < 0.3 → too uniform → suspect bot


# ── Main detectors ────────────────────────────────────────────────────────────

def detect_pump(state: TokenState) -> Tuple[bool, List[str]]:
    trades = state.recent_trades
    if len(trades) < 5:
        return False, []

    buy_ratio   = compute_buy_ratio(trades, PUMP_TRADE_WINDOW)
    trade_freq  = compute_trade_freq(trades, PUMP_FREQ_WINDOW_SECS)
    price_trend = compute_price_trend_pct(trades, lookback_secs=10.0)
    accel       = compute_trade_acceleration(trades)
    whale       = detect_whale_buy(trades)
    organic     = is_organic_volume(trades)

    reasons = []
    buy_ok   = buy_ratio >= PUMP_BUY_RATIO
    freq_ok  = trade_freq >= 0.5
    trend_ok = price_trend > 0

    if buy_ok:    reasons.append(f"buy_vol:{buy_ratio:.2f}")
    if freq_ok:   reasons.append(f"freq:{trade_freq:.1f}/s")
    if trend_ok:  reasons.append(f"price{price_trend:+.2f}%")
    if whale:     reasons.append("whale_buy")
    if accel >= TRADE_ACCEL_RATIO:
        reasons.append(f"accel:{accel:.1f}x")
    if not organic:
        reasons.append("bot_pattern")

    # Whale buy relaxes buy_ratio threshold slightly (whale signals intent)
    effective_buy_threshold = PUMP_BUY_RATIO - (0.05 if whale else 0.0)
    buy_ok_effective = buy_ratio >= effective_buy_threshold

    # Acceleration can substitute for freq_ok
    momentum_ok = freq_ok or accel >= TRADE_ACCEL_RATIO

    # Bot pattern = suspicious → require stronger signals
    if not organic:
        is_pump = buy_ok_effective and momentum_ok and trend_ok and whale
    else:
        is_pump = buy_ok_effective and momentum_ok and trend_ok

    return is_pump, reasons if is_pump else []


def detect_dump(state: TokenState) -> Tuple[bool, List[str]]:
    trades = state.recent_trades
    if len(trades) < 5:
        return False, []

    buy_ratio   = compute_buy_ratio(trades, PUMP_TRADE_WINDOW)
    sell_ratio  = 1.0 - buy_ratio
    price_trend = compute_price_trend_pct(trades, lookback_secs=10.0)
    accel       = compute_trade_acceleration(trades)
    whale_sell  = detect_whale_sell(trades)
    organic     = is_organic_volume(trades)
    vol_ok      = (state.recent_volume > 0 and state.avg_volume_1m > 0
                   and state.recent_volume >= 0.8 * state.avg_volume_1m)

    reasons = []
    sell_ok    = sell_ratio >= PUMP_BUY_RATIO
    trend_down = price_trend < 0

    if sell_ok:    reasons.append(f"sell_vol:{sell_ratio:.2f}")
    if trend_down: reasons.append(f"price{price_trend:+.2f}%")
    if vol_ok:     reasons.append("vol_ok")
    if whale_sell: reasons.append("whale_sell")
    if accel >= TRADE_ACCEL_RATIO:
        reasons.append(f"accel:{accel:.1f}x")
    if not organic:
        reasons.append("bot_pattern")

    effective_sell_threshold = PUMP_BUY_RATIO - (0.05 if whale_sell else 0.0)
    sell_ok_effective = sell_ratio >= effective_sell_threshold
    momentum_ok = (trade_freq := compute_trade_freq(trades, PUMP_FREQ_WINDOW_SECS)) >= 0.5 or accel >= TRADE_ACCEL_RATIO  # noqa: F841

    if not organic:
        is_dump = sell_ok_effective and trend_down and vol_ok and whale_sell
    else:
        is_dump = sell_ok_effective and trend_down and vol_ok

    return is_dump, reasons if is_dump else []
