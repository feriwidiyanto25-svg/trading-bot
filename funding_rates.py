"""
Modul Pelacak Funding Rate Pasar Futures (Binance & Aggregator)
Mendeteksi anomali posisi serakah/panik retail dan risiko Long/Short Squeeze Paus.
"""
import os
import json
import time
import requests
from typing import Dict, Any

CACHE_FILE = os.path.join(os.path.dirname(__file__), "funding_cache.json")
FUTURES_SYMBOLS_CACHE = os.path.join(os.path.dirname(__file__), "futures_symbols_cache.json")

def get_binance_futures_symbols() -> set:
    """
    Mengambil daftar seluruh simbol kontrak USDT-M yang aktif di Binance Futures.
    Menyaring koin spot-only (seperti fan token ATM, BAR, CITY) agar hasil analisis
    100% valid dan bisa langsung ditradingkan di Binance Futures.
    """
    # 1. Cek Cache lokal (< 24 jam)
    if os.path.exists(FUTURES_SYMBOLS_CACHE):
        try:
            mtime = os.path.getmtime(FUTURES_SYMBOLS_CACHE)
            if time.time() - mtime < 86400:
                with open(FUTURES_SYMBOLS_CACHE, "r") as f:
                    cached = json.load(f)
                    if cached and isinstance(cached, list):
                        return set(cached)
        except Exception:
            pass

    symbols = set()

    # 2. Coba direct Binance Futures API (berjalan di GitHub Actions)
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            for s in data.get("symbols", []):
                if s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT":
                    symbols.add(s["symbol"])
    except Exception:
        pass

    # 3. Fallback jika Binance FAPI diblokir ISP lokal: CoinGecko Binance Futures
    if not symbols:
        try:
            url = "https://api.coingecko.com/api/v3/derivatives/exchanges/binance_futures?include_tickers=all"
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                tickers = res.json().get("tickers", [])
                for t in tickers:
                    sym = t.get("symbol", "")
                    if sym.endswith("USDT") or t.get("target") == "USDT":
                        symbols.add(sym)
        except Exception:
            pass

    # Simpan ke cache jika berhasil
    if symbols:
        try:
            with open(FUTURES_SYMBOLS_CACHE, "w") as f:
                json.dump(list(symbols), f)
        except Exception:
            pass
        return symbols

    # Fallback jika offline
    if os.path.exists(FUTURES_SYMBOLS_CACHE):
        try:
            with open(FUTURES_SYMBOLS_CACHE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass

    return set()

def get_all_funding_rates() -> Dict[str, float]:
    """
    Mengambil data Funding Rate futures terbaru.
    1. Cek cache lokal jika masih segar (< 10 menit).
    2. Coba direct Binance Futures API (berjalan di GitHub Actions / non-Indonesian IP).
    3. Fallback ke CoinGecko Derivatives API (lolos blokir ISP Indonesia).
    """
    # 1. Cek Cache
    if os.path.exists(CACHE_FILE):
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            if time.time() - mtime < 600:  # 10 menit
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                    if cached:
                        return cached
        except Exception:
            pass

    rates = {}

    # 2. Coba API Utama: Binance Futures Public Endpoint
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                for item in data:
                    sym = item.get("symbol", "")
                    last_funding = item.get("lastFundingRate")
                    if sym and last_funding is not None:
                        rates[sym] = float(last_funding) * 100 # Konversi ke persen (%)
    except Exception:
        pass

    # 3. Fallback jika Binance FAPI diblokir ISP lokal: CoinGecko Derivatives
    if not rates:
        try:
            url = "https://api.coingecko.com/api/v3/derivatives"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list):
                    for item in data:
                        market = item.get("market", "")
                        symbol = item.get("symbol", "")
                        fr = item.get("funding_rate")
                        if "binance" in market.lower() and symbol and fr is not None:
                            rates[symbol.upper()] = float(fr)
        except Exception:
            pass

    # Simpan ke cache jika dapat data
    if rates:
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(rates, f)
        except Exception:
            pass
    elif os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                rates = json.load(f)
        except Exception:
            pass

    return rates

def evaluate_funding_rate(symbol: str, funding_map: Dict[str, float]) -> Dict[str, Any]:
    """
    Mengevaluasi apakah funding rate koin berada di zona bahaya Squeeze:
    - Normal: 0.005% s/d 0.015%
    - Extreme Positive (> +0.03%): Rawan Long Squeeze (Paus banting harga)
    - Extreme Negative (< -0.02%): Rawan Short Squeeze (Paus pompa harga)
    """
    rate = funding_map.get(symbol, 0.01) # Default neutral 0.01%

    if rate >= 0.035:
        return {
            "rate_pct": round(rate, 4),
            "status": "EXTREME_LONG_HEAVY",
            "score_impact": -20, # Penalti untuk Long, bonus untuk Short
            "label": f"⚡ Funding Tinggi (+{rate:.3f}%): Retail FOMO Long (Rawan Long Squeeze Paus)",
            "bias": "SHORT_BIAS"
        }
    elif rate <= -0.02:
        return {
            "rate_pct": round(rate, 4),
            "status": "EXTREME_SHORT_HEAVY",
            "score_impact": 20, # Bonus untuk Long, penalti untuk Short
            "label": f"⚡ Funding Negatif ({rate:.3f}%): Retail Panik Short (Rawan Short Squeeze Paus)",
            "bias": "LONG_BIAS"
        }
    else:
        return {
            "rate_pct": round(rate, 4),
            "status": "NEUTRAL",
            "score_impact": 0,
            "label": f"Funding Normal ({rate:.3f}%)",
            "bias": "NEUTRAL"
        }
