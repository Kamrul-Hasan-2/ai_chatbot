# AI Chatbot Launcher - PowerShell Script
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   AI Chatbot - Quick Start" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
Write-Host "[1/3] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.8 or higher" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check dependencies
Write-Host "[2/3] Checking dependencies..." -ForegroundColor Yellow
$flaskInstalled = pip show flask 2>$null
if (-not $flaskInstalled) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
} else {
    Write-Host "✓ Dependencies OK" -ForegroundColor Green
}

# Run the application
Write-Host "[3/3] Starting server..." -ForegroundColor Yellow
Write-Host ""

python run.py

Write-Host ""
Write-Host "Server stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
