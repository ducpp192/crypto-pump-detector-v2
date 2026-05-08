import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
CMC_API_KEY = os.getenv("CMC_API_KEY", "")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Token Filtering ───────────────────────────────────────────────────────────
# Lowcap: $1M – $100M  |  Midcap: $50M – $500M  |  All small: $1M – $500M
MIDCAP_MIN_USD = 1_000_000            # lowcap từ $1M
MIDCAP_MAX_USD = 500_000_000          # tới $500M
MIN_VOLUME_24H = 500_000              # volume tối thiểu $500K/ngày
CMC_TOP_N = 500
MAX_TOKENS = 120                      # 120 tokens × 5 ep = 600 req → 60s cycle @ 10 req/s

STABLECOINS = {
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDD",
    "FDUSD", "PYUSD", "FRAX", "LUSD", "SUSD", "GUSD", "USDE", "PAXG",
}

# ── Task Intervals ────────────────────────────────────────────────────────────
# 10 req/s → batch 10 × delay 1s = 10 req/s
# 80 tokens × 5 endpoints = 400 req → 40s/cycle → REST_ENRICH = 45s
# 80 tokens × 3 futures endpoints = 240 req → 24s/cycle → FUTURES = 30s
CMC_REFRESH_SECONDS = 300
REST_ENRICH_SECONDS = 45
FUTURES_ENRICH_SECONDS = 30
SIGNAL_SCORE_SECONDS = 5
SCAN_INTERVAL_SECONDS = 45

# ── Signal Thresholds ─────────────────────────────────────────────────────────
PUMP_SCORE_THRESHOLD = 65
DUMP_SCORE_THRESHOLD = 35

FUNDING_BEARISH_THRESHOLD = 0.001     # FR > 0.1% → crowded longs → bearish
FUNDING_BULLISH_THRESHOLD = -0.001    # FR < -0.1% → crowded shorts → bullish

SQUEEZE_PRICE_MOVE_PCT = 1.5
SQUEEZE_OI_DROP_PCT = -2.0

# ── Pump Detector (WS trade analysis) ────────────────────────────────────────
PUMP_BUY_RATIO = 0.70
PUMP_TRADE_WINDOW = 50
PUMP_FREQ_WINDOW_SECS = 30.0
VOLUME_SPIKE_MULT = 5.0               # ≥5x → score 100 (real pump threshold)
VOLUME_SPIKE_WARN_MULT = 3.0          # 3–5x → warning zone (75–100)
VOLUME_SPIKE_MULTIPLIER = 5.0         # alias
MIN_TRADE_USDT = 10.0                 # ignore micro trades < $10 in pump detection
WHALE_BUY_USDT = 10_000.0             # single trade ≥ $10K = whale signal
TRADE_ACCEL_RATIO = 3.0               # trade/s acceleration ≥ 3x = burst

# ── Quality Filters ───────────────────────────────────────────────────────────
IMBALANCE_BULLISH = 2.0
IMBALANCE_BEARISH = 0.5
SPREAD_MAX_PCT = 0.5
PRICE_SKIP_THRESHOLD = 0.12           # skip tokens already moved > 12% in 1h

# ── Scoring Weights (sum = 1.0) ───────────────────────────────────────────────
WEIGHTS = {
    "spot_momentum": 0.22,
    "volume_spike":  0.18,
    "order_book":    0.13,
    "trade_flow":    0.12,
    "funding_rate":  0.12,
    "open_interest": 0.12,
    "liquidation":   0.11,
}

# ── REST / Concurrency ────────────────────────────────────────────────────────
# 10 req/s = concurrency 10 + delay 1.0s giữa mỗi batch
REST_CONCURRENCY = 10
REST_BATCH_DELAY = 1.0             # 1s / batch → 10 req/s đúng chuẩn

# ── WebSocket ─────────────────────────────────────────────────────────────────
WS_MAX_PER_CONN = 200
WS_RECONNECT_DELAY = 3

# ── Alerts ────────────────────────────────────────────────────────────────────
ALERT_COOLDOWN_SECONDS = 300
SIGNAL_COOLDOWN_SECONDS = 120

# ── Candle Depths ─────────────────────────────────────────────────────────────
CANDLES_1M = 70    # 70 nến 1m = 1h10m → đủ baseline 1h cho volume spike
CANDLES_5M = 12
CANDLES_15M = 30

# Volume spike: số nến gần nhất dùng làm "recent window"
VOLUME_SPIKE_RECENT_CANDLES = 5   # avg của 5 nến gần nhất = "5m volume"
VOLUME_SPIKE_BASELINE_CANDLES = 60  # avg của 60 nến trước đó = "1h baseline"
ORDERBOOK_DEPTH = 20

# ── Binance Endpoints ─────────────────────────────────────────────────────────
BINANCE_SPOT_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"
BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"
CMC_BASE = "https://pro-api.coinmarketcap.com"
