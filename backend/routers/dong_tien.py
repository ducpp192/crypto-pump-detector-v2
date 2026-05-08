"""
Dòng Tiền Router — Money Flow Alert endpoints.

Endpoints:
  GET /api/dong-tien/alerts          — list of scoring alerts (from cache)
  GET /api/dong-tien/detail/{symbol} — full detail including 5m sparkline bars
  GET /api/dong-tien/refresh         — manual trigger (dev/debug)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from services.dong_tien_service import (
    get_cached_alerts,
    is_cache_fresh,
    run_dong_tien_scan,
    set_cache,
    _cache,
)

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dong-tien", tags=["DongTien"])


# ── GET /api/dong-tien/alerts ─────────────────────────────────────────────────

@router.get("/alerts")
async def get_dong_tien_alerts(
    min_score: float = Query(default=55, ge=0, le=100, description="Minimum composite score"),
    limit:     int   = Query(default=30,  ge=1, le=200, description="Max alerts to return"),
):
    """
    Return money-flow alerts from cache.
    Cache is populated every 90s by the background task.
    If cache is empty (cold start), triggers a live fetch once.
    """
    # Cold-start: if cache has never been filled, do a blocking fetch
    if not _cache["alerts"] and not _cache["meta"]:
        log.info("DongTien cache cold — running blocking scan")
        try:
            alerts, meta = await run_dong_tien_scan(min_score=min_score)
            set_cache(alerts, meta)
        except Exception as e:
            log.error(f"DongTien cold scan failed: {e}", exc_info=True)
            return {
                "alerts": [],
                "meta": {
                    "total": 0,
                    "last_updated": None,
                    "data_sources": [],
                    "coinank_available": False,
                    "cache_fresh": False,
                    "error": str(e),
                },
            }

    alerts, meta = get_cached_alerts(min_score=min_score, limit=limit)

    return {
        "alerts": alerts,
        "meta": {
            **meta,
            "cache_fresh": is_cache_fresh(),
        },
    }


# ── GET /api/dong-tien/detail/{symbol} ───────────────────────────────────────

@router.get("/detail/{symbol}")
async def get_dong_tien_detail(symbol: str):
    """
    Return full detail for a single symbol including 5m flow bars for sparkline.
    Reads from cache first; if not found, returns 404.
    """
    sym = symbol.upper().replace("USDT", "")

    # Search cache
    match = next(
        (a for a in _cache.get("alerts", []) if a.get("symbol") == sym),
        None,
    )

    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol {sym} not in current DongTien alerts. "
                   f"It may not meet the score threshold or market cap filter.",
        )

    # Augment with 5m sparkline bars from a live detail fetch (best-effort)
    import aiohttp
    from services.dong_tien_service import (
        COINANK_BASE, COINANK_HEADERS,
    )

    sparkline_bars: list = []
    try:
        async with aiohttp.ClientSession() as session:
            url    = f"{COINANK_BASE}/fundSwap/getFundDetail"
            params = {"coinName": sym, "period": 5, "limit": 24}
            async with session.get(
                url, params=params, headers=COINANK_HEADERS,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as r:
                if r.status == 200:
                    raw  = await r.json(content_type=None)
                    bars = raw.get("data", {}).get("list") or []
                    sparkline_bars = [
                        {
                            "time":     b.get("time"),
                            "fund_in":  float(b.get("fundIn",  0)),
                            "fund_out": float(b.get("fundOut", 0)),
                            "net_fund": float(b.get("netFund", 0)),
                        }
                        for b in bars
                    ]
    except Exception as e:
        log.debug(f"DongTien detail sparkline fetch failed for {sym}: {e}")

    return {
        **match,
        "sparkline_5m": sparkline_bars,
    }


# ── GET /api/dong-tien/refresh ────────────────────────────────────────────────

@router.get("/refresh")
async def manual_refresh(min_score: float = Query(default=55, ge=0, le=100)):
    """
    Manually trigger a full scan and refresh cache.
    Intended for development / debugging.
    """
    log.info("DongTien manual refresh triggered")
    try:
        alerts, meta = await run_dong_tien_scan(min_score=min_score)
        set_cache(alerts, meta)
        return {
            "status":  "ok",
            "scanned": len(alerts),
            "meta":    meta,
        }
    except Exception as e:
        log.error(f"DongTien manual refresh error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
