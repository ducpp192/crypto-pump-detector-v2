"""
Flow History — SQLite storage for periodic flow snapshots and strong signal alerts.

Tables:
  flow_snapshots : every-5-min data for all tokens (kept 3 days)
  flow_alerts    : tokens with score >75 or <25 (kept 30 days)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

DB_PATH = "flow_history.db"
log = logging.getLogger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────────

_SQL_CREATE = """
CREATE TABLE IF NOT EXISTS flow_snapshots (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol    TEXT  NOT NULL,
    ts        REAL  NOT NULL,
    score     REAL  NOT NULL,
    net_flow  REAL  NOT NULL,
    price     REAL  NOT NULL,
    buy_ratio REAL  NOT NULL,
    vol_spike REAL  NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snap ON flow_snapshots (symbol, ts DESC);

CREATE TABLE IF NOT EXISTS flow_alerts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol   TEXT NOT NULL,
    ts       REAL NOT NULL,
    score    REAL NOT NULL,
    direction TEXT NOT NULL,
    price    REAL NOT NULL,
    net_flow REAL NOT NULL,
    smart_signals TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert ON flow_alerts (ts DESC);
"""


async def init_flow_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in _SQL_CREATE.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await db.execute(stmt)
        await db.commit()
    log.info("Flow history DB ready: %s", DB_PATH)


# ── Snapshot save ─────────────────────────────────────────────────────────────

def _net_flow_usd(state) -> float:
    """Approximate 5-min net USD inflow via recent volume × net direction."""
    return state.recent_volume * (2.0 * state.buy_ratio - 1.0)


async def save_flow_snapshots(states: Dict[str, Any]) -> int:
    from services.monitor_service import compute_flow_score, detect_smart_signals

    ts = time.time()
    snap_rows: List[tuple] = []
    alert_rows: List[tuple] = []

    for sym, state in states.items():
        if state.price <= 0:
            continue
        score = compute_flow_score(state, "5m")["flow_score"]
        net_flow = _net_flow_usd(state)

        snap_rows.append((sym, ts, score, net_flow, state.price, state.buy_ratio, state.volume_spike_pct))

        if score > 75 or score < 25:
            direction = "INFLOW" if score >= 60 else "OUTFLOW"
            signals_str = ",".join(detect_smart_signals(state))
            alert_rows.append((sym, ts, score, direction, state.price, net_flow, signals_str))

    if not snap_rows:
        return 0

    cutoff_snap  = ts - 3 * 86400   # keep 3 days of snapshots
    cutoff_alert = ts - 30 * 86400  # keep 30 days of alerts

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO flow_snapshots (symbol,ts,score,net_flow,price,buy_ratio,vol_spike) VALUES (?,?,?,?,?,?,?)",
            snap_rows,
        )
        if alert_rows:
            await db.executemany(
                "INSERT INTO flow_alerts (symbol,ts,score,direction,price,net_flow,smart_signals) VALUES (?,?,?,?,?,?,?)",
                alert_rows,
            )
        await db.execute("DELETE FROM flow_snapshots WHERE ts < ?", (cutoff_snap,))
        await db.execute("DELETE FROM flow_alerts WHERE ts < ?", (cutoff_alert,))
        await db.commit()

    return len(snap_rows)


# ── Fund flow history (Coinank-style) ─────────────────────────────────────────

async def get_fund_flow_history(symbol: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Return rows for Coinank-style table.
    Each row = one 5-min snapshot + rolling sums for 15m/30m/1h/4h/1d.
    """
    fetch_limit = limit + 288  # need extra rows for rolling 1d window

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT ts, net_flow, score, price FROM flow_snapshots WHERE symbol=? ORDER BY ts DESC LIMIT ?",
            (symbol, fetch_limit),
        )
        rows = list(reversed(await cur.fetchall()))  # ascending

    if not rows:
        return []

    total = len(rows)
    start = max(0, total - limit)
    result: List[Dict[str, Any]] = []

    for i in range(start, total):
        def roll(n: int) -> float:
            s = max(0, i - n + 1)
            return sum(rows[j]["net_flow"] for j in range(s, i + 1))

        result.append({
            "ts":       rows[i]["ts"],
            "time":     datetime.fromtimestamp(rows[i]["ts"]).strftime("%m-%d %H:%M"),
            "score":    round(rows[i]["score"], 1),
            "price":    rows[i]["price"],
            "flow_5m":  round(roll(1)),
            "flow_15m": round(roll(3)),
            "flow_30m": round(roll(6)),
            "flow_1h":  round(roll(12)),
            "flow_4h":  round(roll(48)),
            "flow_1d":  round(roll(288)),
        })

    return list(reversed(result))  # most recent first


# ── Signal history ────────────────────────────────────────────────────────────

async def get_signal_history(
    limit: int = 100,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM flow_alerts"
    params: List[Any] = []
    conds: List[str] = []

    if symbol:
        conds.append("symbol = ?")
        params.append(symbol.upper())
    if direction and direction.upper() in ("INFLOW", "OUTFLOW"):
        conds.append("direction = ?")
        params.append(direction.upper())

    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()

    return [
        {
            "symbol":       r["symbol"],
            "ts":           r["ts"],
            "time":         datetime.fromtimestamp(r["ts"]).strftime("%m-%d %H:%M"),
            "score":        r["score"],
            "direction":    r["direction"],
            "price":        r["price"],
            "net_flow":     r["net_flow"],
            "smart_signals": r["smart_signals"].split(",") if r["smart_signals"] else [],
        }
        for r in rows
    ]
