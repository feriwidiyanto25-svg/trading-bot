"""
Modul Analisis Makro Ekonomi The Fed, Sentimen Pasar & Intelijen Paus
Melacak rilis data The Fed (FOMC, CPI, PCE, NFP), Fear & Greed Index,
serta memproyeksikan estimasi pergerakan manipulasi paus (Whale News Projections).
"""
import os
import json
import requests
import datetime
from typing import Dict, Any, List

FEAR_GREED_API = "https://api.alternative.me/fng/?limit=1"
BIQUOTE_API = "https://biquote.io/api/calendar?importance=high&countries=US"
FALLBACK_CALENDAR_API = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "macro_calendar_cache.json")
FNG_CACHE_FILE = os.path.join(os.path.dirname(__file__), "fng_cache.json")

def get_crypto_fear_and_greed() -> Dict[str, Any]:
    """Mengambil sentimen pasar kripto global (Fear & Greed Index) dengan caching"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(FEAR_GREED_API, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", [{}])[0]
            val = int(data.get("value", 50))
            classification = data.get("value_classification", "Neutral")
            
            if val <= 25:
                bias = "Extreme Fear (Peluang Emas Akumulasi saat SFP muncul / Buy The Blood)"
            elif val <= 45:
                bias = "Fear (Pasar Ragu-ragu / Penjual Dominan)"
            elif val <= 65:
                bias = "Neutral / Greed (Sentimen Sehat)"
            else:
                bias = "Extreme Greed (Waspada Pucuk / Rawan Long Squeeze Paus)"
                
            result = {
                "value": val,
                "classification": classification,
                "bias_desc": bias
            }
            try:
                with open(FNG_CACHE_FILE, "w") as f:
                    json.dump(result, f)
            except Exception:
                pass
            return result
    except Exception:
        pass

    # Fallback ke cache jika offline / timeout
    if os.path.exists(FNG_CACHE_FILE):
        try:
            with open(FNG_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
            
    return {"value": 50, "classification": "Neutral", "bias_desc": "Data Sentimen Terbatas"}

def _fetch_calendar_raw() -> List[Dict[str, Any]]:
    """Mengambil data kalender dari primary (biquote) atau fallback (faireconomy) dengan cache 15 menit"""
    # 1. Cek cache lokal jika masih segar (< 15 menit)
    if os.path.exists(CACHE_FILE):
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            age_seconds = datetime.datetime.now().timestamp() - mtime
            if age_seconds < 900:  # 15 menit
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                    if cached:
                        return cached
        except Exception:
            pass

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    events = []

    # 2. Coba API Utama: Biquote
    try:
        res = requests.get(BIQUOTE_API, headers=headers, timeout=5)
        if res.status_code == 200:
            raw = res.json()
            if isinstance(raw, list) and len(raw) > 0:
                for item in raw:
                    events.append({
                        "title": item.get("name", "US Macro Event"),
                        "country": item.get("countryCode", "US"),
                        "impact": "High" if item.get("importance") == "high" else "Medium",
                        "date": item.get("time"),
                        "forecast": str(item.get("forecast", "-")),
                        "previous": str(item.get("previous", "-"))
                    })
    except Exception:
        pass

    # 3. Fallback jika biquote gagal
    if not events:
        try:
            res = requests.get(FALLBACK_CALENDAR_API, headers=headers, timeout=5)
            if res.status_code == 200:
                raw = res.json()
                if isinstance(raw, list):
                    for item in raw:
                        if item.get("country") == "USD" and item.get("impact") in ["High", "Medium"]:
                            events.append(item)
        except Exception:
            pass

    # Simpan ke cache jika berhasil
    if events:
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(events, f)
        except Exception:
            pass
    elif os.path.exists(CACHE_FILE):
        # Jika gagal tarik baru tapi cache lama ada, gunakan cache lama
        try:
            with open(CACHE_FILE, "r") as f:
                events = json.load(f)
        except Exception:
            pass

    return events

def get_fed_and_macro_intel() -> Dict[str, Any]:
    """
    Melacak jadwal rilis berita The Fed / US High Impact terdekat,
    menganalisis konsensus (Forecast vs Previous), dan memprediksi taktik manipulasi paus.
    """
    raw_events = _fetch_calendar_raw()
    if not raw_events:
        return {
            "has_alert": False,
            "status_code": "GREEN",
            "status_text": "🟢 AMAN (Tidak ada data agenda The Fed / US Macro)",
            "diff_minutes": 9999,
            "nearest_event": None,
            "all_events": [],
            "whale_tactic": "Pasar bergerak normal mengikuti teknikal murni."
        }

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    parsed_events = []

    for e in raw_events:
        date_str = e.get("date", "")
        if not date_str:
            continue
        try:
            # Handle ISO string with or without Z
            if date_str.endswith("Z"):
                event_dt_utc = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                event_dt = datetime.datetime.fromisoformat(date_str)
                event_dt_utc = event_dt.astimezone(datetime.timezone.utc)
            
            diff_minutes = (event_dt_utc - now_utc).total_seconds() / 60
            
            # Rentang: 2 jam lalu s/d 48 jam ke depan
            if -120 <= diff_minutes <= 2880:
                e_copy = dict(e)
                e_copy["diff_minutes"] = int(diff_minutes)
                wib_time = event_dt_utc + datetime.timedelta(hours=7)
                e_copy["event_time_wib"] = wib_time.strftime("%d %b %H:%M WIB")
                parsed_events.append(e_copy)
        except Exception:
            continue

    parsed_events.sort(key=lambda x: abs(x["diff_minutes"]))

    if not parsed_events:
        return {
            "has_alert": False,
            "status_code": "GREEN",
            "status_text": "🟢 AMAN (Tidak ada rilis berita The Fed / US High Impact dalam 48 jam)",
            "diff_minutes": 9999,
            "nearest_event": None,
            "all_events": [],
            "whale_tactic": "Pasar bergerak normal mengikuti teknikal murni tanpa ancaman blackout makro."
        }

    nearest = parsed_events[0]
    diff_min = nearest["diff_minutes"]
    title = nearest.get("title", "High Impact Event")
    impact = nearest.get("impact", "High")
    forecast = nearest.get("forecast", "-")
    previous = nearest.get("previous", "-")

    # Evaluasi Status Alert Window
    if 0 <= diff_min <= 60:
        status_code = "RED_ALERT"
        status_text = f"🔴 RED ALERT ({diff_min} Menit Lagi Menuju Rilis!)"
    elif -60 <= diff_min < 0:
        status_code = "AFTER_SHOCK"
        status_text = f"🟠 AFTER-SHOCK / GEMPA PASCA RILIS ({abs(diff_min)} Menit Lalu)"
    elif 60 < diff_min <= 360:
        hours = diff_min // 60
        mins = diff_min % 60
        time_lbl = f"{hours} Jam {mins} Menit" if mins > 0 else f"{hours} Jam"
        status_code = "YELLOW_ALERT"
        status_text = f"🟡 PERINGATAN ({time_lbl} Lagi - {nearest['event_time_wib']})"
    else:
        status_code = "UPCOMING"
        status_text = f"ℹ️ AGENDA TERDEKAT ({nearest['event_time_wib']})"

    # Analisis Prediksi Taktik Manipulasi Paus (Whale Playbook)
    title_lower = title.lower()
    if any(term in title_lower for term in ["cpi", "pce", "inflation", "ppi"]):
        whale_tactic = (
            f"Data Inflasi AS ({title} | Forecast: {forecast} vs Prev: {previous}). "
            f"Jika angka riil LEBIH TINGGI dari forecast, The Fed akan Hawkish (bunga tinggi bertahan lama) "
            f"-> Paus akan membanting pasar (DUMP SQUEEZE). Sebaliknya jika inflasi melandai, koin akan reli roket (PUMP). "
            f"Taktik Paus: 15-30 menit sebelum rilis, paus memancing false breakout (Judas Swing) untuk melahap stop loss retail."
        )
    elif any(term in title_lower for term in ["fed", "fomc", "powell", "rate", "interest"]):
        whale_tactic = (
            f"Kebijakan Suku Bunga / Pidato The Fed ({title}). Paus biasanya mengosongkan order book (likuiditas tipis) "
            f"sehingga candle bisa melompat 3%-6% dua arah menyapu posisi Long dan Short sekaligus (Double Sweep). "
            f"Taktik Paus: Jangan pasang Market Order! Masuk hanya melalui Trigger Breakout atau antre jaring diskon di level Paus."
        )
    elif any(term in title_lower for term in ["gdp", "growth"]):
        whale_tactic = (
            f"Data Pertumbuhan Ekonomi AS ({title} | Forecast: {forecast} vs Prev: {previous}). "
            f"GDP yang melonjak kuat mengindikasikan ekonomi 'panas' yang menunda pemangkasan suku bunga Fed. "
            f"Paus cenderung memanfaatkan volatilitas awal untuk menyapu level High/Low mingguan sebelum tren sebenarnya terbentuk."
        )
    elif any(term in title_lower for term in ["confidence", "sentiment"]):
        whale_tactic = (
            f"Sentimen Konsumen AS ({title} | Forecast: {forecast} vs Prev: {previous}). "
            f"Keyakinan konsumen berdampak pada belanja riil dan proyeksi inflasi. "
            f"Paus sering menguji level Support/Resistance utama sesaat sebelum angka dirilis."
        )
    elif any(term in title_lower for term in ["pmi", "claims", "payrolls", "nfp", "employment", "jobless"]):
        whale_tactic = (
            f"Data Tenaga Kerja & Manufaktur AS ({title} | Forecast: {forecast} vs Prev: {previous}). "
            f"Pasar tenaga kerja yang solid memberi ruang bagi Fed untuk tetap ketat. "
            f"Paus bersiap memicu squeeze pada koin bervolume tinggi."
        )
    else:
        whale_tactic = f"Rilis {title} [{impact}]. Waspadai lonjakan volatilitas mendadak 1.5x - 2.0x ATR."

    return {
        "has_alert": True,
        "status_code": status_code,
        "status_text": status_text,
        "diff_minutes": diff_min,
        "nearest_event": nearest,
        "all_events": parsed_events[:4],
        "whale_tactic": whale_tactic
    }

def project_whale_shakeout_levels(entry_price: float, atr: float, direction: str) -> Dict[str, Any]:
    """
    Menghitung estimasi zona bantingan dan zona pompa paus saat berita rilis:
    Rentang goncangan berita High Impact rata-rata mencapai 2.0x ATR.
    """
    safe_atr = atr if atr > 0 else (entry_price * 0.02)
    shake_range = safe_atr * 2.0
    dump_pocket = max(entry_price - shake_range, entry_price * 0.1)
    pump_pocket = entry_price + shake_range
    
    dump_pct = ((entry_price - dump_pocket) / entry_price) * 100
    pump_pct = ((pump_pocket - entry_price) / entry_price) * 100
    
    if direction == "LONG":
        tactic_guide = (
            f"Jaring Beli Diskon di ${dump_pocket:.4f} (-{dump_pct:.1f}%) | "
            f"TP Pompa Paus di ${pump_pocket:.4f} (+{pump_pct:.1f}%)"
        )
    else:
        tactic_guide = (
            f"TP Bantingan Paus di ${dump_pocket:.4f} (-{dump_pct:.1f}%) | "
            f"Jaring Short Pucuk di ${pump_pocket:.4f} (+{pump_pct:.1f}%)"
        )

    return {
        "shake_range": shake_range,
        "shake_range_pct": round((shake_range / entry_price) * 100, 2),
        "whale_dump_pocket": dump_pocket,
        "whale_pump_pocket": pump_pocket,
        "dump_pct": round(dump_pct, 1),
        "pump_pct": round(pump_pct, 1),
        "tactic_guide": tactic_guide
    }
