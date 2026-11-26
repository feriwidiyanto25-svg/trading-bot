"""
Modul Pelaporan (Formatter Telegram & Terminal)
Mencakup Analisis Multi-Timeframe (1D ➔ 4H ➔ 15M), Bias Rekomendasi 2-Arah,
Setup Long & Setup Short Murni (Tanpa Leverage), serta Sentinel Token Unlock & Keamanan.
"""
import json
import time
import datetime
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def format_telegram_message(data: dict) -> str:
    """Membuat pesan terformat ringkas, padat, dan ramah mobile untuk notifikasi Telegram"""
    now = datetime.datetime.now().strftime("%d %b %Y | %H:%M WIB")

    # A. Format Khusus Cek 1 Koin: Multi-Timeframe (1D ➔ 4H ➔ 15M) Bi-Directional Setups
    if data.get("is_mtf_check"):
        sym = data.get("symbol", "PAIR")
        price = data.get("curr_price_str", "0.0")
        bias = data.get("bias", {})
        mtf = data.get("mtf", {})
        s_long = data.get("setup_long", {})
        s_short = data.get("setup_short", {})
        intel = data.get("token_intel", {})

        msg = f"📊 *[ANALISIS MULTI-TIMEFRAME (1D ➔ 4H ➔ 15M): {sym}]*\n"
        msg += f"💵 Harga Saat Ini: *${price}* | 🕒 {now}\n\n"

        # 1. Bias Kekuatan & Rekomendasi
        msg += "🎯 *BIAS KEKUATAN & REKOMENDASI:*\n"
        msg += f"   🟢 Potensi LONG  : *{bias.get('prob_long', 50)}%* `{bias.get('bar', '')}`\n"
        msg += f"   🔴 Potensi SHORT : *{bias.get('prob_short', 50)}%*\n"
        msg += f"   💡 *Kesimpulan:* _{bias.get('conclusion', '-')}_\n\n"

        # 2. Peta Besar Pasar
        msg += "🧭 *PETA STRUKTUR PASAR:*\n"
        d1 = mtf.get("1d", {})
        h4 = mtf.get("4h", {})
        m15 = mtf.get("15m", {})
        msg += f"• *1D (Harian)*  : {d1.get('trend')} | RSI: `{d1.get('rsi', 50):.1f}` | EMA20: `${d1.get('ema20')}`{d1.get('climax', '')}\n"
        msg += f"• *4H (4 Jam)*   : {h4.get('trend')} | RSI: `{h4.get('rsi', 50):.1f}` | Supp: `${h4.get('support')}` | Res: `${h4.get('resist')}`\n"
        msg += f"• *15m (Sniper)* : RSI: `{m15.get('rsi', 50):.1f}` | Titik Pantul: `${m15.get('bounce_point')}` | Rentang Risiko: `±{m15.get('risk_pct', 2.5):.1f}%`\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 3. Setup Long
        msg += "🟢 *SETUP LONG (Skenario Pantulan / Tembus ke Atas):*\n"
        msg += f"   • *Area Entry*   : `{s_long.get('entry_range')}`\n"
        msg += f"   • *Stop Loss*    : `{s_long.get('sl')}`\n"
        msg += f"   • *Take Profit 1*: `{s_long.get('tp1')}` (RR `{s_long.get('rr_tp1')}`)\n"
        msg += f"   • *Take Profit 2*: `{s_long.get('tp2')}` (RR `{s_long.get('rr_tp2')}`)\n\n"

        # 4. Setup Short
        msg += "🔴 *SETUP SHORT (Skenario Tertolak / Ambles ke Bawah):*\n"
        msg += f"   • *Area Entry*   : `{s_short.get('entry_range')}`\n"
        msg += f"   • *Stop Loss*    : `{s_short.get('sl')}`\n"
        msg += f"   • *Take Profit 1*: `{s_short.get('tp1')}` (RR `{s_short.get('rr_tp1')}`)\n"
        msg += f"   • *Take Profit 2*: `{s_short.get('tp2')}` (RR `{s_short.get('rr_tp2')}`)\n\n"

        # 5. Catatan Fundamental & Risiko
        msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📌 *CATATAN FUNDAMENTAL & RESIKO:*\n"
        if intel.get("unlock_note"):
            msg += f"   • {intel.get('unlock_note')}\n"
        msg += f"   • 🛡️ {intel.get('security_status', 'Status Keamanan: Bersih')}\n"
        return msg

    # B. Format Scan Pasar: Multi-Timeframe (1D ➔ 4H ➔ 15M) Bi-Directional untuk Koin Terpilih
    if data.get("is_market_scan") and data.get("coins_analyzed"):
        coins = data.get("coins_analyzed", [])
        mode = data.get("mode", "trend")
        tf = data.get("timeframe", "4h")
        btc = data.get("btc_status", {})
        fg = data.get("fear_greed", {})
        macro = data.get("macro_intel", {})

        if mode == "pump":
            msg = f"🚀 *[RADAR PRE-PUMP / WHALE HUNTER (1D ➔ 4H ➔ 15M)]*\n"
            msg += f"🕒 {now} | Rezim BTC: *{btc.get('desc', 'N/A')}*\n"
            msg += "⚡ _Mode Independen: Memburu Anomali Volume & Akumulasi Paus Multi-Hari_\n"
        else:
            msg = f"📊 *[RADAR PASAR CRYPTO (TRIPLE SCREEN 1D ➔ 4H ➔ 15M)]*\n"
            msg += f"🕒 {now} | Rezim BTC: *{btc.get('desc', 'N/A')}*\n"

        if fg:
            msg += f"😨 Sentiment: *{fg.get('value', 50)}/100* ({fg.get('classification', 'Neutral')})\n"
        if macro and macro.get("has_alert"):
            nearest = macro.get("nearest_event", {})
            if nearest:
                msg += f"🚨 *Makro:* {nearest.get('title')} ({nearest.get('event_time_wib')})\n"
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

            msg += f"🪙 *{idx}. {sym}* (Harga: *${price}*)\n"
            msg += f"🎯 *BIAS:* 🟢 Long *{bias.get('prob_long', 50)}%* vs 🔴 Short *{bias.get('prob_short', 50)}%*\n"
            msg += f"💡 _{bias.get('conclusion', '-')}_\n\n"

            msg += "🧭 *Struktur Pasar:*\n"
            msg += f"• 1D: {d1.get('trend')} | RSI: `{d1.get('rsi', 50):.1f}` | EMA20: `${d1.get('ema20')}`\n"
            msg += f"• 4H: {h4.get('trend')} | RSI: `{h4.get('rsi', 50):.1f}` | Supp: `${h4.get('support')}` | Res: `${h4.get('resist')}`\n"
            msg += f"• 15m: RSI: `{m15.get('rsi', 50):.1f}` | Titik Pantul: `${m15.get('bounce_point')}`\n\n"

            msg += "🟢 *SETUP LONG (Pantulan / Tembus Atas):*\n"
            msg += f"   • Entry: `{s_long.get('entry_range')}`\n"
            msg += f"   • SL   : `{s_long.get('sl')}`\n"
            msg += f"   • TP 1 : `{s_long.get('tp1')}` (RR `{s_long.get('rr_tp1')}`)\n"
            msg += f"   • TP 2 : `{s_long.get('tp2')}` (RR `{s_long.get('rr_tp2')}`)\n\n"

            msg += "🔴 *SETUP SHORT (Tertolak / Ambles Bawah):*\n"
            msg += f"   • Entry: `{s_short.get('entry_range')}`\n"
            msg += f"   • SL   : `{s_short.get('sl')}`\n"
            msg += f"   • TP 1 : `{s_short.get('tp1')}` (RR `{s_short.get('rr_tp1')}`)\n"
            msg += f"   • TP 2 : `{s_short.get('tp2')}` (RR `{s_short.get('rr_tp2')}`)\n"

            if intel.get("unlock_note"):
                msg += f"   • {intel.get('unlock_note')}\n"
            msg += f"   • 🛡️ {intel.get('security_status', 'Status Keamanan: Bersih')}\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        msg += (
            "💡 *Tips Eksekusi Murni (Tanpa Leverage):*\n"
            "• Gunakan *Trigger Order (Buy/Sell Stop)* untuk konfirmasi arah atau pasang Limit di area Entry.\n"
            "• Perhitungan SL dan TP adalah nominal murni pergerakan harga pada grafik (tanpa leverage).\n"
            "• Begitu TP 1 tercapai: Kunci 50% profit dan geser SL ke BEP (modal)!"
        )
        return msg

    # C. Fallback Format Legacy
    longs = data.get("longs", [])
    shorts = data.get("shorts", [])
    btc = data.get("btc_status", {})
    fg = data.get("fear_greed", {})
    macro = data.get("macro_intel", {})
    tf = data.get("timeframe", "4h")
    mode = data.get("mode", "trend")

    msg = f"📊 *[RADAR PASAR CRYPTO - TF {tf.upper()}]*\n"
    msg += f"🕒 {now} | Rezim BTC: *{btc.get('desc', 'N/A')}*\n"
    if fg:
        msg += f"😨 Sentiment: *{fg.get('value', 50)}/100* ({fg.get('classification', 'Neutral')})\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    if longs:
        msg += "🟢 *TOP REKOMENDASI LONG*\n"
        for i, c in enumerate(longs, 1):
            msg += (
                f"\n*{i}. {c.get('symbol', 'PAIR')}* (1D: `{c.get('daily_trend', 'Neutral')}`)\n"
                f"• Entry: `${c.get('entry_market', '0.0')}` | Trig: `${c.get('trigger_entry', '0.0')}`\n"
                f"• SL: `${c.get('sl', '0.0')}` (-{c.get('risk_pct', 0)}%) | TP1: `${c.get('tp1', '0.0')}` | TP2: `${c.get('tp2', '0.0')}`\n"
            )
    if shorts:
        msg += "\n🔴 *TOP REKOMENDASI SHORT*\n"
        for i, c in enumerate(shorts, 1):
            msg += (
                f"\n*{i}. {c.get('symbol', 'PAIR')}* (1D: `{c.get('daily_trend', 'Neutral')}`)\n"
                f"• Entry: `${c.get('entry_market', '0.0')}` | Trig: `${c.get('trigger_entry', '0.0')}`\n"
                f"• SL: `${c.get('sl', '0.0')}` (+{c.get('risk_pct', 0)}%) | TP1: `${c.get('tp1', '0.0')}` | TP2: `${c.get('tp2', '0.0')}`\n"
            )
    return msg

def print_terminal_report(data: dict):
    """Menampilkan hasil pemindaian di Terminal/CMD dengan format tabel rapi Murni Tanpa Leverage"""
    # 1. Tampilan Cek Koin Tunggal (MTF)
    if data.get("is_mtf_check"):
        sym = data.get("symbol", "PAIR")
        price = data.get("curr_price_str", "0.0")
        bias = data.get("bias", {})
        mtf = data.get("mtf", {})
        s_long = data.get("setup_long", {})
        s_short = data.get("setup_short", {})
        intel = data.get("token_intel", {})

        print("\n" + "="*80)
        print(f"       ANALISIS MULTI-TIMEFRAME (1D ➔ 4H ➔ 15M): {sym}")
        print(f"       Harga Saat Ini: ${price}")
        print("="*80)
        print(f"\n🎯 BIAS KEKUATAN & REKOMENDASI:")
        print(f"   🟢 Potensi LONG  : {bias.get('prob_long', 50)}% {bias.get('bar', '')}")
        print(f"   🔴 Potensi SHORT : {bias.get('prob_short', 50)}%")
        print(f"   💡 Kesimpulan    : {bias.get('conclusion', '-')}")
        print("\n🧭 PETA STRUKTUR PASAR:")
        d1 = mtf.get("1d", {})
        h4 = mtf.get("4h", {})
        m15 = mtf.get("15m", {})
        print(f"• 1D (Harian)  : {d1.get('trend')} | RSI: {d1.get('rsi', 50):.1f} | EMA20: ${d1.get('ema20')}{d1.get('climax', '')}")
        print(f"• 4H (4 Jam)   : {h4.get('trend')} | RSI: {h4.get('rsi', 50):.1f} | Supp: ${h4.get('support')} | Res: ${h4.get('resist')}")
        print(f"• 15m (Sniper) : RSI: {m15.get('rsi', 50):.1f} | Titik Pantul: ${m15.get('bounce_point')} | Rentang Risiko: ±{m15.get('risk_pct', 2.5):.1f}%")
        print("\n" + "-"*80)
        print("🟢 SETUP LONG (Skenario Pantulan / Tembus ke Atas):")
        print(f"   • Area Entry   : {s_long.get('entry_range')}")
        print(f"   • Stop Loss    : {s_long.get('sl')}")
        print(f"   • Take Profit 1: {s_long.get('tp1')} (RR {s_long.get('rr_tp1')})")
        print(f"   • Take Profit 2: {s_long.get('tp2')} (RR {s_long.get('rr_tp2')})")
        print("\n" + "-"*80)
        print("🔴 SETUP SHORT (Skenario Tertolak / Ambles ke Bawah):")
        print(f"   • Area Entry   : {s_short.get('entry_range')}")
        print(f"   • Stop Loss    : {s_short.get('sl')}")
        print(f"   • Take Profit 1: {s_short.get('tp1')} (RR {s_short.get('rr_tp1')})")
        print(f"   • Take Profit 2: {s_short.get('tp2')} (RR {s_short.get('rr_tp2')})")
        print("\n" + "-"*80)
        print("📌 CATATAN FUNDAMENTAL & RESIKO:")
        if intel.get("unlock_note"):
            print(f"   • {intel.get('unlock_note')}")
        print(f"   • 🛡️ {intel.get('security_status', 'Status Keamanan: Bersih')}")
        print("="*80 + "\n")
        return

    # 2. Tampilan Scan Pasar (Multi-Koin MTF)
    if data.get("is_market_scan") and data.get("coins_analyzed"):
        coins = data.get("coins_analyzed", [])
        mode = data.get("mode", "trend")
        tf = data.get("timeframe", "4h")
        btc = data.get("btc_status", {})
        fg = data.get("fear_greed", {})
        macro = data.get("macro_intel", {})

        print("\n" + "="*80)
        mode_label = "RADAR PRE-PUMP / WHALE HUNTER (1D ➔ 4H ➔ 15M)" if mode == "pump" else "RADAR PASAR CRYPTO (TRIPLE SCREEN 1D ➔ 4H ➔ 15M)"
        print(f"       {mode_label}")
        print(f"       Waktu: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if btc:
            print(f"       Rezim Bitcoin: {btc.get('desc', 'N/A')}")
        if fg:
            print(f"       Sentimen: {fg.get('value', 50)}/100 [{fg.get('classification', 'Neutral')}]")
        print("="*80)

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

            print(f"\n🪙 {idx}. {sym} (Harga: ${price})")
            print(f"🎯 BIAS: 🟢 Long {bias.get('prob_long', 50)}% vs 🔴 Short {bias.get('prob_short', 50)}% | {bias.get('conclusion', '-')}")
            print(f"🧭 1D: {d1.get('trend')} | RSI: {d1.get('rsi', 50):.1f} | EMA20: ${d1.get('ema20')}")
            print(f"   4H: {h4.get('trend')} | RSI: {h4.get('rsi', 50):.1f} | Supp: ${h4.get('support')} | Res: ${h4.get('resist')}")
            print(f"   15m: RSI: {m15.get('rsi', 50):.1f} | Titik Pantul: ${m15.get('bounce_point')}")
            print(f"🟢 SETUP LONG  : Entry: {s_long.get('entry_range')} | SL: {s_long.get('sl')} | TP1: {s_long.get('tp1')} (RR {s_long.get('rr_tp1')}) | TP2: {s_long.get('tp2')} (RR {s_long.get('rr_tp2')})")
            print(f"🔴 SETUP SHORT : Entry: {s_short.get('entry_range')} | SL: {s_short.get('sl')} | TP1: {s_short.get('tp1')} (RR {s_short.get('rr_tp1')}) | TP2: {s_short.get('tp2')} (RR {s_short.get('rr_tp2')})")
            if intel.get("unlock_note"):
                print(f"📌 {intel.get('unlock_note')}")
            print(f"🛡️ {intel.get('security_status', 'Status Keamanan: Bersih')}")
            print("-" * 80)

        print("💡 TIPS EKSEKUSI MURNI (TANPA LEVERAGE):")
        print("   1. Gunakan Trigger Order (Buy/Sell Stop) untuk konfirmasi arah atau pasang Limit di area Entry.")
        print("   2. Perhitungan SL dan TP adalah nominal murni pergerakan harga pada grafik (tanpa leverage).")
        print("   3. Begitu TP 1 tercapai: Kunci 50% profit dan geser SL ke BEP (modal)!\n")
        return

    # Fallback jika data kosong
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
    """Mengirim pesan teks ke bot Telegram, otomatis memecah jika melebihi batas 4096 karakter Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN kosong atau belum diatur di Secrets/Environment.")
        return False
    if not TELEGRAM_CHAT_ID:
        print("[!] TELEGRAM_CHAT_ID kosong atau belum diatur di Secrets/Environment.")
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
                print(f"[!] Telegram API Error Bagian {idx} ({r.status_code}): {r.text}")
                payload_plain = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk.replace("*", "").replace("_", "").replace("`", "")
                }
                r_retry = requests.post(url, json=payload_plain, timeout=8)
                if r_retry.status_code == 200:
                    print(f"[+] Bagian {idx} berhasil dikirim (mode teks polos)!")
                else:
                    all_success = False
        except Exception as e:
            print(f"[Warning] Gagal kirim Telegram: {e}")
            all_success = False
        time.sleep(0.5)

    return all_success
