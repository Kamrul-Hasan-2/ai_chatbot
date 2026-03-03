# AI Chatbot Startup Script for Vast.ai (PowerShell)
# This script sets up and runs the chatbot application

Write-Host "==================================" -ForegroundColor Green
Write-Host "AI Chatbot Deployment on Vast.ai" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green

# Create necessary directories
New-Item -ItemType Directory -Force -Path logs | Out-Null
New-Item -ItemType Directory -Force -Path data/knowledge | Out-Null

# Set environment variables if not already set
if (-not $env:PORT) {
    $env:PORT = "5000"
}
$env:FLASK_ENV = "production"

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "Warning: .env file not found. Creating from template..." -ForegroundColor Yellow
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "Please edit .env file with your actual credentials!" -ForegroundColor Yellow
    }
}

# Install/update dependencies
Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

# Start the application with Gunicorn
Write-Host "Starting Gunicorn server on port $env:PORT..." -ForegroundColor Cyan
gunicorn -c gunicorn_config.py app:app
