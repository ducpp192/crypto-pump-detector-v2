"""
CoinMarketCap service — fetches token list by market cap range.
Nếu không có CMC_API_KEY → dùng fallback ~200 lowcap/midcap token từ Binance.
"""
import asyncio
import logging
from typing import Dict, Set
import aiohttp
from config import CMC_API_KEY, CMC_BASE, CMC_TOP_N, MIDCAP_MIN_USD, MIDCAP_MAX_USD, STABLECOINS

logger = logging.getLogger(__name__)


async def fetch_midcap_symbols() -> Dict[str, float]:
    """
    Trả về dict {symbol: market_cap_usd} lọc theo market cap range.
    Nếu không có CMC_API_KEY → fallback hardcoded list (market_cap = 0).
    """
    if not CMC_API_KEY:
        logger.warning("CMC_API_KEY chưa set → dùng fallback list (~200 tokens)")
        return {sym: 0.0 for sym in _fallback_symbols()}

    url = f"{CMC_BASE}/v1/cryptocurrency/listings/latest"
    params = {
        "start": 1,
        "limit": CMC_TOP_N,
        "convert": "USD",
        "sort": "market_cap",
        "sort_dir": "desc",
    }
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
        "Accept": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.error(f"CMC API error: {resp.status}")
                    return {sym: 0.0 for sym in _fallback_symbols()}
                data = await resp.json()

        result: Dict[str, float] = {}
        for coin in data.get("data", []):
            symbol = coin["symbol"].upper()
            mc = coin.get("quote", {}).get("USD", {}).get("market_cap", 0) or 0
            if symbol in STABLECOINS:
                continue
            if MIDCAP_MIN_USD <= mc <= MIDCAP_MAX_USD:
                result[symbol] = float(mc)

        logger.info(f"CMC: {len(result)} tokens trong range ${MIDCAP_MIN_USD/1e6:.0f}M–${MIDCAP_MAX_USD/1e6:.0f}M")
        return result

    except Exception as e:
        logger.error(f"CMC fetch failed: {e}")
        return {sym: 0.0 for sym in _fallback_symbols()}


def _fallback_symbols() -> Set[str]:
    """
    ~200 lowcap/midcap tokens đang active trên Binance.
    Dùng khi không có CMC API key.
    """
    return {
        # ── Lowcap / gaming / DeFi ─────────────────────────────────────────
        "GALA", "SAND", "MANA", "AXS", "ENJ", "ILV", "ALICE", "TLM", "WAXP",
        "CHZ", "SANTOS", "LAZIO", "PORTO", "ACM", "ATM", "BAR", "JUV", "PSG", "CITY",
        "PEOPLE", "JASMY", "AGLD", "BICO", "SPELL", "LEVER", "LINA", "DUSK",
        "REEF", "DENT", "WIN", "HOT", "ZIL", "VET", "ONE", "SKL",
        "CELR", "CTSI", "STORJ", "REN", "ZRX", "BNT", "KNC", "BAND",
        "ANKR", "OXT", "MLN", "REQ", "LPT", "NMR", "UMA", "RAD",
        "AUDIO", "FORTH", "AMP", "POND",

        # ── DeFi midcap ────────────────────────────────────────────────────
        "LINK", "UNI", "AAVE", "COMP", "MKR", "SNX", "YFI", "SUSHI", "CRV",
        "BAL", "ALPHA", "BNX", "XVS", "BAKE", "SFP", "MDX", "BSW",
        "CHESS", "AUCTION", "UFT", "IDEX", "BOND", "POLS", "MASK",
        "SUPER", "DODO", "CFX", "ROSE", "KAVA", "FLOW",
        "LIT", "COMBO", "DF", "MTL", "OGN", "OM",

        # ── L1/L2 ──────────────────────────────────────────────────────────
        "NEAR", "ATOM", "DOT", "ALGO", "ICP", "HBAR", "EOS", "XTZ",
        "THETA", "FTM", "AVAX", "ONE", "CELO", "KLAY", "EGLD",
        "ZEN", "QTUM", "WAVES", "ICX", "ZIL", "IOST", "SC",
        "ARDR", "STEEM", "HIVE", "XEM", "LSK", "ARK",

        # ── Infrastructure ─────────────────────────────────────────────────
        "GRT", "FIL", "AR", "STORJ", "OCEAN", "NKN", "RLC", "ANKR",
        "FLUX", "HNT", "IOTX", "WAN", "CVC", "PHA", "AERGO",

        # ── Newer lowcap ───────────────────────────────────────────────────
        "ID", "EDU", "MAV", "PENDLE", "ARKM", "CYBER", "TIA", "MANTA",
        "ALT", "PIXEL", "PORTAL", "STRK", "AEVO", "ETHFI", "OMNI",
        "REZ", "BB", "NOT", "IO", "ZK", "LISTA", "ZRO", "RENDER",
        "W", "TNSR", "SAFE", "BOME", "SLERF", "WIF",
        "ACE", "XAI", "MEME", "ORDI", "RATS", "SATS",

        # ── Meme / high vol ────────────────────────────────────────────────
        "DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "MEME", "NEIRO",
        "DOGS", "HMSTR", "CATI", "EIGEN", "SCRT",

        # ── Perp-only gems ─────────────────────────────────────────────────
        "BLUR", "APE", "GMT", "GST", "LUNC", "LUNA", "USTC",
        "SRM", "FIDA", "RAY", "ORCA", "MNGO",
        "PYTH", "JTO", "JUP", "WEN", "POPCAT", "MEW",
    }
