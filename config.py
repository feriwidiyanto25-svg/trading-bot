"""
Konfigurasi Screener Kripto Binance
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Endpoint Binance Vision (Official Public Data Endpoint - Tidak diblokir di Indonesia)
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision/api/v3")

# Pengaturan Filter Pasar
QUOTE_ASSET = "USDT"
MIN_24H_VOLUME_USD = 5_000_000  # Minimal volume $5 Juta untuk Mode Trend Konservatif
MIN_VOLUME_PREPUMP_USD = 1_000_000 # Minimal volume $1 Juta untuk Mode Pre-Pump / Whale Hunter (tangkap koin seperti SSV)
MAX_PAIRS_TO_ANALYZE = 50        # Batasi koin teratas agar proses scan cepat
TOP_GAINERS_COUNT = 15           # Sertakan 15 koin kenaikan persentase tertinggi 24 jam
TIMEFRAME = "4h"                 # Timeframe analisis (15m, 1h, 4h)
CANDLE_LIMIT = 200               # Jumlah candle yang diambil untuk kalkulasi EMA 200, ATR, dan ATH/ATL

# Pengaturan Manajemen Risiko (Risk Management)
ATR_SL_MULTIPLIER = 2.0          # Pengali ATR untuk jarak Stop Loss (dinaikkan ke 2.0 untuk toleransi volatilitas & noise)
MIN_RISK_PCT_ALTCOIN = 2.2       # Minimal jarak Stop Loss 2.2% pada altcoin untuk cegah likuidasi spread/noise
MIN_RISK_PCT_MAJORS = 1.5        # Minimal jarak Stop Loss 1.5% untuk BTC/ETH
RRR_TP1 = 1.5                    # Rasio Risk-to-Reward TP 1 (1:1.5)
RRR_TP2 = 2.5                    # Rasio Risk-to-Reward TP 2 (1:2.5)

# Kredensial Telegram (Opsional - Kosongkan jika belum ingin kirim ke bot)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
