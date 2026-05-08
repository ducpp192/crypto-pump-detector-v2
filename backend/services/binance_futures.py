"""
Binance Futures enrichment — funding rate, open interest, liquidations.
Runs on its own task every FUTURES_ENRICH_SECONDS.

Data flow:
  1. Fetch OI history from Binance (limit=20, 5m candles = ~100 min)
     → on first call, seeds state.oi_history with historical points
     → on subsequent calls, appends the latest point only
  2. Fetch current funding rate (premiumIndex endpoint)
     → appended to state.funding_history for divergence detection
  3. Call oi_tracker.compute_oi_metrics(state) to derive all analytics
  4. Bybit is used as OI fallback when Binance returns no data
"""
import asyncio
import logging
import time
from typing import Optional, Set

import aiohttp

from models.token_state import OISnapshot, TokenState
from config import BINANCE_FUTURES_BASE
from services.rate_limiter import acquire as _rl_acquire

log = logging.getLogger(__name__)

BYBIT_BASE = "https://api.bybit.com"

_session: Optional[aiohttp.ClientSession] = None
_futures_symbols: Set[str] = set()
_futures_loaded = False


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def load_futures_symbols() -> Set[str]:
    global _futures_symbols, _futures_loaded
    if _futures_loaded:
        return _futures_symbols
    session = await _get_session()
    try:
        async with session.get(
            f"{BINANCE_FUTURES_BASE}/fapi/v1/exchangeInfo",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            if r.status != 200:
                return set()
            data = await r.json()
        _futures_symbols = {
            s["baseAsset"].upper()
            for s in data.get("symbols", [])
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"
        }
        _futures_loaded = True
        log.info(f"Futures: {len(_futures_symbols)} perpetual pairs loaded")
    except Exception as e:
        log.error(f"load_futures_symbols: {e}")
    return _futures_symbols


# ─────────────────────────────────────────────────────────────────────────────
# Main enrichment function
# ─────────────────────────────────────────────────────────────────────────────

async def enrich_futures(state: TokenState) -> None:
    """Populate funding rate, OI history, and liquidation data on state."""
    syms = await load_futures_symbols()
    if state.symbol not in syms:
        async with state.lock:
            state.has_futures = False
        return

    symbol = f"{state.symbol}USDT"
    session = await _get_session()

    async def _get(url: str, params=None) -> Optional[dict | list]:
        await _rl_acquire()
        try:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 429:
                    log.warning(f"Futures rate limited for {symbol}")
                    await asyncio.sleep(30)
                    return None
                return await r.json() if r.status == 200 else None
        except Exception:
            return None

    # Parallel fetch: funding rate + OI history
    fr_task  = asyncio.create_task(
        _get(f"{BINANCE_FUTURES_BASE}/fapi/v1/premiumIndex", {"symbol": symbol})
    )
    oi_task  = asyncio.create_task(
        _get(
            f"{BINANCE_FUTURES_BASE}/futures/data/openInterestHist",
            {"symbol": symbol, "period": "5m", "limit": 20},
        )
    )

    fr_data, oi_hist = await asyncio.gather(fr_task, oi_task, return_exceptions=True)

    # ── Funding rate ──────────────────────────────────────────────────
    funding: Optional[float] = None
    if isinstance(fr_data, dict):
        try:
            funding = float(fr_data.get("lastFundingRate", 0))
        except Exception:
            pass

    # ── OI history snapshots ──────────────────────────────────────────
    oi_snapshots: list[OISnapshot] = []

    if isinstance(oi_hist, list) and len(oi_hist) >= 2:
        for entry in oi_hist:
            try:
                ts_ms  = int(entry.get("timestamp", 0))
                oi_val = float(entry.get("sumOpenInterestValue", 0))
                if ts_ms > 0 and oi_val > 0:
                    oi_snapshots.append(OISnapshot(
                        timestamp=ts_ms / 1000.0,
                        oi_usd=oi_val,
                        source="binance",
                    ))
            except Exception:
                pass

    # ── Bybit fallback — OI + funding rate trong 1 call ─────────────
    if not oi_snapshots or funding is None:
        bybit_data = await _fetch_bybit_ticker(session, symbol)
        if bybit_data is not None:
            bybit_oi, bybit_fr = bybit_data
            if not oi_snapshots and bybit_oi and bybit_oi > 0:
                oi_snapshots.append(OISnapshot(
                    timestamp=time.time(),
                    oi_usd=bybit_oi,
                    source="bybit",
                ))
            # Dùng Bybit funding nếu Binance không trả về
            if funding is None and bybit_fr is not None:
                funding = bybit_fr
                log.debug(f"Bybit funding fallback {state.symbol}: {bybit_fr:.6f}")

    # ── Liquidations — estimated from OI drop + price move ───────────
    # (allForceOrders endpoint costs weight=20/call, too expensive for bulk scanning)
    liq_detected = False
    liq_side: Optional[str] = None

    if oi_snapshots and len(oi_snapshots) >= 2:
        old_v = oi_snapshots[0].oi_usd
        new_v = oi_snapshots[-1].oi_usd
        oi_change_pct = (new_v - old_v) / old_v * 100 if old_v > 0 else 0.0
        if oi_change_pct < -3.0:
            p1h = state.price_change_1h_pct
            if p1h > 2.0:
                liq_detected, liq_side = True, "short"
            elif p1h < -2.0:
                liq_detected, liq_side = True, "long"

    # ── Update state ──────────────────────────────────────────────────
    async with state.lock:
        state.has_futures = True

        # Funding rate + history
        state.funding_rate = funding
        if funding is not None:
            state.funding_history.append((time.time(), funding))

        # OI history: seed on first call, append latest on subsequent calls
        if oi_snapshots:
            if len(state.oi_history) == 0:
                # First call — seed with all historical points (deduped by ts)
                seen_ts: set[float] = set()
                for snap in oi_snapshots:
                    if snap.timestamp not in seen_ts:
                        state.oi_history.append(snap)
                        seen_ts.add(snap.timestamp)
            else:
                # Subsequent calls — only add if this snapshot is newer
                latest_snap = oi_snapshots[-1]
                last_in_hist = state.oi_history[-1]
                if latest_snap.timestamp > last_in_hist.timestamp:
                    state.oi_history.append(latest_snap)

        # Liquidation
        state.liquidation_detected = liq_detected
        state.liquidation_side     = liq_side
        state.last_futures_update  = time.time()

        # Run OI analytics in-place (inside lock — pure computation, no I/O)
        from services.oi_tracker import compute_oi_metrics
        compute_oi_metrics(state)


# ─────────────────────────────────────────────────────────────────────────────
# Bybit fallback
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_bybit_oi(
    session: aiohttp.ClientSession, symbol: str
) -> Optional[float]:
    """
    Fetch current OI in USD from Bybit linear perpetuals ticker.
    Returns None on any failure — this is a best-effort fallback only.
    """
    result = await _fetch_bybit_ticker(session, symbol)
    if result is None:
        return None
    return result[0]  # oi_usd


async def _fetch_bybit_ticker(
    session: aiohttp.ClientSession, symbol: str
) -> Optional[tuple[float, Optional[float]]]:
    """
    Fetch OI + funding rate từ Bybit ticker trong 1 call.
    Returns (oi_usd, funding_rate) hoặc None nếu lỗi.
    """
    try:
        async with session.get(
            f"{BYBIT_BASE}/v5/market/tickers",
            params={"category": "linear", "symbol": symbol},
            timeout=aiohttp.ClientTimeout(total=4),
        ) as r:
            if r.status != 200:
                return None
            data = await r.json()
            items = data.get("result", {}).get("list", [])
            if not items:
                return None
            item = items[0]
            oi_val = float(item.get("openInterestValue", 0) or 0)
            fr_str = item.get("fundingRate", None)
            fr_val = float(fr_str) if fr_str not in (None, "", "0") else None
            return (oi_val if oi_val > 0 else 0.0, fr_val)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Score helpers (called by signal_engine)
# ─────────────────────────────────────────────────────────────────────────────

def compute_funding_score(funding_rate: Optional[float], price_change_1h: float = 0.0) -> float:
    """
    Funding rate score with price-direction context.

    The naive formula (FR > 0 = bearish) misses real pumps which ALWAYS
    come with rising funding (traders leveraging into the move).

    Logic:
      FR > 0 + price rising  → longs are correct → continuation → bullish-ish
      FR > 0 + price flat    → longs paying for nothing → bearish
      FR < 0 + any direction → crowded shorts → squeeze potential → bullish
      FR ≈ 0                 → neutral
    """
    if funding_rate is None:
        return 50.0

    fr = max(-0.003, min(0.003, funding_rate))

    # Strongly negative FR → crowded shorts → squeeze fuel (most bullish)
    if fr < -0.001:
        return float(50.0 + (-fr / 0.003) * 50.0)   # 67–100

    # Positive FR + price is actively pumping → momentum confirmation
    if fr > 0.001 and price_change_1h > 1.5:
        return float(min(70.0, 55.0 + (price_change_1h - 1.5) * 5))  # 55–70

    # Positive FR + price flat or dropping → crowded longs paying for nothing
    if fr > 0.001:
        return float(50.0 + (-fr / 0.003) * 35.0)   # 15–50 (bearish)

    return 50.0


def compute_oi_score(oi_change_pct: Optional[float], price_change_1h: float) -> float:
    if oi_change_pct is None:
        return 50.0
    oi_up   = oi_change_pct > 1.0
    oi_down = oi_change_pct < -3.0
    p_up    = price_change_1h > 0.5
    p_down  = price_change_1h < -0.5

    if oi_up and p_up:     return 80.0
    if oi_up and p_down:   return 25.0
    if oi_up:              return 60.0
    if oi_down and p_up:   return 90.0
    if oi_down and p_down: return 10.0
    return 50.0


def compute_liquidation_score(state: TokenState) -> float:
    if not state.liquidation_detected:
        return 50.0
    return 90.0 if state.liquidation_side == "short" else 10.0
