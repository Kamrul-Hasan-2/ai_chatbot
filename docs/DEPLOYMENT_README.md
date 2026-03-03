# AI Chatbot - Vast.ai Deployment Files

This directory contains all the files needed to deploy your AI chatbot on Vast.ai with subdomain support.

## 📁 Deployment Files

### Configuration Files
- **`.env.example`** - Environment variables template
- **`gunicorn_config.py`** - Gunicorn WSGI server configuration
- **`nginx.conf`** - Nginx reverse proxy configuration for subdomain
- **`chatbot.service`** - Systemd service file for auto-start

### Deployment Scripts
- **`deploy.sh`** - Automated deployment script (recommended)
- **`start.sh`** - Manual startup script (Linux)
- **`start.ps1`** - Manual startup script (Windows/PowerShell)

### Docker Files (Alternative Deployment)
- **`Dockerfile`** - Docker container configuration
- **`docker-compose.yml`** - Docker Compose orchestration

### Documentation
- **`QUICKSTART.md`** - Fast deployment guide (start here!)
- **`DEPLOYMENT.md`** - Comprehensive deployment documentation
- **`README.md`** - Project overview (this file)

## 🚀 Quick Start

### Option 1: Automated Deployment (Recommended)

1. Upload project to Vast.ai server:
   ```bash
   scp -P [PORT] -r C:\Users\BLG\Desktop\ai_chatbot root@[VAST_AI_IP]:/root/
   ```

2. SSH into Vast.ai instance:
   ```bash
   ssh -p [PORT] root@[VAST_AI_IP]
   ```

3. Run automated deployment:
   ```bash
   cd /root/ai_chatbot
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. Follow the prompts and you're done!

### Option 2: Manual Deployment

Follow the step-by-step guide in [QUICKSTART.md](QUICKSTART.md)

### Option 3: Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

## 🌐 Subdomain Configuration

Your chatbot will be accessible at: **https://ais.bdstall.com/chatbot/**

The nginx configuration handles:
- SSL/HTTPS termination
- URL path routing (`/chatbot` → backend)
- Reverse proxy to Gunicorn
- Security headers
- Static file serving

## 🔧 Configuration Required

Before deployment, update these in `.env`:

```env
GOOGLE_API_KEY=your_google_api_key_here
PAGE_ACCESS_TOKEN=your_facebook_token
VERIFY_TOKEN=your_verify_token
PORT=5000
```

## 📋 System Requirements

- **OS**: Ubuntu 20.04+ (recommended)
- **Python**: 3.8+
- **RAM**: 4GB minimum, 8GB+ recommended
- **Storage**: 10GB minimum
- **GPU**: Optional but will speed up AI responses

## 🔗 Important URLs After Deployment

- **Chat Interface**: https://ais.bdstall.com/chatbot/
- **API Webhook**: https://ais.bdstall.com/chatbot/webhook
- **Test Endpoint**: https://ais.bdstall.com/chatbot/test
- **Health Check**: https://ais.bdstall.com/chatbot/health

## 📊 Monitoring

### Check Service Status
```bash
systemctl status chatbot
```

### View Logs
```bash
# Application logs
tail -f logs/error.log
tail -f logs/access.log

# Service logs
journalctl -u chatbot -f

# Nginx logs
tail -f /var/log/nginx/chatbot_error.log
```

### Restart Services
```bash
systemctl restart chatbot
systemctl restart nginx
```

## 🔒 Security Features

- ✅ HTTPS/SSL encryption
- ✅ Security headers (X-Frame-Options, etc.)
- ✅ Environment variable protection
- ✅ Reverse proxy isolation
- ✅ Rate limiting (via nginx)

## 🆘 Troubleshooting

### Service won't start
```bash
journalctl -u chatbot -n 50
# Check for missing dependencies or configuration errors
```

### Port already in use
```bash
lsof -i :5000
kill -9 [PID]
systemctl restart chatbot
```

### Nginx errors
```bash
nginx -t  # Test configuration
systemctl restart nginx
```

### SSL certificate issues
```bash
certbot renew
systemctl restart nginx
```

## 📚 Additional Documentation

- [QUICKSTART.md](QUICKSTART.md) - Fast deployment steps
- [DEPLOYMENT.md](DEPLOYMENT.md) - Detailed deployment guide
- [GEMINI_IMPLEMENTATION.md](GEMINI_IMPLEMENTATION.md) - AI model details

## 🛠 Maintenance

### Update Application
```bash
cd /root/ai_chatbot
git pull  # if using git
pip3 install -r requirements.txt --upgrade
systemctl restart chatbot
```

### Backup Data
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/
```

### Monitor Resources
```bash
htop  # CPU/Memory
df -h  # Disk space
```

## 💡 Tips

1. **Always test locally first**: Run `python3 app.py` before deploying
2. **Check logs regularly**: Use `journalctl -u chatbot -f` to monitor
3. **Keep backups**: Regular backups of `data/` directory
4. **Update regularly**: Keep dependencies and system packages updated
5. **SSL auto-renewal**: Certbot automatically renews SSL certificates

## 🎯 Facebook Webhook Setup

Once deployed, configure your Facebook webhook:

1. Go to Facebook Developer Console
2. Set Webhook URL: `https://ais.bdstall.com/chatbot/webhook`
3. Set Verify Token: (from your `.env` file)
4. Subscribe to: `messages`, `messaging_postbacks`

## 📞 Support

If you encounter issues:
1. Check the logs (application and nginx)
2. Review [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section
3. Verify DNS configuration
4. Ensure SSL certificate is valid
5. Check environment variables in `.env`

---

**Domain**: https://ais.bdstall.com/chatbot/  
**Server**: Vast.ai  
**Last Updated**: February 2026
