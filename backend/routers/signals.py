from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from services.scanner import get_dashboard_state

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/signals")
async def get_signals(
    min_score: float = Query(0.0, ge=0, le=100),
    max_score: float = Query(100.0, ge=0, le=100),
    signal_type: str = Query("all"),
    squeeze_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
):
    state = get_dashboard_state()
    signals = state.signals

    # Filters
    if squeeze_only:
        signals = [s for s in signals if s.short_squeeze or s.long_squeeze]
    elif signal_type != "all":
        signals = [s for s in signals if s.signal == signal_type.upper()]

    signals = [s for s in signals if min_score <= s.score <= max_score]
    signals = signals[:limit]

    return {
        "signals": [s.model_dump() for s in signals],
        "last_updated": state.last_updated.isoformat(),
        "total_scanned": state.total_scanned,
        "alerts_triggered": state.alerts_triggered,
    }


@router.get("/signals/{symbol}")
async def get_token_signal(symbol: str):
    state = get_dashboard_state()
    symbol = symbol.upper()
    match = next((s for s in state.signals if s.symbol == symbol), None)
    if not match:
        return JSONResponse(status_code=404, content={"error": f"{symbol} not found"})
    return match.model_dump()


@router.get("/status")
async def get_status():
    state = get_dashboard_state()
    return {
        "last_updated": state.last_updated.isoformat(),
        "total_scanned": state.total_scanned,
        "signal_counts": {
            "PUMP": sum(1 for s in state.signals if s.signal == "PUMP"),
            "DUMP": sum(1 for s in state.signals if s.signal == "DUMP"),
            "SHORT_SQUEEZE": sum(1 for s in state.signals if s.short_squeeze),
            "LONG_SQUEEZE": sum(1 for s in state.signals if s.long_squeeze),
            "NEUTRAL": sum(1 for s in state.signals if s.signal == "NEUTRAL"),
        },
    }
