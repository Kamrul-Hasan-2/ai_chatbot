# 🚀 Quick Start - Run Facebook Chatbot (Windows)

## Step 1: Start the Chatbot Server

Open PowerShell in this folder and run:

```powershell
python app_integrated.py
```

You should see:
```
🚀 BDStall Chatbot System fully initialized
✓ Bengali Database Handler initialized
✓ Human Handoff Manager initialized
 * Running on http://127.0.0.1:5000
```

✅ **Server is now running!** Keep this window open.

---

## Step 2: Expose to Internet with ngrok

**Download ngrok:** https://ngrok.com/download

Open a **NEW PowerShell window** and run:

```powershell
ngrok http 5000
```

You'll see:
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5000
```

**Copy this URL:** `https://abc123.ngrok.io`

---

## Step 3: Setup Facebook Webhook

1. Go to: https://developers.facebook.com/apps
2. Select your app → **Messenger** → **Settings**
3. Click **"Setup Webhooks"**

Fill in:
- **Callback URL**: `https://abc123.ngrok.io/webhook` (paste your ngrok URL + /webhook)
- **Verify Token**: `my_verify_token_12345`
- **Subscription Fields**: Check ✅ messages, messaging_postbacks
- Click **"Verify and Save"**

4. Under **"Select a Page"**, choose your page and click **Subscribe**

---

## Step 4: Test Your Bot!

1. Go to your **Facebook Page**
2. Click **"Send Message"**
3. Try these:

```
অর্ডার করবো কিভাবে?
laptop cheap price
I want to talk to a human
```

---

## ✅ You're Done!

Your bot is now live on Facebook Messenger! 🎉

### Keep Both Windows Open:
- **Window 1**: Running `python app_integrated.py`
- **Window 2**: Running `ngrok http 5000`

### To Stop:
Press `Ctrl + C` in both windows

---

## 🔍 Troubleshooting

**Bot not responding?**

1. Check server window for errors
2. Make sure both windows are still running
3. Verify URL: Open `https://your-ngrok-url.ngrok.io/health` in browser

**Webhook verification failed?**

1. Make sure server is running BEFORE setting up webhook
2. Check VERIFY_TOKEN in .env matches what you entered
3. ngrok URL must have `/webhook` at the end

---

## 📝 Important Notes

- **ngrok free URL changes** every restart - update Facebook webhook each time
- **For permanent URL**: Upgrade ngrok or deploy to cloud
- **Keep .env file safe** - never share your tokens!

---

## 🌐 Deploy Permanently

For 24/7 availability without ngrok:

**Option 1: Get ngrok Pro** ($10/month)
- Fixed URL that never changes
- No need to update Facebook webhook

**Option 2: Deploy to VPS**
```bash
# See DEPLOYMENT.md for full guide
```

**Option 3: Deploy to Heroku** (Free tier available)
```bash
heroku create your-bot-name
git push heroku main
```
Then update Facebook webhook to: `https://your-bot-name.herokuapp.com/webhook`

---

## 📞 Quick Reference

**Start Server:**
```powershell
python app_integrated.py
```

**Start ngrok:**
```powershell
ngrok http 5000
```

**Webhook URL Format:**
```
https://YOUR-NGROK-ID.ngrok.io/webhook
```

**Verify Token:**
```
my_verify_token_12345
```

**Check Health:**
```
http://localhost:5000/health
```

Need more help? See **FACEBOOK_SETUP_GUIDE.md** for detailed instructions!
