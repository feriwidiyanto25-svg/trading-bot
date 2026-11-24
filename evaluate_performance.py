"""
Evaluator Kinerja & Win-Rate Otomatis (Auto-Auditor)
Membaca riwayat sinyal di signals_history.json, memeriksa pergerakan harga sesudahnya,
dan menghitung persentase kemenangan (Win Rate %), Profit Factor, dan status eksekusi.
"""
import json
import os
import datetime
import requests
import pandas as pd
from typing import List, Dict, Any
from config import BINANCE_BASE_URL, TIMEFRAME

SIGNALS_FILE = "signals_history.json"

def load_signals_history() -> List[Dict[str, Any]]:
    """Membaca seluruh riwayat sinyal dari signals_history.json"""
    if not os.path.exists(SIGNALS_FILE):
        print(f"[!] File {SIGNALS_FILE} belum ditemukan.")
        return []

    records = []
    with open(SIGNALS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                records.append(data)
            except Exception:
                continue
    return records

def fetch_future_klines(symbol: str, start_time_ms: int, limit: int = 500) -> pd.DataFrame:
    """Mengambil candle granular (15m) yang terjadi SETELAH sinyal dikeluarkan untuk evaluasi presisi tinggi"""
    url = f"{BINANCE_BASE_URL}/klines"
    params = {
        "symbol": symbol,
        "interval": "15m",
        "startTime": start_time_ms,
        "limit": limit
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code != 200:
            return pd.DataFrame()
        raw = res.json()
        if not raw or not isinstance(raw, list):
            return pd.DataFrame()
        df = pd.DataFrame(raw).iloc[:, [0, 1, 2, 3, 4, 5]]
        df.columns = ["time", "open", "high", "low", "close", "volume"]
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df
    except Exception:
        return pd.DataFrame()

def evaluate_single_signal(sig: Dict[str, Any], signal_time_iso: str) -> Dict[str, Any]:
    """Mengevaluasi apakah satu sinyal mengenai TP1, TP2, atau SL terlebih dahulu"""
    symbol = sig["symbol"]
    direction = sig["direction"]
    try:
        entry = float(sig["entry_market"]) if "entry_market" in sig else float(sig["entry"])
        sl = float(sig["sl"])
        tp1 = float(sig["tp1"])
        tp2 = float(sig["tp2"])
    except (ValueError, KeyError):
        return None

    # Ubah timestamp ISO ke milidetik
    try:
        dt = datetime.datetime.fromisoformat(signal_time_iso)
        start_ms = int(dt.timestamp() * 1000)
    except Exception:
        return None

    df_future = fetch_future_klines(symbol, start_ms, limit=100)
    if df_future.empty or len(df_future) < 2:
        return {
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "status": "RUNNING",
            "pnl_pct": 0.0,
            "candles_elapsed": len(df_future)
        }

    # Lewati candle pertama (candle sinyal) dan evaluasi candle berikutnya
    test_candles = df_future.iloc[1:]

    hit_tp1 = False
    hit_tp2 = False
    hit_sl = False

    for _, row in test_candles.iterrows():
        h = row['high']
        l = row['low']

        if direction == "LONG":
            if l <= sl:
                hit_sl = True
                break
            if h >= tp2:
                hit_tp2 = True
                hit_tp1 = True
                break
            elif h >= tp1:
                hit_tp1 = True
        elif direction == "SHORT":
            if h >= sl:
                hit_sl = True
                break
            if l <= tp2:
                hit_tp2 = True
                hit_tp1 = True
                break
            elif l <= tp1:
                hit_tp1 = True

    if hit_tp2:
        status = "WIN TP2 (Maksimal)"
        pnl_pct = sig.get("risk_pct", 1.5) * 2.5
    elif hit_tp1:
        status = "WIN TP1 (Target 1)"
        pnl_pct = sig.get("risk_pct", 1.5) * 1.5
    elif hit_sl:
        status = "LOSS SL (Kena Stop)"
        pnl_pct = -sig.get("risk_pct", 1.5)
    else:
        status = "RUNNING (Sedang Berjalan)"
        pnl_pct = 0.0

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "status": status,
        "pnl_pct": round(pnl_pct, 2),
        "candles_elapsed": len(test_candles)
    }

def run_performance_audit():
    """Menjalankan audit lengkap dan mencetak laporan statistik Win-Rate"""
    print("\n" + "="*85)
    print("               AUDIT KINERJA & EVALUASI WIN-RATE OTOMATIS")
    print(f"               Waktu Audit: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*85)

    records = load_signals_history()
    if not records:
        print("[!] Belum ada riwayat sinyal di 'signals_history.json'.")
        return

    # Ambil sinyal unik berdasarkan simbol dan timestamp
    unique_signals = []
    seen = set()

    for rec in records:
        ts = rec.get("timestamp", "")
        data = rec.get("data", {})
        all_signals = data.get("longs", []) + data.get("shorts", [])
        for s in all_signals:
            key = f"{s.get('symbol')}_{ts[:16]}"
            if key not in seen:
                seen.add(key)
                unique_signals.append((s, ts))

    print(f"[i] Ditemukan {len(unique_signals)} sinyal unik dalam riwayat.")
    print("[+] Sedang memeriksa pergerakan harga historis di Binance...\n")

    results = []
    for s, ts in unique_signals:
        res = evaluate_single_signal(s, ts)
        if res:
            results.append(res)

    if not results:
        print("[!] Tidak ada sinyal yang dapat dievaluasi.")
        return

    # Cetak Tabel Rincian
    print("-" * 85)
    print(f"{'No':<3} {'Pair':<12} {'Arah':<7} {'Entry':<12} {'Status Hasil':<25} {'PnL Estimasi'}")
    print("-" * 85)

    wins = 0
    losses = 0
    running = 0

    for i, r in enumerate(results, 1):
        status = r['status']
        if "WIN" in status:
            wins += 1
            color_mark = "[CUAN]"
        elif "LOSS" in status:
            losses += 1
            color_mark = "[CUT]"
        else:
            running += 1
            color_mark = "[WAIT]"

        pnl_str = f"+{r['pnl_pct']}%" if r['pnl_pct'] > 0 else f"{r['pnl_pct']}%"
        print(f"{i:<3} {r['symbol']:<12} {r['direction']:<7} {r['entry']:<12} {status:<25} {pnl_str} {color_mark}")

    print("-" * 85)

    # Hitung Statistik Ringkasan
    completed_trades = wins + losses
    win_rate = (wins / completed_trades * 100) if completed_trades > 0 else 0.0

    print("\n" + "="*40 + " RINGKASAN STATISTIK " + "="*40)
    print(f"  • Total Sinyal Diuji      : {len(results)} Sinyal")
    print(f"  • Sinyal Selesai (Closed) : {completed_trades} Sinyal")
    print(f"  • Sinyal Berjalan (Active): {running} Sinyal")
    print(f"  • Menang (Hit TP1 / TP2)  : {wins} Sinyal")
    print(f"  • Kalah (Hit Stop Loss)   : {losses} Sinyal")
    print(f"  • WIN RATE RESMI          : {win_rate:.1f}%")
    print("="*85 + "\n")

if __name__ == "__main__":
    run_performance_audit()
