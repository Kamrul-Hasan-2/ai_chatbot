# Quick Start Script for Facebook Chatbot
# Right-click → Run with PowerShell

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Facebook Chatbot Server" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ ERROR: Python not found!" -ForegroundColor Red
    Write-Host "  Please install Python from https://python.org" -ForegroundColor Yellow
    pause
    exit 1
}

# Check if requirements are installed
Write-Host ""
Write-Host "[1/3] Checking dependencies..." -ForegroundColor Yellow

try {
    pip install -q -r requirements.txt
    Write-Host "✓ Dependencies OK" -ForegroundColor Green
} catch {
    Write-Host "⚠ Warning: Could not verify dependencies" -ForegroundColor Yellow
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "✗ WARNING: .env file not found!" -ForegroundColor Red
    Write-Host "  Please make sure your Facebook tokens are configured" -ForegroundColor Yellow
    Write-Host "  Check .env file for PAGE_ACCESS_TOKEN and VERIFY_TOKEN" -ForegroundColor Yellow
    Write-Host ""
}

# Start the server
Write-Host ""
Write-Host "[2/3] Starting chatbot server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  ✓ Server Running!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Local URL:    http://localhost:5000" -ForegroundColor White
Write-Host "  Health Check: http://localhost:5000/health" -ForegroundColor White
Write-Host "  Webhook Path: /webhook" -ForegroundColor White
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Keep this window OPEN" -ForegroundColor White
Write-Host "  2. Open NEW PowerShell and run:" -ForegroundColor White
Write-Host "     ngrok http 5000" -ForegroundColor Yellow
Write-Host "  3. Copy the ngrok HTTPS URL" -ForegroundColor White
Write-Host "  4. Setup Facebook webhook with that URL + /webhook" -ForegroundColor White
Write-Host ""
Write-Host "  Example webhook URL:" -ForegroundColor Cyan
Write-Host "  https://abc123.ngrok.io/webhook" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press Ctrl+C to stop server" -ForegroundColor Red
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Run the application
python app_integrated.py
