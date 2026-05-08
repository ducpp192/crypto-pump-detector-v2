"""
Dòng Tiền Service — Money Flow Scanner.

Fetches fund flow data from Coinank + L/S ratio from Bybit,
scores each coin using a composite algorithm, and returns
"smart money accumulation" alerts.

Data sources:
  1. Coinank /api/fundSwap/getFundList  — hourly net fund flow
  2. Coinank /api/fundSwap/getFundDetail — 5m consistency bars
  3. Bybit   /v5/market/account-ratio    — big holder L/S ratio
  4. _states (scanner.py)               — price, market_cap, funding_rate, buy_ratio

Cache: 60 seconds (set DONG_TIEN_CACHE_TTL env to override).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import aiohttp

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

COINANK_BASE = "https://coinank.com/api"
BYBIT_BASE   = "https://api.bybit.com/v5/market"

COINANK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://coinank.com/",
    "Accept":  "application/json, text/plain, */*",
    "Origin":  "https://coinank.com",
}

CACHE_TTL            = 60      # seconds
MIN_MARKET_CAP       = 0              # không giới hạn dưới
MAX_MARKET_CAP       = 999_000_000_000  # không giới hạn trên
MIN_SCORE            = 0              # hiển thị hết
MAX_CONCURRENT_BYBIT = 5
BYBIT_BATCH_DELAY    = 0.2            # seconds between batches

# ── Module-level cache ────────────────────────────────────────────────────────

_cache: Dict = {
    "alerts":     [],
    "meta":       {},
    "updated_at": 0.0,
}

# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class DongTienAlert:
    symbol: str
    name: str
    price: float
    price_change_1h: float
    market_cap: float

    # Fund flow
    fund_inflow_usd: float
    fund_outflow_usd: float
    fund_net_usd: float
    flow_ratio_pct: float          # net / market_cap * 100
    flow_consistency_pct: float    # % of 5m bars with positive netFund

    # Long/Short data
    big_holder_long_ratio: float   # 0–1
    big_holder_short_ratio: float
    retail_long_ratio: float
    retail_short_ratio: float
    squeeze_setup: bool            # retail short AND big holder long

    # Funding
    funding_rate: Optional[float]

    # Score components
    score: float
    flow_ratio_score: float
    consistency_score: float
    smart_money_score: float
    squeeze_score: float
    funding_score: float
    price_quiet_score: float

    # Classification
    signal_type: str               # ACCUMULATION | SQUEEZE_SETUP | BREAKOUT_READY | WATCH
    alert_reasons: List[str]

    timestamp: str

    # Price delta values (absolute $, not %) — default sau tất cả non-default fields
    price_delta_5m: float = 0.0    # price - price_5m_ago
    price_delta_15m: float = 0.0   # price - price_15m_ago
    price_delta_1h: float = 0.0    # price - price_1h_ago

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "price_change_1h": self.price_change_1h,
            "market_cap": self.market_cap,
            "price_delta_5m": self.price_delta_5m,
            "price_delta_15m": self.price_delta_15m,
            "price_delta_1h": self.price_delta_1h,
            "fund_inflow_usd": self.fund_inflow_usd,
            "fund_outflow_usd": self.fund_outflow_usd,
            "fund_net_usd": self.fund_net_usd,
            "flow_ratio_pct": self.flow_ratio_pct,
            "flow_consistency_pct": self.flow_consistency_pct,
            "big_holder_long_ratio": self.big_holder_long_ratio,
            "big_holder_short_ratio": self.big_holder_short_ratio,
            "retail_long_ratio": self.retail_long_ratio,
            "retail_short_ratio": self.retail_short_ratio,
            "squeeze_setup": self.squeeze_setup,
            "funding_rate": self.funding_rate,
            "score": self.score,
            "flow_ratio_score": self.flow_ratio_score,
            "consistency_score": self.consistency_score,
            "smart_money_score": self.smart_money_score,
            "squeeze_score": self.squeeze_score,
            "funding_score": self.funding_score,
            "price_quiet_score": self.price_quiet_score,
            "signal_type": self.signal_type,
            "alert_reasons": self.alert_reasons,
            "timestamp": self.timestamp,
        }


# ── Scoring ───────────────────────────────────────────────────────────────────

def _flow_ratio_score(flow_ratio_pct: float) -> float:
    """35% weight: net inflow as % of market cap."""
    if flow_ratio_pct >= 5.0:  return 100.0
    if flow_ratio_pct >= 2.0:  return 80.0
    if flow_ratio_pct >= 0.5:  return 60.0
    if flow_ratio_pct >= 0.1:  return 40.0
    return 20.0


def _consistency_score(pct_positive_bars: float) -> float:
    """25% weight: % of last 12 5m bars with positive net fund."""
    if pct_positive_bars >= 80: return 100.0
    if pct_positive_bars >= 60: return 75.0
    if pct_positive_bars >= 40: return 50.0
    return 20.0


def _smart_money_score(long_ratio: float) -> float:
    """20% weight: big holder long ratio (Bybit)."""
    if long_ratio >= 0.60: return 100.0
    if long_ratio >= 0.55: return 80.0
    if long_ratio >= 0.50: return 60.0
    return 20.0


def _squeeze_setup_score(retail_short: float, big_holder_long: float) -> float:
    """10% weight: classic squeeze setup."""
    if retail_short > 0.55 and big_holder_long > 0.55:
        return 100.0
    return 0.0


def _funding_score(funding_rate: Optional[float]) -> float:
    """5% weight: funding rate near 0 or negative = good."""
    if funding_rate is None:
        return 60.0   # neutral if unknown
    fr_pct = funding_rate * 100   # convert to %
    if -0.05 <= fr_pct <= 0.05:  return 100.0
    if -0.10 <= fr_pct <= 0.10:  return 70.0
    return 30.0


def _price_quiet_score(price_change_1h: float) -> float:
    """5% weight: price hasn't pumped yet."""
    abs_chg = abs(price_change_1h)
    if abs_chg < 1.0: return 100.0
    if abs_chg < 3.0: return 70.0
    if abs_chg < 5.0: return 40.0
    return 10.0


def compute_dong_tien_score(
    flow_ratio_pct: float,
    consistency_pct: float,
    big_holder_long: float,
    retail_short: float,
    funding_rate: Optional[float],
    price_change_1h: float,
) -> Tuple[float, float, float, float, float, float, float]:
    """
    Returns (composite_score, flow_ratio_s, consistency_s, smart_money_s,
             squeeze_s, funding_s, price_quiet_s).
    Weights: 35% + 25% + 20% + 10% + 5% + 5% = 100%
    """
    frs  = _flow_ratio_score(flow_ratio_pct)
    cs   = _consistency_score(consistency_pct)
    sms  = _smart_money_score(big_holder_long)
    sqzs = _squeeze_setup_score(retail_short, big_holder_long)
    fns  = _funding_score(funding_rate)
    pqs  = _price_quiet_score(price_change_1h)

    composite = (
        frs  * 0.35 +
        cs   * 0.25 +
        sms  * 0.20 +
        sqzs * 0.10 +
        fns  * 0.05 +
        pqs  * 0.05
    )
    return composite, frs, cs, sms, sqzs, fns, pqs


def _classify_signal(
    squeeze_setup: bool,
    score: float,
    flow_ratio_pct: float,
    price_change_1h: float,
    consistency_pct: float,
) -> Tuple[str, List[str]]:
    reasons: List[str] = []

    if squeeze_setup and score >= 70:
        reasons.append("Big holder long + retail short")
        return "SQUEEZE_SETUP", reasons

    if flow_ratio_pct >= 2.0 and abs(price_change_1h) < 2.0:
        reasons.append(f"Net inflow {flow_ratio_pct:.1f}% of mktcap, price quiet")
        if consistency_pct >= 60:
            reasons.append(f"Consistent flow {consistency_pct:.0f}% bars positive")
        return "ACCUMULATION", reasons

    if flow_ratio_pct >= 1.0 and consistency_pct >= 70:
        reasons.append(f"Breakout ready: flow {flow_ratio_pct:.1f}%, consistency {consistency_pct:.0f}%")
        return "BREAKOUT_READY", reasons

    if flow_ratio_pct >= 0.5:
        reasons.append(f"Moderate inflow {flow_ratio_pct:.2f}% mktcap")
    if squeeze_setup:
        reasons.append("Squeeze setup forming")

    return "WATCH", reasons


# ── Coinank API ───────────────────────────────────────────────────────────────

async def _fetch_coinank_fund_list(
    session: aiohttp.ClientSession,
) -> Optional[List[dict]]:
    """
    Fetch 1h net fund flow for all tokens from Coinank.
    Returns list of {coinName, fundIn, fundOut, netFund, ...} or None on error.
    """
    url = f"{COINANK_BASE}/fundSwap/getFundList"
    params = {
        "pageSize":  100,
        "pageIndex": 1,
        "coinNames": "",
        "period":    60,
    }
    try:
        async with session.get(
            url, params=params, headers=COINANK_HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
        ) as r:
            if r.content_type and "json" not in r.content_type:
                body = await r.text()
                log.warning(f"Coinank fund list returned non-JSON ({r.status}): {body[:120]}")
                return None
            if r.status != 200:
                log.warning(f"Coinank fund list HTTP {r.status}")
                return None
            raw = await r.json(content_type=None)
            return raw.get("data", {}).get("list") or raw.get("data") or []
    except asyncio.TimeoutError:
        log.warning("Coinank fund list timeout")
        return None
    except Exception as e:
        log.warning(f"Coinank fund list error: {e}")
        return None


async def _fetch_coinank_fund_detail(
    session: aiohttp.ClientSession,
    coin_name: str,
) -> Optional[List[dict]]:
    """
    Fetch last 12 5m bars for a single coin.
    Returns list of {time, fundIn, fundOut, netFund} or None.
    """
    url = f"{COINANK_BASE}/fundSwap/getFundDetail"
    params = {
        "coinName": coin_name,
        "period":   5,
        "limit":    12,
    }
    try:
        async with session.get(
            url, params=params, headers=COINANK_HEADERS,
            timeout=aiohttp.ClientTimeout(total=6),
        ) as r:
            if r.status != 200:
                return None
            raw = await r.json(content_type=None)
            return raw.get("data", {}).get("list") or []
    except Exception as e:
        log.debug(f"Coinank fund detail {coin_name} error: {e}")
        return None


# ── Bybit L/S ratio ───────────────────────────────────────────────────────────

async def _fetch_bybit_ls_ratio(
    session: aiohttp.ClientSession,
    symbol: str,
    semaphore: asyncio.Semaphore,
) -> Optional[dict]:
    """
    Fetch big holder (account) L/S ratio from Bybit for one symbol.
    Returns {buy_ratio, sell_ratio} or None.
    """
    async with semaphore:
        url = f"{BYBIT_BASE}/account-ratio"
        params = {
            "category": "linear",
            "symbol":   f"{symbol}USDT",
            "period":   "1h",
            "limit":    1,
        }
        try:
            async with session.get(
                url, params=params,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status != 200:
                    return None
                raw = await r.json(content_type=None)
                items = raw.get("result", {}).get("list", [])
                if not items:
                    return None
                item = items[0]
                buy  = float(item.get("buyRatio",  0.5))
                sell = float(item.get("sellRatio", 0.5))
                return {"buy_ratio": buy, "sell_ratio": sell}
        except Exception as e:
            log.debug(f"Bybit L/S {symbol} error: {e}")
            return None


# ── Main scan logic ───────────────────────────────────────────────────────────

async def run_dong_tien_scan(min_score: float = MIN_SCORE) -> Tuple[List[dict], dict]:
    """
    Full scan:
    1. Pull token_states from scanner for price/market_cap/funding_rate/buy_ratio
    2. Fetch Coinank fund list
    3. For matching coins, fetch 5m consistency detail
    4. Fetch Bybit L/S ratio
    5. Score & filter
    Returns (alerts_list_of_dicts, meta_dict)
    """
    # Late import to avoid circular dependency
    from services.scanner import _states

    now_iso = datetime.now(timezone.utc).isoformat()
    coinank_available = True
    data_sources = ["scanner_states"]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BYBIT)

    async with aiohttp.ClientSession() as session:
        # ── Step 1: Coinank fund list ─────────────────────────────────────
        fund_list = await _fetch_coinank_fund_list(session)
        if fund_list is None:
            coinank_available = False
            log.warning("Coinank unavailable — using fallback estimation")
        else:
            data_sources.append("coinank")

        # ── Step 2: Build fund map: coinName -> fund data ─────────────────
        fund_map: Dict[str, dict] = {}
        if coinank_available and fund_list:
            for entry in fund_list:
                coin = entry.get("coinName", "").upper()
                if coin:
                    fund_map[coin] = entry

        # ── Step 3: Determine candidate symbols ───────────────────────────
        # We only process tokens tracked by scanner that pass market cap filter
        candidates = []
        for sym, state in _states.items():
            mc = getattr(state, "market_cap", 0) or 0
            if mc < MIN_MARKET_CAP or mc > MAX_MARKET_CAP:
                continue
            if getattr(state, "price", 0) <= 0:
                continue
            candidates.append((sym, state))

        if not candidates:
            log.info("DongTien: no candidates after market cap filter")
            return [], {
                "total": 0,
                "last_updated": now_iso,
                "data_sources": data_sources,
                "coinank_available": coinank_available,
            }

        # ── Step 4: Fetch 5m consistency for coins in Coinank ────────────
        # Only fetch detail for coins that matched in fund_map
        detail_map: Dict[str, float] = {}   # sym -> consistency_pct
        if coinank_available:
            detail_tasks = []
            detail_syms  = []
            for sym, _ in candidates:
                if sym in fund_map:
                    detail_syms.append(sym)
                    detail_tasks.append(
                        _fetch_coinank_fund_detail(session, sym)
                    )
            if detail_tasks:
                detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)
                for sym, result in zip(detail_syms, detail_results):
                    if isinstance(result, list) and result:
                        positive = sum(
                            1 for bar in result
                            if float(bar.get("netFund", 0)) > 0
                        )
                        detail_map[sym] = (positive / len(result)) * 100
                    elif not isinstance(result, Exception):
                        detail_map[sym] = 50.0   # neutral fallback

        # ── Step 5: Bybit L/S ratio for all candidates ────────────────────
        bybit_tasks = []
        bybit_syms  = []
        for sym, _ in candidates:
            bybit_syms.append(sym)
            bybit_tasks.append(
                _fetch_bybit_ls_ratio(session, sym, semaphore)
            )

        # Batch with delay
        bybit_map: Dict[str, dict] = {}
        batch_size = MAX_CONCURRENT_BYBIT
        for i in range(0, len(bybit_tasks), batch_size):
            batch_syms    = bybit_syms[i : i + batch_size]
            batch_results = await asyncio.gather(
                *bybit_tasks[i : i + batch_size], return_exceptions=True
            )
            for sym, result in zip(batch_syms, batch_results):
                if isinstance(result, dict) and result:
                    bybit_map[sym] = result
            if i + batch_size < len(bybit_tasks):
                await asyncio.sleep(BYBIT_BATCH_DELAY)

        if bybit_map:
            data_sources.append("bybit_ls")

    # ── Step 6: Score each candidate ─────────────────────────────────────
    alerts: List[DongTienAlert] = []

    for sym, state in candidates:
        price          = float(getattr(state, "price", 0) or 0)
        price_chg_1h   = float(getattr(state, "price_change_1h_pct", 0) or 0)
        market_cap     = float(getattr(state, "market_cap", 0) or 0)
        funding_rate   = getattr(state, "funding_rate", None)
        buy_ratio_raw  = float(getattr(state, "buy_ratio", 0.5) or 0.5)
        volume_24h     = float(getattr(state, "volume_24h", 0) or 0)
        name           = getattr(state, "name", sym) or sym

        # Price delta (absolute dollar value)
        price_5m_ago   = float(getattr(state, "price_5m_ago", 0) or 0)
        price_15m_ago  = float(getattr(state, "price_15m_ago", 0) or 0)
        price_1h_ago   = float(getattr(state, "price_1h_ago", 0) or 0)
        delta_5m  = round(price - price_5m_ago, 8)  if price_5m_ago  > 0 else 0.0
        delta_15m = round(price - price_15m_ago, 8) if price_15m_ago > 0 else 0.0
        delta_1h  = round(price - price_1h_ago, 8)  if price_1h_ago  > 0 else 0.0

        # ── Fund flow data ─────────────────────────────────────────────
        if coinank_available and sym in fund_map:
            fd = fund_map[sym]
            fund_in  = float(fd.get("fundIn",  0) or 0)
            fund_out = float(fd.get("fundOut", 0) or 0)
            net_fund = float(fd.get("netFund", 0) or 0)
        else:
            # Fallback: estimate from buy_ratio + volume
            if buy_ratio_raw > 0.6:
                net_fund = volume_24h * 0.01 * buy_ratio_raw
            else:
                net_fund = -volume_24h * 0.01 * (1.0 - buy_ratio_raw)
            # Split roughly 60/40 in/out
            if net_fund >= 0:
                fund_in  = net_fund * 1.5
                fund_out = net_fund * 0.5
            else:
                fund_in  = abs(net_fund) * 0.3
                fund_out = abs(net_fund) * 1.3

        # Skip coins with no positive inflow
        # if net_fund <= 0:
        #     continue

        flow_ratio_pct = (net_fund / market_cap * 100) if market_cap > 0 else 0.0

        # ── Consistency ────────────────────────────────────────────────
        if sym in detail_map:
            consistency_pct = detail_map[sym]
        elif coinank_available:
            consistency_pct = 50.0   # unknown for this coin
        else:
            # Fallback from trade_flow_score
            tfs = float(getattr(state, "trade_flow_score", 50) or 50)
            consistency_pct = min(100.0, max(0.0, tfs))

        # ── Bybit L/S ──────────────────────────────────────────────────
        if sym in bybit_map:
            big_holder_long  = bybit_map[sym]["buy_ratio"]
            big_holder_short = bybit_map[sym]["sell_ratio"]
        else:
            # Fallback: use scanner buy_ratio as proxy
            big_holder_long  = buy_ratio_raw
            big_holder_short = 1.0 - buy_ratio_raw

        # For retail L/S, invert big holder (whales vs retail often diverge)
        # We use buy_ratio from WS as retail proxy
        retail_long  = buy_ratio_raw
        retail_short = 1.0 - buy_ratio_raw

        squeeze_setup = retail_short > 0.55 and big_holder_long > 0.55

        # ── Score ──────────────────────────────────────────────────────
        score, frs, cs, sms, sqzs, fns, pqs = compute_dong_tien_score(
            flow_ratio_pct  = flow_ratio_pct,
            consistency_pct = consistency_pct,
            big_holder_long = big_holder_long,
            retail_short    = retail_short,
            funding_rate    = funding_rate,
            price_change_1h = price_chg_1h,
        )

        # if score < min_score:
        #     continue

        # ── Signal classification ─────────────────────────────────────
        signal_type, reasons = _classify_signal(
            squeeze_setup   = squeeze_setup,
            score           = score,
            flow_ratio_pct  = flow_ratio_pct,
            price_change_1h = price_chg_1h,
            consistency_pct = consistency_pct,
        )

        alerts.append(DongTienAlert(
            symbol              = sym,
            name                = name,
            price               = round(price, 8),
            price_change_1h     = round(price_chg_1h, 4),
            market_cap          = round(market_cap, 2),
            price_delta_5m      = delta_5m,
            price_delta_15m     = delta_15m,
            price_delta_1h      = delta_1h,
            fund_inflow_usd     = round(fund_in, 2),
            fund_outflow_usd    = round(fund_out, 2),
            fund_net_usd        = round(net_fund, 2),
            flow_ratio_pct      = round(flow_ratio_pct, 4),
            flow_consistency_pct= round(consistency_pct, 2),
            big_holder_long_ratio  = round(big_holder_long, 4),
            big_holder_short_ratio = round(big_holder_short, 4),
            retail_long_ratio   = round(retail_long, 4),
            retail_short_ratio  = round(retail_short, 4),
            squeeze_setup       = squeeze_setup,
            funding_rate        = funding_rate,
            score               = round(score, 2),
            flow_ratio_score    = round(frs, 2),
            consistency_score   = round(cs, 2),
            smart_money_score   = round(sms, 2),
            squeeze_score       = round(sqzs, 2),
            funding_score       = round(fns, 2),
            price_quiet_score   = round(pqs, 2),
            signal_type         = signal_type,
            alert_reasons       = reasons,
            timestamp           = now_iso,
        ))

    # Sort by score descending
    alerts.sort(key=lambda a: a.score, reverse=True)

    meta = {
        "total":            len(alerts),
        "last_updated":     now_iso,
        "data_sources":     data_sources,
        "coinank_available": coinank_available,
    }

    log.info(
        f"DongTien scan done: {len(alerts)} alerts "
        f"(coinank={'ok' if coinank_available else 'fallback'}, "
        f"bybit={len(bybit_map)} symbols)"
    )
    return [a.to_dict() for a in alerts], meta


# ── Cache helpers ─────────────────────────────────────────────────────────────

def get_cached_alerts(min_score: float = MIN_SCORE, limit: int = 30) -> Tuple[List[dict], dict]:
    """Return cached alerts filtered by min_score and limited to limit."""
    alerts = [a for a in _cache["alerts"] if a.get("score", 0) >= min_score]
    return alerts[:limit], _cache["meta"]


def set_cache(alerts: List[dict], meta: dict) -> None:
    _cache["alerts"]     = alerts
    _cache["meta"]       = meta
    _cache["updated_at"] = time.time()


def is_cache_fresh() -> bool:
    return (time.time() - _cache["updated_at"]) < CACHE_TTL


# ── Background refresh task ───────────────────────────────────────────────────

async def dong_tien_refresh_task() -> None:
    """
    Background task — runs every 90 seconds, refreshes the module-level cache.
    Registered in main.py lifespan.
    """
    log.info("DongTien refresh task started")
    # Initial delay — let scanner populate _states first
    await asyncio.sleep(30)

    while True:
        try:
            alerts, meta = await run_dong_tien_scan()
            set_cache(alerts, meta)
        except Exception as e:
            log.error(f"DongTien refresh error: {e}", exc_info=True)

        await asyncio.sleep(90)
