# Upload updated files to server
# Edit these variables with your server details

$SERVER_IP = "128.199.144.145"
$SERVER_USER = "root"
$SERVER_PATH = "/root/ai_services/ai_chatbot"

Write-Host "📤 Uploading updated files to server..." -ForegroundColor Green

# You'll need to enter your password when prompted
scp src/api/app_simple.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/src/api/app_simple.py

Write-Host "✅ File uploaded!" -ForegroundColor Green
Write-Host ""
Write-Host "Now run on your server:" -ForegroundColor Yellow
Write-Host "  pkill -f gunicorn" -ForegroundColor Cyan
Write-Host "  cd /root/ai_services/ai_chatbot" -ForegroundColor Cyan
Write-Host "  gunicorn -c config/gunicorn_config.py src.api.app_simple:app" -ForegroundColor Cyan
