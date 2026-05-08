"""
OI Tracker — Open Interest analytics engine.

Pure functions that operate on per-token OI history to compute:
  - OI changes over 1m / 5m / 15m windows
  - OI trend (UP / DOWN / SIDEWAYS)
  - OI spike detection (0–100 score)
  - OI / Market-cap ratio
  - Signal detection (SHORT_SQUEEZE, LONG_LIQ, TRAP)
  - Funding rate divergence alerts

Called by binance_futures.enrich_futures() after each OI data push.
No external I/O — all computations work on in-memory deques.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from models.token_state import OISnapshot, TokenState

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def compute_oi_metrics(state: "TokenState") -> None:
    """
    Compute all OI metrics from state.oi_history and update state in-place.
    Assumes the caller already holds state.lock (called inside async with state.lock).
    """
    hist: List["OISnapshot"] = list(state.oi_history)
    if len(hist) < 2:
        return

    current = hist[-1]
    current_oi = current.oi_usd
    now_ts = current.timestamp

    # ── Time-window % changes ─────────────────────────────────────────────────
    state.oi_change_1m  = _change_over_window(hist, now_ts, 60)
    state.oi_change_5m  = _change_over_window(hist, now_ts, 300)
    state.oi_change_15m = _change_over_window(hist, now_ts, 900)

    # Back-compat: keep existing field in sync with 5m window
    state.oi_usd = current_oi
    if state.oi_change_5m is not None:
        state.oi_change_pct = round(state.oi_change_5m, 3)

    # ── Trend ─────────────────────────────────────────────────────────────────
    state.oi_trend = _compute_trend(hist)

    # ── Spike ─────────────────────────────────────────────────────────────────
    spike_score = _compute_spike_score(state)
    state.oi_spike       = spike_score >= 40
    state.oi_spike_score = spike_score

    # ── OI / Market-cap ratio ─────────────────────────────────────────────────
    if state.market_cap > 0 and current_oi > 0:
        state.oi_market_cap_ratio = round(current_oi / state.market_cap, 4)
    else:
        state.oi_market_cap_ratio = None

    # ── Manipulation-pattern signals ──────────────────────────────────────────
    _detect_signal(state)

    # ── Funding-rate divergence ───────────────────────────────────────────────
    _detect_funding_divergence(state)


# ─────────────────────────────────────────────────────────────────────────────
# OI change helpers
# ─────────────────────────────────────────────────────────────────────────────

def _change_over_window(
    hist: List["OISnapshot"],
    now_ts: float,
    window_secs: float,
) -> Optional[float]:
    """
    Find the snapshot closest to (now - window_secs) and return % change
    from that point to the latest snapshot.
    """
    target_ts = now_ts - window_secs
    ref: Optional["OISnapshot"] = None
    best_diff = float("inf")

    for snap in hist:
        diff = abs(snap.timestamp - target_ts)
        if diff < best_diff:
            best_diff = diff
            ref = snap

    if ref is None or ref.oi_usd <= 0:
        return None

    current_oi = hist[-1].oi_usd
    return (current_oi - ref.oi_usd) / ref.oi_usd * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# OI trend
# ─────────────────────────────────────────────────────────────────────────────

def _compute_trend(hist: List["OISnapshot"]) -> str:
    """
    Rolling-window trend using the last 6 snapshots (≈3 min at 30s interval).
    Returns UP / DOWN / SIDEWAYS.
    """
    recent = [h.oi_usd for h in hist[-6:]]
    if len(recent) < 3:
        return "SIDEWAYS"

    total = len(recent) - 1
    ups   = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1] * 1.0001)
    downs = sum(1 for i in range(1, len(recent)) if recent[i] < recent[i - 1] * 0.9999)

    if ups / total >= 0.65:
        return "UP"
    if downs / total >= 0.65:
        return "DOWN"
    return "SIDEWAYS"


# ─────────────────────────────────────────────────────────────────────────────
# OI spike detection
# ─────────────────────────────────────────────────────────────────────────────

def _compute_spike_score(state: "TokenState") -> int:
    """
    0–100 score for OI spike severity.

    Spike triggers:
      oi_change_5m  > 15% → moderate spike
      oi_change_5m  > 30% → extreme spike
      oi_change_15m > 30% → confirmed spike (sustained)
    """
    score = 0

    oi5 = state.oi_change_5m
    if oi5 is not None:
        mag5 = abs(oi5)
        if mag5 >= 30:
            score += 70
        elif mag5 >= 15:
            # Linear scale 15→30% maps to 40→70 points
            score += int(40 + (mag5 - 15) / 15.0 * 30)
        elif mag5 >= 5:
            # Linear scale 5→15% maps to 0→40 points
            score += int((mag5 / 15.0) * 40)

    oi15 = state.oi_change_15m
    if oi15 is not None:
        mag15 = abs(oi15)
        if mag15 >= 30:
            score += 30
        elif mag15 >= 10:
            score += int((mag15 / 30.0) * 30)

    return min(100, score)


# ─────────────────────────────────────────────────────────────────────────────
# Manipulation-pattern signal detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_signal(state: "TokenState") -> None:
    """
    Detect and set state.oi_signal_type / oi_signal_confidence.

    Patterns:
      SHORT_SQUEEZE  — OI↑  + Price↑ + FR<0 (crowded shorts being squeezed)
      LONG_LIQ       — OI↓  + Price↓ (long liquidation cascade)
      TRAP           — OI↓  + Price↓ + Volume↑ (bear trap / short trap)
      DIVERGENCE     — OI↑  + Price↓ (building shorts against the trend)
    """
    oi5     = state.oi_change_5m
    price1h = state.price_change_1h_pct
    fr      = state.funding_rate
    vol_sp  = state.volume_spike_pct

    signal_type: Optional[str] = None
    confidence  = 0

    if oi5 is None:
        state.oi_signal_type       = None
        state.oi_signal_confidence = 0
        return

    # ── SHORT SQUEEZE: OI↑ + Price↑ (+ crowded shorts = negative FR) ────────
    if oi5 > 5 and price1h > 1.0:
        c = 40
        if fr is not None and fr < -0.0005:
            c += 30   # negative FR = crowded shorts → squeeze fuel
        if state.buy_ratio > 0.65:
            c += 15
        if state.oi_spike:
            c += 10
        if state.oi_trend == "UP":
            c += 5
        if c >= 50:
            signal_type = "SHORT_SQUEEZE"
            confidence  = min(100, c)

    # ── LONG LIQUIDATION: OI↓ + Price↓ ──────────────────────────────────────
    elif oi5 < -5 and price1h < -1.0:
        c = 50
        if fr is not None and fr > 0.001:
            c += 25   # crowded longs getting flushed
        if state.buy_ratio < 0.40:
            c += 15
        if state.oi_trend == "DOWN":
            c += 10
        signal_type = "LONG_LIQ"
        confidence  = min(100, c)

    # ── BEAR TRAP: OI↓ + Price↓ + Volume spike → likely short trap ──────────
    elif oi5 < -3 and price1h < -0.5 and vol_sp > 50:
        c = 40 + min(40, int(vol_sp / 3))
        signal_type = "TRAP"
        confidence  = min(100, c)

    # ── DIVERGENCE: OI↑ + Price↓ (smart money loading shorts) ───────────────
    elif oi5 > 8 and price1h < -1.5:
        c = 45
        if fr is not None and fr > 0.0005:
            c += 20   # longs paying premium while price drops = danger
        signal_type = "DIVERGENCE"
        confidence  = min(100, c)

    state.oi_signal_type       = signal_type
    state.oi_signal_confidence = confidence


# ─────────────────────────────────────────────────────────────────────────────
# Funding-rate divergence
# ─────────────────────────────────────────────────────────────────────────────

def _detect_funding_divergence(state: "TokenState") -> None:
    """
    Detect when funding rate diverges from price direction.

    Dangerous for longs:  FR rising while price falling  → set oi_fr_divergence = "LONG_DANGER"
    Dangerous for shorts: FR falling while price rising  → set oi_fr_divergence = "SHORT_DANGER"
    """
    fh = list(state.funding_history)
    if len(fh) < 3:
        state.oi_fr_divergence = None
        return

    # Rate of change of funding over last N readings
    rates = [r for _, r in fh[-4:]]
    fr_delta = rates[-1] - rates[0]   # positive = rising funding

    price1h = state.price_change_1h_pct

    if fr_delta > 0.0003 and price1h < -1.0:
        # Funding rising (more longs) but price falling = longs are trapped
        state.oi_fr_divergence = "LONG_DANGER"
    elif fr_delta < -0.0003 and price1h > 1.0:
        # Funding falling (more shorts) but price rising = shorts squeezed
        state.oi_fr_divergence = "SHORT_DANGER"
    else:
        state.oi_fr_divergence = None
