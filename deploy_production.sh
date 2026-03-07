#!/bin/bash

# AI Chatbot Production Deployment Script
# For Ubuntu/Debian servers

set -e  # Exit on error

echo "================================================"
echo "🚀 AI Chatbot Production Deployment"
echo "================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/root/ai_services/ai_chatbot"
NGINX_CONF="/etc/nginx/sites-available/chatbot"
SERVICE_FILE="/etc/systemd/system/chatbot.service"

echo -e "${YELLOW}📁 Working directory: $APP_DIR${NC}"
cd $APP_DIR

# Step 1: Create logs directory
echo -e "${GREEN}Step 1: Creating logs directory...${NC}"
mkdir -p logs

# Step 2: Stop Flask development server if running
echo -e "${GREEN}Step 2: Stopping any running Flask server...${NC}"
pkill -f "flask run" || true
pkill -f "python run.py" || true
pkill -f "python.*app_simple" || true

# Step 3: Install/Update dependencies (already done based on your logs)
echo -e "${GREEN}Step 3: Dependencies already installed${NC}"

# Step 4: Setup Gunicorn service
echo -e "${GREEN}Step 4: Creating systemd service...${NC}"
cat > $SERVICE_FILE << 'EOF'
[Unit]
Description=AI Chatbot Gunicorn Service
After=network.target

[Service]
Type=notify
User=root
WorkingDirectory=/root/ai_services/ai_chatbot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/gunicorn -c config/gunicorn_config.py src.api.app_simple:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Step 5: Setup Nginx
echo -e "${GREEN}Step 5: Configuring Nginx...${NC}"
cp config/nginx_no_ssl.conf $NGINX_CONF

# Enable the site
ln -sf $NGINX_CONF /etc/nginx/sites-enabled/chatbot

# Remove default nginx site if it exists
rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo -e "${YELLOW}Testing Nginx configuration...${NC}"
nginx -t

# Step 6: Start services
echo -e "${GREEN}Step 6: Starting services...${NC}"

# Reload systemd
systemctl daemon-reload

# Enable and start chatbot service
systemctl enable chatbot
systemctl restart chatbot

# Restart nginx
systemctl restart nginx

# Step 7: Check status
echo ""
echo "================================================"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "================================================"
echo ""
echo "Service Status:"
systemctl status chatbot --no-pager -l
echo ""
echo "Nginx Status:"
systemctl status nginx --no-pager | head -10
echo ""
echo "================================================"
echo "🌐 Your chatbot is now running at:"
echo "   http://ais.bdstall.com/chatbot"
echo "   http://128.199.144.145/chatbot"
echo "================================================"
echo ""
echo "📋 Useful commands:"
echo "   View logs:        journalctl -u chatbot -f"
echo "   Restart service:  systemctl restart chatbot"
echo "   Stop service:     systemctl stop chatbot"
echo "   Check status:     systemctl status chatbot"
echo "================================================"
