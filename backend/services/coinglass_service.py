"""
Coinglass Service — Liquidation heatmap data.

Endpoints used:
  - /api/futures/liquidation/v2/chart   (public, no key needed cho BTC/ETH/etc.)
  - /api/pro/v1/futures/liquidation/detail (requires COINGLASS_API_KEY)

Fallback: nếu Coinglass fail → trả về estimated levels từ OI + price data.

Heatmap format trả về:
  {
    "symbol": "BTCUSDT",
    "source":  "coinglass" | "estimated",
    "price_levels": [
      {"price": 65000, "long_liq_usd": 12000000, "short_liq_usd": 3000000},
      ...
    ],
    "current_price": 67000,
    "total_long_liq":  95000000,
    "total_short_liq": 31000000,
  }
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

COINGLASS_BASE   = "https://open-api.coinglass.com"
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")

# Cache đơn giản: symbol → (timestamp, data) — tránh spam API
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 30   # seconds


async def fetch_liquidation_heatmap(
    symbol: str,          # e.g. "BTC" (không có USDT)
    current_price: float,
    oi_usd: Optional[float] = None,
) -> dict:
    """
    Trả về liquidation heatmap data cho 1 symbol.
    Ưu tiên Coinglass → fallback estimated nếu fail.
    """
    cache_key = symbol.upper()
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CACHE_TTL:
        return cached[1]

    data = None

    # ── Thử Coinglass public endpoint ────────────────────────────────
    try:
        data = await _fetch_coinglass_public(symbol)
    except Exception as e:
        log.warning(f"Coinglass public failed for {symbol}: {e}")

    # ── Thử Coinglass pro endpoint (nếu có API key) ──────────────────
    if data is None and COINGLASS_API_KEY:
        try:
            data = await _fetch_coinglass_pro(symbol)
        except Exception as e:
            log.warning(f"Coinglass pro failed for {symbol}: {e}")

    # ── Fallback: ước tính từ price + OI ─────────────────────────────
    if data is None:
        data = _estimate_heatmap(symbol, current_price, oi_usd)

    _cache[cache_key] = (time.time(), data)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Coinglass fetchers
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_coinglass_public(symbol: str) -> Optional[dict]:
    """
    Public endpoint — không cần API key.
    Trả về aggregated liquidation data.
    """
    # Coinglass public map: BTC → BTCUSDT trên Binance
    params = {
        "symbol":    symbol.upper(),
        "time_type": "h4",   # 4h aggregation — đủ để thấy levels
        "ex":        "Binance",
    }
    headers = {"accept": "application/json"}
    if COINGLASS_API_KEY:
        headers["coinglassSecret"] = COINGLASS_API_KEY

    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{COINGLASS_BASE}/api/futures/liquidation/v2/chart",
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=6),
        ) as r:
            if r.status != 200:
                return None
            raw = await r.json()

    if not raw.get("success") or not raw.get("data"):
        return None

    return _parse_coinglass_v2(symbol, raw["data"])


async def _fetch_coinglass_pro(symbol: str) -> Optional[dict]:
    """Pro endpoint với COINGLASS_API_KEY."""
    headers = {
        "accept":          "application/json",
        "coinglassSecret": COINGLASS_API_KEY,
    }
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{COINGLASS_BASE}/api/pro/v1/futures/liquidation/detail",
            params={"symbol": symbol.upper(), "interval": "4h"},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=6),
        ) as r:
            if r.status != 200:
                return None
            raw = await r.json()

    if not raw.get("success") or not raw.get("data"):
        return None

    return _parse_coinglass_pro(symbol, raw["data"])


# ─────────────────────────────────────────────────────────────────────────────
# Parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_coinglass_v2(symbol: str, data: dict) -> dict:
    """Parse Coinglass v2 chart response thành heatmap format chuẩn."""
    price_list  = data.get("priceList",    [])
    long_list   = data.get("longLiqList",  [])
    short_list  = data.get("shortLiqList", [])

    levels = []
    for i, price in enumerate(price_list):
        long_val  = long_list[i]  if i < len(long_list)  else 0
        short_val = short_list[i] if i < len(short_list) else 0
        levels.append({
            "price":         float(price),
            "long_liq_usd":  float(long_val)  * 1_000_000,
            "short_liq_usd": float(short_val) * 1_000_000,
        })

    total_long  = sum(l["long_liq_usd"]  for l in levels)
    total_short = sum(l["short_liq_usd"] for l in levels)

    return {
        "symbol":          symbol.upper(),
        "source":          "coinglass",
        "price_levels":    levels,
        "current_price":   levels[len(levels) // 2]["price"] if levels else 0,
        "total_long_liq":  total_long,
        "total_short_liq": total_short,
    }


def _parse_coinglass_pro(symbol: str, data: list) -> dict:
    """Parse Coinglass pro detail response."""
    levels = []
    for entry in data:
        levels.append({
            "price":         float(entry.get("price",     0)),
            "long_liq_usd":  float(entry.get("longLiq",  0)),
            "short_liq_usd": float(entry.get("shortLiq", 0)),
        })

    total_long  = sum(l["long_liq_usd"]  for l in levels)
    total_short = sum(l["short_liq_usd"] for l in levels)

    return {
        "symbol":          symbol.upper(),
        "source":          "coinglass_pro",
        "price_levels":    levels,
        "current_price":   0,
        "total_long_liq":  total_long,
        "total_short_liq": total_short,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Estimated fallback
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_heatmap(
    symbol: str,
    current_price: float,
    oi_usd: Optional[float],
) -> dict:
    """
    Ước tính liquidation levels khi Coinglass không available.

    Logic đơn giản:
      - Tạo 20 price buckets ± 15% quanh current price
      - Long liq tập trung bên dưới current price (leverage 10x → -10%)
      - Short liq tập trung bên trên current price
      - Volume ~ bell curve quanh ±5%, ±10%, ±15%
    """
    if current_price <= 0:
        return {"symbol": symbol, "source": "estimated", "price_levels": [],
                "current_price": 0, "total_long_liq": 0, "total_short_liq": 0}

    total_oi = oi_usd or 1_000_000   # fallback $1M nếu không có OI
    # Giả sử 60% longs, 40% shorts (typical bull market bias)
    long_pool  = total_oi * 0.60
    short_pool = total_oi * 0.40

    # 20 buckets: -15% đến +15%
    buckets = 20
    step = 0.015  # 1.5% mỗi bucket
    offset_start = -0.15

    import math

    def bell(x: float, mu: float, sigma: float) -> float:
        return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

    levels = []
    total_long  = 0.0
    total_short = 0.0

    for i in range(buckets):
        offset = offset_start + i * step * 2
        price  = current_price * (1 + offset)

        # Long liq = dưới giá hiện tại (10x → -10%, 5x → -20%)
        long_weight  = bell(offset, -0.10, 0.04) + bell(offset, -0.20, 0.05)
        # Short liq = trên giá hiện tại
        short_weight = bell(offset,  0.10, 0.04) + bell(offset,  0.20, 0.05)

        long_liq  = long_pool  * long_weight  * 0.15
        short_liq = short_pool * short_weight * 0.15

        levels.append({
            "price":         round(price, 6),
            "long_liq_usd":  round(long_liq,  2),
            "short_liq_usd": round(short_liq, 2),
        })
        total_long  += long_liq
        total_short += short_liq

    return {
        "symbol":          symbol.upper(),
        "source":          "estimated",
        "price_levels":    levels,
        "current_price":   current_price,
        "total_long_liq":  round(total_long,  2),
        "total_short_liq": round(total_short, 2),
    }
