#!/bin/bash

# Monitor Script for AI Chatbot
# Shows real-time status and logs

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear
echo -e "${BLUE}=========================================="
echo "   AI Chatbot Status Monitor"
echo "==========================================${NC}"
echo ""

# Check Gunicorn
echo -n "Gunicorn: "
if [ -f /tmp/gunicorn.pid ] && ps -p $(cat /tmp/gunicorn.pid) > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running (PID: $(cat /tmp/gunicorn.pid))${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
fi

# Check Nginx
echo -n "Nginx: "
if pgrep nginx > /dev/null; then
    echo -e "${GREEN}✓ Running (PIDs: $(pgrep nginx | tr '\n' ' '))${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
fi

# Check port
echo -n "Port 5000: "
if lsof -i :5000 -t > /dev/null 2>&1; then
    echo -e "${GREEN}✓ In Use${NC}"
else
    echo -e "${RED}✗ Not In Use${NC}"
fi

# Test endpoint
echo -n "Local Endpoint: "
if curl -s http://localhost:5000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Responding${NC}"
else
    echo -e "${RED}✗ Not Responding${NC}"
fi

echo -n "Nginx Proxy: "
if curl -s http://localhost/chatbot/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Working${NC}"
else
    echo -e "${RED}✗ Not Working${NC}"
fi

# Resource usage
echo ""
echo -e "${BLUE}Resource Usage:${NC}"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 " / " $2}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $3 " / " $2 " (" $5 ")"}')"

# Active connections
echo ""
echo -e "${BLUE}Active Connections:${NC}"
netstat -an | grep :5000 | grep ESTABLISHED | wc -l | xargs echo "Port 5000:"

# Recent logs
echo ""
echo -e "${BLUE}Recent Application Logs (last 10 lines):${NC}"
if [ -f logs/error.log ]; then
    tail -n 10 logs/error.log | sed 's/^/  /'
else
    echo "  No logs found"
fi

echo ""
echo -e "${BLUE}Recent Gunicorn Logs (last 5 lines):${NC}"
if [ -f logs/gunicorn.log ]; then
    tail -n 5 logs/gunicorn.log | sed 's/^/  /'
else
    echo "  No logs found"
fi

echo ""
echo "=========================================="
echo "Commands:"
echo "  • Restart: ./restart.sh"
echo "  • Stop: kill \$(cat /tmp/gunicorn.pid); pkill nginx"
echo "  • Tail logs: tail -f logs/error.log"
echo "=========================================="
