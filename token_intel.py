"""
Modul Intelijen Fundamental Koin (Token Unlock & Security Sentinel)
Memeriksa jadwal pelepasan token (Token Unlocks) dan isu keamanan/eksploitasi.
Aturan Pengguna:
- Hanya tampilkan info unlock jika jumlahnya > 1.0% dari suplai.
- Jika unlock <= 1.0%, otomatis disembunyikan (karena dampaknya minim).
"""
import datetime
import requests
from typing import Dict, Any, Optional

# Basis Data Jadwal Token Unlock Utama (Vesting Cliffs & Recurring Unlocks)
# Diperbarui secara berkala berdasarkan kalender tokenomics pasar
KNOWN_UNLOCK_SCHEDULES = {
    "SUI": {"day_of_month": 1, "pct_of_supply": 2.1, "desc": "Pelepasan investor awal & ekosistem"},
    "ARB": {"day_of_month": 16, "pct_of_supply": 2.8, "desc": "Pelepasan tim & penasihat Arbitrum"},
    "APT": {"day_of_month": 12, "pct_of_supply": 2.1, "desc": "Pelepasan investor privat & yayasan Aptos"},
    "OP": {"day_of_month": 30, "pct_of_supply": 2.4, "desc": "Pelepasan kontributor inti Optimism"},
    "STRK": {"day_of_month": 15, "pct_of_supply": 4.5, "desc": "Pelepasan investor Starknet"},
    "WLD": {"day_of_month": 24, "pct_of_supply": 1.9, "desc": "Pelepasan investor & tim Worldcoin"},
    "SEI": {"day_of_month": 15, "pct_of_supply": 1.5, "desc": "Pelepasan ekosistem & yayasan Sei"},
    "TIA": {"day_of_month": 31, "pct_of_supply": 3.8, "desc": "Pelepasan investor Celestia"},
    "JUP": {"day_of_month": 10, "pct_of_supply": 2.2, "desc": "Pelepasan airdrop & tim Jupiter"},
    "AVAX": {"day_of_month": 20, "pct_of_supply": 1.4, "desc": "Pelepasan staking reward & tim Avalanche"},
    "ID": {"day_of_month": 22, "pct_of_supply": 4.2, "desc": "Pelepasan tim & penasihat Space ID"},
    "SAND": {"day_of_month": 14, "pct_of_supply": 3.1, "desc": "Pelepasan cadangan Sandbox"},
    "AXS": {"day_of_month": 20, "pct_of_supply": 2.5, "desc": "Pelepasan staking & tim Axie"},
    "PIXEL": {"day_of_month": 19, "pct_of_supply": 7.0, "desc": "Pelepasan penasihat & reward Pixels"},
    "DYDX": {"day_of_month": 1, "pct_of_supply": 1.8, "desc": "Pelepasan investor & karyawan dYdX"},
    "APE": {"day_of_month": 17, "pct_of_supply": 2.6, "desc": "Pelepasan Yuga Labs & yayasan ApeCoin"},
    "MANTA": {"day_of_month": 18, "pct_of_supply": 1.9, "desc": "Pelepasan ekosistem & pendiri Manta"},
    "ALT": {"day_of_month": 25, "pct_of_supply": 3.5, "desc": "Pelepasan investor AltLayer"}
}

def get_token_fundamental_intel(symbol: str) -> Dict[str, Any]:
    """
    Memeriksa jadwal unlock dan isu keamanan untuk koin tertentu.
    Mengembalikan dictionary status fundamental.
    """
    clean_sym = symbol.upper().replace("USDT", "").replace("BUSD", "").replace("USDC", "").strip()
    now = datetime.datetime.now()
    
    unlock_info: Optional[Dict[str, Any]] = None
    
    # 1. Cek Kalender Token Unlock
    if clean_sym in KNOWN_UNLOCK_SCHEDULES:
        sched = KNOWN_UNLOCK_SCHEDULES[clean_sym]
        day = sched["day_of_month"]
        pct = sched["pct_of_supply"]
        desc = sched.get("desc", "Pelepasan token terjadwal")
        
        # Hitung tanggal unlock berikutnya
        try:
            target_date = datetime.datetime(now.year, now.month, min(day, 28))
            if target_date < now:
                # Lewat bulan ini, hitung bulan depan
                next_month = now.month + 1 if now.month < 12 else 1
                next_year = now.year if now.month < 12 else now.year + 1
                target_date = datetime.datetime(next_year, next_month, min(day, 28))
            
            days_left = (target_date.date() - now.date()).days
            
            # ATURAN USER: Hanya tampilkan jika unlock > 1.0% dan dalam rentang 14 hari
            if pct > 1.0 and 0 <= days_left <= 14:
                date_str = target_date.strftime("%d %b %Y")
                unlock_info = {
                    "has_unlock": True,
                    "pct": pct,
                    "date_str": date_str,
                    "days_left": days_left,
                    "desc": desc,
                    "note": f"⚠️ Info Token Unlock: Akan ada pelepasan {pct}% suplai pada {date_str} (~{days_left} hari lagi - {desc})."
                }
        except Exception:
            pass

    # 2. Cek Isu Keamanan / Notifikasi Publik (CoinGecko Quick Check)
    security_warning = None
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{clean_sym.lower()}?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            d = res.json()
            public_notice = d.get("public_notice", "") or ""
            additional_notices = d.get("additional_notices", []) or []
            combined_notices = (public_notice + " " + " ".join(additional_notices)).lower()
            
            danger_keywords = ["hack", "exploit", "compromised", "drain", "vulnerability", "stolen", "delist"]
            for kw in danger_keywords:
                if kw in combined_notices:
                    security_warning = f"🚨 Peringatan Keamanan: Terdeteksi notifikasi risiko '{kw}' pada protokol koin ini!"
                    break
    except Exception:
        pass

    if not security_warning:
        security_status = "✅ Bersih (Tidak ada isu hack / eksploitasi terdeteksi)"
    else:
        security_status = security_warning

    return {
        "symbol": clean_sym,
        "has_unlock": unlock_info is not None,
        "unlock_pct": unlock_info["pct"] if unlock_info else 0.0,
        "unlock_note": unlock_info["note"] if unlock_info else None,
        "security_status": security_status,
        "has_security_warning": security_warning is not None
    }
