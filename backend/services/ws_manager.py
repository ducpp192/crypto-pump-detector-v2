"""
WebSocket Broadcast Manager
===========================
Central hub for all real-time WS clients.

Responsibilities:
  - Maintain active client connections with per-client filter state
  - Track per-symbol state hashes for delta detection
  - Queue and batch-flush delta updates every BATCH_MS milliseconds
  - Apply per-client filters before sending (reduces payload per client)
  - Provide heartbeats to keep connections alive

Message protocol (server → client):
  {"type": "snapshot", "signals": [...all...], "meta": {...}}   — sent once on connect
  {"type": "delta",    "updates": [...changed...], "meta": {...}} — incremental updates
  {"type": "heartbeat", "ts": float}                             — keepalive

Message protocol (client → server):
  {"filter": "PUMP"}          filter by signal type (PUMP|DUMP|SHORT_SQUEEZE|LONG_SQUEEZE|all)
  {"min_score": 70}
  {"max_score": 100}
  {"squeeze_only": true}

Design notes:
  - Delta detection: MD5 of (price, score, signal, buy_ratio, pump_detected, …)
    Only the fields that matter for trading decisions are hashed.
  - Batching: updates are queued in an asyncio.Queue and flushed every BATCH_MS.
    Multiple updates in the queue are merged (latest value per symbol wins).
  - Per-client filtering: the same delta list is filtered per-client in O(n).
    Clients watching only PUMP see only PUMP updates → minimal bandwidth.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

log = logging.getLogger(__name__)

# ── Tuning constants ──────────────────────────────────────────────────────────
BATCH_MS    = 50    # flush queue every 50 ms  → max 20 broadcasts/sec
HEARTBEAT_S = 15    # keepalive interval
QUEUE_MAX   = 1024  # increased from 128 to handle market-wide spike events


# ── Per-client state ──────────────────────────────────────────────────────────

@dataclass
class _Client:
    ws: WebSocket
    cid: int
    signal_filter: Optional[str] = None   # None = all signals
    min_score: float = 0.0
    max_score: float = 100.0
    squeeze_only: bool = False
    connected_at: float = field(default_factory=time.time)


# ── Broadcast manager ─────────────────────────────────────────────────────────

class WSBroadcastManager:
    """Singleton — import `broadcast_manager` from this module."""

    def __init__(self) -> None:
        self._clients: Dict[int, _Client] = {}
        self._next_id: int = 0

        # Delta detection: symbol → hash of volatile fields
        self._hashes: Dict[str, str] = {}

        # Latest full snapshot (given to new clients immediately on connect)
        self._snapshot: List[dict] = []
        self._meta: dict = {}

        # Pending updates waiting to be flushed
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self._running = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch background tasks. Call once at app startup."""
        self._running = True
        asyncio.create_task(self._broadcast_loop(), name="ws_broadcast_flush")
        asyncio.create_task(self._heartbeat_loop(), name="ws_heartbeat")
        log.info("WSBroadcastManager started (batch=%dms)", BATCH_MS)

    async def stop(self) -> None:
        self._running = False

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ── Client connection management ─────────────────────────────────────────

    async def connect(
        self,
        ws: WebSocket,
        signal_filter: Optional[str] = None,
        min_score: float = 0.0,
        max_score: float = 100.0,
        squeeze_only: bool = False,
    ) -> int:
        await ws.accept()
        cid = self._next_id
        self._next_id += 1
        self._clients[cid] = _Client(
            ws=ws, cid=cid,
            signal_filter=signal_filter,
            min_score=min_score,
            max_score=max_score,
            squeeze_only=squeeze_only,
        )
        log.info("WS client %d connected (total=%d)", cid, len(self._clients))

        # Send full snapshot immediately so UI shows data without waiting
        if self._snapshot:
            client = self._clients[cid]
            filtered = _apply_filter(self._snapshot, client)
            await _send(ws, {
                "type":    "snapshot",
                "signals": filtered,
                "meta":    self._meta,
            })
        return cid

    def disconnect(self, cid: int) -> None:
        self._clients.pop(cid, None)
        log.info("WS client %d disconnected (total=%d)", cid, len(self._clients))

    async def handle_message(self, cid: int, raw: str) -> None:
        """Process filter-update messages sent by the client."""
        client = self._clients.get(cid)
        if not client:
            return
        try:
            msg = json.loads(raw)
        except Exception:
            return

        if "filter" in msg:
            v = msg["filter"]
            client.signal_filter = v if v in ("PUMP","DUMP","SHORT_SQUEEZE","LONG_SQUEEZE") else None
        if "min_score" in msg:
            client.min_score = max(0.0, min(100.0, float(msg["min_score"])))
        if "max_score" in msg:
            client.max_score = max(0.0, min(100.0, float(msg["max_score"])))
        if "squeeze_only" in msg:
            client.squeeze_only = bool(msg["squeeze_only"])

    # ── Producer API (called by signal_task) ─────────────────────────────────

    async def enqueue_update(self, signals: List[dict], meta: dict) -> None:
        """
        Called after every scoring pass (every ~5s).
        Computes which tokens actually changed, queues only those.
        Non-blocking: drops oldest entry if queue is full.
        """
        # Always update snapshot + meta so new clients get fresh data
        self._snapshot = signals
        self._meta = meta

        if not self._clients:
            # No one connected — still update hashes to avoid stale baseline
            for s in signals:
                self._hashes[s["symbol"]] = _hash(s)
            return

        # Delta detection — only queue tokens whose tracked fields changed
        changed: List[dict] = []
        for s in signals:
            sym = s["symbol"]
            h = _hash(s)
            if self._hashes.get(sym) != h:
                self._hashes[sym] = h
                changed.append(s)

        if not changed:
            return   # nothing changed → skip broadcast

        entry = (changed, meta)
        if self._queue.full():
            # Merge: drain entire queue, merge all updates symbol-by-symbol,
            # re-queue as a single entry → zero signal loss on overflow.
            merged_overflow: Dict[str, dict] = {}
            while not self._queue.empty():
                try:
                    old_updates, _ = self._queue.get_nowait()
                    for u in old_updates:
                        merged_overflow[u["symbol"]] = u
                except asyncio.QueueEmpty:
                    break
            for u in changed:
                merged_overflow[u["symbol"]] = u
            self._queue.put_nowait((list(merged_overflow.values()), meta))
            return
        self._queue.put_nowait(entry)

    async def enqueue_immediate(self, signal_dict: dict) -> None:
        """
        Hot-path: push a SINGLE token update immediately (e.g. pump just detected).
        Bypasses the 5s scoring cycle for near-realtime pump alerts.
        Updates hash so the next scoring pass won't re-send the same state.
        """
        sym = signal_dict["symbol"]
        h = _hash(signal_dict)
        if self._hashes.get(sym) == h:
            return   # no change
        self._hashes[sym] = h

        entry = ([signal_dict], self._meta)
        if self._queue.full():
            # Merge like enqueue_update — drain + merge + re-queue
            merged_overflow: Dict[str, dict] = {}
            while not self._queue.empty():
                try:
                    old_updates, _ = self._queue.get_nowait()
                    for u in old_updates:
                        merged_overflow[u["symbol"]] = u
                except asyncio.QueueEmpty:
                    break
            merged_overflow[sym] = signal_dict
            self._queue.put_nowait((list(merged_overflow.values()), self._meta))
            return
        self._queue.put_nowait(entry)

    # ── Broadcast loop (consumer) ────────────────────────────────────────────

    async def _broadcast_loop(self) -> None:
        """
        Flushes the queue every BATCH_MS.
        Merges multiple queued entries (symbol dedup — latest wins).
        """
        while self._running:
            await asyncio.sleep(BATCH_MS / 1000)

            if self._queue.empty() or not self._clients:
                continue

            # Drain all pending entries, merge by symbol
            merged: Dict[str, dict] = {}
            latest_meta = self._meta
            while not self._queue.empty():
                try:
                    updates, meta = self._queue.get_nowait()
                    latest_meta = meta
                    for u in updates:
                        merged[u["symbol"]] = u
                except asyncio.QueueEmpty:
                    break

            if not merged:
                continue

            updates_list = list(merged.values())

            # Fan-out: send to each client with per-client filtering
            dead: List[int] = []
            for cid, client in list(self._clients.items()):
                filtered = _apply_filter(updates_list, client)
                if not filtered:
                    continue
                ok = await _send(client.ws, {
                    "type":    "delta",
                    "updates": filtered,
                    "meta":    latest_meta,
                })
                if not ok:
                    dead.append(cid)

            for cid in dead:
                self.disconnect(cid)

    async def _heartbeat_loop(self) -> None:
        """Periodic keepalive to detect stale connections."""
        while self._running:
            await asyncio.sleep(HEARTBEAT_S)
            if not self._clients:
                continue
            dead: List[int] = []
            for cid, client in list(self._clients.items()):
                ok = await _send(client.ws, {"type": "heartbeat", "ts": time.time()})
                if not ok:
                    dead.append(cid)
            for cid in dead:
                self.disconnect(cid)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(s: dict) -> str:
    """
    Fingerprint the volatile fields that matter for trading decisions.
    Ignores `timestamp` — we only broadcast when substance changes.
    Uses first 8 hex chars of MD5 (good enough for change detection).
    Includes OI spike + signal fields so spike events always propagate.
    """
    key = (
        f"{s.get('price', 0):.8f}"
        f"|{s.get('score', 0):.1f}"
        f"|{s.get('signal', '')}"
        f"|{s.get('buy_ratio', 0):.3f}"
        f"|{int(s.get('pump_detected', False))}"
        f"|{int(s.get('dump_detected', False))}"
        f"|{int(s.get('short_squeeze', False))}"
        f"|{int(s.get('long_squeeze', False))}"
        f"|{s.get('volume_spike_pct', 0):.1f}"
        f"|{s.get('spot_momentum_score', 0):.1f}"
        f"|{s.get('trade_flow_score', 0):.1f}"
        # OI fields — included so spikes / trend changes broadcast immediately
        f"|{int(s.get('oi_spike', False))}"
        f"|{s.get('oi_spike_score', 0)}"
        f"|{s.get('oi_trend', 'SIDEWAYS')}"
        f"|{s.get('oi_signal_type', '') or ''}"
        f"|{s.get('oi_fr_divergence', '') or ''}"
        f"|{round(s.get('oi_change_5m', 0) or 0, 1)}"
        # Crime Coin Score — broadcast when manipulation level changes
        f"|{round(s.get('crime_score', 0) or 0, 0)}"
        f"|{s.get('crime_level', '') or ''}"
    )
    return hashlib.md5(key.encode()).hexdigest()[:8]


def _apply_filter(signals: List[dict], client: _Client) -> List[dict]:
    """O(n) per-client filter before sending."""
    out = []
    for s in signals:
        score = s.get("score", 50.0)
        if score < client.min_score or score > client.max_score:
            continue
        if client.squeeze_only:
            if not (s.get("short_squeeze") or s.get("long_squeeze")):
                continue
        elif client.signal_filter:
            if s.get("signal") != client.signal_filter:
                continue
        out.append(s)
    return out


async def _send(ws: WebSocket, data: dict) -> bool:
    """Send JSON to a client. Returns False if the connection is dead."""
    try:
        if ws.client_state != WebSocketState.CONNECTED:
            log.warning("_send: client_state=%s, not CONNECTED — skipping", ws.client_state)
            return False
        await ws.send_json(data)
        return True
    except Exception as e:
        log.warning("_send failed: %r", e)
        return False


# ── Singleton export ──────────────────────────────────────────────────────────
broadcast_manager = WSBroadcastManager()
