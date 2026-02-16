#!/bin/bash

# Automated Deployment Script for Vast.ai
# This script automates the entire deployment process

set -e  # Exit on error

echo "=========================================="
echo "AI Chatbot - Automated Vast.ai Deployment"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables
PROJECT_DIR="/root/ai_chatbot"
DOMAIN="ais.bdstall.com"
SERVICE_NAME="chatbot"

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

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root"
    exit 1
fi

print_info "Step 1: Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip nginx git certbot python3-certbot-nginx curl
print_success "System dependencies installed"

print_info "Step 2: Checking project directory..."
if [ ! -d "$PROJECT_DIR" ]; then
    print_error "Project directory not found at $PROJECT_DIR"
    print_info "Please upload your project first or adjust PROJECT_DIR in this script"
    exit 1
fi
cd "$PROJECT_DIR"
print_success "Project directory found"

print_info "Step 3: Setting up environment variables..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        print_info "Created .env file from template"
        print_error "IMPORTANT: Edit .env file with your actual credentials!"
        print_info "Run: nano $PROJECT_DIR/.env"
        read -p "Press Enter after you've updated the .env file..."
    else
        print_error ".env.example not found"
        exit 1
    fi
else
    print_success ".env file already exists"
fi

print_info "Step 4: Installing Python dependencies..."
pip3 install -q -r requirements.txt
print_success "Python dependencies installed"

print_info "Step 5: Creating necessary directories..."
mkdir -p logs data/knowledge
print_success "Directories created"

print_info "Step 6: Setting up SSL certificate..."
read -p "Do you want to set up SSL certificate with Let's Encrypt? (y/n): " setup_ssl
if [ "$setup_ssl" = "y" ]; then
    print_info "Setting up SSL for $DOMAIN..."
    certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
        print_error "SSL setup failed. You may need to configure DNS first."
        print_info "Skipping SSL for now. You can run 'certbot --nginx -d $DOMAIN' later."
    }
else
    print_info "Skipping SSL setup. You can run 'certbot --nginx -d $DOMAIN' later."
fi

print_info "Step 7: Configuring Nginx..."
# Update nginx config with actual paths
sed -i "s|/path/to/your/ai_chatbot|$PROJECT_DIR|g" nginx.conf
sed -i "s|/etc/ssl/certs/your_certificate.crt|/etc/letsencrypt/live/$DOMAIN/fullchain.pem|g" nginx.conf
sed -i "s|/etc/ssl/private/your_private_key.key|/etc/letsencrypt/live/$DOMAIN/privkey.pem|g" nginx.conf

# Copy nginx config
cp nginx.conf /etc/nginx/sites-available/$SERVICE_NAME
ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/

# Test nginx config
if nginx -t 2>/dev/null; then
    print_success "Nginx configuration valid"
    systemctl restart nginx
    print_success "Nginx restarted"
else
    print_error "Nginx configuration invalid. Please check manually."
fi

print_info "Step 8: Setting up systemd service..."
# Update service file with actual paths
sed -i "s|/root/ai_chatbot|$PROJECT_DIR|g" chatbot.service

# Copy service file
cp chatbot.service /etc/systemd/system/$SERVICE_NAME.service

# Reload systemd
systemctl daemon-reload
systemctl enable $SERVICE_NAME
print_success "Systemd service configured"

print_info "Step 9: Testing application..."
# Test if app can start
python3 -c "from app import app; print('App import successful')" && print_success "Application imports successfully" || {
    print_error "Application import failed. Check dependencies."
    exit 1
}

print_info "Step 10: Starting services..."
systemctl start $SERVICE_NAME
sleep 3

if systemctl is-active --quiet $SERVICE_NAME; then
    print_success "Chatbot service started successfully"
else
    print_error "Chatbot service failed to start"
    print_info "Check logs with: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

print_info "Step 11: Testing endpoints..."
# Test local endpoint
if curl -s http://localhost:5000/ > /dev/null; then
    print_success "Local endpoint responding"
else
    print_error "Local endpoint not responding"
fi

echo ""
echo "=========================================="
echo "           Deployment Complete!           "
echo "=========================================="
echo ""
print_info "Your chatbot is now running!"
echo ""
echo "URLs:"
echo "  • Chat Interface: https://$DOMAIN/chatbot/"
echo "  • Webhook: https://$DOMAIN/chatbot/webhook"
echo "  • Test API: https://$DOMAIN/chatbot/test"
echo ""
echo "Useful Commands:"
echo "  • Check status: systemctl status $SERVICE_NAME"
echo "  • View logs: journalctl -u $SERVICE_NAME -f"
echo "  • Restart service: systemctl restart $SERVICE_NAME"
echo "  • View app logs: tail -f $PROJECT_DIR/logs/error.log"
echo ""
echo "Next Steps:"
echo "  1. Configure DNS to point $DOMAIN to this server's IP"
echo "  2. If you skipped SSL, run: certbot --nginx -d $DOMAIN"
echo "  3. Test your deployment: curl https://$DOMAIN/chatbot/"
echo "  4. Configure Facebook webhook with: https://$DOMAIN/chatbot/webhook"
echo ""
print_success "Deployment script completed successfully!"
