# 📘 Facebook Page Chatbot Setup Guide

## ✅ Your Current Setup

You already have:
- ✅ Facebook Page Access Token configured in `.env`
- ✅ Webhook verification token set up
- ✅ Chatbot code with Facebook integration
- ✅ Human handoff system integrated

---

## 🚀 Quick Start - Run the Chatbot

### Step 1: Start the Server

**Option A: Using PowerShell Script (Recommended)**
```powershell
.\start.ps1
```

**Option B: Manual Start**
```powershell
python app_integrated.py
```

The server will start on **http://localhost:5000**

---

## 🔗 Step 2: Connect Facebook Page

You need to expose your local server to the internet so Facebook can send messages to your webhook.

### Option 1: Using ngrok (Easiest)

1. **Download ngrok**: https://ngrok.com/download

2. **Start ngrok**:
```powershell
ngrok http 5000
```

3. **Copy the URL**: You'll see something like:
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5000
```

Copy the **https://abc123.ngrok.io** URL.

### Option 2: Using localtunnel

```powershell
npx localtunnel --port 5000
```

### Option 3: Deploy to Cloud (Production)

See deployment options at the end of this guide.

---

## 📝 Step 3: Configure Facebook Webhook

1. **Go to Facebook Developers**: https://developers.facebook.com/apps

2. **Select Your App** (or create one)

3. **Add Messenger Product**:
   - Click "Add Product"
   - Select "Messenger"

4. **Setup Webhooks**:
   - Click "Setup Webhooks"
   - **Callback URL**: `https://your-ngrok-url.ngrok.io/webhook`
   - **Verify Token**: `my_verify_token_12345` (from your .env)
   - **Subscription Fields**: Check these:
     - ✅ messages
     - ✅ messaging_postbacks
     - ✅ messaging_optins
     - ✅ message_deliveries
   - Click "Verify and Save"

5. **Subscribe to Page**:
   - Select your Facebook Page
   - Click "Subscribe"

---

## 🧪 Step 4: Test Your Chatbot

### Test on Facebook Messenger:

1. Go to your Facebook Page
2. Click "Send Message" 
3. Try these test messages:

```
অর্ডার করবো কিভাবে?
ডেলিভারি চার্জ কত?
laptop cheap price
I want to talk to a human agent
```

---

## 🔍 Verify Setup

### Check Server Logs:

You should see:
```
✅ Webhook verified successfully
📨 Received message from 1234567890: অর্ডার করবো কিভাবে?
✅ Message sent successfully to 1234567890
```

### Check Webhook Status:

1. Go to Facebook App Dashboard
2. Messenger → Settings → Webhooks
3. Should show: ✅ "Subscribed"

---

## ⚙️ Your Configuration Files

### .env File (Already Set)
```env
PAGE_ACCESS_TOKEN=EAAa0kM09DkwBQ...  ✅ Configured
VERIFY_TOKEN=my_verify_token_12345   ✅ Configured
PORT=5000                            ✅ Configured
GROQ_API_KEY=gsk_...                 ✅ Configured
```

### app_integrated.py
- ✅ Webhook endpoints configured
- ✅ Message handling with BDStall system
- ✅ Human handoff integrated

---

## 🎯 Features Available

Your chatbot now supports:

### 1. **Automatic Responses**
```
User: "অর্ডার করবো কিভাবে?"
Bot: [Bengali FAQ Response]
```

### 2. **Product Search**
```
User: "laptop cheap price"
Bot: [Shows top 3 products with prices]
```

### 3. **Human Handoff**
```
User: "blah blah unclear"
Bot: "একজন প্রতিনিধি শীঘ্রই যোগাযোগ করবে..."
[Conversation switches to human mode]
```

### 4. **Bengali Support**
- All responses in Bengali
- Mixed language support (English + Bengali)
- Romanized Bengali detection

---

## 🔧 Troubleshooting

### Issue: Webhook Verification Failed

**Solution 1**: Check VERIFY_TOKEN matches
```powershell
# In .env file
VERIFY_TOKEN=my_verify_token_12345
```

**Solution 2**: Make sure server is running
```powershell
# Check if server is up
Invoke-WebRequest -Uri http://localhost:5000/health
```

**Solution 3**: Check ngrok is forwarding
```
Visit: http://127.0.0.1:4040
(ngrok dashboard)
```

### Issue: Bot Not Responding

**Solution 1**: Check logs
```powershell
# Look for errors in terminal where app is running
```

**Solution 2**: Verify Page Access Token
```powershell
# Test token
curl -X GET "https://graph.facebook.com/v18.0/me?access_token=YOUR_TOKEN"
```

**Solution 3**: Check webhook subscription
- Go to Facebook App → Messenger → Webhooks
- Make sure page is subscribed

### Issue: Messages Received but No Response

**Check these:**
1. ✅ Server logs show "Received message"
2. ✅ No errors in logs
3. ✅ PAGE_ACCESS_TOKEN is valid
4. ✅ Database file exists

**Test token validity:**
```powershell
# PowerShell
$token = "YOUR_PAGE_ACCESS_TOKEN"
Invoke-RestMethod -Uri "https://graph.facebook.com/v18.0/me?access_token=$token"
```

---

## 📊 Monitor Your Chatbot

### View Logs:
```powershell
# Logs are in terminal
# Look for these indicators:

✅ Good:
INFO:__main__:Webhook verified successfully
INFO:__main__:Message sent successfully

❌ Problems:
ERROR:__main__:Failed to send message
ERROR:__main__:PAGE_ACCESS_TOKEN not set
```

### Check Health:
```powershell
# Open browser
http://localhost:5000/health

# Or use PowerShell
Invoke-WebRequest -Uri http://localhost:5000/health
```

---

## 🌐 Deploy to Production

### Option 1: VPS (Recommended)

**Requirements:**
- Ubuntu/Debian VPS
- Public IP address
- Domain name (optional)

**Quick Deploy:**
```bash
# On your VPS
git clone <your-repo>
cd ai_chatbot
./deploy.sh
```

### Option 2: Heroku

```bash
# Install Heroku CLI
heroku login
heroku create your-chatbot-name
git push heroku main
```

Update Facebook webhook URL to:
`https://your-chatbot-name.herokuapp.com/webhook`

### Option 3: Railway

1. Go to: https://railway.app
2. Deploy from GitHub
3. Add environment variables
4. Get deployment URL
5. Update Facebook webhook

---

## 🔐 Security Checklist

Before going live:

- [ ] Change VERIFY_TOKEN to something secure
- [ ] Never commit .env file to GitHub
- [ ] Use HTTPS (not HTTP) for webhooks
- [ ] Rotate PAGE_ACCESS_TOKEN regularly
- [ ] Enable HTTPS in production
- [ ] Set up rate limiting

---

## 📞 Common Commands

### Start Server
```powershell
python app_integrated.py
```

### Start with ngrok
```powershell
# Terminal 1
python app_integrated.py

# Terminal 2
ngrok http 5000
```

### Test Locally
```powershell
# Test webhook verification
Invoke-WebRequest -Uri "http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token=my_verify_token_12345&hub.challenge=test123"

# Should return: test123
```

### Stop Server
```
Ctrl + C
```

---

## 📱 Testing Checklist

Test these scenarios on Messenger:

1. **Normal Queries:**
   - [ ] "অর্ডার করবো কিভাবে?"
   - [ ] "ডেলিভারি চার্জ কত?"
   - [ ] "গ্যারান্টি আছে?"

2. **Product Search:**
   - [ ] "laptop cheap price"
   - [ ] "wireless headphone"
   - [ ] "web cam"

3. **Human Handoff:**
   - [ ] Send unclear message 3 times
   - [ ] "I want to talk to human"
   - [ ] Check no AI response after handoff

4. **Mixed Language:**
   - [ ] "order kivabe korbo?"
   - [ ] "delivery koy din?"

---

## 🎓 Next Steps

After basic setup works:

1. **Train with More Data:**
   ```powershell
   python setup_and_train.py
   ```

2. **Add More FAQ to database.csv**

3. **Customize Handoff Messages** in `human_handoff_manager.py`

4. **Monitor Analytics:**
   - Track handoff rate
   - Common queries
   - Response times

5. **Deploy to Production** (see deployment section)

---

## 📚 Useful Links

- **Facebook Messenger Platform Docs**: https://developers.facebook.com/docs/messenger-platform
- **Webhook Testing**: https://webhook.site
- **ngrok Dashboard**: http://127.0.0.1:4040
- **Your App Dashboard**: https://developers.facebook.com/apps

---

## 🆘 Need Help?

### Log Files Location:
- Server logs: Terminal output
- Application logs: Check console

### Debug Mode:
```powershell
# Run with debug
$env:FLASK_DEBUG="1"
python app_integrated.py
```

### Test Webhook Manually:
```powershell
# Send test webhook POST
$body = @{
    object = "page"
    entry = @(
        @{
            messaging = @(
                @{
                    sender = @{ id = "123456" }
                    message = @{ text = "test message" }
                }
            )
        }
    )
} | ConvertTo-Json -Depth 10

Invoke-WebRequest -Uri http://localhost:5000/webhook -Method POST -Body $body -ContentType "application/json"
```

---

## ✅ Quick Reference

```powershell
# Start chatbot
python app_integrated.py

# Start ngrok
ngrok http 5000

# Test health
http://localhost:5000/health

# View logs
# Check terminal output

# Stop server
Ctrl + C
```

**Webhook URL Format:**
```
https://YOUR-NGROK-URL.ngrok.io/webhook
```

**Verify Token:**
```
my_verify_token_12345
```

---

## 🎉 You're All Set!

Your Facebook chatbot is configured with:
- ✅ Bengali FAQ responses
- ✅ Product search integration
- ✅ Human handoff system
- ✅ Mixed language support

**Test it now and start chatting with your customers!** 🚀
