@echo off
REM Mode Manager - Control Bot and Human Modes
REM Double-click this file to manage conversation modes

echo ==========================================
echo   Bot and Human Mode Manager
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed
    pause
    exit /b 1
)

echo Starting Mode Manager...
echo.
echo This tool lets you:
echo  - View who is in BOT MODE vs HUMAN MODE
echo  - Switch users between modes
echo  - View pending messages
echo.
echo Press Ctrl+C to exit
echo ==========================================
echo.

REM Run the mode manager
python mode_manager.py

pause
