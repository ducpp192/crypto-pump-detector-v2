import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers.signals import router as signals_router
from routers.history import router as history_router
from routers.ws import router as ws_router
from routers.oi import router as oi_router
from routers.dong_tien import router as dong_tien_router
from routers.monitor import router as monitor_router
from services.scanner import (
    cmc_refresh_task,
    rest_enrich_task,
    ws_stream_task,
    futures_enrich_task,
    signal_task,
)
from services.ws_manager import broadcast_manager
from services.signal_history import init_db, update_outcomes_task
from services.dong_tien_service import dong_tien_refresh_task
from services.flow_history import init_flow_db, save_flow_snapshots

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting crypto pump detector v2 (WebSocket delta architecture)...")

    # Start broadcast manager before signal tasks
    await broadcast_manager.start()
    # Init signal history SQLite DB
    await init_db()
    # Init flow history DB
    await init_flow_db()

    tasks = [
        asyncio.create_task(cmc_refresh_task(),          name="cmc_refresh"),
        asyncio.create_task(rest_enrich_task(),          name="rest_enrich"),
        asyncio.create_task(ws_stream_task(),            name="ws_stream"),
        asyncio.create_task(futures_enrich_task(),       name="futures_enrich"),
        asyncio.create_task(signal_task(),               name="signal_scoring"),
        asyncio.create_task(update_outcomes_task(),      name="outcome_tracker"),
        asyncio.create_task(dong_tien_refresh_task(),    name="dong_tien_refresh"),
        asyncio.create_task(_flow_snapshot_task(),       name="flow_snapshot"),
    ]
    logger.info(f"Launched {len(tasks)} background tasks")
    yield

    logger.info("Shutting down...")
    await broadcast_manager.stop()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete.")


async def _flow_snapshot_task():
    """Saves flow snapshots to SQLite every 5 minutes."""
    from services.scanner import _states
    await asyncio.sleep(60)  # wait for first data
    while True:
        try:
            n = await save_flow_snapshots(_states)
            logger.info(f"Flow snapshot: saved {n} tokens")
        except Exception as e:
            logger.error(f"Flow snapshot error: {e}", exc_info=True)
        await asyncio.sleep(300)  # 5 minutes


app = FastAPI(
    title="Crypto Pump Detector v2",
    description="Real-time mid-cap signal engine: Spot + Derivatives + WebSocket delta updates",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router)   # REST /api/signals
app.include_router(history_router)   # REST /api/history
app.include_router(ws_router)        # WS   /ws/signals  (real-time delta stream)
app.include_router(oi_router)        # REST /api/oi/*    (OI history + heatmap + alerts)
app.include_router(dong_tien_router) # REST /api/dong-tien/* (money flow scanner)
app.include_router(monitor_router)   # REST /api/monitor/* + WS /ws/monitor (flow monitor)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.1.0",
        "ws_clients": broadcast_manager.client_count,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
