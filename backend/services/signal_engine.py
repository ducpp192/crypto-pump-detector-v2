"""
Signal Engine — merged scoring from both pump-detector and pump-scanner.

Scoring pipeline:
  1. Quality filter (spread, stale data, late-entry)
  2. Pump/dump detection from WS trade data (buy_ratio, freq, price_trend)
  3. Weighted 0–100 score from 7 factors
  4. Integer boost from pump detector (+2 pump / -2 dump)
  5. Squeeze detection (takes priority over score label)
  6. Final signal label
"""
import logging
from typing import Tuple

from models.token_state import TokenState
from config import (
    WEIGHTS,
    PUMP_SCORE_THRESHOLD,
    DUMP_SCORE_THRESHOLD,
    FUNDING_BEARISH_THRESHOLD,
    FUNDING_BULLISH_THRESHOLD,
    SQUEEZE_PRICE_MOVE_PCT,
    SQUEEZE_OI_DROP_PCT,
    IMBALANCE_BULLISH,
    IMBALANCE_BEARISH,
    SPREAD_MAX_PCT,
    PRICE_SKIP_THRESHOLD,
    VOLUME_SPIKE_MULT,
    VOLUME_SPIKE_WARN_MULT,
    MIN_VOLUME_24H,
)
from services.pump_detector import (
    detect_pump, detect_dump,
    compute_buy_ratio, compute_trade_freq, compute_price_trend_pct,
)
from services.binance_futures import (
    compute_funding_score, compute_oi_score, compute_liquidation_score,
)

log = logging.getLogger(__name__)


def filter_token(state: TokenState) -> Tuple[bool, str]:
    """Returns (should_skip, reason)."""
    if state.price <= 0:
        return True, "price=0"
    if state.volume_24h > 0 and state.volume_24h < MIN_VOLUME_24H:
        return True, "vol24h_low"
    if state.spread_pct > SPREAD_MAX_PCT:
        return True, f"spread:{state.spread_pct:.2f}%"
    p1h = abs(state.price_change_1h_pct)
    if p1h > PRICE_SKIP_THRESHOLD * 100:
        return True, f"late_entry:{p1h:.1f}%"
    return False, ""


def score_token(state: TokenState) -> None:
    """Full scoring pass. Writes results directly onto state."""
    skip, reason = filter_token(state)
    if skip:
        state.signal = "NEUTRAL"
        state.score = 50.0
        log.debug(f"skip {state.symbol}: {reason}")
        return

    # ── 1. Spot momentum (EMA + RSI + breakout from 15m klines) ──────
    rsi    = getattr(state, "_rsi", 50.0) or 50.0
    ema_b  = getattr(state, "_ema_bullish", None)
    ema_br = getattr(state, "_ema_bearish", None)
    brkout = getattr(state, "_breakout", False)

    mom_score = float(rsi)
    if ema_b:    mom_score = min(100, mom_score + 15)
    elif ema_br: mom_score = max(0,   mom_score - 15)
    if brkout:   mom_score = min(100, mom_score + 10)
    if state.momentum_5m > 1.0:  mom_score = min(100, mom_score + 5)
    if state.momentum_5m < -1.0: mom_score = max(0,   mom_score - 5)

    # ── 2. Volume spike (5m avg vs 1h baseline) ──────────────────────
    # avg_volume_1m  = avg volume của 60 nến 1m baseline (giờ trước)
    # recent_volume  = avg volume của 5 nến 1m gần nhất  (5 phút vừa rồi)
    # Scoring curve (5-tier):
    #   ≥ 5.0×  → 100  (real pump, VOLUME_SPIKE_MULT)
    #   3–5×    → 75–100 (warning zone, VOLUME_SPIKE_WARN_MULT)
    #   2–3×    → 55–75  (elevated)
    #   1.5–2×  → 45–55  (slightly above avg, near-neutral)
    #   < 1.5×  → 0–45   (below/at average → reduce score)
    avg_vol = state.avg_volume_1m   # baseline 1h (avg/nến)
    rec_vol = state.recent_volume   # recent 5m  (avg/nến)
    if avg_vol > 0 and rec_vol > 0:
        ratio = rec_vol / avg_vol
        spike_pct = (ratio - 1) * 100
        if ratio >= VOLUME_SPIKE_MULT:                            # ≥ 5× → score 100
            vol_score = 100.0
        elif ratio >= VOLUME_SPIKE_WARN_MULT:                     # 3–5× → 75–100
            vol_score = 75.0 + (ratio - VOLUME_SPIKE_WARN_MULT) / (VOLUME_SPIKE_MULT - VOLUME_SPIKE_WARN_MULT) * 25.0
        elif ratio >= 2.0:                                        # 2–3× → 55–75
            vol_score = 55.0 + (ratio - 2.0) * 20.0
        elif ratio >= 1.5:                                        # 1.5–2× → 45–55 (near-neutral)
            vol_score = 45.0 + (ratio - 1.5) * 20.0
        else:                                                     # < 1.5× → 0–45
            vol_score = max(0.0, ratio / 1.5 * 45.0)
    else:
        vol_score = 50.0
        spike_pct = 0.0

    # ── 3. Order book imbalance ───────────────────────────────────────
    imb = state.imbalance
    if imb >= IMBALANCE_BULLISH:
        ob_score = min(100.0, 65.0 + (imb - IMBALANCE_BULLISH) * 10)
    elif imb <= IMBALANCE_BEARISH:
        ob_score = max(0.0, 35.0 - (IMBALANCE_BEARISH - imb) * 20)
    else:
        ob_score = 35.0 + (imb - IMBALANCE_BEARISH) / (IMBALANCE_BULLISH - IMBALANCE_BEARISH) * 30.0

    # ── 4. Trade flow (WS real-time) ──────────────────────────────────
    br = compute_buy_ratio(state.recent_trades, 50)
    tf = compute_trade_freq(state.recent_trades, 30.0)
    pt = compute_price_trend_pct(state.recent_trades, 10.0)
    tf_score = br * 100
    if tf >= 2.0 and pt > 0: tf_score = min(100, tf_score + 10)
    if tf >= 2.0 and pt < 0: tf_score = max(0,   tf_score - 10)

    # ── 5. Pump/dump boost from WS trades ────────────────────────────
    is_pump, pump_reasons = detect_pump(state)
    is_dump, dump_reasons = detect_dump(state)
    boost = 0
    reasons = []
    if is_pump:
        boost += 2
        reasons.extend(pump_reasons)
    if is_dump:
        boost -= 2
        reasons.extend(dump_reasons)

    # ── 6. Derivatives ────────────────────────────────────────────────
    funding_score = compute_funding_score(state.funding_rate, state.price_change_1h_pct)
    oi_score      = compute_oi_score(state.oi_change_pct, state.price_change_1h_pct)
    liq_score     = compute_liquidation_score(state)

    # ── Weighted final score ──────────────────────────────────────────
    weighted = (
        mom_score       * WEIGHTS["spot_momentum"]
        + vol_score     * WEIGHTS["volume_spike"]
        + ob_score      * WEIGHTS["order_book"]
        + tf_score      * WEIGHTS["trade_flow"]
        + funding_score * WEIGHTS["funding_rate"]
        + oi_score      * WEIGHTS["open_interest"]
        + liq_score     * WEIGHTS["liquidation"]
    )
    final_score = max(0.0, min(100.0, weighted + boost * 3.0))

    # ── Squeeze detection ─────────────────────────────────────────────
    fr    = state.funding_rate
    oi_chg = state.oi_change_pct
    p1h   = state.price_change_1h_pct

    short_squeeze = (
        fr is not None
        and fr < FUNDING_BULLISH_THRESHOLD
        and p1h > SQUEEZE_PRICE_MOVE_PCT
        and (state.liquidation_side == "short"
             or (oi_chg is not None and oi_chg < SQUEEZE_OI_DROP_PCT))
    )
    long_squeeze = (
        fr is not None
        and fr > FUNDING_BEARISH_THRESHOLD
        and p1h < -SQUEEZE_PRICE_MOVE_PCT
        and (state.liquidation_side == "long"
             or (oi_chg is not None and oi_chg < SQUEEZE_OI_DROP_PCT))
    )

    if short_squeeze:       signal = "SHORT_SQUEEZE"
    elif long_squeeze:      signal = "LONG_SQUEEZE"
    elif final_score >= PUMP_SCORE_THRESHOLD: signal = "PUMP"
    elif final_score <= DUMP_SCORE_THRESHOLD: signal = "DUMP"
    else:                   signal = "NEUTRAL"

    # ── Write back ────────────────────────────────────────────────────
    state.spot_momentum_score = round(mom_score, 2)
    state.volume_spike_score  = round(vol_score, 2)
    state.order_book_score    = round(ob_score, 2)
    state.trade_flow_score    = round(tf_score, 2)
    state.funding_rate_score  = round(funding_score, 2)
    state.open_interest_score = round(oi_score, 2)
    state.liquidation_score   = round(liq_score, 2)
    state.volume_spike_pct    = round(spike_pct, 1)
    state.score               = round(final_score, 2)
    state.boost               = boost
    state.signal              = signal
    state.short_squeeze       = short_squeeze
    state.long_squeeze        = long_squeeze
    state.pump_detected       = is_pump
    state.dump_detected       = is_dump
    state.buy_ratio           = round(br, 4)
    state.trade_freq          = round(tf, 3)
    state.price_trend_10s     = round(pt, 4)
    state.reasons             = reasons
