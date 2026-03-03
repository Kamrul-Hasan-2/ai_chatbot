# Cloudflare Setup Guide

## Your Current Status

✅ **DNS Configured**: ais.bdstall.com → Cloudflare Proxy  
⏳ **Need to Setup**: Connect Cloudflare to your Vast.ai server

## 🚀 Quick Setup (3 Steps)

### Step 1: Check Your Server IP

On your Vast.ai server:
```bash
curl ifconfig.me
```
Note this IP (e.g., 123.456.789.0)

### Step 2: Configure Cloudflare

Go to Cloudflare Dashboard → DNS for bdstall.com:

1. **Check/Update A Record:**
   - Type: `A`
   - Name: `ais`
   - IPv4 address: `[Your Vast.ai IP from Step 1]`
   - Proxy status: ☁️ **Proxied** (orange cloud)
   - TTL: Auto

2. **Configure SSL/TLS:**
   - Go to SSL/TLS → Overview
   - Set to **"Flexible"** 
   - (Cloudflare uses HTTPS, your server uses HTTP)

3. **Optional - Speed Rules:**
   - Go to Speed → Optimization
   - Enable "Auto Minify" for JS, CSS, HTML

### Step 3: Start Your Server

On Vast.ai:
```bash
cd /root/ai_chatbot
chmod +x *.sh
./deploy_vastai.sh
```

Then test:
```bash
./check_status.sh
```

## 📋 How It Works

```
User Browser
    ↓ HTTPS
Cloudflare (SSL termination)
    ↓ HTTP
Your Vast.ai Server (Port 80)
    ↓
Nginx (Reverse Proxy)
    ↓
Gunicorn (Port 5000)
    ↓
Your Chatbot App
```

## ✅ Verify Setup

### On Your Server:
```bash
# Check services
./check_status.sh

# Should show:
# ✓ Gunicorn Running
# ✓ Nginx Running
# ✓ Port 5000 Open
# ✓ Local endpoint responding
```

### In Your Browser:
Open: **https://ais.bdstall.com/chatbot/**

You should see your chatbot interface!

## 🔧 Troubleshooting

### "Connection Failed" or "Unable to Connect"

**Problem**: Cloudflare can't reach your server

**Solutions**:

1. **Check Server IP in Cloudflare:**
   ```bash
   # On your server
   curl ifconfig.me
   ```
   Make sure this matches the IP in Cloudflare DNS

2. **Verify Services Running:**
   ```bash
   ./check_status.sh
   ```
   All should show ✓

3. **Check Firewall:**
   ```bash
   # Ensure port 80 is open
   ufw status
   ufw allow 80/tcp
   ufw allow 443/tcp
   ```

4. **Test Local Access:**
   ```bash
   curl http://localhost/chatbot/
   ```
   Should return HTML

### "Too Many Redirects"

**Problem**: SSL/TLS mode incorrect

**Solution**: In Cloudflare → SSL/TLS → Set to **"Flexible"**

### "502 Bad Gateway"

**Problem**: Nginx can't reach your app

**Solution**:
```bash
# Check if Gunicorn is running
./monitor.sh

# Restart if needed
./restart.sh
```

### "404 Not Found"

**Problem**: Nginx config issue

**Solution**:
```bash
# Check nginx config
nginx -t

# View logs
tail -f /var/log/nginx/chatbot_error.log

# Restart nginx
pkill nginx && nginx
```

## 🎯 Expected Behavior

Once setup correctly:

1. ✅ https://ais.bdstall.com/chatbot/ → Chat interface
2. ✅ https://ais.bdstall.com/chatbot/webhook → Facebook webhook
3. ✅ https://ais.bdstall.com/chatbot/test → API test endpoint

## 📊 Monitoring

Check your setup anytime:
```bash
./check_status.sh
./monitor.sh
tail -f logs/error.log
```

## 🔐 Security Notes

With Cloudflare:
- ✅ DDoS protection (automatic)
- ✅ SSL/HTTPS (handled by Cloudflare)
- ✅ CDN caching
- ✅ Hide your real IP

Your server runs HTTP internally - Cloudflare adds HTTPS.

## 📱 Facebook Messenger Webhook

After everything works, configure webhook:

1. Go to Facebook Developer Console
2. Webhook URL: `https://ais.bdstall.com/chatbot/webhook`
3. Verify Token: `my_verify_token_12345`
4. Subscribe to: messages, messaging_postbacks

## 🆘 Still Not Working?

Run diagnostic:
```bash
./check_status.sh
```

Send me the output and I'll help troubleshoot!

---

**Quick Command Reference:**
```bash
./deploy_vastai.sh    # Initial setup
./check_status.sh     # Check everything
./monitor.sh          # View status
./restart.sh          # Restart services
tail -f logs/error.log # View logs
```
