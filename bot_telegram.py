"""
Bot Interaktif Telegram (On-Demand Screener & Inline Buttons)
Memungkinkan pengguna memicu pemindaian dan memilih timeframe (15m, 1h, 4h)
langsung lewat tombol interaktif di chat Telegram.
"""
import os
import time
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from screener import run_market_screener, analyze_specific_coin
from reporter import format_telegram_message, send_telegram_alert

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_menu(chat_id: str):
    """Mengirim pesan menu dengan tombol interaktif (Inline Buttons)"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": (
            "🤖 *[RADAR CRYPTO & INTELIJEN PAUS INTERAKTIF]*\n\n"
            "Silakan pilih *Mode Analisis* yang Anda inginkan:\n\n"
            "🚀 *Mode 2: Radar Pre-Pump (15m)*\n"
            "• Memburu koin tidur yang diakumulasi Paus & siap meledak (mengabaikan BTC).\n"
            "• Rekomendasi titik Trigger Buy Stop.\n\n"
            "🛡️ *Mode 1: Trend Konservatif (15m, 1h, 4h)*\n"
            "• Mengikuti rezim makro Bitcoin & proteksi modal ketat.\n\n"
            "💡 *Analisis Koin Khusus:*\n"
            "Ketik: `/cek <koin> [timeframe]` (contoh: `/cek SSV 15m` atau `/cek OM 1h`)\n\n"
            "👇 *Klik tombol di bawah untuk mulai:* "
        ),
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🚀 Radar Pre-Pump (15m)", "callback_data": "pump_15m"},
                    {"text": "🛡️ Trend Aman (4 Jam)", "callback_data": "scan_4h"}
                ],
                [
                    {"text": "⚡ Trend Cepat (15 Menit)", "callback_data": "scan_15m"},
                    {"text": "⏱️ Trend Intraday (1 Jam)", "callback_data": "scan_1h"}
                ]
            ]
        }
    }
    try:
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"[Error] Gagal kirim menu: {e}")

def answer_callback(callback_id: str, text: str):
    """Memberi notifikasi pop-up kecil di Telegram saat tombol ditekan"""
    url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_id, "text": text}, timeout=5)
    except Exception:
        pass

def send_chat_message(chat_id: str, text: str):
    """Kirim pesan teks status biasa"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception:
        pass

def process_scan_request(chat_id: str, timeframe: str = "4h", mode: str = "trend"):
    """Menjalankan pemindaian sesuai timeframe dan mode pilihan dan mengirim hasilnya"""
    if mode == "pump":
        send_chat_message(chat_id, "🚀 *Memulai Radar Pre-Pump (Whale Hunter)...*\n_Memindai anomali volume & akumulasi Paus multi-hari. Tunggu ~25 detik..._")
    else:
        tf_desc = "15 Menit" if timeframe == "15m" else ("1 Jam" if timeframe == "1h" else "4 Jam")
        send_chat_message(chat_id, f"🔍 *Memulai pemindaian pasar Trend Konservatif ({tf_desc})...*\n_Mohon tunggu sekitar 20-30 detik._")
    
    print(f"\n[+] Permintaan scan via Telegram diterima (Timeframe: {timeframe} | Mode: {mode})...")
    data = run_market_screener(timeframe=timeframe, mode=mode)
    msg = format_telegram_message(data)
    
    success = send_telegram_alert(msg)
    if success:
        print(f"[+] Hasil scan {timeframe} ({mode}) berhasil dikirim ke Telegram!")
    else:
        send_chat_message(chat_id, "❌ Gagal mengirim hasil scan. Silakan coba lagi.")

def process_single_coin_request(chat_id: str, symbol: str, timeframe: str = "15m"):
    """Menjalankan analisis instan pada satu koin khusus"""
    sym = symbol.upper().strip()
    if not sym.endswith("USDT"):
        sym += "USDT"

    send_chat_message(chat_id, f"🔍 *Menganalisis koin {sym} (Timeframe {timeframe})...*\n_Mohon tunggu sebentar..._")
    print(f"\n[+] Permintaan analisis khusus {sym} (TF: {timeframe}) diterima...")
    data = analyze_specific_coin(symbol=sym, timeframe=timeframe)
    if not data or not (data.get("longs") or data.get("shorts")):
        send_chat_message(chat_id, f"⚠️ *Koin '{sym}' tidak ditemukan di Binance Vision atau skor saat ini netral.*")
        return

    msg = format_telegram_message(data)
    success = send_telegram_alert(msg)
    if success:
        print(f"[+] Hasil analisis khusus {sym} berhasil dikirim ke Telegram!")
    else:
        send_chat_message(chat_id, "❌ Gagal mengirim hasil analisis koin.")

def run_bot_listener():
    """Mendengarkan pesan Telegram secara interaktif (Long Polling)"""
    if not TELEGRAM_BOT_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN belum disetel di .env!")
        return

    print("=" * 60)
    print("   BOT TELEGRAM INTERAKTIF AKTIF (ON-DEMAND)")
    print("   Buka Telegram Anda dan ketik /menu untuk memicu tombol.")
    print("   Tekan Ctrl+C di terminal ini untuk berhenti.")
    print("=" * 60)

    last_update_id = 0

    while True:
        try:
            url = f"{TELEGRAM_API_URL}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 20}
            res = requests.get(url, params=params, timeout=25)
            
            if res.status_code != 200:
                time.sleep(2)
                continue

            updates = res.json().get("result", [])
            for update in updates:
                last_update_id = update["update_id"]

                # 1. Menangani Klik Tombol Interaktif (Inline Button Callback)
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb["id"]
                    from_id = str(cb["from"]["id"])
                    cb_data = cb.get("data", "")

                    # Validasi keamanan: hanya proses jika dari chat_id terdaftar
                    if TELEGRAM_CHAT_ID and from_id != str(TELEGRAM_CHAT_ID):
                        answer_callback(cb_id, "Akses ditolak: Anda bukan pemilik bot.")
                        continue

                    if cb_data == "pump_15m":
                        answer_callback(cb_id, "Memulai Radar Pre-Pump 15m...")
                        process_scan_request(from_id, "15m", mode="pump")
                    elif cb_data == "scan_15m":
                        answer_callback(cb_id, "Memulai scan Trend 15 Menit...")
                        process_scan_request(from_id, "15m", mode="trend")
                    elif cb_data == "scan_1h":
                        answer_callback(cb_id, "Memulai scan Trend 1 Jam...")
                        process_scan_request(from_id, "1h", mode="trend")
                    elif cb_data == "scan_4h":
                        answer_callback(cb_id, "Memulai scan Trend 4 Jam...")
                        process_scan_request(from_id, "4h", mode="trend")

                # 2. Menangani Pesan Teks (/menu, /pump, /scan 15m, /cek)
                elif "message" in update and "text" in update["message"]:
                    msg = update["message"]
                    from_id = str(msg["from"]["id"])
                    text = msg["text"].strip().lower()

                    # Validasi keamanan
                    if TELEGRAM_CHAT_ID and from_id != str(TELEGRAM_CHAT_ID):
                        continue

                    if text in ["/start", "/menu", "menu", "/help"]:
                        send_menu(from_id)
                    elif text.startswith("/pump") or text.startswith("/prepump") or text.startswith("/hunt"):
                        process_scan_request(from_id, "15m", mode="pump")
                    elif text.startswith("/scan"):
                        parts = text.split()
                        tf = parts[1] if len(parts) > 1 and parts[1] in ["15m", "1h", "4h"] else "4h"
                        process_scan_request(from_id, tf, mode="trend")
                    elif text.startswith("/cek") or text.startswith("/analisa") or text.startswith("/check"):
                        parts = text.split()
                        if len(parts) > 1:
                            target_sym = parts[1]
                            target_tf = parts[2] if len(parts) > 2 and parts[2] in ["15m", "1h", "4h"] else "15m"
                            process_single_coin_request(from_id, target_sym, target_tf)
                        else:
                            send_chat_message(from_id, "💡 *Format salah!*\nGunakan: `/cek <koin> [timeframe]`\nContoh: `/cek SSV 15m` atau `/cek OM 1h`")
                    else:
                        send_menu(from_id)

        except KeyboardInterrupt:
            print("\n[i] Bot interaktif dihentikan.")
            break
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    run_bot_listener()
