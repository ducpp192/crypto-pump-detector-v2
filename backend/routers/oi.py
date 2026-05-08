"""
OI Router — REST endpoints cho OI history + Liquidation heatmap.

Endpoints:
  GET /api/oi/{symbol}/history      — trả về lịch sử OI snapshots
  GET /api/oi/{symbol}/heatmap      — trả về liquidation heatmap (Coinglass + fallback)
  GET /api/oi/alerts                — danh sách tokens đang có OI spike / squeeze signal
"""
from fastapi import APIRouter, HTTPException
from typing import Optional

from services.scanner import _states
from services.coinglass_service import fetch_liquidation_heatmap

router = APIRouter(prefix="/api/oi", tags=["OI"])


# ── GET /api/oi/{symbol}/history ──────────────────────────────────────────────

@router.get("/{symbol}/history")
async def get_oi_history(symbol: str, limit: int = 60):
    """
    Trả về lịch sử OI snapshots của 1 token.
    Dùng để render sparkline chi tiết hoặc chart dài hơn.
    """
    sym = symbol.upper().replace("USDT", "")
    state = _states.get(sym)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not tracked")

    hist = list(state.oi_history)[-limit:]
    return {
        "symbol":    sym,
        "count":     len(hist),
        "snapshots": [
            {
                "timestamp": s.timestamp,
                "oi_usd":    s.oi_usd,
                "source":    s.source,
            }
            for s in hist
        ],
        "latest": {
            "oi_usd":             state.oi_usd,
            "oi_change_1m":       state.oi_change_1m,
            "oi_change_5m":       state.oi_change_5m,
            "oi_change_15m":      state.oi_change_15m,
            "oi_trend":           state.oi_trend,
            "oi_spike":           state.oi_spike,
            "oi_spike_score":     state.oi_spike_score,
            "oi_market_cap_ratio": state.oi_market_cap_ratio,
            "oi_signal_type":     state.oi_signal_type,
            "oi_signal_confidence": state.oi_signal_confidence,
            "oi_fr_divergence":   state.oi_fr_divergence,
        },
    }


# ── GET /api/oi/{symbol}/heatmap ──────────────────────────────────────────────

@router.get("/{symbol}/heatmap")
async def get_liquidation_heatmap(symbol: str):
    """
    Trả về liquidation heatmap data từ Coinglass (hoặc estimated fallback).
    Frontend dùng để render heatmap modal.
    """
    sym = symbol.upper().replace("USDT", "")
    state = _states.get(sym)

    current_price = state.price   if state else 0.0
    oi_usd        = state.oi_usd  if state else None

    # Coinglass nhận symbol không có USDT: "BTC", "ETH", "RAVE"
    data = await fetch_liquidation_heatmap(
        symbol=sym,
        current_price=current_price,
        oi_usd=oi_usd,
    )

    # Gắn thêm OI context nếu có state
    if state:
        data["oi_context"] = {
            "oi_usd":             state.oi_usd,
            "oi_change_5m":       state.oi_change_5m,
            "oi_trend":           state.oi_trend,
            "oi_signal_type":     state.oi_signal_type,
            "funding_rate":       state.funding_rate,
            "market_cap":         state.market_cap,
            "oi_market_cap_ratio": state.oi_market_cap_ratio,
        }

    return data


# ── GET /api/oi/alerts ────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_oi_alerts(min_spike_score: int = 40, limit: int = 20):
    """
    Danh sách tất cả tokens đang có OI alert đáng chú ý.
    Dùng cho alert banner trên dashboard.
    """
    alerts = []
    for sym, state in _states.items():
        if not state.has_futures:
            continue

        is_alert = (
            state.oi_spike and state.oi_spike_score >= min_spike_score
        ) or state.oi_signal_type in ("SHORT_SQUEEZE", "LONG_LIQ", "TRAP")

        if is_alert:
            alerts.append({
                "symbol":              sym,
                "price":               round(state.price, 8),
                "oi_usd":              state.oi_usd,
                "oi_change_5m":        state.oi_change_5m,
                "oi_trend":            state.oi_trend,
                "oi_spike":            state.oi_spike,
                "oi_spike_score":      state.oi_spike_score,
                "oi_market_cap_ratio": state.oi_market_cap_ratio,
                "oi_signal_type":      state.oi_signal_type,
                "oi_signal_confidence": state.oi_signal_confidence,
                "oi_fr_divergence":    state.oi_fr_divergence,
                "funding_rate":        state.funding_rate,
                "score":               state.score,
                "signal":              state.signal,
            })

    # Sort theo spike score + signal confidence
    alerts.sort(
        key=lambda a: (a["oi_spike_score"] or 0) + (a["oi_signal_confidence"] or 0),
        reverse=True,
    )

    return {"alerts": alerts[:limit], "total": len(alerts)}
