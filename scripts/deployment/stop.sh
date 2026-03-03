#!/bin/bash

# Stop Script for AI Chatbot
# Stops both Gunicorn and Nginx

echo "Stopping AI Chatbot..."

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Stop Gunicorn
echo "Stopping Gunicorn..."
if [ -f /tmp/gunicorn.pid ]; then
    kill $(cat /tmp/gunicorn.pid) 2>/dev/null && echo -e "${GREEN}✓ Gunicorn stopped${NC}" || echo -e "${RED}✗ Failed to stop Gunicorn${NC}"
    rm -f /tmp/gunicorn.pid
fi
pkill gunicorn || true

# Stop Nginx
echo "Stopping Nginx..."
pkill nginx && echo -e "${GREEN}✓ Nginx stopped${NC}" || echo -e "${RED}✗ Failed to stop Nginx${NC}"

# Check if stopped
sleep 2
if ! pgrep gunicorn > /dev/null && ! pgrep nginx > /dev/null; then
    echo -e "${GREEN}✓ All services stopped${NC}"
else
    echo -e "${RED}⚠ Some processes may still be running${NC}"
    echo "Gunicorn: $(pgrep gunicorn || echo 'stopped')"
    echo "Nginx: $(pgrep nginx || echo 'stopped')"
fi
