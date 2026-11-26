"""
Mesin Pemindai Pasar Kripto (Screener Engine)
Memindai koin teraktif di Binance, menghitung skor multi-faktor,
dan menentukan titik Entry, Stop Loss, dan Take Profit secara otomatis.
"""
import requests
import pandas as pd
from typing import List, Dict, Any
from config import (
    BINANCE_BASE_URL,
    QUOTE_ASSET,
    MIN_24H_VOLUME_USD,
    MIN_VOLUME_PREPUMP_USD,
    MAX_PAIRS_TO_ANALYZE,
    TOP_GAINERS_COUNT,
    TIMEFRAME,
    CANDLE_LIMIT,
    ATR_SL_MULTIPLIER,
    MIN_RISK_PCT_ALTCOIN,
    MIN_RISK_PCT_MAJORS,
    RRR_TP1,
    RRR_TP2
)
from token_intel import get_token_fundamental_intel
from indicators import (
    calculate_ema,
    calculate_sma,
    calculate_rsi,
    calculate_atr,
    calculate_adx,
    detect_candlestick_patterns,
    detect_liquidity_sweep,
    detect_wick_rejection,
    detect_volume_status,
    detect_ath_atl_and_fibonacci,
    detect_rsi_divergence,
    detect_fair_value_gap,
    detect_whale_accumulation_and_breakout
)
from macro_news import (
    get_crypto_fear_and_greed,
    get_fed_and_macro_intel,
    project_whale_shakeout_levels
)
from funding_rates import (
    get_all_funding_rates,
    evaluate_funding_rate,
    get_binance_futures_symbols
)

MEGA_CAPS = {
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", 
    "ADAUSDT", "TRXUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "LTCUSDT", 
    "SUIUSDT", "NEARUSDT", "BCHUSDT", "ETCUSDT", "XLMUSDT", "SHIBUSDT"
}

def get_top_liquid_pairs(min_volume: float = MIN_24H_VOLUME_USD, mode: str = "trend") -> List[Dict[str, Any]]:
    """
    Mengambil seluruh ticker 24 jam dan memfilter koin berlikuiditas tinggi:
    - Mode Trend: Mengambil koin teratas berbasis volume transaksi dan likuiditas tinggi.
    - Mode Pump: KHUSUS memburu koin tidur (Mid/Low Cap) yang belum terbang:
      1. Menyingkirkan koin raksasa (Mega-Caps: BTC, SOL, DOGE, dll).
      2. Menyingkirkan koin yang sudah terbang tinggi (price change 24h > 5%).
      3. Menyaring koin tidur di rentang -7% s/d +4% dengan likuiditas $1M s/d $60M.
    """
    url = f"{BINANCE_BASE_URL}/ticker/24hr"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        tickers = res.json()
    except Exception as e:
        print(f"[Error] Gagal mengambil ticker 24hr: {e}")
        return []

    valid_pairs = []
    excluded_coins = {
        "USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "EURUSDT", "DAIUSDT", 
        "UUSDT", "USDUSDT", "AEURUSDT", "USDPUSDT", "WBTCUSDT", "USD1USDT",
        "BFUSDUSDT", "RWUSDUSDT", "XUSDUSDT", "RLUSDUSDT", "EURIUSDT", "USDEUSDT"
    }

    # Ambil daftar koin Binance Futures agar hanya menyaring koin yang ada di Futures
    futures_symbols = get_binance_futures_symbols()

    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith(QUOTE_ASSET) or symbol in excluded_coins:
            continue
        if symbol.endswith("USDUSDT") or symbol.endswith("BUSDT"):
            continue
        
        # Saring koin spot-only (misal Fan Token ATMUSDT tidak ada di futures)
        if futures_symbols and symbol not in futures_symbols:
            continue
            
        try:
            quote_volume = float(t.get("quoteVolume", 0))
            price_change_pct = float(t.get("priceChangePercent", 0))
            last_price = float(t.get("lastPrice", 0))
            bid_qty = float(t.get("bidQty", 0))
            ask_qty = float(t.get("askQty", 0))
        except (ValueError, TypeError):
            continue

        if quote_volume >= min_volume and last_price > 0:
            valid_pairs.append({
                "symbol": symbol,
                "quote_volume": quote_volume,
                "price_change_pct": price_change_pct,
                "last_price": last_price,
                "bid_qty": bid_qty,
                "ask_qty": ask_qty
            })

    if mode == "pump":
        sleeping_pairs = []
        for p in valid_pairs:
            sym = p["symbol"]
            chg = p["price_change_pct"]
            q_vol = p["quote_volume"]
            if sym in MEGA_CAPS:
                continue
            if chg > 5.0:
                continue
            if not (-8.0 <= chg <= 4.0):
                continue
            if 1_000_000 <= q_vol <= 60_000_000:
                sleeping_pairs.append(p)
        
        sleeping_pairs.sort(key=lambda x: (abs(x["price_change_pct"]), -x["quote_volume"]))
        return sleeping_pairs[:MAX_PAIRS_TO_ANALYZE]

    # 1. Ambil koin dengan volume transaksi terbesar
    by_volume = sorted(valid_pairs, key=lambda x: x["quote_volume"], reverse=True)[:MAX_PAIRS_TO_ANALYZE]

    # 2. Ambil koin yang sedang meledak naik (Top Gainers)
    by_gainers = sorted(valid_pairs, key=lambda x: x["price_change_pct"], reverse=True)[:TOP_GAINERS_COUNT]

    # Gabungkan tanpa duplikasi simbol
    combined = {p["symbol"]: p for p in (by_volume + by_gainers)}
    return list(combined.values())

def get_klines_data(symbol: str, interval: str = TIMEFRAME, limit: int = CANDLE_LIMIT) -> pd.DataFrame:
    """Mengambil data OHLCV historis dari Binance (Spot / Futures) dengan fallback multi-source"""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    # 1. Coba Binance Vision (Spot)
    try:
        url = f"{BINANCE_BASE_URL}/klines"
        res = requests.get(url, params=params, timeout=4)
        if res.status_code == 200:
            raw = res.json()
            if raw and isinstance(raw, list):
                df = pd.DataFrame(raw).iloc[:, [0, 1, 2, 3, 4, 5]]
                df.columns = ["time", "open", "high", "low", "close", "volume"]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df
    except Exception:
        pass

    # 2. Coba Binance Futures FAPI (Direct di GitHub Actions / non-ID IP)
    try:
        fapi_url = "https://fapi.binance.com/fapi/v1/klines"
        res = requests.get(fapi_url, params=params, timeout=3)
        if res.status_code == 200:
            raw = res.json()
            if raw and isinstance(raw, list):
                df = pd.DataFrame(raw).iloc[:, [0, 1, 2, 3, 4, 5]]
                df.columns = ["time", "open", "high", "low", "close", "volume"]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df
    except Exception:
        pass

    # 3. Fallback jika koin Futures-Only dan diakses dari IP lokal (misal DOS_USDT via Gate.io)
    try:
        gate_sym = symbol.replace("USDT", "_USDT")
        gate_url = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={gate_sym}&interval={interval}&limit={limit}"
        res = requests.get(gate_url, timeout=5)
        if res.status_code == 200:
            raw = res.json()
            if raw and isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list):
                # Gate format: [time, volume, close, high, low, open]
                df = pd.DataFrame(raw).iloc[:, [0, 5, 3, 4, 2, 1]]
                df.columns = ["time", "open", "high", "low", "close", "volume"]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df
    except Exception:
        pass

    return pd.DataFrame()

def get_daily_macro_trend(symbol: str) -> str:
    """
    Mengambil arah tren harian (1D) untuk Multi-Timeframe Confluence (MTF)
    """
    df_daily = get_klines_data(symbol, interval="1d", limit=60)
    if df_daily.empty or len(df_daily) < 30:
        return "Neutral"
    c_daily = df_daily.iloc[-2]
    ema50 = calculate_ema(df_daily['close'], period=min(50, len(df_daily))).iloc[-2]
    if c_daily['close'] > ema50:
        return "Uptrend"
    else:
        return "Downtrend"

def analyze_single_coin(coin_meta: Dict[str, Any], btc_status: Dict[str, Any] = None, timeframe: str = TIMEFRAME, funding_map: Dict[str, float] = None, mode: str = "trend") -> Dict[str, Any]:
    """
    Menganalisis satu koin dengan multi-kondisi pasar kripto komprehensif:
    1. Tren Makro (EMA 200) & Retest (EMA 50)
    2. Multi-Timeframe Confluence (MTF 1D + TF Pilihan)
    3. RSI Momentum & Extreme Overbought/Oversold Filter
    4. Leading Indicator: RSI Divergence (Bullish / Bearish)
    5. Volatilitas & Filter Sideways: ADX 14
    6. Deteksi Sapu Likuiditas Dua Arah (SFP Reclaim / Rejection)
    7. Deteksi Jebakan Jarum (Bull Trap & Bear Trap Rejection)
    8. Validasi Volume Nyata vs Volume Kering (Dry Volume Fakeout)
    9. Sentiment Order Book: Imbalansi Bid vs Ask
    10. Korelasi Rezim Pasar Bitcoin (BTC Macro Correlation)
    11. Fase ATH/ATL & Proyeksi Matematika Fibonacci (1.618 & 2.618)
    12. Fair Value Gap (FVG Imbalance - Smart Money Concepts)
    13. Funding Rate Futures & Squeeze Risk Analysis
    14. Mode 2: Deteksi Akumulasi Paus Multi-Hari & Ledakan Pre-Pump 15m
    15. Manajemen Risiko Anti-Likuidasi & Rekomendasi Leverage Aman
    """
    symbol = coin_meta["symbol"]
    df = get_klines_data(symbol, interval=timeframe)
    if len(df) < 50:
        return None

    # Deteksi Pre-Pump / Whale Hunter jika Mode Pump aktif
    pump_eval = None
    if mode == "pump":
        df_daily = get_klines_data(symbol, interval="1d", limit=30)
        df_15m = df if timeframe == "15m" else get_klines_data(symbol, interval="15m", limit=30)
        if not df_15m.empty:
            pump_eval = detect_whale_accumulation_and_breakout(df_15m, df_daily=df_daily if not df_daily.empty else None)

    # 1. Kalkulasi Indikator Dasar & Lanjutan
    df['ema_200'] = calculate_ema(df['close'], period=min(200, len(df)))
    df['ema_50'] = calculate_ema(df['close'], period=50)
    df['rsi'] = calculate_rsi(df['close'], period=14)
    df['vol_sma_20'] = calculate_sma(df['volume'], period=20)
    df['atr'] = calculate_atr(df['high'], df['low'], df['close'], period=14)
    df['adx'] = calculate_adx(df['high'], df['low'], df['close'], period=14)

    # Candle penutupan resmi
    c = df.iloc[-2]
    
    # Deteksi Kondisi Pasar Cerdas
    patterns = detect_candlestick_patterns(df)
    sweep = detect_liquidity_sweep(df, lookback=8)
    wick = detect_wick_rejection(df)
    vol_status = detect_volume_status(df)
    ath_atl = detect_ath_atl_and_fibonacci(df)
    divergence = detect_rsi_divergence(df, lookback=20)
    fvg = detect_fair_value_gap(df, lookback=15)
    fr_eval = evaluate_funding_rate(symbol, funding_map if funding_map else {})

    close_p = c['close']
    ema200_p = c['ema_200']
    rsi_val = c['rsi']
    atr_val = c['atr']
    adx_val = c['adx']
    pattern_name = patterns["pattern"]
    pattern_bias = patterns["bias"]

    score = 0
    reasons = []

    # A. Faktor Tren Makro (EMA 200)
    if close_p > ema200_p:
        score += 25
        reasons.append("Uptrend (>EMA200)")
    else:
        score -= 25
        reasons.append("Downtrend (<EMA200)")

    # B. Multi-Timeframe Confluence (MTF 1D)
    daily_trend = get_daily_macro_trend(symbol)
    tf_str = timeframe.upper()
    if close_p > ema200_p and daily_trend == "Uptrend":
        score += 25
        reasons.append(f"🏆 MTF Selaras (1D & {tf_str} Uptrend)")
    elif close_p < ema200_p and daily_trend == "Downtrend":
        score -= 25
        reasons.append(f"🏆 MTF Selaras (1D & {tf_str} Downtrend)")
    elif close_p > ema200_p and daily_trend == "Downtrend":
        score -= 20
        reasons.append("⚠️ MTF Konflik (1D Downtrend)")
    elif close_p < ema200_p and daily_trend == "Uptrend":
        score += 20
        reasons.append("⚠️ MTF Konflik (1D Uptrend)")

    # C. Faktor RSI Divergence (Leading Reversal Signal)
    if divergence["score_impact"] != 0:
        score += divergence["score_impact"]
        reasons.append(divergence["label"])

    # D. Faktor Momentum RSI & Extreme Filter
    if close_p > ema200_p:
        if 30 <= rsi_val <= 48:
            score += 20
            reasons.append(f"Pullback Diskon (RSI {rsi_val:.1f})")
        elif rsi_val > 75:
            score -= 30
            reasons.append(f"⚠️ RSI Ekstrem >75 (Jenuh Beli)")
        elif rsi_val > 68:
            score -= 10
            reasons.append("RSI Tinggi (>68)")
    else:
        if 52 <= rsi_val <= 70:
            score -= 20
            reasons.append(f"Retest Mahal (RSI {rsi_val:.1f})")
        elif rsi_val < 25:
            score += 30
            reasons.append(f"⚠️ RSI Ekstrem <25 (Jenuh Jual)")
        elif rsi_val < 32:
            score += 10
            reasons.append("RSI Rendah (<32)")

    # E. Faktor Kekuatan Tren vs Sideways (ADX)
    if adx_val < 20:
        # Penalti untuk pasar lesu / sideways yang rawan whipsaw
        score = int(score * 0.7)
        reasons.append(f"⚠️ Pasar Sideways (ADX {adx_val:.0f})")
    elif adx_val >= 25:
        score += 15 if score > 0 else -15
        reasons.append(f"🌊 Tren Kuat (ADX {adx_val:.0f})")

    # F. Faktor Pola Candlestick Reversal
    if pattern_bias == "Bullish":
        score += 20
        reasons.append(f"Pola {pattern_name}")
    elif pattern_bias == "Bearish":
        score -= 20
        reasons.append(f"Pola {pattern_name}")

    # G. Faktor Sapu Likuiditas Dua Arah (SFP / Reclaim)
    if sweep["score_impact"] != 0:
        score += sweep["score_impact"]
        reasons.append(sweep["label"])

    # H. Faktor Jebakan Jarum (Bull Trap & Bear Trap)
    if wick["penalty"] != 0:
        score += wick["penalty"]
        reasons.append(wick["warning"])

    # I. Faktor Validasi Volume (Spike vs Kering)
    if vol_status["score_impact"] != 0:
        score += vol_status["score_impact"]
        reasons.append(vol_status["label"])

    # J. Faktor Sentiment Order Book (Imbalansi Bid vs Ask)
    bid_qty = coin_meta.get("bid_qty", 0)
    ask_qty = coin_meta.get("ask_qty", 0)
    total_book = bid_qty + ask_qty
    if total_book > 0:
        bid_ratio = (bid_qty / total_book) * 100
        if bid_ratio >= 65:
            score += 15
            reasons.append(f"⚡ Order Book Dominan Beli ({bid_ratio:.0f}% Bid)")
        elif bid_ratio <= 35:
            score -= 15
            reasons.append(f"⚡ Order Book Dominan Jual ({100-bid_ratio:.0f}% Ask)")

    # K. Faktor Rezim Pasar Bitcoin (BTC Macro Hard Filter - Berlaku pada Mode Trend)
    if mode == "trend" and btc_status and symbol != "BTCUSDT":
        btc_trend = btc_status.get("trend")
        if btc_trend == "Downtrend":
            if score > 0:
                has_reversal = any("SFP" in r or "Divergence" in r for r in reasons)
                if has_reversal and score >= 85:
                    score -= 15
                    reasons.append("⚠️ Counter-Trend Long (Wajib Disiplin SL)")
                else:
                    score = -20  # Anulir Long jadi non-rekomendasi
                    reasons.append("🛡️ Veto Makro: Long Dilarang saat BTC Downtrend")
            else:
                score -= 20
                reasons.append("🌊 Selaras Tren Makro BTC (Short Diunggulkan)")
        elif btc_trend == "Uptrend":
            if score < 0:
                has_reversal = any("SFP" in r or "Divergence" in r for r in reasons)
                if has_reversal and score <= -85:
                    score += 15
                    reasons.append("⚠️ Counter-Trend Short (Wajib Disiplin SL)")
                else:
                    score = 20  # Anulir Short jadi non-rekomendasi
                    reasons.append("🛡️ Veto Makro: Short Dilarang saat BTC Uptrend")
            else:
                score += 20
                reasons.append("🌊 Selaras Tren Makro BTC (Long Diunggulkan)")
    elif mode == "pump" and btc_status and symbol != "BTCUSDT":
        btc_trend = btc_status.get("trend")
        if btc_trend == "Downtrend" and score > 0:
            reasons.append("⚡ Anomali Independen (Melawan Arus BTC)")

    # L. Faktor ATH / ATL Breakout & Fibonacci Extension
    if ath_atl["score_impact"] != 0:
        score += ath_atl["score_impact"]
        reasons.append(ath_atl["label"])

    # M. Faktor Fair Value Gap (FVG Imbalance - Smart Money Concepts)
    if fvg["has_fvg"]:
        score += fvg["score_impact"]
        reasons.append(fvg["label"])

    # N. Faktor Funding Rate Futures (Squeeze Risk Detection)
    if fr_eval["status"] != "NEUTRAL":
        if fr_eval["bias"] == "SHORT_BIAS":
            score -= 20
            reasons.append(fr_eval["label"])
        elif fr_eval["bias"] == "LONG_BIAS":
            score += 20
            reasons.append(fr_eval["label"])

    # O. Penilaian Berdasarkan Mode (Mode Trend vs Mode Pre-Pump)
    price_change_24h = coin_meta.get("price_change_pct", 0)
    if mode == "trend":
        if price_change_24h > 14.0 or rsi_val > 68:
            if score > 0:
                score -= 40
            reasons.append("⛔ Anti-FOMO: Pucuk Pompa / Jenuh Beli (Dilarang Long)")

        if price_change_24h < -18.0 and rsi_val < 28:
            if score < 0:
                score += 40
            reasons.append("⚠️ Anti-Capitulation: Dasar Dump (Rawan Squeeze)")
    elif mode == "pump" and pump_eval:
        if pump_eval.get("is_pump_setup"):
            score = max(score, 0) + pump_eval["score"]
            reasons.insert(0, pump_eval["label"])
            for d in pump_eval.get("details", []):
                reasons.append(d)
        elif pump_eval.get("is_dump_setup"):
            score = min(score, 0) + pump_eval["score"]
            reasons.insert(0, pump_eval["label"])
            for d in pump_eval.get("details", []):
                reasons.append(d)

    # 3. Hitung Setup Eksekusi Cerdas (Institutional Swing Stop Loss)
    # Gunakan harga LIVE real-time saat ini dari ticker (bukan harga candle tutup sebelumnya)
    entry_market = coin_meta["last_price"] if coin_meta.get("last_price", 0) > 0 else close_p
    safe_atr = atr_val if atr_val > 0 else (entry_market * 0.02)
    
    # Deteksi Swing High/Low dari 8 candle terakhir (tidak termasuk candle yang sedang aktif)
    lookback_slice = df.iloc[-9:-1] if len(df) >= 10 else df.iloc[:-1]
    recent_swing_low = lookback_slice['low'].min() if not lookback_slice.empty else (entry_market * 0.98)
    recent_swing_high = lookback_slice['high'].max() if not lookback_slice.empty else (entry_market * 1.02)

    # Minimum Risk Floor (2.2% untuk altcoins, 1.5% untuk BTC/ETH)
    is_major = symbol in ["BTCUSDT", "ETHUSDT"]
    min_risk_pct = (MIN_RISK_PCT_MAJORS / 100.0) if is_major else (MIN_RISK_PCT_ALTCOIN / 100.0)
    min_risk_dist = entry_market * min_risk_pct

    # Jarak risiko dinamis: gabungan ATR 2.0x dan Floor Minimum
    dynamic_risk_distance = max(safe_atr * ATR_SL_MULTIPLIER, min_risk_dist)
    tp_model = "RRR Standard (1:1.5 & 1:2.5)"

    if score > 0:
        direction = "LONG"
        # Stop Loss ditaruh di bawah Swing Low dengan buffer 0.2 ATR, dan wajib melewati dynamic_risk_distance
        swing_sl = recent_swing_low - (0.2 * safe_atr)
        sl = min(entry_market - dynamic_risk_distance, swing_sl)
        
        # Batasi batas maksimal jarak SL agar tidak lebih dari 12%
        if (entry_market - sl) > (entry_market * 0.12):
            sl = entry_market * 0.88

        risk_distance = entry_market - sl
        risk_pct = (risk_distance / entry_market) * 100
        
        if ath_atl["status"] in ["ATH_BREAKOUT", "NEAR_ATH"] and ath_atl["fib_tp1"]:
            tp1 = ath_atl["fib_tp1"]
            tp2 = ath_atl["fib_tp2"]
            tp_model = "Fibonacci Golden Ratio (1.618 & 2.618)"
        else:
            tp1 = entry_market + (risk_distance * RRR_TP1)
            tp2 = entry_market + (risk_distance * RRR_TP2)

        # Proteksi Arah TP Long: Wajib di atas harga Entry dan TP2 > TP1
        if tp1 <= entry_market or tp2 <= tp1:
            tp1 = entry_market + (risk_distance * RRR_TP1)
            tp2 = entry_market + (risk_distance * RRR_TP2)
            tp_model = "RRR Standard (1:1.5 & 1:2.5)"

        # Trigger Breakout (Buy Stop): Tembus pucuk wajar (maksimal 1.5% dari entry)
        trigger_entry = max(min(c['high'], entry_market * 1.015), entry_market * 1.002)

        # Retest Diskon (Limit Buy): Wajib memberikan diskon bermakna (minimal 25% dari jarak SL atau 0.8% dari entry)
        min_discount = max(entry_market * 0.008, 0.25 * risk_distance)
        target_discount_cap = entry_market - min_discount

        if fvg["has_fvg"] and fvg["type"] == "BULLISH_FVG" and fvg["fvg_price"] <= target_discount_cap and fvg["fvg_price"] > sl:
            retest_entry = fvg["fvg_price"]
        elif 'ema_50' in df.columns and df['ema_50'].iloc[-2] <= target_discount_cap and df['ema_50'].iloc[-2] > sl:
            retest_entry = df['ema_50'].iloc[-2]
        else:
            retest_entry = max(entry_market - (0.35 * risk_distance), sl + (0.2 * risk_distance))

    elif score < 0:
        direction = "SHORT"
        # Stop Loss ditaruh di atas Swing High dengan buffer 0.2 ATR, dan wajib melewati dynamic_risk_distance
        swing_sl = recent_swing_high + (0.2 * safe_atr)
        sl = max(entry_market + dynamic_risk_distance, swing_sl)
        
        # Batasi batas maksimal jarak SL agar tidak lebih dari 12%
        if (sl - entry_market) > (entry_market * 0.12):
            sl = entry_market * 1.12

        risk_distance = sl - entry_market
        risk_pct = (risk_distance / entry_market) * 100

        if ath_atl["status"] in ["ATL_BREAKDOWN", "NEAR_ATL"] and ath_atl["fib_tp1"]:
            tp1 = ath_atl["fib_tp1"]
            tp2 = ath_atl["fib_tp2"]
            tp_model = "Fibonacci Inversion (1.618 & 2.618)"
        else:
            tp1 = entry_market - (risk_distance * RRR_TP1)
            tp2 = entry_market - (risk_distance * RRR_TP2)

        # Proteksi Arah TP Short: Wajib di bawah harga Entry dan TP2 < TP1
        if tp1 >= entry_market or tp2 >= tp1:
            tp1 = entry_market - (risk_distance * RRR_TP1)
            tp2 = entry_market - (risk_distance * RRR_TP2)
            tp_model = "RRR Standard (1:1.5 & 1:2.5)"

        # Trigger Breakdown (Sell Stop): Jebol dasar wajar (maksimal 1.5% di bawah entry)
        trigger_entry = min(max(c['low'], entry_market * 0.985), entry_market * 0.998)

        # Retest Pantulan (Limit Sell): Wajib memberikan pantulan bermakna (minimal 25% dari jarak SL atau 0.8% dari entry)
        min_bounce = max(entry_market * 0.008, 0.25 * risk_distance)
        target_bounce_cap = entry_market + min_bounce

        if fvg["has_fvg"] and fvg["type"] == "BEARISH_FVG" and fvg["fvg_price"] >= target_bounce_cap and fvg["fvg_price"] < sl:
            retest_entry = fvg["fvg_price"]
        elif 'ema_50' in df.columns and df['ema_50'].iloc[-2] >= target_bounce_cap and df['ema_50'].iloc[-2] < sl:
            retest_entry = df['ema_50'].iloc[-2]
        else:
            retest_entry = min(entry_market + (0.35 * risk_distance), sl - (0.2 * risk_distance))
    else:
        return None

    def format_price(val: float) -> str:
        if val <= 0:
            return "0.0"
        if val < 0.0001:
            return f"{val:.8f}".rstrip("0").rstrip(".") if len(f"{val:.8f}".rstrip("0").rstrip(".")) > 3 else f"{val:.8f}"
        elif val < 1.0:
            return f"{val:.6f}".rstrip("0").rstrip(".")
        elif val < 10.0:
            return f"{val:.4f}".rstrip("0").rstrip(".")
        else:
            return f"{val:.2f}"

    whale_proj = project_whale_shakeout_levels(entry_market, safe_atr, direction)

    # Hitung Rekomendasi Leverage Aman & Titik Anti-Likuidasi
    safe_lev = int(50.0 / max(risk_pct, 1.0))
    max_safe_leverage = max(min(safe_lev, 20), 2)
    recommended_leverage = "3x - 5x" if max_safe_leverage >= 5 else f"2x - {max_safe_leverage}x"

    if direction == "LONG":
        safe_liq_price = entry_market * (1.0 - (risk_pct * 1.5 / 100.0))
        safe_liq_label = f"< ${format_price(safe_liq_price)}"
    else:
        safe_liq_price = entry_market * (1.0 + (risk_pct * 1.5 / 100.0))
        safe_liq_label = f"> ${format_price(safe_liq_price)}"

    return {
        "symbol": symbol,
        "score": score,
        "direction": direction,
        "entry_market": format_price(entry_market),
        "trigger_entry": format_price(trigger_entry),
        "retest_entry": format_price(retest_entry),
        "sl": format_price(sl),
        "tp1": format_price(tp1),
        "tp2": format_price(tp2),
        "tp_model": tp_model,
        "recommended_leverage": recommended_leverage,
        "max_safe_leverage": f"{max_safe_leverage}x",
        "safe_liq_price": safe_liq_label,
        "funding_rate": fr_eval["rate_pct"],
        "funding_status": fr_eval["status"],
        "fvg_status": fvg["label"] if fvg["has_fvg"] else "-",
        "whale_dump": format_price(whale_proj["whale_dump_pocket"]),
        "whale_pump": format_price(whale_proj["whale_pump_pocket"]),
        "whale_drop_pct": whale_proj["dump_pct"],
        "whale_pump_pct": whale_proj["pump_pct"],
        "whale_shake_pct": whale_proj["shake_range_pct"],
        "whale_tactic_guide": whale_proj["tactic_guide"],
        "ath_atl_status": ath_atl["status"],
        "adx": round(adx_val, 1),
        "daily_trend": daily_trend,
        "risk_pct": round(risk_pct, 2),
        "reasons": reasons,
        "volume_24h": round(coin_meta["quote_volume"] / 1_000_000, 1),
        "change_24h": round(coin_meta["price_change_pct"], 2),
        "rsi": round(rsi_val, 1)
    }

def get_btc_macro_regime() -> Dict[str, Any]:
    """Mengambil status tren makro Bitcoin untuk filter keamanan pasar kripto"""
    df = get_klines_data("BTCUSDT")
    if df.empty or len(df) < 50:
        return {"trend": "Neutral", "price": 0, "desc": "Netral (Data BTC Terbatas)"}

    ema200 = calculate_ema(df['close'], period=min(200, len(df)))
    c = df.iloc[-2]
    price = c['close']
    ema = ema200.iloc[-2]

    if price > ema:
        return {
            "trend": "Uptrend",
            "price": price,
            "desc": f"Uptrend (>EMA200 di ${price:,.0f})"
        }
    else:
        return {
            "trend": "Downtrend",
            "price": price,
            "desc": f"Downtrend (<EMA200 di ${price:,.0f})"
        }

def run_market_screener(timeframe: str = TIMEFRAME, mode: str = "trend") -> Dict[str, Any]:
    """
    Menjalankan pemindaian pasar:
    - Mode 'trend' (Trend Konservatif): Mengikuti rezim makro BTC, minim risiko.
    - Mode 'pump'  (Pre-Pump & Whale Hunter): Mengabaikan BTC, deteksi koin tidur yang diakumulasi Paus & siap meledak.
    """
    min_vol = MIN_24H_VOLUME_USD if mode == "trend" else MIN_VOLUME_PREPUMP_USD
    pairs = get_top_liquid_pairs(min_volume=min_vol, mode=mode)
    if not pairs:
        print("[Warning] Tidak ada koin yang berhasil ditarik.")
        return {"longs": [], "shorts": [], "btc_status": {}, "total_scanned": 0, "timeframe": timeframe, "mode": mode}

    btc_status = get_btc_macro_regime()
    fear_greed = get_crypto_fear_and_greed()
    macro_intel = get_fed_and_macro_intel()
    funding_map = get_all_funding_rates()

    results = []
    for p in pairs:
        res = analyze_single_coin(p, btc_status=btc_status, timeframe=timeframe, funding_map=funding_map, mode=mode)
        if res:
            results.append(res)

    results.sort(key=lambda x: x["score"], reverse=True)

    if mode == "pump":
        # Mode Pre-Pump: Koin tidur (Mid/Low Cap) di area support yang siap terbang
        top_longs = [r for r in results if r["direction"] == "LONG" and r["score"] >= 25][:3]
        if not top_longs:
            top_longs = [r for r in results if r["direction"] == "LONG"][:2]
        top_shorts = []
    else:
        # Filter Kualitas Sinyal Berdasarkan Rezim Pasar Makro
        btc_trend = btc_status.get("trend") if btc_status else "Neutral"
        if btc_trend == "Downtrend":
            # Saat BTC Downtrend: Blokir Long biasa, hanya izinkan Long jika skor sangat tinggi (>=75)
            top_longs = [r for r in results if r["direction"] == "LONG" and r["score"] >= 75][:2]
            top_shorts = [r for r in results if r["direction"] == "SHORT" and r["score"] <= -35]
        elif btc_trend == "Uptrend":
            # Saat BTC Uptrend: Blokir Short biasa, hanya izinkan Short jika skor sangat negatif (<=-75)
            top_longs = [r for r in results if r["direction"] == "LONG" and r["score"] >= 35][:2]
            top_shorts = [r for r in results if r["direction"] == "SHORT" and r["score"] <= -75]
        else:
            top_longs = [r for r in results if r["direction"] == "LONG" and r["score"] >= 40][:2]
            top_shorts = [r for r in results if r["direction"] == "SHORT" and r["score"] <= -40]

        top_shorts.sort(key=lambda x: x["score"])
        top_shorts = top_shorts[:2]

    # Jalankan Triple Screen Multi-Timeframe (1D ➔ 4H ➔ 15M) Bi-Directional
    # untuk koin-koin terbaik yang disaring oleh pasar
    candidates = []
    seen = set()
    for r in (top_longs + top_shorts):
        sym = r.get("symbol")
        if sym and sym not in seen:
            seen.add(sym)
            candidates.append(sym)

    coins_mtf = []
    for sym in candidates[:3]:
        mtf_data = analyze_specific_coin(symbol=sym, timeframe=timeframe, mode=mode)
        if mtf_data and mtf_data.get("is_mtf_check"):
            coins_mtf.append(mtf_data)

    return {
        "is_market_scan": True,
        "timeframe": timeframe,
        "mode": mode,
        "btc_status": btc_status,
        "fear_greed": fear_greed,
        "macro_intel": macro_intel,
        "coins_analyzed": coins_mtf,
        "longs": top_longs,
        "shorts": top_shorts,
        "total_scanned": len(results)
    }

def analyze_specific_coin(symbol: str, timeframe: str = TIMEFRAME, mode: str = "trend") -> Dict[str, Any]:
    """
    Menganalisis satu koin spesifik secara komprehensif menggunakan:
    1. Triple Screen Multi-Timeframe: 1D (Arus Laut) ➔ 4H (Ombak) ➔ 15M (Sniper)
    2. Bi-Directional Setups: 🟢 Setup LONG & 🔴 Setup SHORT (Zona Entry, SL, TP1, TP2, RRR)
    3. Persentase Rekomendasi Probabilitas: Potensi Long X% vs Potensi Short Y%
    4. Sentinel Fundamental: Token Unlock (> 1% suplai) & Isu Keamanan
    """
    clean_sym = symbol.upper().strip()
    if not clean_sym.endswith(QUOTE_ASSET):
        clean_sym += QUOTE_ASSET

    # 1. Ambil data klines untuk 3 Timeframe (1D, 4H, 15m)
    df_1d = get_klines_data(clean_sym, interval="1d", limit=60)
    df_4h = get_klines_data(clean_sym, interval="4h", limit=60)
    df_15m = get_klines_data(clean_sym, interval="15m", limit=60)

    if df_15m.empty or len(df_15m) < 15:
        print(f"[Error] Data klines tidak mencukupi untuk {clean_sym}")
        return {}

    # Hitung indikator untuk tiap timeframe
    for df in [df_1d, df_4h, df_15m]:
        if not df.empty and len(df) >= 14:
            df['ema20'] = calculate_ema(df['close'], period=min(20, len(df)))
            df['ema50'] = calculate_ema(df['close'], period=min(50, len(df)))
            df['ema200'] = calculate_ema(df['close'], period=min(200, len(df)))
            df['rsi'] = calculate_rsi(df['close'], period=14)
            df['atr'] = calculate_atr(df['high'], df['low'], df['close'], period=14)

    curr_price = float(df_15m['close'].iloc[-1])
    atr_15m = float(df_15m['atr'].iloc[-1]) if 'atr' in df_15m.columns and pd.notna(df_15m['atr'].iloc[-1]) else curr_price * 0.015
    if atr_15m <= 0:
        atr_15m = curr_price * 0.015

    # 2. Rangkuman 1D (Harian)
    if not df_1d.empty and len(df_1d) >= 14:
        close_1d = float(df_1d['close'].iloc[-1])
        ema20_1d = float(df_1d['ema20'].iloc[-1])
        rsi_1d = float(df_1d['rsi'].iloc[-1])
        vol_1d = float(df_1d['volume'].iloc[-1])
        vol_avg_1d = float(df_1d['volume'].tail(10).mean())
        trend_1d_bull = close_1d > ema20_1d
        trend_1d_desc = "Uptrend (>EMA20)" if trend_1d_bull else "Downtrend (<EMA20)"
        is_selling_climax = (vol_1d >= 1.8 * vol_avg_1d) and (close_1d < df_1d['open'].iloc[-1])
        climax_note = " | Vol: Selling Climax" if is_selling_climax else ""
    else:
        close_1d = curr_price
        ema20_1d = curr_price
        rsi_1d = 50.0
        trend_1d_bull = True
        trend_1d_desc = "Netral"
        climax_note = ""

    # 3. Rangkuman 4H (4 Jam)
    if not df_4h.empty and len(df_4h) >= 14:
        close_4h = float(df_4h['close'].iloc[-1])
        ema20_4h = float(df_4h['ema20'].iloc[-1])
        rsi_4h = float(df_4h['rsi'].iloc[-1])
        trend_4h_bull = close_4h > ema20_4h
        trend_4h_desc = "Uptrend (>EMA20)" if trend_4h_bull else "Downtrend (<EMA20)"
        swing_low_4h = float(df_4h['low'].tail(15).min())
        swing_high_4h = float(df_4h['high'].tail(15).max())
    else:
        close_4h = curr_price
        ema20_4h = curr_price
        rsi_4h = 50.0
        trend_4h_bull = True
        trend_4h_desc = "Netral"
        swing_low_4h = curr_price * 0.95
        swing_high_4h = curr_price * 1.05

    # 4. Rangkuman 15m (Sniper)
    rsi_15m = float(df_15m['rsi'].iloc[-1])
    swing_low_15m = float(df_15m['low'].tail(10).min())
    swing_high_15m = float(df_15m['high'].tail(10).max())
    
    last_15m = df_15m.iloc[-1]
    c_tot = last_15m['high'] - last_15m['low']
    wick_bwh_pct = ((min(last_15m['open'], last_15m['close']) - last_15m['low']) / c_tot * 100) if c_tot > 0 else 0
    wick_atas_pct = ((last_15m['high'] - max(last_15m['open'], last_15m['close'])) / c_tot * 100) if c_tot > 0 else 0
    vol_ratio_15m = float(last_15m['volume'] / df_15m['volume'].tail(10).mean()) if df_15m['volume'].tail(10).mean() > 0 else 1.0
    is_green_15m = last_15m['close'] >= last_15m['open']

    # 5. Hitung Probabilitas Kekuatan & Deteksi Tipe Setup (Anti-Shorting the Bottom)
    long_pts = 0
    short_pts = 0

    dist_ema20_1d = ((curr_price - ema20_1d) / ema20_1d * 100) if ema20_1d > 0 else 0
    is_extreme_oversold = (rsi_1d < 25 or rsi_4h < 22 or dist_ema20_1d <= -20)
    is_extreme_overbought = (rsi_1d > 75 or rsi_4h > 78)

    if is_extreme_oversold:
        setup_type = "🩸 Pantulan Jenuh Jual (Rebound)"
        long_pts += 30   # Dorongan kuat pantulan elastis
        short_pts -= 15  # Penalti keras agar tidak short di dasar!
    elif is_extreme_overbought:
        setup_type = "⚠️ Pucuk Jenuh Beli (Koreksi)"
        short_pts += 30
        long_pts -= 15
    else:
        if trend_1d_bull:
            setup_type = "🌊 Mengikuti Tren (Trend Following)"
            long_pts += 15
        else:
            setup_type = "📉 Tren Menurun"
            short_pts += 15

        if trend_4h_bull:
            long_pts += 15
        else:
            short_pts += 15

    # Validasi Reaksi Lilin 15m
    if wick_bwh_pct >= 45:
        long_pts += 15
    elif wick_atas_pct >= 45:
        short_pts += 15

    if vol_ratio_15m >= 1.4:
        if is_green_15m:
            long_pts += 10
        else:
            short_pts += 10

    diff = long_pts - short_pts
    shift = max(min(diff, 30), -30)
    prob_long = int(50 + shift)
    prob_short = 100 - prob_long

    # Visual Bar
    green_blocks = int(round(prob_long / 10))
    white_blocks = 10 - green_blocks
    bar_str = ("🟩" * green_blocks) + ("⬜" * white_blocks)

    if prob_long >= 55:
        conclusion = "Peluang lebih condong ke LONG"
    elif prob_short >= 55:
        conclusion = "Peluang lebih condong ke SHORT"
    else:
        conclusion = "Kekuatan Seimbang 50-50"

    # Helper format price
    def _fmt(val: float) -> str:
        if val <= 0: return "0.0"
        if val < 0.0001: return f"{val:.8f}".rstrip("0").rstrip(".")
        elif val < 1.0: return f"{val:.6f}".rstrip("0").rstrip(".")
        elif val < 10.0: return f"{val:.4f}".rstrip("0").rstrip(".")
        else: return f"{val:.2f}"

    # 6. SETUP LONG BERBASIS SUPPORT & PULLBACK
    key_supp_long = swing_low_4h if swing_low_4h > 0 else (curr_price * 0.95)
    if curr_price < key_supp_long:
        key_supp_long = min(curr_price * 0.98, swing_low_15m)
    
    dist_supp_pct = ((curr_price - key_supp_long) / key_supp_long) * 100 if key_supp_long > 0 else 0

    if dist_supp_pct <= 2.0:
        long_status = f"✅ Dekat Support (${_fmt(key_supp_long)})"
        long_entry_low = max(key_supp_long, curr_price - (0.5 * atr_15m))
        long_entry_high = curr_price + (0.2 * atr_15m)
        long_sl = key_supp_long - (0.3 * atr_15m)
    else:
        long_status = f"⚠️ Tunggu Koreksi (+{dist_supp_pct:.1f}% dr Supp ${_fmt(key_supp_long)})"
        move_up = curr_price - key_supp_long
        long_entry_low = key_supp_long + (0.15 * move_up)
        long_entry_high = key_supp_long + (0.50 * move_up)
        long_sl = key_supp_long - (0.25 * atr_15m)

    long_mid_entry = (long_entry_low + long_entry_high) / 2
    long_risk = max(long_mid_entry - long_sl, long_mid_entry * 0.015)
    long_risk_pct = (long_risk / long_mid_entry) * 100
    long_tp1 = long_mid_entry + (1.5 * long_risk)
    long_tp2 = max(swing_high_4h, long_mid_entry + (2.5 * long_risk))

    # 7. SETUP SHORT BERBASIS RESISTENSI & PULLBACK
    key_res_short = swing_high_4h if swing_high_4h > 0 else (curr_price * 1.05)
    if curr_price > key_res_short:
        key_res_short = max(curr_price * 1.02, swing_high_15m)

    dist_res_pct = ((key_res_short - curr_price) / key_res_short) * 100 if key_res_short > 0 else 0

    if dist_res_pct <= 2.0:
        short_status = f"✅ Dekat Resistensi (${_fmt(key_res_short)})"
        short_entry_low = curr_price - (0.2 * atr_15m)
        short_entry_high = min(key_res_short, curr_price + (0.5 * atr_15m))
        short_sl = key_res_short + (0.3 * atr_15m)
    else:
        short_status = f"⚠️ Tunggu Pantulan (-{dist_res_pct:.1f}% dr Res ${_fmt(key_res_short)})"
        move_down = key_res_short - curr_price
        short_entry_low = key_res_short - (0.50 * move_down)
        short_entry_high = key_res_short - (0.15 * move_down)
        short_sl = key_res_short + (0.25 * atr_15m)

    short_mid_entry = (short_entry_low + short_entry_high) / 2
    short_risk = max(short_sl - short_mid_entry, short_mid_entry * 0.015)
    short_risk_pct = (short_risk / short_mid_entry) * 100
    short_tp1 = short_mid_entry - (1.5 * short_risk)
    short_tp2 = min(swing_low_4h, short_mid_entry - (2.5 * short_risk))

    # 8. Token Intel
    token_intel = get_token_fundamental_intel(clean_sym)

    btc_status = get_btc_macro_regime()
    fear_greed = get_crypto_fear_and_greed()
    macro_intel = get_fed_and_macro_intel()

    return {
        "is_mtf_check": True,
        "symbol": clean_sym,
        "timeframe": timeframe,
        "mode": mode,
        "curr_price": curr_price,
        "curr_price_str": _fmt(curr_price),
        "btc_status": btc_status,
        "fear_greed": fear_greed,
        "macro_intel": macro_intel,
        "bias": {
            "setup_type": setup_type,
            "prob_long": prob_long,
            "prob_short": prob_short,
            "bar": bar_str,
            "conclusion": conclusion
        },
        "mtf": {
            "1d": {
                "trend": trend_1d_desc,
                "rsi": rsi_1d,
                "ema20": _fmt(ema20_1d),
                "climax": climax_note
            },
            "4h": {
                "trend": trend_4h_desc,
                "rsi": rsi_4h,
                "support": _fmt(swing_low_4h),
                "resist": _fmt(swing_high_4h)
            },
            "15m": {
                "rsi": rsi_15m,
                "bounce_point": _fmt(swing_low_15m),
                "risk_pct": long_risk_pct
            }
        },
        "setup_long": {
            "status": long_status,
            "entry_range": f"${_fmt(long_entry_low)} - ${_fmt(long_entry_high)}",
            "sl": f"${_fmt(long_sl)} (-{long_risk_pct:.2f}%)",
            "tp1": f"${_fmt(long_tp1)} (+{((long_tp1-long_mid_entry)/long_mid_entry)*100:.2f}%)",
            "tp2": f"${_fmt(long_tp2)} (+{((long_tp2-long_mid_entry)/long_mid_entry)*100:.2f}%)",
            "rr_tp1": f"1 : {((long_tp1-long_mid_entry)/long_risk):.1f}",
            "rr_tp2": f"1 : {((long_tp2-long_mid_entry)/long_risk):.1f}"
        },
        "setup_short": {
            "status": short_status,
            "entry_range": f"${_fmt(short_entry_low)} - ${_fmt(short_entry_high)}",
            "sl": f"${_fmt(short_sl)} (+{short_risk_pct:.2f}%)",
            "tp1": f"${_fmt(short_tp1)} (-{((short_mid_entry-short_tp1)/short_mid_entry)*100:.2f}%)",
            "tp2": f"${_fmt(short_tp2)} (-{((short_mid_entry-short_tp2)/short_mid_entry)*100:.2f}%)",
            "rr_tp1": f"1 : {((short_mid_entry-short_tp1)/short_risk):.1f}",
            "rr_tp2": f"1 : {((short_mid_entry-short_tp2)/short_risk):.1f}"
        },
        "token_intel": token_intel,
        "total_scanned": 1
    }
