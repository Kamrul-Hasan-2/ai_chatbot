@echo off
REM Quick Start Script for Facebook Chatbot
REM Double-click this file to start the chatbot server

echo ==========================================
echo   Starting Facebook Chatbot Server
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
pip install -q -r requirements.txt

echo.
echo [2/3] Starting server on port 5000...
echo.
echo ==========================================
echo   Server Running!
echo ==========================================
echo.
echo   Local:    http://localhost:5000
echo   Health:   http://localhost:5000/health
echo.
echo   NEXT STEPS:
echo   1. Keep this window open
echo   2. Open NEW terminal and run: ngrok http 5000
echo   3. Copy ngrok URL and setup Facebook webhook
echo.
echo   Press Ctrl+C to stop server
echo ==========================================
echo.

REM Start the application
python app_integrated.py

pause
