#!/bin/bash

# Simplified Deployment Script for Vast.ai Docker Environment
# This script works without systemd

set -e  # Exit on error

echo "=========================================="
echo "AI Chatbot - Vast.ai Deployment (Docker)"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Configuration
PROJECT_DIR="/root/ai_chatbot"
DOMAIN="ais.bdstall.com"

print_info "Step 1: Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip nginx curl lsof
print_success "System dependencies installed"

print_info "Step 2: Checking project directory..."
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Project directory not found at $PROJECT_DIR"
    exit 1
fi
cd "$PROJECT_DIR"
print_success "Project directory found"

print_info "Step 3: Checking environment file..."
if [ ! -f .env ]; then
    print_error ".env file not found!"
    exit 1
fi
print_success ".env file exists"

print_info "Step 4: Installing Python dependencies..."
pip3 install -q -r requirements.txt
print_success "Python dependencies installed"

print_info "Step 5: Creating necessary directories..."
mkdir -p logs data/knowledge
chmod -R 755 logs data
print_success "Directories created"

print_info "Step 6: Configuring Nginx (HTTP only)..."
# Use HTTP-only config initially
cp nginx_no_ssl.conf /etc/nginx/sites-available/chatbot
ln -sf /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx config
if nginx -t 2>&1 | grep -q "successful"; then
    print_success "Nginx configuration valid"
else
    print_error "Nginx configuration invalid"
    nginx -t
    exit 1
fi

print_info "Step 7: Starting Nginx..."
# Kill any existing nginx processes
pkill nginx || true
sleep 2
nginx
if pgrep nginx > /dev/null; then
    print_success "Nginx started"
else
    print_error "Nginx failed to start"
    exit 1
fi

print_info "Step 8: Testing application..."
python3 -c "from src.api.app_simple import app; print('OK')" 2>&1 | grep -q "OK" && print_success "Application imports successfully" || {
    print_error "Application import failed"
    python3 -c "from src.api.app_simple import app"
    exit 1
}

print_info "Step 9: Starting Gunicorn server..."
# Kill any existing gunicorn processes
pkill gunicorn || true
sleep 2

# Start gunicorn in background
cd "$PROJECT_DIR"
nohup gunicorn -c config/gunicorn_config.py src.api.app_simple:app > logs/gunicorn.log 2>&1 &
GUNICORN_PID=$!

# Wait a bit for startup
sleep 5

if ps -p $GUNICORN_PID > /dev/null; then
    echo $GUNICORN_PID > /tmp/gunicorn.pid
    print_success "Gunicorn started (PID: $GUNICORN_PID)"
else
    print_error "Gunicorn failed to start"
    cat logs/gunicorn.log
    exit 1
fi

print_info "Step 10: Testing endpoints..."
sleep 3

# Test local endpoint
if curl -s http://localhost:5000/ > /dev/null; then
    print_success "Local endpoint responding"
else
    print_error "Local endpoint not responding"
    cat logs/error.log
fi

# Test through nginx
if curl -s http://localhost/chatbot/ > /dev/null; then
    print_success "Nginx proxy working"
else
    print_error "Nginx proxy not working"
fi

echo ""
echo "=========================================="
echo "         Deployment Complete!           "
echo "=========================================="
echo ""
print_success "Your chatbot is now running!"
echo ""
echo "Process IDs:"
echo "  • Gunicorn PID: $GUNICORN_PID (saved to /tmp/gunicorn.pid)"
echo "  • Nginx PIDs: $(pgrep nginx | tr '\n' ' ')"
echo ""
echo "Local URLs (for testing):"
echo "  • Direct: http://localhost:5000/"
echo "  • Via Nginx: http://localhost/chatbot/"
echo ""
echo "Public URLs (after DNS configuration):"
echo "  • Chat Interface: http://$DOMAIN/chatbot/"
echo "  • Webhook: http://$DOMAIN/chatbot/webhook"
echo "  • Test API: http://$DOMAIN/chatbot/test"
echo ""
echo "Important Commands:"
echo "  • View logs: tail -f logs/error.log"
echo "  • View Gunicorn logs: tail -f logs/gunicorn.log"
echo "  • Stop Gunicorn: kill \$(cat /tmp/gunicorn.pid)"
echo "  • Restart Gunicorn: ./restart.sh"
echo "  • Monitor: ./monitor.sh"
echo ""
echo "Next Steps:"
echo "  1. Configure DNS: Point $DOMAIN A record to this server's IP"
echo "  2. Test locally: curl http://localhost/chatbot/"
echo "  3. After DNS propagates, set up SSL: ./setup_ssl.sh"
echo ""
print_success "Deployment completed successfully!"
