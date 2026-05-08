"""
Signal History — SQLite log of qualifying signals (score ≥ 75, non-neutral).

Saves full snapshot at moment of signal and automatically tracks:
  - Price 4h  after signal → pnl_4h_pct
  - Price 24h after signal → pnl_24h_pct

Purpose: back-testing and iterative improvement of scoring weights.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
import aiohttp

log = logging.getLogger(__name__)

# DB path: <project_root>/data/signal_history.db
_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "signal_history.db")
)

# ── Dedup: don't save same symbol+signal within 15 min ───────────────────────
_last_saved: dict[str, float] = {}
SAVE_COOLDOWN    = 900    # seconds — 15 min
SCORE_THRESHOLD  = 60.0   # lowered from 75 → reduces survivorship bias
VALID_SIGNALS    = {"PUMP", "DUMP", "SHORT_SQUEEZE", "LONG_SQUEEZE"}

def _score_tier(score: float) -> str:
    """Tag records so we can compare outcome quality across threshold tiers."""
    if score >= 80:  return "HIGH"
    if score >= 70:  return "MED"
    return "LOW"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS signal_history (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    saved_at             TEXT    NOT NULL,
    symbol               TEXT    NOT NULL,
    name                 TEXT    NOT NULL,
    price                REAL    NOT NULL,
    price_change_1h      REAL,
    price_change_24h     REAL,
    market_cap           REAL,
    volume_24h           REAL,
    volume_spike_pct     REAL,
    spot_momentum_score  REAL,
    volume_spike_score   REAL,
    order_book_score     REAL,
    trade_flow_score     REAL,
    funding_rate_score   REAL,
    open_interest_score  REAL,
    liquidation_score    REAL,
    score                REAL    NOT NULL,
    signal               TEXT    NOT NULL,
    funding_rate         REAL,
    oi_change_pct        REAL,
    oi_usd               REAL,
    short_squeeze        INTEGER,
    long_squeeze         INTEGER,
    liquidation_detected INTEGER,
    liquidation_side     TEXT,
    buy_ratio            REAL,
    trade_freq           REAL,
    price_trend_10s      REAL,
    pump_detected        INTEGER,
    dump_detected        INTEGER,
    boost                INTEGER,
    reasons              TEXT,
    score_tier           TEXT,   -- HIGH(>=80) | MED(>=70) | LOW(>=60)
    -- Outcome columns (filled later by outcome task)
    price_4h             REAL,
    price_24h            REAL,
    pnl_4h_pct           REAL,
    pnl_24h_pct          REAL,
    outcome_4h_at        TEXT,
    outcome_24h_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_sh_saved_at ON signal_history(saved_at);
CREATE INDEX IF NOT EXISTS idx_sh_symbol   ON signal_history(symbol);
CREATE INDEX IF NOT EXISTS idx_sh_signal   ON signal_history(signal);
"""


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_db():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.executescript(_CREATE_SQL)
        # Migration: add score_tier column to existing databases that don't have it
        try:
            await db.execute("ALTER TABLE signal_history ADD COLUMN score_tier TEXT")
            await db.commit()
            log.info("Migrated signal_history: added score_tier column")
        except Exception:
            pass  # column already exists
        # score_tier index — created AFTER migration so the column is guaranteed to exist
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sh_score_tier ON signal_history(signal, score_tier)"
        )
        await db.commit()
    log.info("Signal history DB ready: %s", _DB_PATH)


# ── Save signal ───────────────────────────────────────────────────────────────

async def save_signal(signal) -> bool:
    """
    Save a TokenSignal if it qualifies.
    Returns True if saved, False if skipped (wrong type / score too low / dedup).
    """
    if signal.signal not in VALID_SIGNALS:
        return False
    if signal.score < SCORE_THRESHOLD:
        return False

    key = f"{signal.symbol}:{signal.signal}"
    now = time.time()
    if now - _last_saved.get(key, 0) < SAVE_COOLDOWN:
        return False
    _last_saved[key] = now

    saved_at     = datetime.now(timezone.utc).isoformat()
    reasons_json = json.dumps(signal.reasons or [])
    tier         = _score_tier(signal.score)

    try:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute("""
                INSERT INTO signal_history (
                    saved_at, symbol, name, price, price_change_1h, price_change_24h,
                    market_cap, volume_24h, volume_spike_pct,
                    spot_momentum_score, volume_spike_score, order_book_score,
                    trade_flow_score, funding_rate_score, open_interest_score,
                    liquidation_score, score, signal,
                    funding_rate, oi_change_pct, oi_usd,
                    short_squeeze, long_squeeze, liquidation_detected, liquidation_side,
                    buy_ratio, trade_freq, price_trend_10s,
                    pump_detected, dump_detected, boost, reasons, score_tier
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                saved_at,
                signal.symbol, signal.name,
                signal.price, signal.price_change_1h, signal.price_change_24h,
                signal.market_cap, signal.volume_24h, signal.volume_spike_pct,
                signal.spot_momentum_score, signal.volume_spike_score, signal.order_book_score,
                signal.trade_flow_score, signal.funding_rate_score, signal.open_interest_score,
                signal.liquidation_score, signal.score, signal.signal,
                signal.funding_rate, signal.oi_change_pct, signal.oi_usd,
                int(signal.short_squeeze), int(signal.long_squeeze),
                int(signal.liquidation_detected), signal.liquidation_side,
                signal.buy_ratio, signal.trade_freq, signal.price_trend_10s,
                int(signal.pump_detected), int(signal.dump_detected),
                signal.boost, reasons_json, tier,
            ))
            await db.commit()
        log.info("History saved: %s %s  score=%.1f", signal.symbol, signal.signal, signal.score)
        return True
    except Exception as e:
        log.error("save_signal error: %r", e)
        return False


# ── Outcome price fetcher ─────────────────────────────────────────────────────

async def _fetch_price(symbol: str) -> Optional[float]:
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as sess:
            async with sess.get(url) as r:
                if r.status == 200:
                    return float((await r.json())["price"])
    except Exception:
        pass
    return None


# ── Outcome tracker background task ──────────────────────────────────────────

async def update_outcomes_task():
    """
    Every 5 minutes:
      • Find records ≥ 3h50m old with no price_4h  → fetch current price, compute pnl_4h_pct
      • Find records ≥ 23h50m old with no price_24h → fetch current price, compute pnl_24h_pct
    """
    await asyncio.sleep(60)   # let system stabilise on startup
    while True:
        try:
            async with aiosqlite.connect(_DB_PATH) as db:
                db.row_factory = aiosqlite.Row

                # ── 4h outcomes ───────────────────────────────────────────
                async with db.execute("""
                    SELECT id, symbol, price FROM signal_history
                    WHERE price_4h IS NULL
                      AND saved_at <= datetime('now', '-3 hours 50 minutes')
                """) as cur:
                    rows_4h = await cur.fetchall()

                for row in rows_4h:
                    p = await _fetch_price(row["symbol"])
                    if p is None:
                        continue
                    pnl = round((p - row["price"]) / row["price"] * 100, 3)
                    await db.execute(
                        "UPDATE signal_history SET price_4h=?, pnl_4h_pct=?, outcome_4h_at=? WHERE id=?",
                        (p, pnl, datetime.now(timezone.utc).isoformat(), row["id"]),
                    )
                    log.debug("4h outcome  %s  pnl=%.2f%%", row["symbol"], pnl)

                # ── 24h outcomes ──────────────────────────────────────────
                async with db.execute("""
                    SELECT id, symbol, price FROM signal_history
                    WHERE price_24h IS NULL
                      AND saved_at <= datetime('now', '-23 hours 50 minutes')
                """) as cur:
                    rows_24h = await cur.fetchall()

                for row in rows_24h:
                    p = await _fetch_price(row["symbol"])
                    if p is None:
                        continue
                    pnl = round((p - row["price"]) / row["price"] * 100, 3)
                    await db.execute(
                        "UPDATE signal_history SET price_24h=?, pnl_24h_pct=?, outcome_24h_at=? WHERE id=?",
                        (p, pnl, datetime.now(timezone.utc).isoformat(), row["id"]),
                    )
                    log.debug("24h outcome %s  pnl=%.2f%%", row["symbol"], pnl)

                if rows_4h or rows_24h:
                    await db.commit()
                    log.info("Outcomes updated: %d @ 4h,  %d @ 24h", len(rows_4h), len(rows_24h))

        except Exception as e:
            log.error("update_outcomes_task: %r", e, exc_info=True)

        await asyncio.sleep(300)   # check every 5 minutes


# ── Query helpers ─────────────────────────────────────────────────────────────

async def get_history(
    signal_type: Optional[str] = None,
    min_score: float = 0.0,
    has_outcome: Optional[str] = None,   # "4h" | "24h" | "pending"
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    try:
        conds  = ["score >= ?"]
        params: list = [min_score]

        if signal_type and signal_type.lower() != "all":
            conds.append("signal = ?")
            params.append(signal_type.upper())

        if has_outcome == "4h":
            conds.append("price_4h IS NOT NULL")
        elif has_outcome == "24h":
            conds.append("price_24h IS NOT NULL")
        elif has_outcome == "pending":
            conds.append("(price_4h IS NULL OR price_24h IS NULL)")

        where = " AND ".join(conds)
        sql   = f"SELECT * FROM signal_history WHERE {where} ORDER BY saved_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d.get("reasons") or "[]")
            result.append(d)
        return result
    except Exception as e:
        log.error("get_history: %r", e)
        return []


async def get_stats() -> dict:
    """Win-rate / average PnL stats by signal type + score tier breakdown."""
    try:
        stats: dict = {}
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            for sig in ["PUMP", "DUMP", "SHORT_SQUEEZE", "LONG_SQUEEZE"]:
                # Overall stats for this signal type
                async with db.execute("""
                    SELECT
                        COUNT(*)                                               AS total,
                        SUM(CASE WHEN price_4h  IS NOT NULL THEN 1 ELSE 0 END) AS checked_4h,
                        SUM(CASE WHEN price_24h IS NOT NULL THEN 1 ELSE 0 END) AS checked_24h,
                        AVG(pnl_4h_pct)                                        AS avg_pnl_4h,
                        AVG(pnl_24h_pct)                                       AS avg_pnl_24h,
                        SUM(CASE WHEN pnl_4h_pct  > 0 THEN 1 ELSE 0 END)      AS win_4h,
                        SUM(CASE WHEN pnl_24h_pct > 0 THEN 1 ELSE 0 END)      AS win_24h
                    FROM signal_history WHERE signal = ?
                """, (sig,)) as cur:
                    row = dict(await cur.fetchone())
                c4  = row["checked_4h"]  or 0
                c24 = row["checked_24h"] or 0
                row["win_rate_4h"]  = round(row["win_4h"]  / c4  * 100, 1) if c4  else None
                row["win_rate_24h"] = round(row["win_24h"] / c24 * 100, 1) if c24 else None

                # Tier breakdown — compare HIGH vs MED vs LOW outcome quality
                tiers: dict = {}
                async with db.execute("""
                    SELECT
                        COALESCE(score_tier, 'HIGH') AS tier,
                        COUNT(*)                                               AS total,
                        AVG(pnl_4h_pct)                                        AS avg_pnl_4h,
                        AVG(pnl_24h_pct)                                       AS avg_pnl_24h,
                        SUM(CASE WHEN pnl_4h_pct  > 0 THEN 1 ELSE 0 END)      AS win_4h,
                        SUM(CASE WHEN price_4h IS NOT NULL THEN 1 ELSE 0 END)  AS checked_4h
                    FROM signal_history WHERE signal = ?
                    GROUP BY COALESCE(score_tier, 'HIGH')
                """, (sig,)) as cur:
                    for t in await cur.fetchall():
                        td = dict(t)
                        c = td["checked_4h"] or 0
                        td["win_rate_4h"] = round(td["win_4h"] / c * 100, 1) if c else None
                        tiers[td["tier"]] = td
                row["tiers"] = tiers
                stats[sig] = row
        return stats
    except Exception as e:
        log.error("get_stats: %r", e)
        return {}
