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
    MAX_PAIRS_TO_ANALYZE,
    TOP_GAINERS_COUNT,
    TIMEFRAME,
    CANDLE_LIMIT,
    ATR_SL_MULTIPLIER,
    RRR_TP1,
    RRR_TP2
)
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
    detect_fair_value_gap
)
from macro_news import (
    get_crypto_fear_and_greed,
    get_fed_and_macro_intel,
    project_whale_shakeout_levels
)
from funding_rates import (
    get_all_funding_rates,
    evaluate_funding_rate
)

def get_top_liquid_pairs() -> List[Dict[str, Any]]:
    """
    Mengambil seluruh ticker 24 jam dan memfilter koin berlikuiditas tinggi
    serta mencatat kedalaman order book (bid vs ask)
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
        "UUSDT", "USDUSDT", "AEURUSDT", "USDPUSDT", "WBTCUSDT", "USD1USDT"
    }

    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith(QUOTE_ASSET) or symbol in excluded_coins:
            continue
        if symbol.endswith("USDUSDT") or symbol.endswith("BUSDT"):
            continue
            
        try:
            quote_volume = float(t.get("quoteVolume", 0))
            price_change_pct = float(t.get("priceChangePercent", 0))
            last_price = float(t.get("lastPrice", 0))
            bid_qty = float(t.get("bidQty", 0))
            ask_qty = float(t.get("askQty", 0))
        except (ValueError, TypeError):
            continue

        if quote_volume >= MIN_24H_VOLUME_USD and last_price > 0:
            valid_pairs.append({
                "symbol": symbol,
                "quote_volume": quote_volume,
                "price_change_pct": price_change_pct,
                "last_price": last_price,
                "bid_qty": bid_qty,
                "ask_qty": ask_qty
            })

    # 1. Ambil koin dengan volume transaksi terbesar
    by_volume = sorted(valid_pairs, key=lambda x: x["quote_volume"], reverse=True)[:MAX_PAIRS_TO_ANALYZE]

    # 2. Ambil koin yang sedang meledak naik (Top Gainers)
    by_gainers = sorted(valid_pairs, key=lambda x: x["price_change_pct"], reverse=True)[:TOP_GAINERS_COUNT]

    # Gabungkan tanpa duplikasi simbol
    combined = {p["symbol"]: p for p in (by_volume + by_gainers)}
    return list(combined.values())

def get_klines_data(symbol: str, interval: str = TIMEFRAME, limit: int = CANDLE_LIMIT) -> pd.DataFrame:
    """Mengambil data OHLCV historis dari Binance"""
    url = f"{BINANCE_BASE_URL}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        raw = res.json()
    except Exception:
        return pd.DataFrame()

    if not raw or not isinstance(raw, list):
        return pd.DataFrame()

    df = pd.DataFrame(raw).iloc[:, [0, 1, 2, 3, 4, 5]]
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df

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

def analyze_single_coin(coin_meta: Dict[str, Any], btc_status: Dict[str, Any] = None, timeframe: str = TIMEFRAME, funding_map: Dict[str, float] = None) -> Dict[str, Any]:
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
    14. Manajemen Risiko Anti-Likuidasi & Rekomendasi Leverage Aman
    """
    symbol = coin_meta["symbol"]
    df = get_klines_data(symbol, interval=timeframe)
    if len(df) < 50:
        return None

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
    if close_p > ema200_p and daily_trend == "Uptrend":
        score += 25
        reasons.append("🏆 MTF Selaras (1D & 4H Uptrend)")
    elif close_p < ema200_p and daily_trend == "Downtrend":
        score -= 25
        reasons.append("🏆 MTF Selaras (1D & 4H Downtrend)")
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

    # K. Faktor Rezim Pasar Bitcoin (BTC Macro Correlation)
    if btc_status and symbol != "BTCUSDT":
        btc_trend = btc_status.get("trend")
        if btc_trend == "Downtrend" and score > 0:
            score -= 15
            reasons.append("⚠️ BTC Downtrend (Waspada Long)")
        elif btc_trend == "Uptrend" and score < 0:
            score += 15
            reasons.append("⚠️ BTC Uptrend (Waspada Short)")

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
        if score > 0: # Sinyal Long
            if fr_eval["bias"] == "SHORT_BIAS":
                score -= 20
                reasons.append(fr_eval["label"])
            elif fr_eval["bias"] == "LONG_BIAS":
                score += 20
                reasons.append(fr_eval["label"])
        elif score < 0: # Sinyal Short
            if fr_eval["bias"] == "SHORT_BIAS":
                score -= 20
                reasons.append(fr_eval["label"])
            elif fr_eval["bias"] == "LONG_BIAS":
                score += 20
                reasons.append(fr_eval["label"])

    # 3. Hitung Setup Eksekusi Cerdas
    # Gunakan harga LIVE real-time saat ini dari ticker (bukan harga candle tutup sebelumnya)
    entry_market = coin_meta["last_price"] if coin_meta.get("last_price", 0) > 0 else close_p
    safe_atr = atr_val if atr_val > 0 else (entry_market * 0.02)
    risk_distance = safe_atr * ATR_SL_MULTIPLIER
    tp_model = "RRR Standard (1:1.5 & 1:2.5)"

    if score > 0:
        direction = "LONG"
        sl = entry_market - risk_distance
        risk_pct = ((entry_market - sl) / entry_market) * 100
        
        if ath_atl["status"] in ["ATH_BREAKOUT", "NEAR_ATH"] and ath_atl["fib_tp1"]:
            tp1 = ath_atl["fib_tp1"]
            tp2 = ath_atl["fib_tp2"]
            tp_model = "Fibonacci Golden Ratio (1.618 & 2.618)"
        else:
            tp1 = entry_market + (risk_distance * RRR_TP1)
            tp2 = entry_market + (risk_distance * RRR_TP2)

        # Trigger Breakout (Buy Stop): Tembus pucuk (High), wajib di atas harga pasar saat ini
        trigger_entry = max(c['high'], entry_market * 1.002)

        # Retest Diskon (Limit Buy): Gunakan bibir FVG jika tersedia, atau swing low candle sebelumnya
        if fvg["has_fvg"] and fvg["type"] == "BULLISH_FVG" and fvg["fvg_price"] < entry_market and fvg["fvg_price"] > sl:
            retest_entry = fvg["fvg_price"]
        elif c['low'] < entry_market and c['low'] > sl:
            retest_entry = c['low']
        else:
            retest_entry = max(entry_market - (0.5 * risk_distance), sl + (0.2 * risk_distance))

    elif score < 0:
        direction = "SHORT"
        sl = entry_market + risk_distance
        risk_pct = ((sl - entry_market) / entry_market) * 100

        if ath_atl["status"] in ["ATL_BREAKDOWN", "NEAR_ATL"] and ath_atl["fib_tp1"]:
            tp1 = ath_atl["fib_tp1"]
            tp2 = ath_atl["fib_tp2"]
            tp_model = "Fibonacci Inversion (1.618 & 2.618)"
        else:
            tp1 = entry_market - (risk_distance * RRR_TP1)
            tp2 = entry_market - (risk_distance * RRR_TP2)

        # Trigger Breakdown (Sell Stop): Jebol dasar (Low), wajib di bawah harga pasar saat ini
        trigger_entry = min(c['low'], entry_market * 0.998)

        # Retest Pantulan (Limit Sell): Gunakan bibir FVG jika tersedia, atau swing high candle sebelumnya
        if fvg["has_fvg"] and fvg["type"] == "BEARISH_FVG" and fvg["fvg_price"] > entry_market and fvg["fvg_price"] < sl:
            retest_entry = fvg["fvg_price"]
        elif c['high'] > entry_market and c['high'] < sl:
            retest_entry = c['high']
        else:
            retest_entry = min(entry_market + (0.5 * risk_distance), sl - (0.2 * risk_distance))
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

def run_market_screener(timeframe: str = TIMEFRAME) -> Dict[str, Any]:
    """Menjalankan pemindaian seluruh koin teratas dan menghasilkan Top 5 Long & Short"""
    pairs = get_top_liquid_pairs()
    if not pairs:
        print("[Warning] Tidak ada koin yang berhasil ditarik.")
        return {"longs": [], "shorts": [], "btc_status": {}, "total_scanned": 0, "timeframe": timeframe}

    btc_status = get_btc_macro_regime()
    fear_greed = get_crypto_fear_and_greed()
    macro_intel = get_fed_and_macro_intel()
    funding_map = get_all_funding_rates()

    results = []
    for p in pairs:
        res = analyze_single_coin(p, btc_status=btc_status, timeframe=timeframe, funding_map=funding_map)
        if res:
            results.append(res)

    results.sort(key=lambda x: x["score"], reverse=True)

    top_longs = [r for r in results if r["direction"] == "LONG" and r["score"] >= 30][:5]

    top_shorts = [r for r in results if r["direction"] == "SHORT" and r["score"] <= -30]
    top_shorts.sort(key=lambda x: x["score"])
    top_shorts = top_shorts[:5]

    return {
        "timeframe": timeframe,
        "btc_status": btc_status,
        "fear_greed": fear_greed,
        "macro_intel": macro_intel,
        "longs": top_longs,
        "shorts": top_shorts,
        "total_scanned": len(results)
    }
