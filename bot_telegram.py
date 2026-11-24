"""
Bot Interaktif Telegram (On-Demand Screener & Inline Buttons)
Memungkinkan pengguna memicu pemindaian dan memilih timeframe (15m, 1h, 4h)
langsung lewat tombol interaktif di chat Telegram.
"""
import os
import time
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from screener import run_market_screener
from reporter import format_telegram_message, send_telegram_alert

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_menu(chat_id: str):
    """Mengirim pesan menu dengan tombol interaktif (Inline Buttons)"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": (
            "🤖 *[RADAR CRYPTO & INTELIJEN PAUS INTERAKTIF]*\n\n"
            "Silakan pilih *Timeframe* pemindaian di bawah ini:\n"
            "• *15 Menit (15m)*: Trading kilat selesai dalam 1–3 jam.\n"
            "• *1 Jam (1h)*: Intraday selesai dalam 3–8 jam.\n"
            "• *4 Jam (4h)*: Swing tenang selesai dalam 1–2 hari.\n\n"
            "👇 *Klik tombol untuk memulai pemindaian:* "
        ),
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "⚡ Scan Cepat (15 Menit)", "callback_data": "scan_15m"},
                    {"text": "⏱️ Scan Intraday (1 Jam)", "callback_data": "scan_1h"}
                ],
                [
                    {"text": "📊 Scan Swing (4 Jam)", "callback_data": "scan_4h"}
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

def process_scan_request(chat_id: str, timeframe: str):
    """Menjalankan pemindaian sesuai timeframe pilihan dan mengirim hasilnya"""
    tf_desc = "15 Menit" if timeframe == "15m" else ("1 Jam" if timeframe == "1h" else "4 Jam")
    send_chat_message(chat_id, f"🔍 *Memulai pemindaian pasar timeframe {tf_desc}...*\n_Mohon tunggu sekitar 20-30 detik._")
    
    print(f"\n[+] Permintaan scan via Telegram diterima (Timeframe: {timeframe})...")
    data = run_market_screener(timeframe=timeframe)
    msg = format_telegram_message(data)
    
    success = send_telegram_alert(msg)
    if success:
        print(f"[+] Hasil scan {timeframe} berhasil dikirim ke Telegram!")
    else:
        send_chat_message(chat_id, "❌ Gagal mengirim hasil scan. Silakan coba lagi.")

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

                    if cb_data == "scan_15m":
                        answer_callback(cb_id, "Memulai scan 15 Menit...")
                        process_scan_request(from_id, "15m")
                    elif cb_data == "scan_1h":
                        answer_callback(cb_id, "Memulai scan 1 Jam...")
                        process_scan_request(from_id, "1h")
                    elif cb_data == "scan_4h":
                        answer_callback(cb_id, "Memulai scan 4 Jam...")
                        process_scan_request(from_id, "4h")

                # 2. Menangani Pesan Teks (/menu, /scan 15m, /start)
                elif "message" in update and "text" in update["message"]:
                    msg = update["message"]
                    from_id = str(msg["from"]["id"])
                    text = msg["text"].strip().lower()

                    # Validasi keamanan
                    if TELEGRAM_CHAT_ID and from_id != str(TELEGRAM_CHAT_ID):
                        continue

                    if text in ["/start", "/menu", "menu", "/help"]:
                        send_menu(from_id)
                    elif text.startswith("/scan"):
                        parts = text.split()
                        tf = parts[1] if len(parts) > 1 and parts[1] in ["15m", "1h", "4h"] else "4h"
                        process_scan_request(from_id, tf)
                    else:
                        send_menu(from_id)

        except KeyboardInterrupt:
            print("\n[i] Bot interaktif dihentikan.")
            break
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    run_bot_listener()
