"""
Binance Spot service — price, volume, klines, order book, trade tape.
"""
import asyncio
import logging
from typing import Optional
import aiohttp
import numpy as np
from config import BINANCE_SPOT_BASE, MIN_VOLUME_24H

logger = logging.getLogger(__name__)

_session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


# ─── Ticker ───────────────────────────────────────────────────────────────────

async def get_ticker_24h(symbol: str) -> Optional[dict]:
    session = await get_session()
    url = f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr"
    try:
        async with session.get(url, params={"symbol": f"{symbol}USDT"}, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            return await r.json()
    except Exception as e:
        logger.debug(f"ticker 24h {symbol}: {e}")
        return None


async def get_all_tickers() -> list[dict]:
    """Bulk fetch all USDT tickers in one call."""
    session = await get_session()
    url = f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return []
            data = await r.json()
            return [t for t in data if t["symbol"].endswith("USDT")]
    except Exception as e:
        logger.error(f"get_all_tickers: {e}")
        return []


# ─── Klines ───────────────────────────────────────────────────────────────────

async def get_klines(symbol: str, interval: str = "5m", limit: int = 50) -> Optional[list]:
    """Returns list of OHLCV arrays."""
    session = await get_session()
    url = f"{BINANCE_SPOT_BASE}/api/v3/klines"
    params = {"symbol": f"{symbol}USDT", "interval": interval, "limit": limit}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            return await r.json()
    except Exception as e:
        logger.debug(f"klines {symbol} {interval}: {e}")
        return None


def parse_klines(raw: list) -> dict:
    """Parse raw klines into numpy arrays."""
    if not raw:
        return {}
    opens = np.array([float(k[1]) for k in raw])
    highs = np.array([float(k[2]) for k in raw])
    lows = np.array([float(k[3]) for k in raw])
    closes = np.array([float(k[4]) for k in raw])
    volumes = np.array([float(k[5]) for k in raw])
    return {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}


# ─── Technical Indicators ─────────────────────────────────────────────────────

def ema(series: np.ndarray, period: int) -> np.ndarray:
    k = 2 / (period + 1)
    result = np.zeros_like(series)
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = series[i] * k + result[i - 1] * (1 - k)
    return result


def rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_momentum_score(klines_5m: list, klines_15m: list) -> float:
    """
    Returns 0–100 momentum score based on EMA alignment + RSI.
    >50 = bullish bias, <50 = bearish bias.
    """
    k5 = parse_klines(klines_5m)
    if not k5:
        return 50.0

    closes = k5["close"]
    if len(closes) < 21:
        return 50.0

    e5 = ema(closes, 5)
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)

    # EMA alignment
    bullish_ema = (e5[-1] > e9[-1] > e21[-1])
    bearish_ema = (e5[-1] < e9[-1] < e21[-1])

    rsi_val = rsi(closes, period=9)

    # Base score from RSI
    score = rsi_val  # 0–100

    # Adjust for EMA
    if bullish_ema:
        score = min(100, score + 15)
    elif bearish_ema:
        score = max(0, score - 15)

    # Breakout detection: last close > highest high of previous 10 candles
    if len(closes) >= 12:
        prev_high = np.max(k5["high"][-12:-1])
        prev_low = np.min(k5["low"][-12:-1])
        if closes[-1] > prev_high:
            score = min(100, score + 10)
        elif closes[-1] < prev_low:
            score = max(0, score - 10)

    return float(score)


# ─── Volume Spike ─────────────────────────────────────────────────────────────

def compute_volume_spike(ticker: dict, klines_5m: list) -> tuple[float, float]:
    """
    Returns (score 0–100, spike_pct).
    spike_pct: current 5m volume vs average 5m volume derived from 24h.
    """
    if not ticker or not klines_5m:
        return 50.0, 0.0

    k5 = parse_klines(klines_5m)
    if not k5 or len(k5["volume"]) < 10:
        return 50.0, 0.0

    avg_5m_vol = float(ticker.get("quoteVolume", 0)) / (24 * 12)  # 24h / 288 5m candles
    if avg_5m_vol == 0:
        return 50.0, 0.0

    recent_vol = np.mean(k5["volume"][-3:])  # avg of last 3 candles
    spike_ratio = recent_vol / avg_5m_vol
    spike_pct = (spike_ratio - 1) * 100

    # Score: 50 = no spike, 100 = 3x+ spike, 0 = very low volume
    if spike_ratio >= 3.0:
        score = 100.0
    elif spike_ratio >= 2.0:
        score = 75.0 + (spike_ratio - 2.0) * 25.0
    elif spike_ratio >= 1.0:
        score = 50.0 + (spike_ratio - 1.0) * 25.0
    else:
        score = max(0.0, 50.0 * spike_ratio)

    return float(score), float(spike_pct)


# ─── Order Book ───────────────────────────────────────────────────────────────

async def get_order_book(symbol: str, limit: int = 20) -> Optional[dict]:
    session = await get_session()
    url = f"{BINANCE_SPOT_BASE}/api/v3/depth"
    try:
        async with session.get(url, params={"symbol": f"{symbol}USDT", "limit": limit}, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            return await r.json()
    except Exception as e:
        logger.debug(f"order_book {symbol}: {e}")
        return None


def compute_order_book_score(book: dict) -> float:
    """
    Returns 0–100.
    >50 = bid dominance (bullish), <50 = ask dominance (bearish).
    """
    if not book:
        return 50.0
    bids = book.get("bids", [])
    asks = book.get("asks", [])
    if not bids or not asks:
        return 50.0

    bid_vol = sum(float(b[1]) for b in bids[:10])
    ask_vol = sum(float(a[1]) for a in asks[:10])
    total = bid_vol + ask_vol
    if total == 0:
        return 50.0

    ratio = bid_vol / total  # 0–1
    score = ratio * 100
    return float(score)


# ─── Trade Flow ───────────────────────────────────────────────────────────────

async def get_recent_trades(symbol: str, limit: int = 200) -> Optional[list]:
    session = await get_session()
    url = f"{BINANCE_SPOT_BASE}/api/v3/trades"
    try:
        async with session.get(url, params={"symbol": f"{symbol}USDT", "limit": limit}, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            return await r.json()
    except Exception as e:
        logger.debug(f"recent_trades {symbol}: {e}")
        return None


def compute_trade_flow_score(trades: list) -> float:
    """
    Returns 0–100 based on buy vs sell pressure.
    isBuyerMaker=False → taker buy (aggressive buyer).
    """
    if not trades:
        return 50.0

    buy_vol = sum(float(t["qty"]) for t in trades if not t.get("isBuyerMaker", True))
    sell_vol = sum(float(t["qty"]) for t in trades if t.get("isBuyerMaker", True))
    total = buy_vol + sell_vol
    if total == 0:
        return 50.0

    ratio = buy_vol / total  # 0–1
    return float(ratio * 100)
