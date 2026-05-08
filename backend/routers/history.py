"""
History router — REST endpoints for saved signal history.

GET /api/history         → paginated list of saved signals
GET /api/history/stats   → win-rate / accuracy stats by signal type
"""
from fastapi import APIRouter, Query
from typing import Optional
from services import signal_history

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def list_history(
    signal_type: str          = Query("all",   description="PUMP|DUMP|SHORT_SQUEEZE|LONG_SQUEEZE|all"),
    min_score:   float        = Query(75.0,    ge=0, le=100),
    has_outcome: Optional[str]= Query(None,    description="4h | 24h | pending"),
    limit:       int          = Query(200,     ge=1, le=1000),
    offset:      int          = Query(0,       ge=0),
):
    """Return saved signals matching filters, sorted by time desc."""
    rows = await signal_history.get_history(
        signal_type=signal_type,
        min_score=min_score,
        has_outcome=has_outcome,
        limit=limit,
        offset=offset,
    )
    return {"records": rows, "count": len(rows)}


@router.get("/stats")
async def history_stats():
    """
    Win-rate and average PnL per signal type.
    win_rate_4h  = % of signals where price was higher 4h  later (for PUMP/SQZ)
    win_rate_24h = % of signals where price was higher 24h later
    """
    return await signal_history.get_stats()
