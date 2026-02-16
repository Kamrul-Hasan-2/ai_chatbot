# Deployment Guide for Vast.ai with Subdomain

## Overview
This guide will help you deploy your AI Chatbot on Vast.ai and configure it to work with your subdomain: https://ais.bdstall.com/chatbot

## Prerequisites
- Vast.ai account with a running GPU instance
- Domain control for ais.bdstall.com
- SSL certificate for HTTPS (can use Let's Encrypt)
- Your Facebook Page Access Token and Verify Token (if using Messenger integration)
- Google API Key (for Gemini AI model)

## Step 1: Prepare Your Vast.ai Instance

### 1.1 SSH into your Vast.ai instance
```bash
ssh -p [PORT] root@[VAST_AI_IP]
```

### 1.2 Update system and install dependencies
```bash
apt-get update
apt-get install -y python3 python3-pip nginx git
```

## Step 2: Deploy Your Application

### 2.1 Clone or upload your project
```bash
cd /root
# If using git:
git clone [YOUR_REPO_URL] ai_chatbot
# Or upload via SCP:
# scp -P [PORT] -r /path/to/local/ai_chatbot root@[VAST_AI_IP]:/root/
```

### 2.2 Navigate to project directory
```bash
cd /root/ai_chatbot
```

### 2.3 Set up environment variables
```bash
# Copy the example file
cp .env.example .env

# Edit with your actual credentials
nano .env
```

**Important**: Update these values in `.env`:
- `GOOGLE_API_KEY`: Your Google Gemini API key
- `PAGE_ACCESS_TOKEN`: Your Facebook Page Access Token
- `VERIFY_TOKEN`: Your Facebook Webhook Verify Token
- `PORT`: 5000 (or your preferred port)

### 2.4 Install Python dependencies
```bash
pip3 install -r requirements.txt
```

## Step 3: Configure Nginx for Subdomain

### 3.1 Copy nginx configuration
```bash
cp nginx.conf /etc/nginx/sites-available/chatbot
```

### 3.2 Edit the configuration
```bash
nano /etc/nginx/sites-available/chatbot
```

Update these lines:
- Replace `/etc/ssl/certs/your_certificate.crt` with your SSL certificate path
- Replace `/etc/ssl/private/your_private_key.key` with your private key path
- Update `/path/to/your/ai_chatbot` with actual path (likely `/root/ai_chatbot`)

### 3.3 Set up SSL Certificate (Let's Encrypt - Recommended)
```bash
apt-get install -y certbot python3-certbot-nginx

# Get SSL certificate
certbot --nginx -d ais.bdstall.com

# Follow the prompts to complete setup
```

### 3.4 Enable the site
```bash
ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
nginx -t  # Test configuration
systemctl restart nginx
```

## Step 4: Start Your Application

### 4.1 Option A: Run directly with startup script
```bash
chmod +x start.sh
./start.sh
```

### 4.2 Option B: Run with systemd (Recommended for production)

Create a systemd service file:
```bash
nano /etc/systemd/system/chatbot.service
```

Add this content:
```ini
[Unit]
Description=AI Chatbot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/ai_chatbot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/local/bin/gunicorn -c gunicorn_config.py app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
systemctl daemon-reload
systemctl enable chatbot
systemctl start chatbot
systemctl status chatbot
```

## Step 5: Configure DNS

### 5.1 Point your subdomain to Vast.ai IP
In your domain registrar (where bdstall.com is registered):
- Create an A record:
  - **Subdomain**: `ais`
  - **Type**: A
  - **Value**: [Your Vast.ai instance IP]
  - **TTL**: 3600 (or default)

### 5.2 Wait for DNS propagation (5-30 minutes)
Check with:
```bash
dig ais.bdstall.com
nslookup ais.bdstall.com
```

## Step 6: Test Your Deployment

### 6.1 Test the chatbot endpoint
```bash
curl http://localhost:5000/
curl https://ais.bdstall.com/chatbot/
```

### 6.2 Test the chat interface
Open in browser: https://ais.bdstall.com/chatbot/

### 6.3 Test the API
```bash
curl -X POST https://ais.bdstall.com/chatbot/test \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

## Step 7: Facebook Messenger Webhook Setup

### 7.1 Configure webhook URL
In Facebook Developer Console:
- Webhook URL: `https://ais.bdstall.com/chatbot/webhook`
- Verify Token: [Your VERIFY_TOKEN from .env]
- Subscribe to: messages, messaging_postbacks

## Troubleshooting

### Check application logs
```bash
# View logs
tail -f logs/error.log
tail -f logs/access.log

# Check systemd service logs
journalctl -u chatbot -f
```

### Check Nginx logs
```bash
tail -f /var/log/nginx/chatbot_error.log
tail -f /var/log/nginx/chatbot_access.log
```

### Restart services
```bash
# Restart application
systemctl restart chatbot

# Restart Nginx
systemctl restart nginx
```

### Port already in use
```bash
# Find process using port 5000
lsof -i :5000
# Kill the process
kill -9 [PID]
```

### Permission issues
```bash
# Fix permissions
chown -R root:root /root/ai_chatbot
chmod +x start.sh
```

## Maintenance

### Update application
```bash
cd /root/ai_chatbot
git pull  # if using git
pip3 install -r requirements.txt --upgrade
systemctl restart chatbot
```

### Monitor resources
```bash
# Check CPU and memory
htop
# Check disk space
df -h
```

### Backup data
```bash
# Backup database and logs
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/
```

## Security Recommendations

1. **Firewall**: Only allow ports 80, 443, and SSH port
```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow [SSH_PORT]/tcp
ufw enable
```

2. **Environment Variables**: Never commit `.env` to git
```bash
echo ".env" >> .gitignore
```

3. **Regular Updates**: Keep system and dependencies updated
```bash
apt-get update && apt-get upgrade -y
pip3 install -r requirements.txt --upgrade
```

4. **SSL**: Keep SSL certificates updated (certbot auto-renews)
```bash
certbot renew --dry-run  # Test renewal
```

## URLs After Deployment

- **Chat Interface**: https://ais.bdstall.com/chatbot/
- **Webhook**: https://ais.bdstall.com/chatbot/webhook
- **Test API**: https://ais.bdstall.com/chatbot/test
- **Health Check**: https://ais.bdstall.com/chatbot/health

## Support

If you encounter issues:
1. Check logs (application and nginx)
2. Verify environment variables in `.env`
3. Ensure all dependencies are installed
4. Verify domain DNS is pointing correctly
5. Check SSL certificate is valid

---
**Last Updated**: February 2026
