"""
Global Binance rate limiter — token bucket, dùng chung cho mọi request.

Binance limit: 1200 weight/phút = 20 req/s (weight=1 mỗi request).
Ta giới hạn ở 10 req/s để an toàn (50% headroom).

Tất cả binance_rest.py và binance_futures.py đều acquire từ đây.
"""
import asyncio
import time
import logging

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TARGET_RPS = 10          # requests per second
BUCKET_SIZE = 20         # burst tối đa (2 giây tích lũy)

# ── Token bucket ──────────────────────────────────────────────────────────────
_tokens: float = BUCKET_SIZE
_last_refill: float = time.monotonic()
_lock: asyncio.Lock = None   # init lazily (cần event loop)


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def acquire() -> None:
    """
    Chờ cho đến khi có token. Gọi trước mỗi Binance HTTP request.
    """
    global _tokens, _last_refill
    lock = _get_lock()

    async with lock:
        now = time.monotonic()
        elapsed = now - _last_refill
        # Refill tokens theo thời gian đã trôi qua
        _tokens = min(BUCKET_SIZE, _tokens + elapsed * TARGET_RPS)
        _last_refill = now

        if _tokens >= 1.0:
            _tokens -= 1.0
            return

        # Chưa có token → tính thời gian cần chờ
        wait = (1.0 - _tokens) / TARGET_RPS

    # Sleep ngoài lock để không block các coroutine khác
    await asyncio.sleep(wait)

    # Sau khi sleep, lấy token
    async with lock:
        now = time.monotonic()
        elapsed = now - _last_refill
        _tokens = min(BUCKET_SIZE, _tokens + elapsed * TARGET_RPS)
        _last_refill = now
        _tokens = max(0.0, _tokens - 1.0)
