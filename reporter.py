"""
Modul Pelaporan (Formatter Telegram & Terminal)
Mencakup Radar Sinyal Teknis, Radar The Fed, Fear & Greed Sentimen,
serta Proyeksi Target Manipulasi Paus (Whale Shakeout Levels).
"""
import json
import datetime
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def format_telegram_message(data: dict) -> str:
    """Membuat pesan terformat rapi untuk notifikasi Telegram lengkap dengan Intelijen Paus"""
    now = datetime.datetime.now().strftime("%d %b %Y | %H:%M WIB")
    longs = data.get("longs", [])
    shorts = data.get("shorts", [])
    btc = data.get("btc_status", {})
    fg = data.get("fear_greed", {})
    macro = data.get("macro_intel", {})

    tf = data.get("timeframe", "4h")
    tf_label = "15 Menit (Intraday Cepat)" if tf == "15m" else ("1 Jam (Intraday)" if tf == "1h" else "4 Jam (Swing)")

    msg = f"📊 *[RADAR PASAR CRYPTO & SETUP EKSEKUSI CERDAS]*\n"
    msg += f"🕒 Waktu: {now}\n"
    msg += f"⏱️ Timeframe Analisis: *{tf}* ({tf_label})\n"
    if btc:
        msg += f"🌐 Rezim BTC: *{btc.get('desc', 'N/A')}*\n"
    if fg:
        msg += f"😨 Fear & Greed: *{fg.get('value', 50)}/100* ({fg.get('classification', 'Neutral')})\n"
    msg += f"🔍 Total Koin Dipindai: {data.get('total_scanned', 0)} koin\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    # --- RADAR THE FED & BERITA MAKRO ---
    if macro and macro.get("has_alert"):
        status_text = macro.get("status_text", "")
        nearest = macro.get("nearest_event", {})
        msg += f"🚨 *RADAR THE FED & AGENDA MAKRO:*\n"
        msg += f"• Status: *{status_text}*\n"
        if nearest:
            msg += (
                f"• Event: *{nearest.get('title')}* [{nearest.get('impact')}]\n"
                f"• Jadwal: {nearest.get('event_time_wib')} (Forecast: {nearest.get('forecast')} vs Prev: {nearest.get('previous')})\n"
            )
        msg += f"• 🐋 *Taktik Paus:* _{macro.get('whale_tactic')}_\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    # --- TOP 5 LONGS ---
    msg += "🟢 *TOP POTENSI NAIK (LONG SETUP)*\n\n"
    if longs:
        for i, c in enumerate(longs, 1):
            reasons_str = " + ".join(c['reasons'][:3])
            tp_info = c.get('tp_model', 'RRR Standard')
            fvg_line = f"   • {c['fvg_status']}\n" if c.get('fvg_status') and c.get('fvg_status') != "-" else ""
            msg += (
                f"{i}. 🚀 *{c['symbol']}* (Skor: `+{c['score']}` | 1D: `{c.get('daily_trend')}`)\n"
                f"   • Sinyal: _{reasons_str}_\n"
                f"{fvg_line}"
                f"   • Market Entry: `${c['entry_market']}`\n"
                f"   • ⚡ Trigger Konfirmasi: `${c['trigger_entry']}` (Tembus Pucuk)\n"
                f"   • 🎯 Retest Diskon: `${c['retest_entry']}`\n"
                f"   • Stop Loss: `${c['sl']}` (-{c['risk_pct']}%)\n"
                f"   • Target TP 1: `${c['tp1']}` ({tp_info})\n"
                f"   • Target TP 2: `${c['tp2']}`\n"
                f"   • 🛡️ *Anti-Likuidasi:* Rekomendasi Lev *{c.get('recommended_leverage', '3x-5x')}* (Maks: `{c.get('max_safe_leverage')}`) | Batas Liq: `{c.get('safe_liq_price')}`\n"
                f"   • 💰 *Alokasi Modal:* Maks. 20%–30% saldo (sisa 70% penahan liq)\n"
                f"   • ⚡ *Funding Rate:* `{c.get('funding_rate', 0.01)}%`\n"
                f"   • 🐋 *Level Paus:* Dump `${c.get('whale_dump')}` (-{c.get('whale_drop_pct')}%) | Pump `${c.get('whale_pump')}` (+{c.get('whale_pump_pct')}%)\n\n"
            )
    else:
        msg += "   _Tidak ada koin yang memenuhi kriteria Long saat ini._\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    # --- TOP 5 SHORTS ---
    msg += "🔴 *TOP POTENSI TURUN (SHORT SETUP)*\n\n"
    if shorts:
        for i, c in enumerate(shorts, 1):
            reasons_str = " + ".join(c['reasons'][:3])
            tp_info = c.get('tp_model', 'RRR Standard')
            fvg_line = f"   • {c['fvg_status']}\n" if c.get('fvg_status') and c.get('fvg_status') != "-" else ""
            msg += (
                f"{i}. 🔻 *{c['symbol']}* (Skor: `{c['score']}` | 1D: `{c.get('daily_trend')}`)\n"
                f"   • Sinyal: _{reasons_str}_\n"
                f"{fvg_line}"
                f"   • Market Entry: `${c['entry_market']}`\n"
                f"   • ⚡ Trigger Konfirmasi: `${c['trigger_entry']}` (Jebol Dasar)\n"
                f"   • 🎯 Retest Diskon: `${c['retest_entry']}`\n"
                f"   • Stop Loss: `${c['sl']}` (+{c['risk_pct']}%)\n"
                f"   • Target TP 1: `${c['tp1']}` ({tp_info})\n"
                f"   • Target TP 2: `${c['tp2']}`\n"
                f"   • 🛡️ *Anti-Likuidasi:* Rekomendasi Lev *{c.get('recommended_leverage', '3x-5x')}* (Maks: `{c.get('max_safe_leverage')}`) | Batas Liq: `{c.get('safe_liq_price')}`\n"
                f"   • 💰 *Alokasi Modal:* Maks. 20%–30% saldo (sisa 70% penahan liq)\n"
                f"   • ⚡ *Funding Rate:* `{c.get('funding_rate', 0.01)}%`\n"
                f"   • 🐋 *Level Paus:* Dump `${c.get('whale_dump')}` (-{c.get('whale_drop_pct')}%) | Pump `${c.get('whale_pump')}` (+{c.get('whale_pump_pct')}%)\n\n"
            )
    else:
        msg += "   _Tidak ada koin yang memenuhi kriteria Short saat ini._\n\n"

    msg += (
        "💡 *Panduan Eksekusi Emas:*\n"
        "• Anti-Likuidasi: Gunakan leverage aman (3x-5x) & masuk maks. 20%-30% dari saldo dompet.\n"
        "• Pastikan titik likuidasi exchange Anda berada jauh di luar batas aman yang tertera.\n"
        "• Kunci 50% profit di TP1 dan segera geser SL ke BEP (Zero-Risk Trade).\n"
    )
    return msg

def print_terminal_report(data: dict):
    """Menampilkan hasil pemindaian di Terminal/CMD dengan format tabel rapi dan Intelijen Paus"""
    btc = data.get("btc_status", {})
    fg = data.get("fear_greed", {})
    macro = data.get("macro_intel", {})
    longs = data.get("longs", [])
    shorts = data.get("shorts", [])

    print("\n" + "="*118)
    print("                 RADAR PASAR CRYPTO & SETUP EKSEKUSI CERDAS (BINANCE)")
    print(f"                 Waktu: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if btc:
        print(f"                 Rezim Bitcoin: {btc.get('desc', 'N/A')}")
    if fg:
        print(f"                 Sentimen Global: Fear & Greed Index {fg.get('value', 50)}/100 [{fg.get('classification', 'Neutral')}]")
        print(f"                 Bias Sentimen: {fg.get('bias_desc', '-')}")
    print("="*118)

    # --- BANNER RADAR THE FED & AGENDA MAKRO ---
    if macro and macro.get("has_alert"):
        print("\n" + "!"*118)
        print(f" 🚨 RADAR THE FED & AGENDA MAKRO AS: {macro.get('status_text')}")
        nearest = macro.get("nearest_event", {})
        if nearest:
            print(f"    • Rilis Terdekat : {nearest.get('title')} [{nearest.get('impact')}]")
            print(f"    • Waktu Rilis    : {nearest.get('event_time_wib')} (Hitung Mundur: {nearest.get('diff_minutes')} menit)")
            print(f"    • Konsensus Data : Forecast: {nearest.get('forecast')} | Previous: {nearest.get('previous')}")
        
        all_e = macro.get("all_events", [])
        if len(all_e) > 1:
            agenda_preview = " | ".join([f"{e.get('title')} ({e.get('event_time_wib')})" for e in all_e[1:3]])
            print(f"    • Agenda Berikut : {agenda_preview}")

        print(f"\n 🐋 INTELIJEN TAKTIK PAUS (WHALE PLAYBOOK):")
        print(f"    {macro.get('whale_tactic')}")
        print("!"*118)

    # Status Catatan Red Alert
    is_red_alert = macro.get("status_code") in ["RED_ALERT", "AFTER_SHOCK"]
    if is_red_alert:
        print("\n⚠️  [CATATAN RED ALERT AKTIF]: Berita High Impact sedang/segera rilis! Sinyal trading tetap ditampilkan di bawah,")
        print("    namun HINDARI MARKET ORDER instan. Pasang Buy Stop di atas Trigger atau jaring Limit di Zona Paus.\n")

    # --- TABEL LONG ---
    print("\n[+] TOP POTENSI NAIK (LONG WATCHLIST)")
    print("-" * 118)
    print(f"{'No':<3} {'Pair':<10} {'Skor':<6} {'1D/ADX':<10} {'Market':<11} {'Trigger':<11} {'Retest':<11} {'Stop Loss':<11} {'TP 1':<11} {'Alasan & Sinyal'}")
    print("-" * 118)
    if longs:
        for i, c in enumerate(longs, 1):
            reasons = ", ".join(c['reasons'][:2])
            mtf_adx = f"{c.get('daily_trend', 'N/A')[:2].upper()}/{c.get('adx', 0):.0f}"
            print(f"{i:<3} {c['symbol']:<10} +{c['score']:<5} {mtf_adx:<10} {c['entry_market']:<11} {c['trigger_entry']:<11} {c['retest_entry']:<11} {c['sl']:<11} {c['tp1']:<11} {reasons}")
    else:
        print("   (Tidak ada koin yang memenuhi syarat Long berkonfirmasi kuat saat ini)")

    # --- TABEL SHORT ---
    print("\n[-] TOP POTENSI TURUN (SHORT WATCHLIST)")
    print("-" * 118)
    print(f"{'No':<3} {'Pair':<10} {'Skor':<6} {'1D/ADX':<10} {'Market':<11} {'Trigger':<11} {'Retest':<11} {'Stop Loss':<11} {'TP 1':<11} {'Alasan & Sinyal'}")
    print("-" * 118)
    if shorts:
        for i, c in enumerate(shorts, 1):
            reasons = ", ".join(c['reasons'][:2])
            mtf_adx = f"{c.get('daily_trend', 'N/A')[:2].upper()}/{c.get('adx', 0):.0f}"
            print(f"{i:<3} {c['symbol']:<10} {c['score']:<6} {mtf_adx:<10} {c['entry_market']:<11} {c['trigger_entry']:<11} {c['retest_entry']:<11} {c['sl']:<11} {c['tp1']:<11} {reasons}")
    else:
        print("   (Tidak ada koin yang memenuhi syarat Short berkonfirmasi kuat saat ini)")

    # --- TABEL PROYEKSI PERGERAKAN PAUS (WHALE SHAKEOUT ZONES) ---
    active_signals = longs + shorts
    if active_signals:
        print("\n" + "="*118)
        print(" 🐋 PROYEKSI TARGET GOYANGAN PAUS SAAT BERITA RILIS (WHALE SHAKEOUT TARGETS - 2.0x ATR)")
        print("    Estimasi jangkauan bantingan (Dump Pocket) dan lonjakan pompa (Pump Pocket) saat terjadi news spike:")
        print("-" * 118)
        print(f"{'Pair':<10} {'Arah':<7} {'Harga Market':<14} {'Zona Bantingan Paus':<24} {'Zona Pompa Paus':<24} {'Rentang Goyangan'}")
        print("-" * 118)
        for c in active_signals:
            dump_str = f"${c.get('whale_dump')} (-{c.get('whale_drop_pct')}%)"
            pump_str = f"${c.get('whale_pump')} (+{c.get('whale_pump_pct')}%)"
            shake_str = f"±{c.get('whale_shake_pct')}%"
            print(f"{c['symbol']:<10} {c['direction']:<7} {c['entry_market']:<14} {dump_str:<24} {pump_str:<24} {shake_str}")
        print("="*118)

        print("\n" + "="*118)
        print(" 🛡️ PANDUAN MANAJEMEN RISIKO & ANTI-LIKUIDASI (SAFE LEVERAGE & FVG IMBALANCE)")
        print("    Aturan agar harga likuidasi TIDAK PERNAH tersentuh sebelum Stop Loss:")
        print("-" * 118)
        print(f"{'Pair':<10} {'Arah':<7} {'SL Distance':<13} {'Rekomendasi Lev':<18} {'Batas Likuidasi Wajib':<26} {'Funding':<10} {'Smart Money FVG'}")
        print("-" * 118)
        for c in active_signals:
            fvg_disp = c.get('fvg_status', '-') if c.get('fvg_status') != '-' else 'Normal'
            fr_str = f"{c.get('funding_rate', 0.01)}%"
            print(f"{c['symbol']:<10} {c['direction']:<7} {c['risk_pct']:<12}% {c.get('recommended_leverage', '3x-5x'):<18} {c.get('safe_liq_price', '-'):<26} {fr_str:<10} {fvg_disp}")
        print("="*118)

    print("💡 STRATEGI EKSEKUSI EMAS:")
    print("   1. Anti-Likuidasi: Gunakan leverage aman (3x-5x) & masuk maksimal 20%-30% dari total saldo dompet.")
    print("   2. Titik Likuidasi WAJIB berada di luar batas yang tertera agar Stop Loss terlindungi penuh.")
    print("   3. Smart Money FVG: Pasang antrean 'Retest Diskon' tepat di celah imbalance untuk harga paling murah.")
    print("   4. Begitu TP 1 tercapai: KUNCI 50% PROFIT, lalu GESER SL ke titik Entry (BEP / Zero-Risk).")
    print("="*118 + "\n")

def send_telegram_alert(message: str) -> bool:
    """Mengirim pesan teks ke bot Telegram, otomatis memecah jika melebihi batas 4096 karakter Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN kosong atau belum diatur di Secrets/Environment.")
        return False
    if not TELEGRAM_CHAT_ID:
        print("[!] TELEGRAM_CHAT_ID kosong atau belum diatur di Secrets/Environment.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Telegram memiliki batas maksimal 4096 karakter per pesan.
    # Jika pesan lebih dari 3500 karakter, pecah berdasarkan pemisah '━━━━━━━━━━━━━━━━━━━━━\n\n'
    chunks = []
    if len(message) <= 3800:
        chunks.append(message)
    else:
        parts = message.split("━━━━━━━━━━━━━━━━━━━━━\n\n")
        current_chunk = ""
        for p in parts:
            if len(current_chunk) + len(p) + 30 < 3800:
                current_chunk += p + "━━━━━━━━━━━━━━━━━━━━━\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = p + "━━━━━━━━━━━━━━━━━━━━━\n\n"
        if current_chunk:
            chunks.append(current_chunk.strip())

    all_success = True
    for idx, chunk in enumerate(chunks, 1):
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"}
        try:
            r = requests.post(url, json=payload, timeout=8)
            if r.status_code == 200:
                print(f"[+] Bagian {idx}/{len(chunks)} berhasil dikirim ke Telegram!")
            else:
                print(f"[!] Telegram API Error Bagian {idx} ({r.status_code}): {r.text}")
                # Fallback jika ada format karakter khusus markdown yang gagal di-parse oleh Telegram
                print(f"[i] Mencoba kirim ulang bagian {idx} dalam mode teks polos...")
                payload_plain = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk.replace("*", "").replace("_", "").replace("`", "")
                }
                r_retry = requests.post(url, json=payload_plain, timeout=8)
                if r_retry.status_code == 200:
                    print(f"[+] Bagian {idx} berhasil dikirim (mode teks polos)!")
                else:
                    print(f"[!] Gagal kirim ulang bagian {idx}: {r_retry.text}")
                    all_success = False
        except Exception as e:
            print(f"[Warning] Gagal kirim Telegram: {e}")
            all_success = False
        time.sleep(0.5)

    return all_success

def save_to_json(data: dict, filepath: str = "signals_history.json"):
    """Menyimpan hasil ke file JSON agar bisa dianalisis kembali"""
    record = {
        "timestamp": datetime.datetime.now().isoformat(),
        "data": data
    }
    try:
        with open(filepath, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[Warning] Gagal menyimpan log: {e}")
