@echo off
REM ========================================
REM Downloads Monitor - Daily Task
REM Designed for Windows Task Scheduler
REM ========================================

REM Change to script directory
cd /d "%~dp0"

REM Create logs directory if not exists
if not exist "logs" mkdir "logs"

REM Generate log filename with timestamp using PowerShell
for /f "tokens=*" %%i in ('powershell -Command "Get-Date -Format 'yyyyMMdd'"') do set DATESTAMP=%%i
set LOG_FILE=logs\daily_%DATESTAMP%.log

REM Run monitor with minimal output, log to file
echo [%date% %time%] Starting Downloads Monitor... >> "%LOG_FILE%"
python app.py --log-level WARNING --log-file "%LOG_FILE%" 2>&1

REM Check exit code
if errorlevel 1 (
    echo [%date% %time%] ERROR: Scan failed >> "%LOG_FILE%"
    exit /b 1
) else (
    echo [%date% %time%] SUCCESS: Scan completed >> "%LOG_FILE%"
    exit /b 0
)
