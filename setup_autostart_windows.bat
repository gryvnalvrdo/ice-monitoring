@echo off
TITLE Registrasi Auto-Start Windows (Boot Otomatis Pabrik 24/7)
COLOR 0A

echo ======================================================================
echo    INSTALLASI AUTO-START WINDOWS UNTUK MINI PC PABRIK
echo ======================================================================
echo  Skrip ini akan mendaftarkan sistem ke Windows Task Scheduler
echo  agar program otomatis menyala sendiri saat komputer dinyalakan/booting
echo  tanpa perlu ada operator yang login atau membuka terminal!
echo ======================================================================
echo.

set TASK_NAME=IceMonitoringServer
set BAT_PATH=%~dp0start_production.bat

:: Hapus task lama jika ada
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Buat task baru yang jalan saat ONSTART / boot
schtasks /create /tn "%TASK_NAME%" /tr "\"%BAT_PATH%\"" /sc onlogon /rl highest /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUKSES] Auto-start berhasil dipasang!
    echo Sistem akan otomatis berjalan di background setiap kali Mini PC menyala.
) else (
    echo.
    echo [INFO] Harap jalankan file .bat ini dengan cara: Klik Kanan -> Run as Administrator.
)

echo.
pause

