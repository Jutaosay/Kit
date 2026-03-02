@echo off
title Downloads Monitor
color 0A

echo ========================================
echo    Downloads Folder Monitor v2.5.0
echo ========================================
echo.

python app.py --log-level INFO

echo.
if errorlevel 1 (
    echo [ERROR] Scan failed
    echo.
    pause
) else (
    echo ========================================
    echo [SUCCESS] Scan completed!
    echo ========================================
    echo.
    echo Closing in 5 seconds...
    timeout /t 5 /nobreak >nul
)
