# 🎯 Facebook Chatbot - 3 Simple Steps

## ⚡ Quick Setup (5 minutes)

### Step 1: Start Chatbot Server ✅

**Double-click:** `START_FACEBOOK_BOT.bat`

OR

**PowerShell:** `.\RUN_FACEBOOK_BOT.ps1`

OR

**Manual:**
```powershell
python app_integrated.py
```

✅ **You should see:** "Server Running on http://127.0.0.1:5000"

---

### Step 2: Expose to Internet ✅

**Install ngrok:** https://ngrok.com/download (Free!)

**Open NEW terminal and run:**
```powershell
ngrok http 5000
```

**Copy the HTTPS URL** (looks like: `https://abc123.ngrok.io`)

---

### Step 3: Connect Facebook ✅

**1. Go to:** https://developers.facebook.com/apps

**2. Setup Webhook:**
   - Messenger → Settings → Webhooks
   - Click "Setup Webhooks"
   - Callback URL: `https://abc123.ngrok.io/webhook` ← Your ngrok URL + /webhook
   - Verify Token: `my_verify_token_12345`
   - Check: ✅ messages
   - Click "Verify and Save"

**3. Subscribe Page:**
   - Select your Facebook Page
   - Click "Subscribe"

---

## 🎉 Done! Test Your Bot

**Go to your Facebook Page → Send Message**

Try:
```
অর্ডার করবো কিভাবে?
```

Bot responds in Bengali! ✅

---

## 🔍 Verify It's Working

**Check 1:** Server window shows:
```
✓ Webhook verified successfully
📨 Received message from [user]: অর্ডার করবো কিভাবে?
✅ Message sent successfully
```

**Check 2:** Open in browser:
```
http://localhost:5000/health
```
Should show: "OK" or health status

**Check 3:** ngrok dashboard:
```
http://127.0.0.1:4040
```
Shows incoming webhook requests

---

## ⚠️ Common Issues

### Issue: "Webhook verification failed"

**Fix:**
1. Make sure server is running FIRST
2. Then setup webhook
3. Check VERIFY_TOKEN matches in .env file

### Issue: "Bot not responding"

**Fix:**
1. Check both windows are open (server + ngrok)
2. Look for errors in server window
3. Verify PAGE_ACCESS_TOKEN in .env is correct

### Issue: "ngrok URL expired"

**Fix:**
- Free ngrok URLs change every restart
- Update Facebook webhook with new URL each time
- OR upgrade to ngrok Pro for fixed URL

---

## 🎮 Try These Commands

**Bengali FAQ:**
```
অর্ডার করবো কিভাবে?
ডেলিভারি চার্জ কত?
গ্যারান্টি আছে?
কাস্টমার সার্ভিস নাম্বার?
```

**Product Search:**
```
laptop cheap price
wireless headphone
web cam
```

**Human Handoff:**
```
blah blah unclear message
[Send 3 times to trigger handoff]

OR

I want to talk to a human agent
```

---

## 📊 Your Bot Features

✅ **Automatic Bengali Responses**
- Answers common questions instantly
- Database of pre-configured Q&As

✅ **Smart Product Search**
- Searches BDStall.com API
- Shows top 3 results with prices
- Bengali response formatting

✅ **Human Handoff**
- AI detects when it can't understand
- Automatically switches to human mode
- Provides contact information

✅ **Mixed Language**
- Bengali + English
- Romanized Bengali (e.g., "kivabe order korbo")

---

## 🌐 Make It Permanent

**Currently:** ngrok URL changes each restart

**For 24/7 chatbot:**

**Option 1: ngrok Pro** ($10/month)
- Fixed URL forever
- No need to update Facebook webhook

**Option 2: Deploy to VPS**
- Rent server ($5-10/month)
- Get fixed IP/domain
- See DEPLOYMENT.md

**Option 3: Heroku/Railway** (Free tier available)
- Cloud hosting
- Fixed URL
- Auto-deploys from GitHub

---

## 📋 Checklist for Going Live

- [ ] Server starts without errors
- [ ] ngrok is running and forwarding
- [ ] Facebook webhook verified
- [ ] Test messages work
- [ ] Bot responds in Bengali
- [ ] Human handoff works
- [ ] .env file is secure (not shared)

---

## 🆘 Need Help?

**View Logs:**
- Check the server terminal window
- Look for red ERROR messages

**Test Webhook:**
```powershell
# Test GET (verification)
Invoke-WebRequest "http://localhost:5000/webhook?hub.mode=subscribe&hub.verify_token=my_verify_token_12345&hub.challenge=test"

# Should return: test
```

**Check Facebook App:**
- Go to App Dashboard → Messenger
- Check webhook status: Should be green ✅

**Still stuck?**
- See FACEBOOK_SETUP_GUIDE.md for detailed troubleshooting
- Check .env file configuration
- Verify Python and dependencies installed

---

## 📞 Contact Info in Bot

When users trigger handoff, they get:
```
Phone: 01612378255
Hours: 10 AM - 6 PM
```

Update this in: `human_handoff_manager.py`

---

## 🎓 Resources

- **Detailed Guide**: FACEBOOK_SETUP_GUIDE.md
- **Handoff System**: HUMAN_HANDOFF_SYSTEM.md
- **Deployment**: DEPLOYMENT.md
- **ngrok**: https://ngrok.com
- **Facebook Docs**: https://developers.facebook.com/docs/messenger-platform

---

## ✨ Pro Tips

1. **Test locally first** before going live
2. **Monitor logs** for errors
3. **Update database.csv** with more Q&As
4. **Train with real conversations** to improve responses
5. **Set up analytics** to track usage
6. **Backup .env file** securely

---

## 🚀 You're Ready!

Your Facebook chatbot is configured and ready to handle:
- Bengali customer questions
- Product searches  
- Human handoffs when needed
- 24/7 automated support

**Start now:** Double-click `START_FACEBOOK_BOT.bat` 🎉
