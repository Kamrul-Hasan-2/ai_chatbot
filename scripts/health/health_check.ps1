# AI Chatbot Health Check Script
# Monitors the health and status of the chatbot service

# Configuration
$SERVICE_NAME = "chatbot"
$LOCAL_URL = "http://localhost:5000/health"
$PUBLIC_URL = "https://ais.bdstall.com/chatbot/health"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   AI Chatbot Health Check" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if service is running (Linux systemd)
Write-Host "Checking service status..." -ForegroundColor Yellow
try {
    $serviceStatus = systemctl is-active $SERVICE_NAME 2>$null
    if ($serviceStatus -eq "active") {
        Write-Host "✓ Service Running" -ForegroundColor Green
    } else {
        Write-Host "✗ Service Not Running" -ForegroundColor Red
    }
} catch {
    Write-Host "⚠ Systemd not available (are you on Windows?)" -ForegroundColor Yellow
}

# Check local endpoint
Write-Host ""
Write-Host "Checking local endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri $LOCAL_URL -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Local Endpoint Responding" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Local Endpoint Not Responding" -ForegroundColor Red
}

# Check public endpoint
Write-Host ""
Write-Host "Checking public endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri $PUBLIC_URL -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ Public Endpoint Responding" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠ Public Endpoint Not Responding (DNS may not be configured)" -ForegroundColor Yellow
}

# Check port
Write-Host ""
Write-Host "Checking port 5000..." -ForegroundColor Yellow
$port5000 = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($port5000) {
    Write-Host "✓ Port 5000 in use" -ForegroundColor Green
} else {
    Write-Host "✗ Port 5000 not in use" -ForegroundColor Red
}

# Check recent logs
Write-Host ""
Write-Host "Recent Error Logs:" -ForegroundColor Yellow
if (Test-Path "logs/error.log") {
    Get-Content "logs/error.log" -Tail 5
} else {
    Write-Host "No error log found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Health check complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
