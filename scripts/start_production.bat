@echo off
TITLE Sistem AI Monitoring Loading Es Kristal - Auto-Watchdog
COLOR 0B

cd /d "%~dp0.."

start "" powershell -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000'"

:WATCHDOG_LOOP
echo [%DATE% %TIME%] Memulai server monitoring...
python server.py

echo.
echo [PERINGATAN %TIME%] Server berhenti atau crash! Restart otomatis dalam 5 detik...
timeout /t 5 /nobreak >nul
goto WATCHDOG_LOOP
