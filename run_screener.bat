@echo off
title Crypto Screener Binance
cd /d "%~dp0"
echo ========================================================
echo   MENJALANKAN PEMINDAI PASAR KRIPTO (BINANCE VISION)
echo   Python: E:\motivasi-sarkas-main\motivasi-sarkas-main\.venv
echo ========================================================
echo.
"E:\motivasi-sarkas-main\motivasi-sarkas-main\.venv\Scripts\python.exe" main.py
echo.
echo Selesai. Tekan tombol apa saja untuk menutup...
pause >nul
