"""
Modul Pelaporan (Formatter Telegram & Terminal)
Format Singkat, Padat, dan Jelas (Murni Tanpa Leverage & Tanpa Fluff Paus).
"""
import json
import time
import datetime
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def format_telegram_message(data: dict) -> str:
    """Membuat pesan ringkas, padat, dan ramah mobile untuk Telegram"""
    now = datetime.datetime.now().strftime("%d %b %H:%M WIB")

    # A. Format Singkat: Cek 1 Koin (MTF 1D ➔ 4H ➔ 15M)
    if data.get("is_mtf_check"):
        sym = data.get("symbol", "PAIR")
        price = data.get("curr_price_str", "0.0")
        bias = data.get("bias", {})
        mtf = data.get("mtf", {})
        s_long = data.get("setup_long", {})
        s_short = data.get("setup_short", {})
        intel = data.get("token_intel", {})

        d1 = mtf.get("1d", {})
        h4 = mtf.get("4h", {})
        m15 = mtf.get("15m", {})

        msg = f"📊 *[ANALISIS: {sym}]*\n"
        msg += f"💵 Harga: *${price}* | Tipe: *{bias.get('setup_type', 'Market Setup')}*\n\n"

        msg += f"🎯 *BIAS:* 🟢 Long *{bias.get('prob_long', 50)}%* vs 🔴 Short *{bias.get('prob_short', 50)}%*\n"
        msg += f"• 1D: {d1.get('trend')} (RSI {d1.get('rsi', 50):.0f})\n"
        msg += f"• 4H: Supp `${h4.get('support')}` | Res `${h4.get('resist')}`\n"
        msg += f"• 15m: Pantul `${m15.get('bounce_point')}` (RSI {m15.get('rsi', 50):.0f})\n\n"

        msg += "🟢 *SETUP LONG:*\n"
        if s_long.get("status"):
            msg += f"• Status: *{s_long.get('status')}*\n"
        msg += f"• Entry : `{s_long.get('entry_range')}`\n"
        msg += f"• SL    : `{s_long.get('sl')}`\n"
        msg += f"• TP 1  : `{s_long.get('tp1')}` | TP 2: `{s_long.get('tp2')}`\n\n"

        msg += "🔴 *SETUP SHORT:*\n"
        if s_short.get("status"):
            msg += f"• Status: *{s_short.get('status')}*\n"
        msg += f"• Entry : `{s_short.get('entry_range')}`\n"
        msg += f"• SL    : `{s_short.get('sl')}`\n"
        msg += f"• TP 1  : `{s_short.get('tp1')}` | TP 2: `{s_short.get('tp2')}`\n\n"

        msg += "📌 *Info:* "
        notes = []
        if intel.get("unlock_note"):
            notes.append(intel.get("unlock_note"))
        notes.append(intel.get("security_status", "✅ Bersih"))
        msg += " | ".join(notes)
        return msg

    # B. Format Singkat: Scan Pasar (Multi-Koin Terpilih)
    if data.get("is_market_scan") and data.get("coins_analyzed"):
        coins = data.get("coins_analyzed", [])
        mode = data.get("mode", "trend")
        tf = data.get("timeframe", "4h")
        btc = data.get("btc_status", {})
        fg = data.get("fear_greed", {})

        mode_title = "RADAR PRE-PUMP" if mode == "pump" else "RADAR PASAR"
        msg = f"📊 *[{mode_title} - TF {tf.upper()}]*\n"
        msg += f"🕒 {now} | BTC: *{btc.get('desc', 'N/A')}*\n"
        if fg:
            msg += f"😨 Sentiment: *{fg.get('value', 50)}/100* ({fg.get('classification', 'Neutral')})\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        for idx, c in enumerate(coins, 1):
            sym = c.get("symbol", "PAIR")
            price = c.get("curr_price_str", "0.0")
            bias = c.get("bias", {})
            mtf = c.get("mtf", {})
            s_long = c.get("setup_long", {})
            s_short = c.get("setup_short", {})
            intel = c.get("token_intel", {})

            d1 = mtf.get("1d", {})
            h4 = mtf.get("4h", {})
            m15 = mtf.get("15m", {})

            msg += f"🪙 *{idx}. {sym}* (*${price}*) | {bias.get('setup_type', '')}\n"
            msg += f"🎯 *Bias:* 🟢 Long *{bias.get('prob_long', 50)}%* vs 🔴 Short *{bias.get('prob_short', 50)}%*\n"
            msg += f"• 1D: {d1.get('trend')} (RSI {d1.get('rsi', 50):.0f}) | 4H: Res `${h4.get('resist')}`\n"
            msg += f"🟢 *LONG* : `{s_long.get('entry_range')}` | SL `{s_long.get('sl')}` | TP `{s_long.get('tp1')}`\n"
            if "Tunggu" in s_long.get("status", ""):
                msg += f"   _{s_long.get('status')}_\n"
            msg += f"🔴 *SHORT*: `{s_short.get('entry_range')}` | SL `{s_short.get('sl')}` | TP `{s_short.get('tp1')}`\n"
            if "Tunggu" in s_short.get("status", ""):
                msg += f"   _{s_short.get('status')}_\n"

            info_line = []
            if intel.get("unlock_note"):
                info_line.append(intel.get("unlock_note"))
            info_line.append(intel.get("security_status", "✅ Bersih"))
            msg += f"📌 {' | '.join(info_line)}\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        return msg.strip()

    # C. Fallback Sederhana
    return "⚠️ Tidak ada sinyal koin yang memenuhi kriteria saat ini."

def print_terminal_report(data: dict):
    """Menampilkan hasil pemindaian di Terminal secara singkat, padat, dan jelas"""
    # 1. Terminal: Cek Koin Tunggal
    if data.get("is_mtf_check"):
        sym = data.get("symbol", "PAIR")
        price = data.get("curr_price_str", "0.0")
        bias = data.get("bias", {})
        mtf = data.get("mtf", {})
        s_long = data.get("setup_long", {})
        s_short = data.get("setup_short", {})
        intel = data.get("token_intel", {})

        print("\n" + "="*70)
        print(f"📊 [ANALISIS: {sym}]  Harga: ${price}  |  Tipe: {bias.get('setup_type', '-')}")
        print("="*70)
        print(f"🎯 BIAS: 🟢 Long {bias.get('prob_long', 50)}% vs 🔴 Short {bias.get('prob_short', 50)}% | {bias.get('conclusion', '-')}")
        d1 = mtf.get("1d", {})
        h4 = mtf.get("4h", {})
        m15 = mtf.get("15m", {})
        print(f"• 1D: {d1.get('trend')} (RSI {d1.get('rsi', 50):.0f}) | 4H: Supp ${h4.get('support')} Res ${h4.get('resist')} | 15m: Pantul ${m15.get('bounce_point')}")
        print("-" * 70)
        print(f"🟢 SETUP LONG  [{s_long.get('status', '-')}]")
        print(f"   Entry: {s_long.get('entry_range')} | SL: {s_long.get('sl')} | TP1: {s_long.get('tp1')} | TP2: {s_long.get('tp2')}")
        print(f"🔴 SETUP SHORT [{s_short.get('status', '-')}]")
        print(f"   Entry: {s_short.get('entry_range')} | SL: {s_short.get('sl')} | TP1: {s_short.get('tp1')} | TP2: {s_short.get('tp2')}")
        print("-" * 70)
        notes = []
        if intel.get("unlock_note"):
            notes.append(intel.get("unlock_note"))
        notes.append(intel.get("security_status", "✅ Bersih"))
        print(f"📌 Info: {' | '.join(notes)}")
        print("="*70 + "\n")
        return

    # 2. Terminal: Scan Pasar
    if data.get("is_market_scan") and data.get("coins_analyzed"):
        coins = data.get("coins_analyzed", [])
        mode = data.get("mode", "trend")
        btc = data.get("btc_status", {})
        fg = data.get("fear_greed", {})

        print("\n" + "="*70)
        title = "RADAR PRE-PUMP" if mode == "pump" else "RADAR PASAR"
        print(f"📊 [{title}]  Waktu: {datetime.datetime.now().strftime('%d %b %H:%M WIB')}")
        if btc:
            print(f"Rezim BTC: {btc.get('desc', 'N/A')} | Sentimen: {fg.get('value', 50)}/100")
        print("="*70)

        for idx, c in enumerate(coins, 1):
            sym = c.get("symbol", "PAIR")
            price = c.get("curr_price_str", "0.0")
            bias = c.get("bias", {})
            mtf = c.get("mtf", {})
            s_long = c.get("setup_long", {})
            s_short = c.get("setup_short", {})
            intel = c.get("token_intel", {})

            d1 = mtf.get("1d", {})
            h4 = mtf.get("4h", {})
            m15 = mtf.get("15m", {})

            print(f"\n🪙 {idx}. {sym} (${price}) | {bias.get('setup_type', '')}")
            print(f"🎯 Bias: 🟢 Long {bias.get('prob_long', 50)}% vs 🔴 Short {bias.get('prob_short', 50)}%")
            print(f"• 1D: {d1.get('trend')} (RSI {d1.get('rsi', 50):.0f}) | 4H: Res ${h4.get('resist')}")
            print(f"🟢 LONG : Entry {s_long.get('entry_range')} | SL {s_long.get('sl')} | TP {s_long.get('tp1')}")
            print(f"🔴 SHORT: Entry {s_short.get('entry_range')} | SL {s_short.get('sl')} | TP {s_short.get('tp1')}")
            notes = []
            if intel.get("unlock_note"):
                notes.append(intel.get("unlock_note"))
            notes.append(intel.get("security_status", "✅ Bersih"))
            print(f"📌 Info : {' | '.join(notes)}")
            print("-" * 70)
        print()
        return

    print("\n[!] Tidak ada koin yang memenuhi kriteria pemindaian saat ini.\n")

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

def send_telegram_alert(message: str) -> bool:
    """Mengirim pesan teks ke bot Telegram, memecah jika melebihi batas 4096 karakter"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

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
                payload_plain = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk.replace("*", "").replace("_", "").replace("`", "")
                }
                r_retry = requests.post(url, json=payload_plain, timeout=8)
                if not (r_retry.status_code == 200):
                    all_success = False
        except Exception as e:
            print(f"[Warning] Gagal kirim Telegram: {e}")
            all_success = False
        time.sleep(0.5)

    return all_success
