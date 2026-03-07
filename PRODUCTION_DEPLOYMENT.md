# AI Chatbot Production Deployment Guide

## Current Issue
Your Flask development server is running directly, which:
- ❌ Not production-ready
- ❌ No HTTPS support (causing TLS errors)
- ❌ Direct Internet exposure
- ❌ No process management
- ❌ Poor performance under load

## Solution: Gunicorn + Nginx

### Architecture:
```
Internet → Nginx (Port 80/443) → Gunicorn → Flask App
```

---

## Quick Deployment (Recommended)

### Step 1: Stop current server
Press `CTRL+C` in your current terminal to stop Flask development server.

### Step 2: Run deployment script
```bash
cd /root/ai_services/ai_chatbot
chmod +x deploy_production.sh
./deploy_production.sh
```

This will:
1. ✅ Create systemd service for auto-restart
2. ✅ Configure Nginx as reverse proxy
3. ✅ Start Gunicorn with optimized settings
4. ✅ Enable automatic startup on boot

### Step 3: Access your site
- **URL**: http://ais.bdstall.com/chatbot
- **Direct IP**: http://128.199.144.145/chatbot

---

## Manual Deployment (Alternative)

### Option A: Run Gunicorn directly (without systemd)

1. Stop current Flask server (CTRL+C)

2. Start with Gunicorn:
```bash
cd /root/ai_services/ai_chatbot
chmod +x start_gunicorn.sh
./start_gunicorn.sh
```

### Option B: Use systemd service

1. Create service file:
```bash
nano /etc/systemd/system/chatbot.service
```

Paste this content:
```ini
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
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Start the service:
```bash
systemctl daemon-reload
systemctl enable chatbot
systemctl start chatbot
systemctl status chatbot
```

---

## Setup Nginx (Reverse Proxy)

### 1. Install Nginx (if not installed)
```bash
apt-get update
apt-get install -y nginx
```

### 2. Configure Nginx
```bash
cp config/nginx_no_ssl.conf /etc/nginx/sites-available/chatbot
ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
```

### 3. Test and restart Nginx
```bash
nginx -t
systemctl restart nginx
```

---

## Setup HTTPS (SSL) - Optional but Recommended

### Using Let's Encrypt (Free SSL)

1. Install Certbot:
```bash
apt-get install -y certbot python3-certbot-nginx
```

2. Get SSL certificate:
```bash
certbot --nginx -d ais.bdstall.com
```

3. Follow prompts and certbot will automatically:
   - Get SSL certificate
   - Update Nginx config
   - Setup auto-renewal

4. Your site will be available at: `https://ais.bdstall.com/chatbot`

---

## Verify Deployment

### Check if services are running:
```bash
# Check Gunicorn/Chatbot service
systemctl status chatbot

# Check Nginx
systemctl status nginx

# Check if port 5000 is listening (Gunicorn)
netstat -tlnp | grep 5000

# Check if port 80 is listening (Nginx)
netstat -tlnp | grep :80
```

### View logs:
```bash
# Gunicorn logs
tail -f /root/ai_services/ai_chatbot/logs/access.log
tail -f /root/ai_services/ai_chatbot/logs/error.log

# Systemd service logs
journalctl -u chatbot -f

# Nginx logs
tail -f /var/log/nginx/chatbot_access.log
tail -f /var/log/nginx/chatbot_error.log
```

### Test the application:
```bash
# Test locally
curl http://localhost:5000/health
curl http://localhost/chatbot/health

# Test from outside
curl http://ais.bdstall.com/chatbot/health
```

---

## Useful Commands

### Service Management:
```bash
# Restart chatbot
systemctl restart chatbot

# Stop chatbot
systemctl stop chatbot

# Start chatbot
systemctl start chatbot

# Check status
systemctl status chatbot

# View logs
journalctl -u chatbot -f
```

### Nginx Management:
```bash
# Restart Nginx
systemctl restart nginx

# Test config
nginx -t

# Reload config (without downtime)
systemctl reload nginx
```

### Process Management:
```bash
# Find gunicorn processes
ps aux | grep gunicorn

# Kill all gunicorn processes (if needed)
pkill -f gunicorn

# Monitor resource usage
htop
```

---

## Troubleshooting

### Issue: Port 5000 already in use
```bash
# Find what's using port 5000
lsof -i :5000
# or
netstat -tlnp | grep 5000

# Kill the process
kill -9 <PID>
```

### Issue: Nginx 502 Bad Gateway
- Gunicorn probably isn't running
```bash
systemctl status chatbot
journalctl -u chatbot -n 50
```

### Issue: Can't access from outside
- Check firewall:
```bash
ufw status
ufw allow 80/tcp
ufw allow 443/tcp
```

### Issue: Permission denied
```bash
# Fix permissions
chmod +x deploy_production.sh start_gunicorn.sh
chown -R root:root /root/ai_services/ai_chatbot
```

---

## Performance Tuning

### Adjust worker count in `config/gunicorn_config.py`:
```python
# Default: (CPU cores * 2) + 1
workers = 5  # Adjust based on your server

# Worker class for async handling
worker_class = 'gevent'
worker_connections = 1000
```

### Monitor performance:
```bash
# Check CPU/Memory usage
htop

# Check worker count
ps aux | grep gunicorn | wc -l
```

---

## Next Steps

1. ✅ Deploy with Gunicorn + Nginx
2. ✅ Setup HTTPS with Let's Encrypt
3. ✅ Monitor logs for errors
4. ✅ Test API endpoints
5. ✅ Setup monitoring/alerting (optional)

---

## Support

If you encounter issues:
1. Check logs: `journalctl -u chatbot -f`
2. Verify Nginx config: `nginx -t`
3. Test locally first: `curl http://localhost:5000/health`
4. Check firewall/security groups
