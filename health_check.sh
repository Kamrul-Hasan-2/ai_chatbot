#!/bin/bash

# Health Check Script for AI Chatbot
# Monitors the health and status of the chatbot service

# Configuration
SERVICE_NAME="chatbot"
LOCAL_URL="http://localhost:5000/health"
PUBLIC_URL="https://ais.bdstall.com/chatbot/health"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "   AI Chatbot Health Check"
echo "=========================================="
echo ""

# Check if service is running
echo -n "Systemd Service Status: "
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    echo "Start with: systemctl start $SERVICE_NAME"
fi

# Check service details
echo ""
echo -e "${BLUE}Service Details:${NC}"
systemctl status $SERVICE_NAME --no-pager -l | head -n 10

# Check local endpoint
echo ""
echo -n "Local Endpoint ($LOCAL_URL): "
if curl -s -o /dev/null -w "%{http_code}" $LOCAL_URL | grep -q "200"; then
    echo -e "${GREEN}✓ Responding${NC}"
else
    echo -e "${RED}✗ Not Responding${NC}"
fi

# Check public endpoint (if DNS is configured)
echo -n "Public Endpoint ($PUBLIC_URL): "
if curl -s -o /dev/null -w "%{http_code}" $PUBLIC_URL | grep -q "200"; then
    echo -e "${GREEN}✓ Responding${NC}"
else
    echo -e "${YELLOW}⚠ Not Responding (DNS may not be configured)${NC}"
fi

# Check nginx
echo ""
echo -n "Nginx Status: "
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
fi

# Check port
echo ""
echo -n "Port 5000 Status: "
if lsof -i :5000 -t > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Port in use${NC}"
    echo "Process: $(lsof -i :5000 -t | xargs ps -p | tail -n 1)"
else
    echo -e "${RED}✗ Port not in use${NC}"
fi

# Check recent logs
echo ""
echo -e "${BLUE}Recent Error Logs (last 5 lines):${NC}"
if [ -f "logs/error.log" ]; then
    tail -n 5 logs/error.log
else
    echo "No error log found"
fi

# Resource usage
echo ""
echo -e "${BLUE}Resource Usage:${NC}"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 " / " $2 " (" $3/$2*100 "%)"}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $3 " / " $2 " (" $5 ")"}')"
if command -v nvidia-smi &> /dev/null; then
    echo "GPU: $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)%"
fi

echo ""
echo "=========================================="
echo "For detailed logs: journalctl -u $SERVICE_NAME -f"
echo "To restart: systemctl restart $SERVICE_NAME"
echo "=========================================="
