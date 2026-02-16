# Vast.ai Deployment Guide (Without Systemd)

## 🚀 Quick Deployment for Vast.ai Docker Environment

Your Vast.ai instance doesn't have systemd, so use this simplified approach.

### Step 1: Make Scripts Executable
```bash
chmod +x deploy_vastai.sh restart.sh monitor.sh setup_ssl.sh stop.sh
```

### Step 2: Run Deployment
```bash
./deploy_vastai.sh
```

This will:
- ✅ Install all dependencies
- ✅ Configure Nginx (HTTP only initially)
- ✅ Start Gunicorn
- ✅ Test all endpoints

### Step 3: Verify It's Running
```bash
./monitor.sh
```

You should see:
- ✓ Gunicorn: Running
- ✓ Nginx: Running
- ✓ Local Endpoint: Responding
- ✓ Nginx Proxy: Working

### Step 4: Test Locally
```bash
# Test direct access
curl http://localhost:5000/

# Test through Nginx
curl http://localhost/chatbot/

# Test API
curl -X POST http://localhost/chatbot/test \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

### Step 5: Configure DNS
In your domain registrar (where bdstall.com is registered):
1. Go to DNS settings
2. Add A record:
   - **Name**: `ais`
   - **Type**: A
   - **Value**: [Your Vast.ai IP address]
   - **TTL**: 3600
3. Save and wait 5-30 minutes

**Find your Vast.ai IP:**
```bash
curl ifconfig.me
```

### Step 6: Wait for DNS Propagation
Check when DNS is ready:
```bash
# Check DNS
nslookup ais.bdstall.com
dig ais.bdstall.com

# Test if accessible
curl http://ais.bdstall.com/chatbot/
```

### Step 7: Set Up SSL (After DNS Works)
```bash
./setup_ssl.sh
```

This will:
- Get SSL certificate from Let's Encrypt
- Configure HTTPS
- Restart Nginx with SSL

After this, access your site at: **https://ais.bdstall.com/chatbot/**

---

## 📋 Management Commands

### Check Status
```bash
./monitor.sh
```

### Restart Services
```bash
./restart.sh
```

### Stop Services
```bash
./stop.sh
```

### View Logs
```bash
# Application logs
tail -f logs/error.log

# Gunicorn logs
tail -f logs/gunicorn.log

# Access logs
tail -f logs/access.log

# Nginx error logs
tail -f /var/log/nginx/chatbot_error.log
```

### Manual Start
```bash
# Start Nginx
nginx

# Start Gunicorn
cd /root/ai_chatbot
nohup gunicorn -c gunicorn_config.py app:app > logs/gunicorn.log 2>&1 &
echo $! > /tmp/gunicorn.pid
```

---

## 🔧 Troubleshooting

### Port Already in Use
```bash
# Check what's using port 5000
lsof -i :5000

# Kill it
kill $(lsof -i :5000 -t)

# Or kill all gunicorn
pkill gunicorn

# Restart
./restart.sh
```

### Nginx Won't Start
```bash
# Test config
nginx -t

# Check if already running
pgrep nginx

# Kill and restart
pkill nginx
nginx
```

### Application Not Responding
```bash
# Check if running
./monitor.sh

# Check logs
tail -50 logs/error.log
tail -50 logs/gunicorn.log

# Restart
./restart.sh
```

### DNS Not Working
```bash
# Check current DNS
dig ais.bdstall.com

# Check what IP your server has
curl ifconfig.me

# Wait and try again (can take 30 minutes)
```

### SSL Certificate Failed
```bash
# Make sure DNS is working first
curl http://ais.bdstall.com/chatbot/

# Then retry SSL
./setup_ssl.sh
```

---

## 🎯 Your URLs

### Before SSL (HTTP only)
- **Chat Interface**: http://ais.bdstall.com/chatbot/
- **Webhook**: http://ais.bdstall.com/chatbot/webhook
- **Test API**: http://ais.bdstall.com/chatbot/test

### After SSL (HTTPS)
- **Chat Interface**: https://ais.bdstall.com/chatbot/
- **Webhook**: https://ais.bdstall.com/chatbot/webhook
- **Test API**: https://ais.bdstall.com/chatbot/test

---

## 🔐 Facebook Webhook Configuration

After deployment, configure your Facebook webhook:

1. Go to Facebook Developer Console
2. Your webhook URL: `https://ais.bdstall.com/chatbot/webhook`
3. Verify Token: `my_verify_token_12345` (from your .env)
4. Subscribe to: `messages`, `messaging_postbacks`

---

## 📊 Monitoring & Maintenance

### Keep Services Running
The services don't auto-restart in Docker. If your container restarts, you need to:
```bash
cd /root/ai_chatbot
./deploy_vastai.sh
```

Or add to container startup script.

### Update Application
```bash
cd /root/ai_chatbot
# Upload new files or git pull
./restart.sh
```

### Check Resource Usage
```bash
# CPU and Memory
htop

# Disk space
df -h

# Network connections
netstat -tulpn | grep :5000
```

---

## ✅ Verification Checklist

- [ ] Scripts are executable (`chmod +x *.sh`)
- [ ] Deployment script ran successfully
- [ ] Monitor shows all services running
- [ ] Local test works: `curl http://localhost/chatbot/`
- [ ] DNS A record created (ais -> Vast.ai IP)
- [ ] DNS propagated (wait 5-30 min)
- [ ] Public test works: `curl http://ais.bdstall.com/chatbot/`
- [ ] SSL setup completed (after DNS)
- [ ] HTTPS works: `curl https://ais.bdstall.com/chatbot/`
- [ ] Facebook webhook configured

---

## 🆘 Quick Help

**Services not starting?**
```bash
./monitor.sh       # Check status
tail -f logs/gunicorn.log  # See errors
./restart.sh       # Try restart
```

**Can't access from internet?**
```bash
curl ifconfig.me   # Your server IP
dig ais.bdstall.com  # Check DNS
# Make sure DNS points to your server IP
```

**SSL not working?**
```bash
# DNS must work first!
curl http://ais.bdstall.com/chatbot/
# Then run SSL setup
./setup_ssl.sh
```

---

## 📞 Support Resources

- Local test: http://localhost/chatbot/
- Public URL: https://ais.bdstall.com/chatbot/
- Logs: `/root/ai_chatbot/logs/`
- Nginx: `/var/log/nginx/`

**Remember**: Vast.ai containers may restart. Keep your project files backed up!
