# Quick Start Guide for Vast.ai Deployment

## 🚀 Fast Deployment Steps

### 1. Connect to your Vast.ai instance
```bash
ssh -p [PORT] root@[VAST_AI_IP]
```

### 2. Install system requirements
```bash
apt-get update && apt-get install -y python3 python3-pip nginx git certbot python3-certbot-nginx
```

### 3. Upload your project
```bash
cd /root
# Upload via SCP from your local machine:
# scp -P [PORT] -r C:\Users\BLG\Desktop\ai_chatbot root@[VAST_AI_IP]:/root/
```

### 4. Configure environment
```bash
cd /root/ai_chatbot
cp .env.example .env
nano .env
```
**Update these required values:**
- `GOOGLE_API_KEY` - Your Google Gemini API key
- `PAGE_ACCESS_TOKEN` - Your Facebook token (if using Messenger)

### 5. Install dependencies
```bash
pip3 install -r requirements.txt
```

### 6. Test locally first
```bash
python3 app.py
# Open another terminal and test:
curl http://localhost:5000/
```

### 7. Set up SSL certificate
```bash
certbot --nginx -d ais.bdstall.com
```

### 8. Configure Nginx
```bash
cp nginx.conf /etc/nginx/sites-available/chatbot
nano /etc/nginx/sites-available/chatbot
# Update SSL paths if needed (certbot usually auto-configures)
ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### 9. Create systemd service
```bash
cat > /etc/systemd/system/chatbot.service << 'EOF'
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
EOF

systemctl daemon-reload
systemctl enable chatbot
systemctl start chatbot
```

### 10. Configure DNS
In your domain registrar:
- Create A record: `ais` → `[Vast.ai IP]`
- Wait 5-30 minutes for propagation

### 11. Test your deployment
```bash
# Test locally
curl http://localhost:5000/

# Test via subdomain (after DNS propagates)
curl https://ais.bdstall.com/chatbot/
```

### 12. View in browser
Open: **https://ais.bdstall.com/chatbot/**

---

## 📋 Useful Commands

### Check status
```bash
systemctl status chatbot
systemctl status nginx
```

### View logs
```bash
tail -f logs/error.log
journalctl -u chatbot -f
tail -f /var/log/nginx/chatbot_error.log
```

### Restart services
```bash
systemctl restart chatbot
systemctl restart nginx
```

### Update application
```bash
cd /root/ai_chatbot
# Make changes or pull updates
systemctl restart chatbot
```

---

## ⚠️ Common Issues

**Port already in use:**
```bash
lsof -i :5000
kill -9 [PID]
systemctl restart chatbot
```

**Nginx configuration error:**
```bash
nginx -t  # Test config
# Fix issues shown
systemctl restart nginx
```

**SSL certificate issues:**
```bash
certbot renew
systemctl restart nginx
```

**Application not starting:**
```bash
journalctl -u chatbot -n 50  # Last 50 lines
cd /root/ai_chatbot
python3 app.py  # Test manually
```

---

## 🔐 Security Checklist

- [ ] SSL certificate installed and working
- [ ] `.env` file created with actual credentials
- [ ] `.env` added to `.gitignore`
- [ ] Firewall configured (ports 80, 443, SSH only)
- [ ] Strong passwords for all services
- [ ] Regular backups scheduled

---

## 📞 Support URLs

After deployment, your URLs will be:
- **Chat Interface**: https://ais.bdstall.com/chatbot/
- **API Webhook**: https://ais.bdstall.com/chatbot/webhook
- **Test Endpoint**: https://ais.bdstall.com/chatbot/test

---

For detailed information, see [DEPLOYMENT.md](DEPLOYMENT.md)
