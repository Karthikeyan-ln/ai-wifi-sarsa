@echo off
title AI Wi-Fi SARSA Scanner

echo.
echo ==========================================
echo       AI Wi-Fi SARSA Local Scanner
echo ==========================================
echo.

cd /d C:\Users\HP\Downloads\adaptive_wifi_sarsa

echo Checking Python...
python --version

echo.
echo Starting real Windows Wi-Fi scanner...
echo.
echo This window must remain open while
echo you want live Wi-Fi updates.
echo.
echo Press Ctrl+C to stop.
echo.

python local_scanner.py --server https://ai-wifi-sarsa.onrender.com --interval 10

echo.
echo Scanner stopped.
pause
