@echo off
cd /d "%~dp0"

echo ========================================
echo AI Review Trading - Setup
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10 or higher and enable Add Python to PATH.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [CHECK] Python found:
python --version
echo.

if not exist requirements.txt (
    echo [ERROR] requirements.txt not found. Please run this file in project root.
    echo.
    pause
    exit /b 1
)

echo [INSTALL] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed.
    echo Please check network and Python environment, then run setup.bat again.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Setup completed. You can run start_trader.bat after market close.
echo.
pause
