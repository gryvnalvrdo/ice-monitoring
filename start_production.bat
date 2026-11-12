@echo off
TITLE Sistem AI Monitoring Loading Es Kristal - Auto-Watchdog
COLOR 0B

echo ======================================================================
echo    SISTEM AI MONITORING LOADING ES KRISTAL (PRODUKSI PABRIK 24/7)
echo ======================================================================
echo  Menjalankan Server Web & Pipeline Deteksi Pure YOLO...
echo  Auto-Watchdog Aktif: Jika terjadi crash, sistem auto-restart otomatis!
echo ======================================================================
echo.

cd /d "%~dp0"

:: Buka browser dashboard otomatis setelah jeda 3 detik
start "" powershell -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000'"

:WATCHDOG_LOOP
echo [%DATE% %TIME%] Memulai server monitoring...
python server.py

echo.
echo [PERINGATAN %TIME%] Server berhenti atau crash!
echo Melakukan restart otomatis dalam 5 detik...
timeout /t 5 /nobreak >nul
goto WATCHDOG_LOOP

