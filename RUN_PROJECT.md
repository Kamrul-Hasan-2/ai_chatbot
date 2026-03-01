# ⚡ RUN PROJECT - 3 Minutes

## 🏃 Quick Steps

### 1️⃣ Install Dependencies
```powershell
pip install -r requirements.txt
```
⏱️ Takes 1-2 minutes

---

### 2️⃣ Start Server
```powershell
python app_integrated.py
```
✅ You'll see: `Running on http://127.0.0.1:5000`

---

### 3️⃣ Start ngrok
**New window:**
```powershell
ngrok http 5000
```
📋 Copy the HTTPS URL (like `https://abc123.ngrok.io`)

---

### 4️⃣ Setup Facebook
1. Go to: https://developers.facebook.com/apps
2. Your App → **Messenger** → **Webhooks**
3. Callback URL: `https://abc123.ngrok.io/webhook`
4. Verify Token: `my_verify_token_12345`
5. Subscribe your page

---

### 5️⃣ Test!
Message your page:
```
অর্ডার করবো কিভাবে?
```

🎉 **Bot responds!**

---

## 🛠️ Troubleshooting

**Webhook failed?**
→ Start server FIRST, then setup webhook

**Bot not responding?**
→ Keep both windows open (server + ngrok)

**Errors?**
→ `pip install --upgrade -r requirements.txt`

---

## 📖 Full Guide

See **[HOW_TO_RUN.md](HOW_TO_RUN.md)** for detailed instructions.

---

## 🎛️ Manage Modes (Optional)

**New window:**
```powershell
python mode_manager.py
```

Commands:
- `status` - See modes
- `bot <id>` - AI responds
- `human <id>` - You respond
- `quit` - Exit

---

## 🔌 Windows You Need

Keep these open:

**Window 1: Server**
```powershell
python app_integrated.py
```

**Window 2: ngrok**
```powershell
ngrok http 5000
```

**Window 3: Mode Manager (Optional)**
```powershell
python mode_manager.py
```

---

## 🛑 Stop

Press `Ctrl+C` in each window

---

**That's it!** Your Facebook chatbot is running! 🚀
