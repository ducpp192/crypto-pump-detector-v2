"""
Crime Coin Score (CCS) — phát hiện coin bị market maker thao túng.

Score 0–100:
  0–40  : Bình thường
  40–60 : Có dấu hiệu
  60–75 : Suspicious
  75–90 : Crime coin
  90+   : MM đang active (RAVE stage)

8 components (tổng 100):
  1. OI/MC ratio          20pts
  2. Funding behavior     15pts
  3. OI change dynamics   15pts
  4. Price vs OI diverge  15pts
  5. Spot flow            10pts
  6. Liquidity/orderbook  10pts
  7. Exchange pattern     10pts
  8. Volatility profile    5pts
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CrimeScoreResult:
    symbol: str
    score: float                    # 0–100 tổng
    level: str                      # "NORMAL" | "WARNING" | "SUSPICIOUS" | "CRIME_COIN" | "MM_ACTIVE"
    signals: list[str]              # list lý do

    # Breakdown từng component
    oi_mc_score: float = 0
    funding_score: float = 0
    oi_change_score: float = 0
    divergence_score: float = 0
    flow_score: float = 0
    liquidity_score: float = 0
    exchange_score: float = 0
    volatility_score: float = 0

    def to_dict(self) -> dict:
        return {
            "crime_score":       round(self.score, 1),
            "crime_level":       self.level,
            "crime_signals":     self.signals,
            "crime_oi_mc":       round(self.oi_mc_score, 1),
            "crime_funding":     round(self.funding_score, 1),
            "crime_oi_change":   round(self.oi_change_score, 1),
            "crime_divergence":  round(self.divergence_score, 1),
            "crime_flow":        round(self.flow_score, 1),
            "crime_liquidity":   round(self.liquidity_score, 1),
            "crime_exchange":    round(self.exchange_score, 1),
            "crime_volatility":  round(self.volatility_score, 1),
        }


def _classify(score: float) -> str:
    if score >= 90: return "MM_ACTIVE"
    if score >= 75: return "CRIME_COIN"
    if score >= 60: return "SUSPICIOUS"
    if score >= 40: return "WARNING"
    return "NORMAL"


# ── Component 1: OI / Market Cap (20pts) ─────────────────────────────────────

def _score_oi_mc(ratio: Optional[float]) -> tuple[float, Optional[str]]:
    """ratio = oi_usd / market_cap (0–1 scale, not percent)"""
    if ratio is None or ratio <= 0:
        return 2.0, None
    pct = ratio * 100
    if pct > 40:  return 20.0, f"OI/MC {pct:.0f}% (cực cao, dễ thao túng)"
    if pct > 20:  return 15.0, f"OI/MC {pct:.0f}% (cao)"
    if pct > 10:  return 10.0, f"OI/MC {pct:.0f}% (trung bình cao)"
    if pct > 5:   return 5.0,  None
    return 2.0, None


# ── Component 2: Funding Behavior (15pts) ────────────────────────────────────

def _score_funding(fr: Optional[float]) -> tuple[float, Optional[str]]:
    if fr is None:
        return 3.0, None
    pct = fr * 100
    if pct < -0.5:
        return 15.0, f"Funding cực âm ({pct:.4f}%) — MM đang ép long"
    if pct < -0.1:
        return 10.0, f"Funding âm ({pct:.4f}%) — crowded shorts"
    if -0.05 <= pct <= 0.05:
        return 5.0, None
    if pct > 0.3:
        return 12.0, f"Funding dương cao ({pct:.4f}%) — trap long"
    if pct > 0.1:
        return 8.0, f"Funding dương ({pct:.4f}%)"
    return 4.0, None


# ── Component 3: OI Change Dynamics (15pts) ──────────────────────────────────

def _score_oi_change(oi_change_15m: Optional[float], oi_change_5m: Optional[float]) -> tuple[float, Optional[str]]:
    """Dùng 15m change làm proxy cho 1h; fallback sang 5m nếu không có"""
    change = oi_change_15m if oi_change_15m is not None else (oi_change_5m or 0)
    abs_c  = abs(change)
    if abs_c > 10:
        return 15.0, f"OI thay đổi mạnh {change:+.1f}% — build trap"
    if abs_c > 5:
        return 10.0, f"OI thay đổi {change:+.1f}%"
    if abs_c > 2:
        return 7.0, None
    return 3.0, None


# ── Component 4: Price vs OI Divergence (15pts) ──────────────────────────────

def _score_divergence(price_chg: float, oi_change_5m: Optional[float]) -> tuple[float, Optional[str]]:
    if oi_change_5m is None:
        return 3.0, None
    price_up = price_chg > 1.0
    price_dn = price_chg < -1.0
    oi_up    = oi_change_5m > 2.0
    oi_dn    = oi_change_5m < -2.0

    if price_up and oi_dn:
        return 15.0, "Giá tăng + OI giảm → Fake pump (trap long)"
    if price_dn and oi_up:
        return 12.0, "Giá giảm + OI tăng → Trap short (squeeze sắp xảy ra)"
    if price_up and oi_up:
        return 5.0, None   # trend thật
    if price_dn and oi_dn:
        return 7.0, "Giá giảm + OI giảm → Liq cascade"
    return 3.0, None


# ── Component 5: Spot Flow (10pts) ───────────────────────────────────────────

def _score_flow(buy_ratio: float, volume_24h: float, market_cap: float) -> tuple[float, Optional[str]]:
    """
    Ước tính net inflow từ buy_ratio + volume.
    flow_ratio = estimated_net_inflow / market_cap
    """
    if market_cap <= 0:
        return 2.0, None
    # Net inflow estimate: buy_ratio > 0.5 → tiền vào, ngược lại tiền ra
    net_inflow_est = volume_24h * 0.01 * (buy_ratio - 0.5) * 2  # normalized
    flow_ratio_pct = abs(net_inflow_est) / market_cap * 100

    if flow_ratio_pct > 2:
        return 10.0, f"Spot inflow cao ({flow_ratio_pct:.1f}% mcap) — tiền vào nhưng giá chưa chạy"
    if flow_ratio_pct > 1:
        return 8.0, f"Spot inflow {flow_ratio_pct:.1f}% mcap"
    if flow_ratio_pct > 0.5:
        return 5.0, None
    return 2.0, None


# ── Component 6: Liquidity / Orderbook (10pts) ───────────────────────────────

def _score_liquidity(order_book_score: float, volume_spike_score: float, volume_spike_pct: float) -> tuple[float, Optional[str]]:
    """
    order_book_score thấp = thanh khoản mỏng
    volume_spike cao + orderbook thấp = manipulation signal
    """
    low_liq    = order_book_score < 35
    med_liq    = 35 <= order_book_score < 60
    vol_spike  = volume_spike_pct > 200 or volume_spike_score > 70

    if low_liq and vol_spike:
        return 10.0, f"Thanh khoản thấp + volume spike {volume_spike_pct:.0f}% — dễ kéo giá"
    if low_liq:
        return 7.0, "Thanh khoản mỏng"
    if med_liq and vol_spike:
        return 6.0, None
    if vol_spike:
        return 5.0, None
    return 2.0, None


# ── Component 7: Exchange Pattern (10pts) ────────────────────────────────────

def _score_exchange(has_futures: bool, oi_usd: Optional[float], volume_24h: float) -> tuple[float, Optional[str]]:
    """
    Approximation: nếu có futures (Binance perp) + OI/volume ratio cao
    = concentrated on 1 exchange = dễ thao túng
    """
    if not has_futures:
        return 2.0, None
    oi = oi_usd or 0
    # OI chiếm > 20% volume 24h = futures concentration cao
    oi_vol_ratio = oi / volume_24h if volume_24h > 0 else 0
    if oi_vol_ratio > 0.5:
        return 10.0, f"Futures OI/{volume_24h/1e6:.1f}M vol = {oi_vol_ratio:.1f}x — tập trung 1 sàn"
    if oi_vol_ratio > 0.2:
        return 6.0, "Futures concentration trung bình"
    return 4.0, None


# ── Component 8: Volatility Profile (5pts) ───────────────────────────────────

def _score_volatility(price_chg_1h: float, volume_spike_pct: float) -> tuple[float, Optional[str]]:
    """
    Giá ổn định + volume spike bất thường = tích lũy trước pump
    """
    low_vol_price = abs(price_chg_1h) < 1.5
    high_vol_vol  = volume_spike_pct > 150

    if low_vol_price and high_vol_vol:
        return 5.0, "Giá flat + volume spike — tích lũy âm thầm"
    if high_vol_vol:
        return 3.0, None
    return 2.0, None


# ── Main ─────────────────────────────────────────────────────────────────────

def compute_crime_score(state) -> CrimeScoreResult:
    """
    state: TokenState object
    Trả về CrimeScoreResult với đầy đủ breakdown.
    """
    signals: list[str] = []

    def _add(sig: Optional[str]) -> None:
        if sig:
            signals.append(sig)

    # 1. OI/MC
    s1, msg1 = _score_oi_mc(getattr(state, "oi_market_cap_ratio", None))
    _add(msg1)

    # 2. Funding
    s2, msg2 = _score_funding(getattr(state, "funding_rate", None))
    _add(msg2)

    # 3. OI Change
    s3, msg3 = _score_oi_change(
        getattr(state, "oi_change_15m", None),
        getattr(state, "oi_change_5m", None),
    )
    _add(msg3)

    # 4. Divergence
    s4, msg4 = _score_divergence(
        getattr(state, "price_change_1h_pct", 0) or 0,
        getattr(state, "oi_change_5m", None),
    )
    _add(msg4)

    # 5. Flow
    s5, msg5 = _score_flow(
        getattr(state, "buy_ratio", 0.5) or 0.5,
        getattr(state, "volume_24h", 0) or 0,
        getattr(state, "market_cap", 0) or 0,
    )
    _add(msg5)

    # 6. Liquidity
    s6, msg6 = _score_liquidity(
        getattr(state, "order_book_score", 50) or 50,
        getattr(state, "volume_spike_score", 0) or 0,
        getattr(state, "volume_spike_pct", 0) or 0,
    )
    _add(msg6)

    # 7. Exchange
    s7, msg7 = _score_exchange(
        getattr(state, "has_futures", False),
        getattr(state, "oi_usd", None),
        getattr(state, "volume_24h", 0) or 0,
    )
    _add(msg7)

    # 8. Volatility
    s8, msg8 = _score_volatility(
        getattr(state, "price_change_1h_pct", 0) or 0,
        getattr(state, "volume_spike_pct", 0) or 0,
    )
    _add(msg8)

    total = s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8

    return CrimeScoreResult(
        symbol           = state.symbol,
        score            = min(100.0, total),
        level            = _classify(total),
        signals          = signals,
        oi_mc_score      = s1,
        funding_score    = s2,
        oi_change_score  = s3,
        divergence_score = s4,
        flow_score       = s5,
        liquidity_score  = s6,
        exchange_score   = s7,
        volatility_score = s8,
    )
