"""
Scanner — 6-task orchestrator (merged architecture).

Tasks:
  1. cmc_refresh_task   — every 5 min: refresh mid-cap universe, update states
  2. rest_enrich_task   — every 30s: klines + orderbook for all tokens
  3. ws_stream_task     — continuous: live trade ticks via WebSocket
  4. futures_enrich_task— every 15s: funding rate, OI, liquidations
  5. signal_task        — every 5s: full scoring pass
  6. FastAPI serves state directly (no 6th task needed)
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict

import aiohttp

from config import (
    CMC_REFRESH_SECONDS, REST_ENRICH_SECONDS,
    FUTURES_ENRICH_SECONDS, SIGNAL_SCORE_SECONDS,
    REST_BATCH_DELAY, STABLECOINS, MIN_VOLUME_24H,
    BINANCE_SPOT_BASE, SIGNAL_COOLDOWN_SECONDS,
)
from models.token_state import TokenState
from models import DashboardState
from services.cmc_service import fetch_midcap_symbols
from services.binance_rest import BinanceRestClient
from services.binance_futures import enrich_futures, load_futures_symbols
from services.binance_ws import BinanceWSManager
from services.signal_engine import score_token
from services.crime_score import compute_crime_score
from services.alert_service import check_and_send_alerts, send_hourly_report_task
from services.ws_manager import broadcast_manager
from services.signal_history import save_signal as _history_save

log = logging.getLogger(__name__)

# ── Shared state ──────────────────────────────────────────────────────────────
_states: Dict[str, TokenState] = {}

dashboard_state = DashboardState(
    signals=[],
    last_updated=datetime.now(timezone.utc),
    total_scanned=0,
    alerts_triggered=0,
)

_ws_manager: BinanceWSManager = None
_alerts_total = 0


# ── 1. CMC Refresh ────────────────────────────────────────────────────────────

async def cmc_refresh_task():
    """Refreshes the tracked symbol universe every CMC_REFRESH_SECONDS."""
    global _states, _ws_manager
    while True:
        try:
            midcap_map = await fetch_midcap_symbols()   # {symbol: market_cap_usd}
            all_tickers = await _fetch_all_tickers()
            ticker_map = {
                t["symbol"].replace("USDT", ""): t
                for t in all_tickers
                if t["symbol"].endswith("USDT")
                and t["symbol"].replace("USDT", "") not in STABLECOINS
            }

            # Build new symbol set: mid-cap ∩ Binance, with volume filter
            new_syms = {
                sym for sym in midcap_map
                if sym in ticker_map
                and float(ticker_map[sym].get("quoteVolume", 0)) >= MIN_VOLUME_24H
            }

            # Add new tokens
            for sym in new_syms - set(_states.keys()):
                t = ticker_map.get(sym, {})
                _states[sym] = TokenState(
                    symbol=sym,
                    name=sym,
                    market_cap=midcap_map.get(sym, 0.0),
                    volume_24h=float(t.get("quoteVolume", 0)),
                    price=float(t.get("lastPrice", 0)),
                )
                log.debug(f"CMC: added {sym}")

            # Update market_cap for existing tokens (refreshes every cycle)
            for sym in set(_states.keys()) & new_syms:
                mc = midcap_map.get(sym, 0.0)
                if mc > 0:
                    _states[sym].market_cap = mc

            # Remove dropped tokens
            for sym in set(_states.keys()) - new_syms:
                del _states[sym]
                log.debug(f"CMC: removed {sym}")

            # Update WS manager with new symbol set
            if _ws_manager:
                _ws_manager.update_symbols(_states)

            log.info(f"CMC refresh: {len(_states)} tokens tracked")

        except Exception as e:
            log.error(f"cmc_refresh_task: {e}", exc_info=True)

        await asyncio.sleep(CMC_REFRESH_SECONDS)


async def _fetch_all_tickers() -> list:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                return await r.json() if r.status == 200 else []
    except Exception as e:
        log.error(f"_fetch_all_tickers: {e}")
        return []


# ── 2. REST Enrich ────────────────────────────────────────────────────────────

async def rest_enrich_task():
    """Enriches all tokens with klines + orderbook every REST_ENRICH_SECONDS."""
    # Wait for CMC to populate states first
    await asyncio.sleep(5)
    async with BinanceRestClient() as client:
        while True:
            try:
                syms = list(_states.keys())
                # Rate limiter handles throttling — chạy all tasks concurrently
                tasks = [client.enrich_token(_states[s]) for s in syms if s in _states]
                await asyncio.gather(*tasks, return_exceptions=True)
                log.debug(f"REST enrich: {len(syms)} tokens done")
            except Exception as e:
                log.error(f"rest_enrich_task: {e}")
            await asyncio.sleep(REST_ENRICH_SECONDS)


# ── 3. WebSocket Stream ───────────────────────────────────────────────────────

async def ws_stream_task():
    """Maintains live WebSocket trade streams for all tracked tokens."""
    global _ws_manager
    # Wait for states to populate
    await asyncio.sleep(8)
    # Pass broadcast_manager so binance_ws can push immediate pump alerts
    _ws_manager = BinanceWSManager(_states, broadcast_manager)
    await _ws_manager.run()
    # Keep task alive — WS connections are managed as sub-tasks via create_task
    while True:
        await asyncio.sleep(60)


# ── 4. Futures Enrich ─────────────────────────────────────────────────────────

async def futures_enrich_task():
    """Enriches futures-listed tokens with FR, OI, liquidations."""
    await asyncio.sleep(10)
    await load_futures_symbols()
    while True:
        try:
            syms = list(_states.keys())
            tasks = [enrich_futures(_states[s]) for s in syms if s in _states]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.error(f"futures_enrich_task: {e}")
        await asyncio.sleep(FUTURES_ENRICH_SECONDS)


# ── 5. Signal Scoring ─────────────────────────────────────────────────────────

async def signal_task():
    """Runs full scoring pass every SIGNAL_SCORE_SECONDS."""
    global dashboard_state, _alerts_total
    await asyncio.sleep(12)
    while True:
        try:
            now = time.time()
            scored = []
            alerts_this_pass = 0

            for sym, state in list(_states.items()):
                if state.is_stale:
                    continue
                state.reset_signal()
                score_token(state)

                # Compute Crime Coin Score
                ccs = compute_crime_score(state)
                state.crime_score = ccs.score
                state.crime_level = ccs.level
                state.crime_signals = ccs.signals
                state._ccs_dict = ccs.to_dict()  # store full breakdown for _state_to_signal

                # Alert check: kiểm tra cooldown TRƯỚC khi update last_signal_time
                if now - state.last_signal_time > SIGNAL_COOLDOWN_SECONDS:
                    state.last_signal_time = now
                    triggered = await check_and_send_alerts(_state_to_signal(state))
                    alerts_this_pass += triggered
                    _alerts_total += triggered

                scored.append(state)

            scored.sort(key=lambda s: s.score, reverse=True)

            now_dt = datetime.now(timezone.utc)
            signal_list = [_state_to_signal(s) for s in scored]

            dashboard_state = DashboardState(
                signals=signal_list,
                last_updated=now_dt,
                total_scanned=len(scored),
                alerts_triggered=alerts_this_pass,
            )

            # ── Save qualifying signals to history DB ─────────────────────
            for _sig in signal_list:
                if _sig.signal in ("PUMP", "DUMP", "SHORT_SQUEEZE", "LONG_SQUEEZE") and _sig.score >= 75:
                    asyncio.create_task(_history_save(_sig))

            # ── Hourly Telegram report ────────────────────────────────────
            asyncio.create_task(send_hourly_report_task(signal_list))

            # ── Push delta updates to all WS clients ──────────────────────
            meta = {
                "total_scanned":    len(scored),
                "last_updated":     now_dt.isoformat(),
                "alerts_triggered": alerts_this_pass,
            }
            await broadcast_manager.enqueue_update(
                [s.model_dump(mode="json") for s in signal_list],
                meta,
            )

        except Exception as e:
            log.error(f"signal_task: {e}", exc_info=True)

        await asyncio.sleep(SIGNAL_SCORE_SECONDS)


def _state_to_signal(state: TokenState):
    from models import TokenSignal
    return TokenSignal(
        symbol=state.symbol,
        name=state.name,
        price=round(state.price, 8),
        price_change_1h=round(state.price_change_1h_pct, 3),
        price_change_24h=round(state.price_change_24h_pct, 3),
        market_cap=state.market_cap,
        volume_24h=round(state.volume_24h, 2),
        spot_momentum_score=state.spot_momentum_score,
        volume_spike_score=state.volume_spike_score,
        order_book_score=state.order_book_score,
        trade_flow_score=state.trade_flow_score,
        funding_rate_score=state.funding_rate_score,
        open_interest_score=state.open_interest_score,
        liquidation_score=state.liquidation_score,
        score=state.score,
        signal=state.signal,
        # Derivatives (base)
        funding_rate=state.funding_rate,
        oi_change_pct=state.oi_change_pct,
        oi_usd=state.oi_usd,
        volume_spike_pct=state.volume_spike_pct,
        short_squeeze=state.short_squeeze,
        long_squeeze=state.long_squeeze,
        liquidation_detected=state.liquidation_detected,
        liquidation_side=state.liquidation_side,
        # OI sparkline — lấy 30 điểm gần nhất từ history
        oi_sparkline=[round(s.oi_usd, 2) for s in list(state.oi_history)[-30:]] if state.oi_history else [],
        # OI enhanced metrics
        oi_change_1m=round(state.oi_change_1m, 3) if state.oi_change_1m is not None else None,
        oi_change_5m=round(state.oi_change_5m, 3) if state.oi_change_5m is not None else None,
        oi_change_15m=round(state.oi_change_15m, 3) if state.oi_change_15m is not None else None,
        oi_trend=state.oi_trend,
        oi_spike=state.oi_spike,
        oi_spike_score=state.oi_spike_score,
        oi_market_cap_ratio=state.oi_market_cap_ratio,
        oi_signal_type=state.oi_signal_type,
        oi_signal_confidence=state.oi_signal_confidence,
        oi_fr_divergence=state.oi_fr_divergence,
        # WS trade metrics
        buy_ratio=round(state.buy_ratio, 4),
        trade_freq=round(state.trade_freq, 3),
        price_trend_10s=round(state.price_trend_10s, 4),
        pump_detected=state.pump_detected,
        dump_detected=state.dump_detected,
        boost=state.boost,
        reasons=state.reasons,
        timestamp=datetime.now(timezone.utc),
        # Crime Coin Score
        crime_score=getattr(state, "crime_score", 0.0),
        crime_level=getattr(state, "crime_level", "NORMAL"),
        crime_signals=list(getattr(state, "crime_signals", [])),
        crime_oi_mc=getattr(state, "_ccs_dict", {}).get("crime_oi_mc", 0.0),
        crime_funding=getattr(state, "_ccs_dict", {}).get("crime_funding", 0.0),
        crime_oi_change=getattr(state, "_ccs_dict", {}).get("crime_oi_change", 0.0),
        crime_divergence=getattr(state, "_ccs_dict", {}).get("crime_divergence", 0.0),
        crime_flow=getattr(state, "_ccs_dict", {}).get("crime_flow", 0.0),
        crime_liquidity=getattr(state, "_ccs_dict", {}).get("crime_liquidity", 0.0),
        crime_exchange=getattr(state, "_ccs_dict", {}).get("crime_exchange", 0.0),
        crime_volatility=getattr(state, "_ccs_dict", {}).get("crime_volatility", 0.0),
    )


def get_dashboard_state() -> DashboardState:
    return dashboard_state
