"""
Modul Analisis Indikator Teknikal, Pola Candlestick & Deteksi Pasar Lanjutan
Dibuat dengan Pure Pandas & NumPy.
"""
import pandas as pd
import numpy as np

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Menghitung Exponential Moving Average (EMA)"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Menghitung Simple Moving Average (SMA)"""
    return series.rolling(window=period).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Menghitung Relative Strength Index (RSI)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Menghitung Average True Range (ATR) untuk Stop Loss dinamis"""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Menghitung Average Directional Index (ADX) untuk mendeteksi apakah pasar
    sedang tren kuat (ADX >= 25) atau sedang sideways / choppy (ADX < 20).
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm_smooth / tr_smooth.replace(0, np.nan))

    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100 * (di_diff / di_sum.replace(0, np.nan))
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx.fillna(20)

def detect_candlestick_patterns(df: pd.DataFrame) -> dict:
    """
    Mendeteksi pola candlestick pada candle terakhir yang SUDAH SELESAI (closed candle).
    """
    if len(df) < 3:
        return {"pattern": "None", "bias": "Neutral"}
        
    c0 = df.iloc[-2]  # Candle yang baru saja ditutup resmi
    c1 = df.iloc[-3]  # Candle sebelumnya
    
    body0 = abs(c0['close'] - c0['open'])
    lower_wick0 = min(c0['open'], c0['close']) - c0['low']
    upper_wick0 = c0['high'] - max(c0['open'], c0['close'])
    
    # 1. Bullish Pin Bar / Hammer: Ekor bawah >= 2x body, ekor atas kecil
    if lower_wick0 >= 2 * body0 and upper_wick0 <= 0.4 * body0 and body0 > 0:
        return {"pattern": "Bullish Pin Bar (Hammer)", "bias": "Bullish"}
        
    # 2. Bearish Pin Bar / Shooting Star: Ekor atas >= 2x body, ekor bawah kecil
    if upper_wick0 >= 2 * body0 and lower_wick0 <= 0.4 * body0 and body0 > 0:
        return {"pattern": "Bearish Pin Bar (Shooting Star)", "bias": "Bearish"}
        
    # 3. Bullish Engulfing: Candle hijau menelan seluruh candle merah sebelumnya
    if c0['close'] > c0['open'] and c1['close'] < c1['open']:
        if c0['close'] >= c1['open'] and c0['open'] <= c1['close']:
            return {"pattern": "Bullish Engulfing", "bias": "Bullish"}
            
    # 4. Bearish Engulfing: Candle merah menelan seluruh candle hijau sebelumnya
    if c0['close'] < c0['open'] and c1['close'] > c1['open']:
        if c0['close'] <= c1['open'] and c0['open'] >= c1['close']:
            return {"pattern": "Bearish Engulfing", "bias": "Bearish"}
            
    return {"pattern": "Normal", "bias": "Neutral"}

def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 8) -> dict:
    """
    Mendeteksi Swing Failure Pattern (SFP) / Sapu Likuiditas Dua Arah:
    - Bullish SFP: Harga menusuk ke bawah Swing Low sebelumnya, tapi candle TUTUP kembali di atasnya (Reclaim).
    - Bearish SFP: Harga menusuk ke atas Swing High sebelumnya, tapi candle TUTUP kembali di bawahnya (Rejection).
    """
    if len(df) < lookback + 3:
        return {"type": "None", "label": "", "bias": "Neutral", "score_impact": 0}

    c0 = df.iloc[-2]  # Closed candle
    prev = df.iloc[-(lookback + 2):-2]  # N candle sebelumnya

    recent_low = prev['low'].min()
    recent_high = prev['high'].max()

    body = abs(c0['close'] - c0['open'])
    lower_wick = min(c0['open'], c0['close']) - c0['low']
    upper_wick = c0['high'] - max(c0['open'], c0['close'])

    # 1. Bullish SFP: Sapu Likuiditas Bawah (Spring / Reclaim)
    if c0['low'] < recent_low and c0['close'] > recent_low:
        if lower_wick >= 1.2 * body:
            return {
                "type": "Bullish SFP",
                "label": "💎 Sapu Likuiditas Bawah (SFP Reclaim)",
                "bias": "Bullish",
                "score_impact": 35
            }

    # 2. Bearish SFP: Sapu Likuiditas Atas (Upthrust / Rejection)
    if c0['high'] > recent_high and c0['close'] < recent_high:
        if upper_wick >= 1.2 * body:
            return {
                "type": "Bearish SFP",
                "label": "🔻 Sapu Likuiditas Atas (SFP Rejection)",
                "bias": "Bearish",
                "score_impact": -35
            }

    return {"type": "None", "label": "", "bias": "Neutral", "score_impact": 0}

def detect_wick_rejection(df: pd.DataFrame) -> dict:
    """
    Mendeteksi jebakan jarum ekor panjang (Bull Trap & Bear Trap):
    - Bull Trap: Ekor atas sangat panjang di puncak (pembeli dibanting).
    - Bear Trap: Ekor bawah sangat panjang di dasar (penjual disapu).
    """
    if len(df) < 3:
        return {"warning": "", "bias": "Neutral", "penalty": 0}

    c0 = df.iloc[-2]
    body = max(abs(c0['close'] - c0['open']), 1e-8)
    lower_wick = min(c0['open'], c0['close']) - c0['low']
    upper_wick = c0['high'] - max(c0['open'], c0['close'])
    candle_range = max(c0['high'] - c0['low'], 1e-8)

    # Bull Trap Rejection: Ekor atas >= 2x body dan >= 45% dari total range candle
    if upper_wick >= 2.0 * body and upper_wick >= 0.45 * candle_range:
        return {
            "warning": "⚠️ Awas Bull Trap (Jarum Pucuk Dibanting)",
            "bias": "Bearish_Trap",
            "penalty": -30
        }

    # Bear Trap Rejection: Ekor bawah >= 2x body dan >= 45% dari total range candle
    if lower_wick >= 2.0 * body and lower_wick >= 0.45 * candle_range:
        return {
            "warning": "⚠️ Awas Bear Trap (Jarum Dasar Ditarik Naik)",
            "bias": "Bullish_Trap",
            "penalty": 30
        }

    return {"warning": "", "bias": "Neutral", "penalty": 0}

def detect_volume_status(df: pd.DataFrame) -> dict:
    """
    Memvalidasi apakah pergerakan harga didukung volume nyata atau volume kering (manipulasi)
    """
    if len(df) < 25:
        return {"status": "Normal", "label": "", "score_impact": 0}

    c0 = df.iloc[-2]
    vol_sma = df['vol_sma_20'].iloc[-2]
    vol = c0['volume']

    if vol_sma <= 0:
        return {"status": "Normal", "label": "", "score_impact": 0}

    # Volume Spike Masif (> 2x rata-rata)
    if vol >= 2.0 * vol_sma:
        return {
            "status": "Volume Spike",
            "label": "🔥 Volume Masif (>2x Avg)",
            "score_impact": 20 if c0['close'] >= c0['open'] else -20
        }
    # Volume Kering (< 0.6x rata-rata) - Rawan Fakeout
    elif vol <= 0.6 * vol_sma:
        return {
            "status": "Dry Volume",
            "label": "⚠️ Volume Kering (Rawan Fakeout)",
            "score_impact": -15 if c0['close'] >= c0['open'] else 15
        }

    return {"status": "Normal", "label": "", "score_impact": 0}

def detect_ath_atl_and_fibonacci(df: pd.DataFrame) -> dict:
    """
    Mendeteksi apakah koin berada dalam fase ATH (All-Time High / Price Discovery)
    atau ATL (All-Time Low / Terjun Bebas), serta memproyeksikan target harga menggunakan
    Fibonacci Extensions (Golden Ratio 1.618 & Euphoria 2.618).
    """
    if len(df) < 30:
        return {"status": "Normal", "label": "", "fib_tp1": None, "fib_tp2": None, "score_impact": 0}

    c0 = df.iloc[-2]  # Candle penutupan sinyal
    history = df.iloc[:-2]  # Riwayat sebelumnya

    highest_high = history['high'].max()
    lowest_low = history['low'].min()

    close_p = c0['close']
    high_p = c0['high']
    low_p = c0['low']

    # 1. Deteksi ATH Breakout (Price Discovery Mode)
    if close_p >= highest_high or (high_p >= highest_high and close_p >= 0.99 * highest_high):
        lookback_slice = df.iloc[-25:-2]
        swing_low = lookback_slice['low'].min()
        pullback_depth = max(highest_high - swing_low, highest_high * 0.02)

        fib_1618 = highest_high + (0.618 * pullback_depth)
        fib_2618 = highest_high + (1.618 * pullback_depth)

        return {
            "status": "ATH_BREAKOUT",
            "label": "🚀 ATH Price Discovery",
            "fib_tp1": fib_1618,
            "fib_tp2": fib_2618,
            "score_impact": 30
        }
    elif close_p >= 0.98 * highest_high:
        lookback_slice = df.iloc[-25:-2]
        swing_low = lookback_slice['low'].min()
        pullback_depth = max(highest_high - swing_low, highest_high * 0.02)
        fib_1618 = highest_high + (0.618 * pullback_depth)
        fib_2618 = highest_high + (1.618 * pullback_depth)

        return {
            "status": "NEAR_ATH",
            "label": "🔥 Menguji ATH (<2% Pucuk)",
            "fib_tp1": fib_1618,
            "fib_tp2": fib_2618,
            "score_impact": 15
        }

    # 2. Deteksi ATL Breakdown (Price Free-Fall)
    if close_p <= lowest_low or (low_p <= lowest_low and close_p <= 1.01 * lowest_low):
        lookback_slice = df.iloc[-25:-2]
        swing_high = lookback_slice['high'].max()
        relief_depth = max(swing_high - lowest_low, lowest_low * 0.02)

        fib_1618_down = max(lowest_low - (0.618 * relief_depth), lowest_low * 0.5)
        fib_2618_down = max(lowest_low - (1.618 * relief_depth), lowest_low * 0.2)

        return {
            "status": "ATL_BREAKDOWN",
            "label": "⚠️ ATL Free-Fall (Jebol Terendah)",
            "fib_tp1": fib_1618_down,
            "fib_tp2": fib_2618_down,
            "score_impact": -30
        }
    elif close_p <= 1.02 * lowest_low:
        lookback_slice = df.iloc[-25:-2]
        swing_high = lookback_slice['high'].max()
        relief_depth = max(swing_high - lowest_low, lowest_low * 0.02)
        fib_1618_down = max(lowest_low - (0.618 * relief_depth), lowest_low * 0.5)
        fib_2618_down = max(lowest_low - (1.618 * relief_depth), lowest_low * 0.2)

        return {
            "status": "NEAR_ATL",
            "label": "🔻 Menguji ATL (<2% Dasar)",
            "fib_tp1": fib_1618_down,
            "fib_tp2": fib_2618_down,
            "score_impact": -15
        }

    return {"status": "Normal", "label": "", "fib_tp1": None, "fib_tp2": None, "score_impact": 0}

def detect_rsi_divergence(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Mendeteksi RSI Divergence (Leading Indicator):
    - Bullish Divergence: Harga membentuk Lower Low, tapi RSI membentuk Higher Low (Sinyal Pantulan Kuat).
    - Bearish Divergence: Harga membentuk Higher High, tapi RSI membentuk Lower High (Sinyal Pucuk/Dump Kuat).
    """
    if len(df) < lookback + 5 or 'rsi' not in df.columns:
        return {"type": "None", "label": "", "score_impact": 0}

    slice_df = df.iloc[-(lookback + 2):-2]
    c_recent = df.iloc[-2]  # Closed candle

    curr_price_low = c_recent['low']
    curr_price_high = c_recent['high']
    curr_rsi = c_recent['rsi']

    half_len = max(len(slice_df) // 2, 5)
    past_slice = slice_df.iloc[:half_len]

    # 1. Bullish Divergence: Harga lebih rendah, tapi RSI lebih tinggi
    past_low_price = past_slice['low'].min()
    past_low_idx = past_slice['low'].idxmin()
    past_low_rsi = df.loc[past_low_idx, 'rsi']

    if curr_price_low < past_low_price and curr_rsi > (past_low_rsi + 2.5) and curr_rsi < 55:
        return {
            "type": "Bullish Divergence",
            "label": "🔥 Bullish Divergence (RSI Menguat)",
            "score_impact": 35
        }

    # 2. Bearish Divergence: Harga lebih tinggi, tapi RSI lebih rendah
    past_high_price = past_slice['high'].max()
    past_high_idx = past_slice['high'].idxmax()
    past_high_rsi = df.loc[past_high_idx, 'rsi']

    if curr_price_high > past_high_price and curr_rsi < (past_high_rsi - 2.5) and curr_rsi > 45:
        return {
            "type": "Bearish Divergence",
            "label": "🔻 Bearish Divergence (RSI Melemah)",
            "score_impact": -35
        }

    return {"type": "None", "label": "", "score_impact": 0}
