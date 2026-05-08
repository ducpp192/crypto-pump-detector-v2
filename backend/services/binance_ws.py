"""
Binance WebSocket trade-stream manager.

Subscribes to <symbol>@trade streams for all tracked tokens.
Symbols are chunked into groups of WS_MAX_PER_CONN.
Each chunk runs on a persistent connection with exponential reconnect.
Received trades are written into TokenState under the asyncio lock.

v2: accepts optional broadcast_manager to push immediate alerts when
pump_detected or dump_detected flips — bypasses the 5s scoring cycle
for near-realtime low-latency pump/dump notifications.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from models.token_state import TokenState, Trade
from config import WS_MAX_PER_CONN, WS_RECONNECT_DELAY, BINANCE_WS_BASE

if TYPE_CHECKING:
    from services.ws_manager import WSBroadcastManager

log = logging.getLogger(__name__)

_MAX_RECONNECT_DELAY = 60
_PING_INTERVAL = 20
_PING_TIMEOUT = 10

# How often to run pump/dump detection per symbol (every N trades)
_PUMP_CHECK_EVERY = 5


class BinanceWSManager:
    """Manages one or more Binance trade-stream WebSocket connections."""

    def __init__(
        self,
        states: Dict[str, TokenState],
        broadcast_manager: Optional["WSBroadcastManager"] = None,
    ) -> None:
        self._states = states
        self._broadcast = broadcast_manager
        self._tasks: List[asyncio.Task] = []
        self._subscribed_symbols: set = set()
        # Trade counter per symbol for throttled pump detection
        self._trade_counts: Dict[str, int] = {}

    async def run(self) -> None:
        """Start all connection tasks. Runs until cancelled."""
        await self._restart_connections()

    def update_symbols(self, states: Dict[str, TokenState]) -> None:
        """Hot-swap the shared state dict; restart WS if symbol set changed."""
        self._states = states
        new_syms = set(states.keys())
        added = new_syms - self._subscribed_symbols
        removed = self._subscribed_symbols - new_syms
        if added or removed:
            log.info(f"WS: symbols changed (+{len(added)} -{len(removed)}) → restarting connections")
            asyncio.create_task(self._restart_connections())

    async def _restart_connections(self) -> None:
        """Cancel existing WS tasks and start fresh with current symbol set."""
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        symbols = list(self._states.keys())
        if not symbols:
            return

        self._subscribed_symbols = set(symbols)
        chunks = [
            symbols[i:i + WS_MAX_PER_CONN]
            for i in range(0, len(symbols), WS_MAX_PER_CONN)
        ]
        self._tasks = [
            asyncio.create_task(self._connection_loop(chunk, idx))
            for idx, chunk in enumerate(chunks)
        ]
        log.info(f"WS: {len(self._tasks)} connection(s) for {len(symbols)} symbols")

    async def _connection_loop(self, symbols: List[str], conn_idx: int) -> None:
        """Persistent connection with exponential backoff on disconnect."""
        delay = WS_RECONNECT_DELAY
        streams = "/".join(f"{s.lower()}usdt@trade" for s in symbols)
        url = f"{BINANCE_WS_BASE}?streams={streams}"

        while True:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=_PING_INTERVAL,
                    ping_timeout=_PING_TIMEOUT,
                    open_timeout=15,
                ) as ws:
                    log.info(f"WS[{conn_idx}] connected ({len(symbols)} symbols)")
                    delay = WS_RECONNECT_DELAY  # reset on success
                    async for raw in ws:
                        await self._handle_message(raw)

            except asyncio.CancelledError:
                return
            except (ConnectionClosed, WebSocketException, OSError) as e:
                log.warning(f"WS[{conn_idx}] disconnected: {e} – reconnect in {delay}s")
            except Exception as e:
                log.error(f"WS[{conn_idx}] unexpected: {e}")

            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_RECONNECT_DELAY)

    async def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
            data = msg.get("data", msg)
            if data.get("e") != "trade":
                return

            symbol_full = data["s"]                # e.g. "ARBUSDT"
            symbol = symbol_full.replace("USDT", "")
            state = self._states.get(symbol)
            if state is None:
                return

            trade = Trade(
                price=float(data["p"]),
                qty=float(data["q"]),
                is_buyer_maker=bool(data["m"]),
                timestamp=time.time(),
            )
            async with state.lock:
                state.recent_trades.append(trade)
                state.price = trade.price          # keep price live from WS
                state.last_ws_trade_time = trade.timestamp

            # ── Early pump/dump detection (every N trades) ────────────────
            # Runs outside the lock to avoid blocking the WS reader.
            # Only triggers if broadcast_manager is wired up.
            if self._broadcast and self._broadcast.client_count > 0:
                cnt = self._trade_counts.get(symbol, 0) + 1
                self._trade_counts[symbol] = cnt
                if cnt % _PUMP_CHECK_EVERY == 0:
                    asyncio.create_task(
                        self._maybe_push_pump_alert(symbol, state)
                    )

        except (KeyError, ValueError, TypeError):
            pass

    async def _maybe_push_pump_alert(
        self, symbol: str, state: TokenState
    ) -> None:
        """
        Run pump/dump detection on fresh trade data.
        If the flag flipped since last check, push an immediate WS update
        rather than waiting for the next 5s scoring cycle.
        """
        from services.pump_detector import detect_pump, detect_dump, compute_buy_ratio, compute_trade_freq, compute_price_trend_pct
        from models import TokenSignal

        prev_pump = state.pump_detected
        prev_dump = state.dump_detected

        is_pump, pump_reasons = detect_pump(state)
        is_dump, dump_reasons = detect_dump(state)

        # Only push if the flag changed (avoids hammering the WS)
        if is_pump == prev_pump and is_dump == prev_dump:
            return

        state.pump_detected = is_pump
        state.dump_detected = is_dump
        if is_pump:
            state.buy_ratio = compute_buy_ratio(state.recent_trades, 50)
            state.trade_freq = compute_trade_freq(state.recent_trades, 30)
            state.price_trend_10s = compute_price_trend_pct(state.recent_trades, 10)

        log.debug(
            "Early alert %s: pump=%s→%s dump=%s→%s",
            symbol, prev_pump, is_pump, prev_dump, is_dump,
        )

        # Build a minimal signal dict with the fields that changed
        # Scores are kept from last scoring pass — only WS fields are fresh
        try:
            from models import TokenSignal
            sig = TokenSignal(
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
                funding_rate=state.funding_rate,
                oi_change_pct=state.oi_change_pct,
                oi_usd=state.oi_usd,
                volume_spike_pct=state.volume_spike_pct,
                short_squeeze=state.short_squeeze,
                long_squeeze=state.long_squeeze,
                liquidation_detected=state.liquidation_detected,
                liquidation_side=state.liquidation_side,
                buy_ratio=round(state.buy_ratio, 4),
                trade_freq=round(state.trade_freq, 3),
                price_trend_10s=round(state.price_trend_10s, 4),
                pump_detected=state.pump_detected,
                dump_detected=state.dump_detected,
                boost=state.boost,
                reasons=pump_reasons or dump_reasons or state.reasons,
                timestamp=datetime.now(timezone.utc),
            )
            await self._broadcast.enqueue_immediate(sig.model_dump(mode="json"))
        except Exception as e:
            log.debug("early push error %s: %s", symbol, e)
