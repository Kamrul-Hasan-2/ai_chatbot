@echo off
REM Complete Project Runner
REM This starts the chatbot server

echo ==========================================
echo   Facebook Chatbot - Starting Server
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Install from: https://python.org
    pause
    exit /b 1
)

echo Step 1/4: Installing dependencies...
pip install -q -r requirements.txt

echo.
echo Step 2/4: Checking configuration...
if not exist .env (
    echo WARNING: .env file not found!
    echo Make sure your Facebook tokens are configured.
    echo.
)

echo Step 3/4: Starting chatbot server...
echo.
echo ==========================================
echo   SERVER RUNNING!
echo ==========================================
echo.
echo   Local:  http://localhost:5000
echo   Health: http://localhost:5000/health
echo.
echo   NEXT STEPS:
echo   1. Keep this window OPEN
echo   2. Open NEW terminal: ngrok http 5000
echo   3. Copy ngrok URL
echo   4. Setup Facebook webhook
echo.
echo   Full guide: HOW_TO_RUN.md
echo   Press Ctrl+C to stop
echo ==========================================
echo.

REM Run the application
python app_integrated.py

pause
