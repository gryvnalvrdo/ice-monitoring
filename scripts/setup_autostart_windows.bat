@echo off
TITLE Registrasi Auto-Start Windows (Boot Otomatis Pabrik 24/7)
COLOR 0A

set TASK_NAME=IceMonitoringServer
set BAT_PATH=%~dp0start_production.bat

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /create /tn "%TASK_NAME%" /tr "\"%BAT_PATH%\"" /sc onlogon /rl highest /f

if %ERRORLEVEL% EQU 0 (
    echo [SUKSES] Auto-start berhasil dipasang!
) else (
    echo [INFO] Jalankan file .bat ini dengan Klik Kanan -> Run as Administrator.
)
pause
