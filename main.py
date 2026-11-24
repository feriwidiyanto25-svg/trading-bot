"""
File Utama (Main Runner)
"""
import sys
import time
import argparse
from screener import run_market_screener
from reporter import print_terminal_report, format_telegram_message, send_telegram_alert, save_to_json

def scan_once(enable_telegram: bool = False):
    print("\n[+] Memulai pemindaian koin di Binance Vision API...")
    data = run_market_screener()
    
    # Cetak ke layar CMD
    print_terminal_report(data)
    
    # Simpan riwayat ke file
    save_to_json(data)
    print("[+] Riwayat sinyal berhasil disimpan ke 'signals_history.json'.")
    
    # Kirim ke Telegram jika diminta
    if enable_telegram:
        msg = format_telegram_message(data)
        success = send_telegram_alert(msg)
        if success:
            print("[+] Notifikasi berhasil dikirim ke Telegram!")
        else:
            print("[!] Token Telegram belum diisi atau gagal terhubung.")

def main():
    parser = argparse.ArgumentParser(description="Crypto Market Screener (Binance)")
    parser.add_argument("--loop", type=int, default=0, help="Jalankan berkala tiap X menit (contoh: --loop 15)")
    parser.add_argument("--telegram", action="store_true", help="Kirim hasil ke Telegram")
    args = parser.parse_args()

    if args.loop > 0:
        print(f"[+] Bot berjalan dalam mode LOOP setiap {args.loop} menit. Tekan Ctrl+C untuk berhenti.")
        while True:
            scan_once(enable_telegram=args.telegram)
            print(f"[i] Menunggu {args.loop} menit untuk pemindaian berikutnya...")
            time.sleep(args.loop * 60)
    else:
        scan_once(enable_telegram=args.telegram)

if __name__ == "__main__":
    main()
