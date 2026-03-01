# 🚀 How to Run This Project - Complete Guide

## ✅ Prerequisites Checklist

Before running, make sure you have:
- [x] Python installed (3.8 or higher)
- [x] Facebook Page created
- [x] Facebook App created with Messenger product
- [x] PAGE_ACCESS_TOKEN in .env file
- [x] ngrok downloaded (for local testing)

---

## 📦 Step 1: Install Dependencies

Open PowerShell in this folder and run:

```powershell
pip install -r requirements.txt
```

Wait for all packages to install (may take 2-3 minutes).

---

## 🚀 Step 2: Run the Chatbot Server

### **Option A: Using Batch File (Easiest)**

Double-click this file:
```
START_FACEBOOK_BOT.bat
```

### **Option B: Using PowerShell**

```powershell
python app_integrated.py
```

### **Option C: Using app.py (Alternative)**

```powershell
python app.py
```

**You should see:**
```
✓ Bengali Database Handler initialized
✓ Human Handoff Manager initialized
✓ Groq 3-Step Search initialized
 * Running on http://127.0.0.1:5000
```

✅ **Server is running!** Keep this window open.

---

## 🌐 Step 3: Expose to Internet with ngrok

Facebook needs a public URL to send messages to your bot. Use ngrok for testing:

### **Download ngrok:**
https://ngrok.com/download

### **Run ngrok:**

Open a **NEW PowerShell window** and run:

```powershell
ngrok http 5000
```

**You'll see:**
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5000
```

**Copy the HTTPS URL:** `https://abc123.ngrok.io`

✅ **ngrok is running!** Keep this window open too.

---

## 🔗 Step 4: Connect to Facebook

### **4.1 Go to Facebook Developers**

Visit: https://developers.facebook.com/apps

### **4.2 Select Your App**

Click on your app (or create one if you haven't)

### **4.3 Add Messenger Product**

- Click "Add Product" → Select "Messenger"

### **4.4 Setup Webhooks**

Go to: **Messenger** → **Settings** → **Webhooks**

Click **"Setup Webhooks"** and fill in:

- **Callback URL**: `https://your-ngrok-url.ngrok.io/webhook`
  - Example: `https://abc123.ngrok.io/webhook`
  - ⚠️ Don't forget `/webhook` at the end!

- **Verify Token**: `my_verify_token_12345`
  - (This matches your .env file)

- **Subscription Fields**: Check these boxes:
  - ✅ messages
  - ✅ messaging_postbacks

Click **"Verify and Save"**

### **4.5 Subscribe to Your Page**

Under **"Select a Page"**:
- Choose your Facebook Page
- Click **"Subscribe"**

✅ **Webhook connected!**

---

## 🧪 Step 5: Test Your Bot

### **5.1 Send a Test Message**

1. Go to your Facebook Page
2. Click **"Send Message"**
3. Type: `অর্ডার করবো কিভাবে?`
4. Press Send

### **5.2 Check Server Logs**

In your server window, you should see:
```
INFO:__main__:Received message from 1234567890: অর্ডার করবো কিভাবে?
INFO:__main__:✅ Database match found!
INFO:__main__:Message sent successfully
```

### **5.3 Bot Should Respond**

Your bot replies with Bengali answer! 🎉

---

## 🎛️ Step 6: Manage Bot/Human Modes (Optional)

To control when AI responds vs when you respond manually:

### **Open a NEW PowerShell window:**

**Option A: Double-click**
```
MANAGE_MODES.bat
```

**Option B: Command line**
```powershell
python mode_manager.py
```

### **Commands:**

```bash
# View current modes
> status

# Switch user to bot mode (AI responds)
> bot 1234567890

# Switch user to human mode (you respond)
> human 1234567890

# Exit
> quit
```

---

## 📊 Complete Setup Summary

You should have **3 windows open**:

### **Window 1: Chatbot Server**
```powershell
python app_integrated.py
```
Status: ✅ Running on port 5000

### **Window 2: ngrok**
```powershell
ngrok http 5000
```
Status: ✅ Forwarding to localhost:5000

### **Window 3: Mode Manager (Optional)**
```powershell
python mode_manager.py
```
Status: ✅ Managing bot/human modes

---

## 🧪 Test Messages

Try sending these to your Facebook Page:

### **Bengali FAQ:**
```
অর্ডার করবো কিভাবে?
ডেলিভারি চার্জ কত?
গ্যারান্টি আছে?
কাস্টমার সার্ভিস নাম্বার?
```

### **Product Search:**
```
laptop cheap price
wireless headphone
web cam price
```

### **Mixed Language:**
```
order kivabe korbo?
delivery koto din lagbe?
```

### **Human Handoff:**
```
I want to talk to a human
blah blah unclear message
```

---

## 🔍 Verify Everything is Working

### **Check 1: Server Health**

Open browser: http://localhost:5000/health

Should show: Health check response

### **Check 2: ngrok Dashboard**

Open browser: http://127.0.0.1:4040

Should show: Incoming webhook requests

### **Check 3: Facebook Webhook Status**

Go to: Facebook App → Messenger → Webhooks

Should show: ✅ Green checkmark (Subscribed)

### **Check 4: Server Logs**

Look for these in your server window:
```
✅ Good signs:
✓ Webhook verified successfully
✓ Message sent successfully
📨 Received message from...

❌ Problems:
ERROR: Failed to send message
ERROR: PAGE_ACCESS_TOKEN not set
```

---

## ⚠️ Troubleshooting

### **Problem: "Webhook verification failed"**

**Solutions:**
1. Make sure server is running FIRST
2. Check VERIFY_TOKEN in .env: `my_verify_token_12345`
3. Restart server and try again
4. Make sure ngrok URL ends with `/webhook`

### **Problem: "Bot not responding"**

**Solutions:**
1. Check both windows are open (server + ngrok)
2. Look for errors in server window
3. Verify PAGE_ACCESS_TOKEN in .env is valid
4. Test token:
```powershell
$token = "YOUR_PAGE_ACCESS_TOKEN"
Invoke-RestMethod -Uri "https://graph.facebook.com/v18.0/me?access_token=$token"
```

### **Problem: "Import errors or dependencies missing"**

**Solution:**
```powershell
pip install --upgrade -r requirements.txt
```

### **Problem: "ngrok URL expired"**

**Solution:**
- Free ngrok URLs change every restart
- Get new URL from ngrok window
- Update Facebook webhook with new URL
- OR upgrade to ngrok Pro for fixed URL

### **Problem: "Port 5000 already in use"**

**Solution:**
```powershell
# Find and kill process using port 5000
Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process

# Or change port in .env file
PORT=5001
```

---

## 🛑 How to Stop

1. **Stop Server**: Press `Ctrl+C` in server window
2. **Stop ngrok**: Press `Ctrl+C` in ngrok window
3. **Stop Mode Manager**: Press `Ctrl+C` or type `quit`

---

## 🌐 Deploy for Production (24/7)

For permanent deployment without ngrok:

### **Option 1: ngrok Pro** ($10/month)
- Fixed URL that never changes
- No need to update webhook
- Simple and reliable

### **Option 2: VPS (DigitalOcean, Linode, etc.)**

```bash
# On your VPS
git clone <your-repo>
cd ai_chatbot
pip install -r requirements.txt
python app_integrated.py
```

Get domain name and point to VPS IP.

### **Option 3: Heroku (Free tier available)**

```bash
heroku create your-bot-name
git push heroku main
```

Webhook URL: `https://your-bot-name.herokuapp.com/webhook`

### **Option 4: Railway.app**

1. Connect GitHub repo
2. Deploy automatically
3. Get deployment URL
4. Update Facebook webhook

---

## 📋 Quick Reference Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Run chatbot server
python app_integrated.py

# Run ngrok (in new window)
ngrok http 5000

# Manage modes (in new window)
python mode_manager.py

# Test health
http://localhost:5000/health

# Stop server
Ctrl + C
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `app_integrated.py` | Main chatbot server |
| `mode_manager.py` | Control bot/human modes |
| `.env` | Facebook tokens & config |
| `database.csv` | Bengali FAQ database |
| `requirements.txt` | Python dependencies |

---

## 🆘 Still Having Issues?

### **View Detailed Logs:**
```powershell
# Run with debug mode
$env:FLASK_DEBUG="1"
python app_integrated.py
```

### **Test Webhook Manually:**
```powershell
# Test verification
Invoke-WebRequest "http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token=my_verify_token_12345&hub.challenge=test123"

# Should return: test123
```

### **Check Your Configuration:**
```powershell
# Make sure .env exists
Get-Content .env

# Check if tokens are set
$env:PAGE_ACCESS_TOKEN
```

---

## 📚 Documentation

- **[FACEBOOK_3_STEPS.md](FACEBOOK_3_STEPS.md)** - Quick 3-step setup
- **[TWO_MODES_SIMPLE.md](TWO_MODES_SIMPLE.md)** - Bot vs Human modes
- **[MODE_MANAGER_GUIDE.md](MODE_MANAGER_GUIDE.md)** - Detailed mode control
- **[HUMAN_HANDOFF_SYSTEM.md](HUMAN_HANDOFF_SYSTEM.md)** - Handoff system docs

---

## ✨ Summary

**To run this project:**

1. Install dependencies: `pip install -r requirements.txt`
2. Run server: `python app_integrated.py`
3. Run ngrok: `ngrok http 5000`
4. Setup Facebook webhook with ngrok URL
5. Test by messaging your Facebook Page

**You're done!** 🎉

Your chatbot is now:
- ✅ Responding in Bengali
- ✅ Searching BDStall products
- ✅ Handling human handoff
- ✅ Running on Facebook Messenger

Need help? Check the troubleshooting section above!
