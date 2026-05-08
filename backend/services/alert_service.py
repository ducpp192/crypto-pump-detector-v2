"""
Alert Service — Telegram alerts với format trực quan.

Alert types:
  🚀 Pump Alert     — pump_detected, score >= threshold
  🔴 Dump Alert     — dump_detected
  🔥 OI Spike       — oi_spike_score >= 40
  ⚡ Squeeze        — short/long squeeze
  📊 Hourly Report  — top 10 OI coins mỗi giờ
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    PUMP_SCORE_THRESHOLD,
    DUMP_SCORE_THRESHOLD,
)
from models import TokenSignal

logger = logging.getLogger(__name__)

# ── Cooldown per symbol ───────────────────────────────────────────────────────

COOLDOWN_SECS = {
    "pump":    300,   # 5 phút
    "dump":    300,
    "oi":      600,   # 10 phút
    "squeeze": 600,
    "crime":   1800,  # 30 phút
}
_cooldown: dict[str, float] = {}   # "type:symbol" → timestamp


def _in_cooldown(sym: str, alert_type: str) -> bool:
    key = f"{alert_type}:{sym}"
    return (time.time() - _cooldown.get(key, 0)) < COOLDOWN_SECS.get(alert_type, 300)


def _mark(sym: str, alert_type: str) -> None:
    _cooldown[f"{alert_type}:{sym}"] = time.time()


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_price(p: float) -> str:
    if p >= 1:     return f"${p:.4f}"
    if p >= 0.01:  return f"${p:.5f}"
    return f"${p:.8f}"


def _fmt_vol(v: float) -> str:
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    if v >= 1e6:  return f"${v/1e6:.1f}M"
    if v >= 1e3:  return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def _pct(v: Optional[float], plus: bool = True) -> str:
    if v is None: return "—"
    sign = "+" if (plus and v >= 0) else ""
    return f"{sign}{v:.1f}%"


def _fr(v: Optional[float]) -> str:
    if v is None: return "—"
    pct = v * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.4f}%"


def _time_utc() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M UTC")


# ── Core send ─────────────────────────────────────────────────────────────────

_send_times: list[float] = []


async def _send(text: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False

    # Throttle: max 20 msg/phút
    now = time.time()
    while _send_times and now - _send_times[0] > 60:
        _send_times.pop(0)
    if len(_send_times) >= 20:
        logger.warning("Telegram throttled")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    _send_times.append(time.time())
                    return True
                body = await r.text()
                logger.warning(f"Telegram {r.status}: {body[:100]}")
                return False
    except Exception as e:
        logger.warning(f"Telegram error: {e}")
        return False


# ── Alert builders ────────────────────────────────────────────────────────────

def _build_pump(s: TokenSignal) -> str:
    oi  = s.oi_usd or 0
    vol = s.volume_24h or 0
    chg_1h = s.price_change_1h or 0
    chg_24 = s.price_change_24h or 0
    return (
        f"🚀 <b>Pump Alert</b>  {_time_utc()}\n"
        f"\n"
        f"<b>{s.symbol}</b>\n"
        f"Tăng: <b>{_pct(chg_1h)}</b> (1h) | <b>{_pct(chg_24)}</b> (24h)\n"
        f"Giá: <b>{_fmt_price(s.price)}</b>\n"
        f"OI: {_fmt_vol(oi)} | Vol 24h: {_fmt_vol(vol)}\n"
        f"Funding: {_fr(s.funding_rate)} | Score: <b>{s.score:.0f}/100</b>"
    )


def _build_dump(s: TokenSignal) -> str:
    oi  = s.oi_usd or 0
    vol = s.volume_24h or 0
    chg_1h = s.price_change_1h or 0
    chg_24 = s.price_change_24h or 0
    return (
        f"🔴 <b>Dump Alert</b>  {_time_utc()}\n"
        f"\n"
        f"<b>{s.symbol}</b>\n"
        f"Giảm: <b>{_pct(chg_1h)}</b> (1h) | <b>{_pct(chg_24)}</b> (24h)\n"
        f"Giá: <b>{_fmt_price(s.price)}</b>\n"
        f"OI: {_fmt_vol(oi)} | Vol 24h: {_fmt_vol(vol)}\n"
        f"Funding: {_fr(s.funding_rate)} | Score: <b>{s.score:.0f}/100</b>"
    )


def _build_oi_spike(s: TokenSignal) -> str:
    oi      = s.oi_usd or 0
    oi_chg  = s.oi_change_5m or 0
    price_c = s.price_change_1h or 0
    score   = s.oi_spike_score or 0
    sig_map = {
        "SHORT_SQUEEZE": "🟢 Đa đầu xây dựng",
        "LONG_LIQ":      "🔴 Long thanh lý",
        "TRAP":          "🟣 Bear Trap",
        "DIVERGENCE":    "🟡 Phân kỳ OI",
    }
    sig_label = sig_map.get(s.oi_signal_type or "", "📈 OI Spike")
    return (
        f"🔥 <b>OI Spike Alert</b>  {_time_utc()}\n"
        f"\n"
        f"<b>{s.symbol}</b> {sig_label}\n"
        f"OI: <b>{_pct(oi_chg)}</b> | Giá: <b>{_pct(price_c)}</b>\n"
        f"OI Total: {_fmt_vol(oi)}\n"
        f"Funding: {_fr(s.funding_rate)} | Spike Score: <b>{score}/100</b>"
    )


def _build_squeeze(s: TokenSignal) -> str:
    oi      = s.oi_usd or 0
    oi_chg  = s.oi_change_5m or 0
    price_c = s.price_change_1h or 0
    sqz_type = "Short" if s.short_squeeze else "Long"
    return (
        f"⚡ <b>{sqz_type} Squeeze Setup</b>  {_time_utc()}\n"
        f"\n"
        f"<b>{s.symbol}</b>\n"
        f"OI: <b>{_pct(oi_chg)}</b> | Giá: <b>{_pct(price_c)}</b>\n"
        f"OI Total: {_fmt_vol(oi)}\n"
        f"Funding: {_fr(s.funding_rate)} | Score: <b>{s.score:.0f}/100</b>"
    )


def _build_crime_alert(s: TokenSignal) -> str:
    level_emoji = {
        "MM_ACTIVE":  "🚨",
        "CRIME_COIN": "⚠️",
        "SUSPICIOUS": "🔍",
    }.get(s.crime_level, "⚠️")

    level_label = {
        "MM_ACTIVE":  "MM ĐANG ACTIVE — Rủi ro cực cao",
        "CRIME_COIN": "Crime Coin — Có dấu hiệu thao túng",
        "SUSPICIOUS": "Suspicious — Cần theo dõi",
    }.get(s.crime_level, "Warning")

    breakdown = (
        f"├ OI/MC:        {s.crime_oi_mc:.0f}/20\n"
        f"├ Funding:      {s.crime_funding:.0f}/15\n"
        f"├ OI Change:    {s.crime_oi_change:.0f}/15\n"
        f"├ Price/OI Div: {s.crime_divergence:.0f}/15\n"
        f"├ Spot Flow:    {s.crime_flow:.0f}/10\n"
        f"├ Liquidity:    {s.crime_liquidity:.0f}/10\n"
        f"├ Exchange:     {s.crime_exchange:.0f}/10\n"
        f"└ Volatility:   {s.crime_volatility:.0f}/5"
    )

    signals_str = "\n".join(f"• {sig}" for sig in (s.crime_signals or [])[:5])

    return (
        f"{level_emoji} <b>Crime Coin Score Alert</b>  {_time_utc()}\n"
        f"\n"
        f"<b>{s.symbol}</b> — <b>{s.crime_score:.0f}/100</b>\n"
        f"Level: <b>{level_label}</b>\n"
        f"\n"
        f"<b>Breakdown:</b>\n"
        f"{breakdown}\n"
        f"\n"
        f"<b>Tín hiệu:</b>\n"
        f"{signals_str or '—'}\n"
        f"\n"
        f"Giá: {_fmt_price(s.price)} | OI: {_fmt_vol(s.oi_usd or 0)}"
    )


def _build_hourly_report(signals: list[TokenSignal]) -> str:
    now = datetime.now(timezone.utc).strftime("%m/%d %H:%M")
    # Sort theo |oi_change_5m| desc, lấy top 10 có OI data
    top = sorted(
        [s for s in signals if s.oi_usd],
        key=lambda s: abs(s.oi_change_5m or 0),
        reverse=True,
    )[:10]

    if not top:
        return ""

    lines = [f"📊 <b>OI Report {now} UTC</b>\n"]
    for i, s in enumerate(top, 1):
        oi_chg  = s.oi_change_5m or 0
        price_c = s.price_change_1h or 0
        oi      = s.oi_usd or 0
        arrow   = "📈" if oi_chg > 0 else "📉"
        direction = "Đa đầu" if oi_chg > 0 else "Không đầu"
        lines.append(
            f"{i}. <b>{s.symbol}</b> {arrow} {direction} "
            f"{_pct(price_c)} | OI: {_pct(oi_chg)} | {_fmt_vol(oi)}"
        )
    return "\n".join(lines)


# ── Thresholds ────────────────────────────────────────────────────────────────

OI_SPIKE_SCORE_MIN = 30
PRICE_CHG_MIN      = 3.0    # % — chỉ gửi khi giá thay đổi >= 3%


# ── Public API ────────────────────────────────────────────────────────────────

async def check_and_send_alerts(signal: TokenSignal) -> int:
    """Được gọi từ signal_task mỗi lần score. Trả về số alert đã gửi."""
    sent = 0
    price_chg = abs(signal.price_change_1h or 0)

    # Pump
    if (signal.pump_detected
            and signal.score >= PUMP_SCORE_THRESHOLD
            and price_chg >= PRICE_CHG_MIN
            and not _in_cooldown(signal.symbol, "pump")):
        if await _send(_build_pump(signal)):
            _mark(signal.symbol, "pump")
            sent += 1

    # Dump
    if (signal.dump_detected
            and signal.score >= DUMP_SCORE_THRESHOLD
            and price_chg >= PRICE_CHG_MIN
            and not _in_cooldown(signal.symbol, "dump")):
        if await _send(_build_dump(signal)):
            _mark(signal.symbol, "dump")
            sent += 1

    # OI Spike
    if (signal.oi_spike
            and (signal.oi_spike_score or 0) >= OI_SPIKE_SCORE_MIN
            and not _in_cooldown(signal.symbol, "oi")):
        if await _send(_build_oi_spike(signal)):
            _mark(signal.symbol, "oi")
            sent += 1

    # Squeeze
    if ((signal.short_squeeze or signal.long_squeeze)
            and signal.score >= 65
            and not _in_cooldown(signal.symbol, "squeeze")):
        if await _send(_build_squeeze(signal)):
            _mark(signal.symbol, "squeeze")
            sent += 1

    # Crime Coin Score
    crime_score = getattr(signal, "crime_score", 0) or 0
    crime_level = getattr(signal, "crime_level", "NORMAL") or "NORMAL"
    if (crime_score >= 75
            and crime_level in ("CRIME_COIN", "MM_ACTIVE", "SUSPICIOUS")
            and not _in_cooldown(signal.symbol, "crime")):
        if await _send(_build_crime_alert(signal)):
            _mark(signal.symbol, "crime")
            sent += 1

    return sent


_last_hourly: float = 0.0


async def send_hourly_report_task(signals: list[TokenSignal]) -> None:
    """Gọi từ signal_task — tự kiểm tra đủ 1 giờ chưa rồi mới gửi."""
    global _last_hourly
    if time.time() - _last_hourly < 3600:
        return
    text = _build_hourly_report(signals)
    if text and await _send(text):
        _last_hourly = time.time()
        logger.info("Telegram: hourly report sent")
