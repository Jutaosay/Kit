@echo off
setlocal EnableExtensions

REM =====================================================
REM Kit launcher for Windows
REM - Ensures .venv exists
REM - Activates .venv
REM - Installs dependencies (best effort)
REM - Launches kit.py
REM =====================================================

cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found. Please install Python 3 and add it to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] .venv not found, creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate .venv
    pause
    exit /b 1
)

if exist "requirements.txt" (
    echo [INFO] Installing/updating dependencies from requirements.txt ...
    python -m pip install --upgrade pip >nul 2>nul
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [WARN] Dependency install failed. Continuing to launch Kit anyway...
    )
)

echo [INFO] Launching Kit...
python kit.py
set "EXIT_CODE=%errorlevel%"

echo.
echo [INFO] Kit exited with code %EXIT_CODE%
endlocal & exit /b %EXIT_CODE%
