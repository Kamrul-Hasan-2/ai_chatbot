#!/bin/bash

# Restart Script for AI Chatbot
# Restarts both Gunicorn and Nginx

echo "Restarting AI Chatbot..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Kill existing processes
echo "Stopping Gunicorn..."
if [ -f /tmp/gunicorn.pid ]; then
    kill $(cat /tmp/gunicorn.pid) 2>/dev/null || true
fi
pkill gunicorn || true
sleep 2

echo "Restarting Nginx..."
pkill nginx || true
sleep 1
nginx

# Start Gunicorn
echo "Starting Gunicorn..."
cd /root/ai_chatbot
nohup gunicorn -c gunicorn_config.py app:app > logs/gunicorn.log 2>&1 &
GUNICORN_PID=$!
echo $GUNICORN_PID > /tmp/gunicorn.pid

sleep 3

# Check if running
if ps -p $GUNICORN_PID > /dev/null && pgrep nginx > /dev/null; then
    echo -e "${GREEN}✓ Services restarted successfully${NC}"
    echo "Gunicorn PID: $GUNICORN_PID"
    echo "Nginx PIDs: $(pgrep nginx | tr '\n' ' ')"
else
    echo -e "${RED}✗ Failed to restart services${NC}"
    echo "Check logs: tail -f logs/gunicorn.log"
    exit 1
fi
