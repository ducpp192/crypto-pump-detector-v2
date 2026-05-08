"""Monitor router — REST + WebSocket for Money Flow Monitor tab."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from services.scanner import _states
from services.monitor_service import build_monitor_token, get_monitor_snapshot
from services.flow_history import get_fund_flow_history, get_signal_history

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitor", tags=["monitor"])


# ── REST: main snapshot ───────────────────────────────────────────────────────

@router.get("/snapshot")
async def monitor_snapshot(
    min_score: float = Query(0, ge=0, le=100),
    max_score: float = Query(100, ge=0, le=100),
    direction: Optional[str] = Query(None),
    has_futures: Optional[bool] = Query(None),
    signal: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    tokens = get_monitor_snapshot(_states)
    if min_score > 0 or max_score < 100:
        tokens = [t for t in tokens if min_score <= t["flow_score_5m"] <= max_score]
    if direction and direction.upper() != "ALL":
        tokens = [t for t in tokens if t["flow_direction"] == direction.upper()]
    if has_futures is not None:
        tokens = [t for t in tokens if t["has_futures"] == has_futures]
    if signal and signal.upper() != "ALL":
        tokens = [t for t in tokens if signal.upper() in t["smart_signals"]]
    return {"tokens": tokens[:limit], "total": len(tokens)}


@router.get("/token/{symbol}")
async def monitor_token_detail(symbol: str):
    state = _states.get(symbol.upper())
    if state is None:
        raise HTTPException(status_code=404, detail=f"Token {symbol.upper()} not tracked")
    return build_monitor_token(state)


@router.get("/heatmap")
async def monitor_heatmap():
    tokens = get_monitor_snapshot(_states)
    return [
        {
            "symbol":          t["symbol"],
            "flow_score_5m":   t["flow_score_5m"],
            "market_cap":      t["market_cap"],
            "direction":       t["flow_direction"],
            "smart_signals":   t["smart_signals"],
            "price_change_5m": t["price_change_5m"],
        }
        for t in tokens
    ]


@router.get("/alerts")
async def monitor_alerts(limit: int = Query(50, ge=1, le=200)):
    tokens = get_monitor_snapshot(_states)
    alerts = [t for t in tokens if t["flow_score_5m"] >= 70 or t["flow_score_5m"] <= 30]
    alerts.sort(key=lambda t: abs(t["flow_score_5m"] - 50), reverse=True)
    return {"alerts": alerts[:limit]}


# ── REST: fund flow history (Coinank-style) ───────────────────────────────────

@router.get("/fund-flow/{symbol}")
async def fund_flow(
    symbol: str,
    limit: int = Query(24, ge=5, le=100),
):
    """Coinank-style net inflow table: each row = 5-min snapshot + rolling windows."""
    rows = await get_fund_flow_history(symbol.upper(), limit)
    return {"symbol": symbol.upper(), "rows": rows}


# ── REST: signal history ──────────────────────────────────────────────────────

@router.get("/history")
async def signal_history(
    limit: int = Query(100, ge=1, le=500),
    symbol: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
):
    """Historical strong signals: score >75 (INFLOW) or <25 (OUTFLOW)."""
    data = await get_signal_history(limit, symbol, direction)
    return {"signals": data, "total": len(data)}


# ── WebSocket /ws/monitor ─────────────────────────────────────────────────────

class _MonitorWSManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def broadcast(self, data: dict):
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    @property
    def count(self) -> int:
        return len(self._clients)


_mgr = _MonitorWSManager()
_push_task: Optional[asyncio.Task] = None


async def _push_loop():
    while True:
        try:
            if _mgr.count > 0:
                tokens = get_monitor_snapshot(_states)
                await _mgr.broadcast({"type": "snapshot", "tokens": tokens, "total": len(tokens)})
        except Exception as e:
            log.error(f"Monitor WS push error: {e}")
        await asyncio.sleep(5)


@router.websocket("/ws/monitor")
async def monitor_ws(websocket: WebSocket):
    global _push_task
    await _mgr.connect(websocket)

    if _push_task is None or _push_task.done():
        _push_task = asyncio.create_task(_push_loop())

    try:
        tokens = get_monitor_snapshot(_states)
        await websocket.send_json({"type": "snapshot", "tokens": tokens, "total": len(tokens)})
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.debug(f"Monitor WS client error: {e}")
    finally:
        _mgr.disconnect(websocket)
