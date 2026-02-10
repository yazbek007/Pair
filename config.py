import os
from datetime import timezone
import pytz

# === الإعدادات العامة ===
SYRIA_TZ = pytz.timezone('Asia/Damascus')
API_UPDATE_INTERVAL = 15  # دقائق

# === قائمة العملات المراقبة ===
COINS_TO_MONITOR = [
    "BTC", "ETH", "BNB", "XRP", "ADA", 
    "SOL", "DOGE", "DOT", "MATIC", "AVAX",
    "LTC", "UNI", "LINK", "ATOM", "XLM"
]

# === إعدادات NTFY ===
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "crypto-alerts-syria")
NTFY_PRIORITY = "high"  # high, low, default, min, max

# === إعدادات التداول ===
MIN_LIQUIDITY_USD = 10000000  # 10 مليون دولار
MAX_SPREAD_PERCENT = 0.1  # 0.1%
VOLATILITY_THRESHOLD = 5.0  # ATR نسبة مئوية

# === أطر زمنية للتحليل ===
TIME_FRAMES = {
    "5m": "5m",
    "15m": "15m", 
    "1h": "1h",
    "4h": "4h",
    "1d": "1d"
}

# === نقاط الترجيح للتصنيف ===
SCORE_WEIGHTS = {
    "performance_vs_btc": 0.35,
    "momentum": 0.25,
    "volatility_score": 0.20,
    "liquidity_score": 0.10,
    "volume_trend": 0.10
}
