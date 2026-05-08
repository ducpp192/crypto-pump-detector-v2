"""
Binance REST enrichment — klines, orderbook, ticker.
Uses httpx with connection pooling + semaphore rate limiting.
Adapted from pump-scanner BinanceRestClient with 15m klines added.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from models.token_state import TokenState
from config import (
    BINANCE_SPOT_BASE,
    REST_CONCURRENCY,
    CANDLES_1M, CANDLES_5M, CANDLES_15M, ORDERBOOK_DEPTH,
    VOLUME_SPIKE_RECENT_CANDLES, VOLUME_SPIKE_BASELINE_CANDLES,
)
from services.rate_limiter import acquire as _rl_acquire

log = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5


class BinanceRestClient:
    def __init__(self, semaphore: Optional[asyncio.Semaphore] = None) -> None:
        self._sem = semaphore or asyncio.Semaphore(REST_CONCURRENCY)
        self._http: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "BinanceRestClient":
        self._http = httpx.AsyncClient(
            base_url=BINANCE_SPOT_BASE,
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()

    async def enrich_token(self, state: TokenState) -> None:
        """Populate all REST-sourced spot fields on state."""
        symbol = f"{state.symbol}USDT"

        k1m_t = asyncio.create_task(self._get("/api/v3/klines", {"symbol": symbol, "interval": "1m", "limit": CANDLES_1M}))
        k5m_t = asyncio.create_task(self._get("/api/v3/klines", {"symbol": symbol, "interval": "5m", "limit": CANDLES_5M}))
        k15m_t = asyncio.create_task(self._get("/api/v3/klines", {"symbol": symbol, "interval": "15m", "limit": CANDLES_15M}))
        ob_t = asyncio.create_task(self._get("/api/v3/depth", {"symbol": symbol, "limit": ORDERBOOK_DEPTH}))
        tk_t = asyncio.create_task(self._get("/api/v3/ticker/24hr", {"symbol": symbol}))

        k1m, k5m, k15m, ob, ticker = await asyncio.gather(k1m_t, k5m_t, k15m_t, ob_t, tk_t, return_exceptions=True)

        p1m, mom1m, avg_vol, h20, l20, rec_vol = _parse_klines_1m(k1m if isinstance(k1m, list) else [])
        p5m, mom5m = _parse_klines_5m(k5m if isinstance(k5m, list) else [])
        p15m, mom15m, ema5, ema9, ema21, rsi_val, breakout, p15m_ago = _parse_klines_15m(k15m if isinstance(k15m, list) else [])
        cur_price, p1h, change24h_pct = _parse_ticker(ticker if isinstance(ticker, dict) else {})
        imbalance, bid, ask, spread = _parse_orderbook(ob if isinstance(ob, dict) else {})

        async with state.lock:
            if cur_price > 0:
                state.price = cur_price
            if p1m > 0:
                state.price_1m_ago = p1m
            if p5m > 0:
                state.price_5m_ago = p5m
            # Prefer 15m klines (4 × 15m = 60 min ago) over rough ticker estimate
            if p15m > 0:
                state.price_1h_ago = p15m
            elif p1h > 0:
                state.price_1h_ago = p1h
            if p15m_ago > 0:
                state.price_15m_ago = p15m_ago
            if change24h_pct != 0.0:
                state.price_change_24h_pct = change24h_pct
            if h20 > 0:
                state.high_20 = h20
            if l20 > 0:
                state.low_20 = l20
            if avg_vol > 0:
                state.avg_volume_1m = avg_vol
            if rec_vol > 0:
                state.recent_volume = rec_vol
            state.momentum_1m = mom1m
            state.momentum_5m = max(mom5m, mom15m, key=abs) if mom5m != 0 else mom15m
            state.imbalance = imbalance
            state.best_bid = bid
            state.best_ask = ask
            state.spread_pct = spread
            # Store EMA/RSI/breakout for signal engine
            state._ema_bullish = ema5 > ema9 > ema21 if ema21 > 0 else None
            state._ema_bearish = ema5 < ema9 < ema21 if ema21 > 0 else None
            state._rsi = rsi_val
            state._breakout = breakout
            state.last_rest_update = time.time()

    async def _get(self, path: str, params: Dict = None) -> Any:
        assert self._http is not None
        for attempt in range(1, _MAX_RETRIES + 1):
            await _rl_acquire()          # global rate limiter
            try:
                r = await self._http.get(path, params=params)
                if r.status_code in (429, 418):
                    wait = float(r.headers.get("Retry-After", 30))
                    log.warning(f"Rate limited! Sleeping {wait}s")
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    await asyncio.sleep(_BACKOFF_BASE ** attempt)
                else:
                    return None
            except (httpx.RequestError, httpx.TimeoutException):
                await asyncio.sleep(_BACKOFF_BASE ** attempt)
        log.debug("_get %s failed after %d retries", path, _MAX_RETRIES)
        return None


# ── Parse helpers ─────────────────────────────────────────────────────────────

def _parse_klines_1m(klines: list) -> Tuple[float, float, float, float, float, float]:
    """
    Parse 1m klines.

    Volume spike logic (5m vs 1h):
      - recent_vol = avg volume của VOLUME_SPIKE_RECENT_CANDLES nến hoàn chỉnh gần nhất
                     (tức nến [-RECENT-1 : -1], loại bỏ nến đang hình thành)
      - avg_vol    = avg volume của VOLUME_SPIKE_BASELINE_CANDLES nến TRƯỚC đó
                     (không overlap với recent → không self-referential)
      - Cần ít nhất RECENT + BASELINE + 1 nến (nến đang hình thành)

    Trả về: (price_1m_ago, mom_1m, avg_vol_baseline, high_20, low_20, recent_vol)
    """
    R = VOLUME_SPIKE_RECENT_CANDLES    # 5
    B = VOLUME_SPIKE_BASELINE_CANDLES  # 60
    min_needed = R + B + 1             # 66 (nến đang hình thành + recent + baseline)

    if len(klines) < 2:
        return 0, 0, 0, 0, 0, 0
    try:
        closes  = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        highs   = [float(k[2]) for k in klines]
        lows    = [float(k[3]) for k in klines]

        p1m   = closes[-2]
        mom1m = (closes[-1] - p1m) / p1m * 100 if p1m > 0 else 0

        if len(klines) >= min_needed:
            # Nến đang hình thành = [-1], bỏ qua
            # Recent: nến [-R-1 : -1]  (R nến hoàn chỉnh gần nhất)
            # Baseline: nến [-R-B-1 : -R-1]  (B nến trước đó, không overlap)
            recent_vols   = volumes[-R - 1 : -1]          # 5 nến gần nhất
            baseline_vols = volumes[-R - B - 1 : -R - 1]  # 60 nến baseline

            recent_vol = sum(recent_vols) / len(recent_vols)
            avg_vol    = sum(baseline_vols) / len(baseline_vols)
        else:
            # Không đủ dữ liệu baseline: fallback sang avg toàn bộ (trừ nến đang hình thành)
            complete    = volumes[:-1]
            recent_vol  = complete[-1] if complete else 0
            avg_vol     = sum(complete) / max(len(complete), 1)

        return p1m, mom1m, avg_vol, max(highs), min(lows), recent_vol
    except Exception:
        return 0, 0, 0, 0, 0, 0


def _parse_klines_5m(klines: list) -> Tuple[float, float]:
    if len(klines) < 2:
        return 0, 0
    try:
        closes = [float(k[4]) for k in klines]
        p5m = closes[-2]
        return p5m, (closes[-1] - p5m) / p5m * 100 if p5m > 0 else 0
    except Exception:
        return 0, 0


def _parse_klines_15m(klines: list):
    """Returns (price_1h_ago, mom15m, ema5, ema9, ema21, rsi, breakout, price_15m_ago)."""
    if len(klines) < 22:
        return 0, 0, 0, 0, 0, 50.0, False, 0
    try:
        import numpy as np

        closes = np.array([float(k[4]) for k in klines])
        highs  = np.array([float(k[2]) for k in klines])

        # EMA
        def ema(s, p):
            k = 2 / (p + 1)
            r = np.zeros_like(s)
            r[0] = s[0]
            for i in range(1, len(s)):
                r[i] = s[i] * k + r[i-1] * (1-k)
            return r

        e5  = ema(closes, 5)[-1]
        e9  = ema(closes, 9)[-1]
        e21 = ema(closes, 21)[-1]

        # RSI(9)
        deltas = np.diff(closes)
        gains  = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_g  = np.mean(gains[-9:])
        avg_l  = np.mean(losses[-9:])
        rsi    = 100 - (100 / (1 + avg_g / avg_l)) if avg_l > 0 else 100.0

        # Breakout above 12-candle high
        breakout = closes[-1] > np.max(highs[-13:-1]) if len(highs) >= 13 else False

        # price 60m ago (4 × 15m candles back)
        p1h_ago = closes[-4] if len(closes) >= 4 else closes[-2]
        mom15m  = (closes[-1] - p1h_ago) / p1h_ago * 100 if p1h_ago > 0 else 0

        # price 15m ago (previous completed candle)
        p15m_ago = closes[-2] if len(closes) >= 2 else 0.0

        return p1h_ago, mom15m, e5, e9, e21, float(rsi), bool(breakout), p15m_ago
    except Exception:
        return 0, 0, 0, 0, 0, 50.0, False, 0


def _parse_ticker(ticker: dict) -> Tuple[float, float, float]:
    """Returns (current_price, price_1h_ago_estimate, price_change_24h_pct)."""
    try:
        price = float(ticker.get("lastPrice") or 0)
        change24_pct = float(ticker.get("priceChangePercent") or 0)  # e.g. 5.23 (%)
        if price <= 0:
            return 0, 0, 0.0
        # Rough estimate: price 1h ago from 24h change rate
        change24_frac = change24_pct / 100
        hourly = change24_frac / 24
        p1h = price / (1 + hourly) if (1 + hourly) != 0 else price
        return price, p1h, change24_pct
    except Exception:
        return 0, 0, 0.0


def _parse_orderbook(ob: dict) -> Tuple[float, float, float, float]:
    try:
        bids = ob.get("bids", [])
        asks = ob.get("asks", [])
        if not bids or not asks:
            return 1.0, 0, 0, 0
        bid = float(bids[0][0])
        ask = float(asks[0][0])
        bv  = sum(float(b[1]) for b in bids)
        av  = sum(float(a[1]) for a in asks)
        imb = max(0.01, min(100.0, bv / av)) if av > 0 else 1.0
        spread = (ask - bid) / bid * 100 if bid > 0 else 0
        return imb, bid, ask, spread
    except Exception:
        return 1.0, 0, 0, 0
