"""
WebSocket endpoint: GET /ws/signals

Clients connect once and receive:
  1. Immediate full snapshot of current state
  2. Incremental delta updates as tokens change (every ~50ms flush)
  3. Periodic heartbeats every 15s

Optional query params set initial per-client filter:
  ?filter=PUMP            (PUMP | DUMP | SHORT_SQUEEZE | LONG_SQUEEZE | all)
  ?min_score=70
  ?max_score=100
  ?squeeze_only=true

Clients can also update their filter at any time by sending a JSON message:
  {"filter": "PUMP"}
  {"min_score": 60, "max_score": 100}
  {"squeeze_only": true}
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.ws_manager import broadcast_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/signals")
async def ws_signals(
    ws: WebSocket,
    filter: Optional[str] = Query(None,  description="PUMP|DUMP|SHORT_SQUEEZE|LONG_SQUEEZE"),
    min_score: float       = Query(0.0,  ge=0, le=100),
    max_score: float       = Query(100.0, ge=0, le=100),
    squeeze_only: bool     = Query(False),
) -> None:
    # Normalise filter param
    valid_filters = {"PUMP", "DUMP", "SHORT_SQUEEZE", "LONG_SQUEEZE"}
    signal_filter = filter.upper() if filter and filter.upper() in valid_filters else None

    cid = await broadcast_manager.connect(
        ws,
        signal_filter=signal_filter,
        min_score=min_score,
        max_score=max_score,
        squeeze_only=squeeze_only,
    )
    try:
        while True:
            # Keep connection alive and process inbound filter-update messages
            raw = await ws.receive_text()
            await broadcast_manager.handle_message(cid, raw)
    except WebSocketDisconnect:
        broadcast_manager.disconnect(cid)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("WS client %d error: %r", cid, e, exc_info=True)
        broadcast_manager.disconnect(cid)
