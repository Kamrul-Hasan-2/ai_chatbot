#!/bin/bash

# SSL Setup Script - Run this AFTER DNS is configured
# This will add HTTPS support to your chatbot

set -e

echo "=========================================="
echo "   SSL Certificate Setup"
echo "=========================================="
echo ""

DOMAIN="ais.bdstall.com"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if DNS is configured
print_info "Checking DNS configuration..."
if ! host $DOMAIN > /dev/null 2>&1; then
    print_error "DNS not configured yet for $DOMAIN"
    echo "Please configure your DNS first:"
    echo "  1. Go to your domain registrar"
    echo "  2. Add A record: ais -> [Your Server IP]"
    echo "  3. Wait 5-30 minutes for propagation"
    echo "  4. Run this script again"
    exit 1
fi

RESOLVED_IP=$(host $DOMAIN | awk '/has address/ { print $4 }' | head -n1)
print_success "DNS configured: $DOMAIN -> $RESOLVED_IP"

# Install certbot if not installed
if ! command -v certbot &> /dev/null; then
    print_info "Installing certbot..."
    apt-get update -qq
    apt-get install -y -qq certbot
    print_success "Certbot installed"
fi

# Stop nginx temporarily
print_info "Stopping Nginx temporarily..."
pkill nginx || true
sleep 2

# Get SSL certificate
print_info "Requesting SSL certificate from Let's Encrypt..."
certbot certonly --standalone \
    -d $DOMAIN \
    --non-interactive \
    --agree-tos \
    --email admin@$DOMAIN \
    --preferred-challenges http

if [ $? -eq 0 ]; then
    print_success "SSL certificate obtained"
else
    print_error "Failed to obtain SSL certificate"
    # Restart nginx even if SSL failed
    nginx
    exit 1
fi

# Update nginx config to use SSL
print_info "Updating Nginx configuration for HTTPS..."
cp nginx.conf /etc/nginx/sites-available/chatbot

# Update SSL paths in config
sed -i "s|/etc/ssl/certs/your_certificate.crt|/etc/letsencrypt/live/$DOMAIN/fullchain.pem|g" /etc/nginx/sites-available/chatbot
sed -i "s|/etc/ssl/private/your_private_key.key|/etc/letsencrypt/live/$DOMAIN/privkey.pem|g" /etc/nginx/sites-available/chatbot
sed -i "s|/path/to/your/ai_chatbot|/root/ai_chatbot|g" /etc/nginx/sites-available/chatbot

# Test nginx config
if nginx -t 2>&1 | grep -q "successful"; then
    print_success "Nginx configuration valid"
    nginx
    print_success "Nginx restarted with SSL"
else
    print_error "Nginx configuration invalid"
    nginx -t
    # Start with old config
    nginx
    exit 1
fi

echo ""
echo "=========================================="
echo "         SSL Setup Complete!           "
echo "=========================================="
echo ""
print_success "HTTPS is now enabled!"
echo ""
echo "Your URLs:"
echo "  • HTTPS: https://$DOMAIN/chatbot/"
echo "  • HTTP: http://$DOMAIN/chatbot/ (redirects to HTTPS)"
echo ""
echo "SSL Certificate Info:"
echo "  • Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "  • Private Key: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
echo "  • Valid for: 90 days"
echo "  • Auto-renewal: certbot renew"
echo ""
echo "Test your HTTPS site:"
echo "  curl https://$DOMAIN/chatbot/"
echo ""
print_success "Setup completed successfully!"
