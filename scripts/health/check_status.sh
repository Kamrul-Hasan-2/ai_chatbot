#!/bin/bash

# Quick Status Check for Cloudflare Setup

echo "=========================================="
echo "   Cloudflare + Vast.ai Status Check"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get server IP
echo -e "${BLUE}Your Server IP:${NC}"
SERVER_IP=$(curl -s ifconfig.me)
echo "  $SERVER_IP"
echo ""

# Check DNS
echo -e "${BLUE}DNS Configuration:${NC}"
echo "  Domain: ais.bdstall.com"
DNS_IPS=$(dig +short ais.bdstall.com | head -n 3)
echo "  Resolves to: $DNS_IPS"
if echo "$DNS_IPS" | grep -q "104.26\|172.67"; then
    echo -e "  ${YELLOW}⚠ Using Cloudflare Proxy${NC}"
    echo "  This is OK - Cloudflare will forward to your server"
else
    echo -e "  ${GREEN}✓ Direct IP${NC}"
fi
echo ""

# Check if services are running
echo -e "${BLUE}Service Status:${NC}"

if pgrep gunicorn > /dev/null; then
    echo -e "  ${GREEN}✓ Gunicorn Running${NC}"
else
    echo -e "  ${RED}✗ Gunicorn Not Running${NC}"
    echo "    Run: ./deploy_vastai.sh"
fi

if pgrep nginx > /dev/null; then
    echo -e "  ${GREEN}✓ Nginx Running${NC}"
else
    echo -e "  ${RED}✗ Nginx Not Running${NC}"
    echo "    Run: nginx"
fi

# Check if port is open
if lsof -i :5000 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Port 5000 Open${NC}"
else
    echo -e "  ${RED}✗ Port 5000 Not Open${NC}"
fi

echo ""

# Test local endpoint
echo -e "${BLUE}Testing Endpoints:${NC}"
if curl -s http://localhost:5000/ > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Local (localhost:5000)${NC}"
else
    echo -e "  ${RED}✗ Local Not Responding${NC}"
fi

if curl -s http://localhost/chatbot/ > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Nginx Proxy (localhost/chatbot)${NC}"
else
    echo -e "  ${RED}✗ Nginx Proxy Not Working${NC}"
fi

# Test public endpoint (HTTP)
if curl -s -o /dev/null -w "%{http_code}" http://ais.bdstall.com/chatbot/ | grep -q "200\|301\|302"; then
    echo -e "  ${GREEN}✓ Public HTTP (http://ais.bdstall.com/chatbot/)${NC}"
else
    echo -e "  ${YELLOW}⚠ Public HTTP Not Responding Yet${NC}"
fi

# Test public endpoint (HTTPS)
if curl -s -k -o /dev/null -w "%{http_code}" https://ais.bdstall.com/chatbot/ | grep -q "200\|301\|302"; then
    echo -e "  ${GREEN}✓ Public HTTPS (https://ais.bdstall.com/chatbot/)${NC}"
else
    echo -e "  ${YELLOW}⚠ Public HTTPS Not Responding Yet${NC}"
fi

echo ""
echo "=========================================="
echo -e "${BLUE}Next Steps:${NC}"
echo ""

if ! pgrep gunicorn > /dev/null || ! pgrep nginx > /dev/null; then
    echo "1. Start services:"
    echo "   ./deploy_vastai.sh"
    echo ""
fi

echo "2. Configure Cloudflare:"
echo "   • Go to Cloudflare Dashboard"
echo "   • SSL/TLS → Set to 'Flexible'"
echo "   • DNS → Verify A record points to: $SERVER_IP"
echo ""

echo "3. Test your site:"
echo "   https://ais.bdstall.com/chatbot/"
echo ""
echo "=========================================="
