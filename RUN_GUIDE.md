# 🚀 How to Run This Project

## Quick Start (5 Minutes)

### Step 1: Install Dependencies
```powershell
cd C:\Users\BLG\Desktop\ai_chatbot
pip install -r requirements.txt
```

### Step 2: Configure Environment
Your `.env` file is already configured with:
- ✅ Groq API Key
- ✅ Facebook tokens
- ✅ Model settings

### Step 3: Run the Application

**⚠️ IMPORTANT:** Due to the new project structure, you need to run from the root directory:

```powershell
# From the root directory (ai_chatbot/)
cd C:\Users\BLG\Desktop\ai_chatbot

# Add src to Python path and run
$env:PYTHONPATH="C:\Users\BLG\Desktop\ai_chatbot"; python src/api/app.py
```

**OR** create a simple launcher script (recommended):

```powershell
# Create run.py in root directory
python run.py
```

---

## 📝 Create run.py (Recommended)

I'll create a `run.py` file in the root that handles the imports correctly:

```python
# run.py - Place this in the root directory
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Now run the app
from api.app import app, initialize_chatbot
import os

if __name__ == '__main__':
    # Initialize chatbot
    initialize_chatbot()
    
    # Run Flask app
    port = int(os.getenv('PORT', 8000))
    print(f"\n🚀 Server starting on http://localhost:{port}")
    print(f"📱 Web chat: http://localhost:{port}/")
    print(f"🔧 Health check: http://localhost:{port}/health")
    print(f"📊 Analytics: http://localhost:{port}/analytics\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
```

---

## 🎯 Testing the API

### Option 1: Web Browser
```
http://localhost:8000/
```

### Option 2: PowerShell (Test endpoint)
```powershell
$body = @{
    user_id = "test_user"
    message = "Show me laptops"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/test" -Method Post -Body $body -ContentType "application/json"
```

### Option 3: cURL (if installed)
```bash
curl -X POST http://localhost:8000/test -H "Content-Type: application/json" -d "{\"message\": \"Hello\"}"
```

### Option 4: Postman
Import the collection from: `docs/Postman_Collection.json`

---

## 🌐 Facebook Messenger Setup (Optional)

If you want to connect to Facebook Messenger:

### 1. Install ngrok
Download from: https://ngrok.com/download

### 2. Run ngrok
```powershell
# In a new terminal
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 3. Configure Facebook Webhook
1. Go to https://developers.facebook.com/apps
2. Select your app → Messenger → Settings
3. Webhook URL: `https://abc123.ngrok.io/webhook`
4. Verify Token: `my_verify_token_12345` (from your .env)
5. Subscribe to: `messages`, `messaging_postbacks`

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'bdstall_chatbot_system'"

**Solution:** The imports need to be updated for the new structure. Run using:
```powershell
$env:PYTHONPATH="C:\Users\BLG\Desktop\ai_chatbot"; python src/api/app.py
```

Or use the `run.py` launcher script I'll create for you.

### Error: "No module named 'groq'"

**Solution:** Install dependencies:
```powershell
pip install -r requirements.txt
```

### Error: "PORT already in use"

**Solution:** Change port in `.env`:
```
PORT=8080
```

### Server starts but no response

**Solution:** Check if all components initialized:
```powershell
curl http://localhost:8000/health
```

---

## 📂 Project Structure

Your app runs from this structure:
```
ai_chatbot/
├── run.py              ← Run this file
├── .env                ← Your config
├── requirements.txt    ← Dependencies
├── src/
│   ├── api/
│   │   └── app.py     ← Main application
│   ├── core/          ← Core components
│   ├── models/        ← AI models
│   ├── handlers/      ← Handlers
│   └── utils/         ← Utilities
└── data/              ← Database files
```

---

## ✅ Verify Everything Works

After starting the server, test these endpoints:

1. **Health Check:**
   ```
   http://localhost:8000/health
   ```
   Should return: `{"status": "healthy"}`

2. **Web Interface:**
   ```
   http://localhost:8000/
   ```
   Should show chat interface

3. **Test Message:**
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/test" -Method Post -Body '{"message":"test"}' -ContentType "application/json"
   ```

---

## 🎉 Success Indicators

When running correctly, you'll see:
```
🤖 BDStall AI Chatbot Server
============================================================
✓ Channel Adapter - Multi-channel support
✓ Intent & Entity Detection - NLP processing
✓ Context Router - Conversation management
✓ Business Rule Engine - Logic processing
✓ Decision Router - Strategy selection
✓ Response Composer - Final response generation
============================================================
🚀 Server starting on http://localhost:8000
📱 Web chat: http://localhost:8000/
🔧 Health check: http://localhost:8000/health
```

---

## 📚 Additional Documentation

- **API Documentation:** [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)
- **API Quick Reference:** [docs/API_QUICK_REFERENCE.md](docs/API_QUICK_REFERENCE.md)
- **Project Structure:** [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- **Deployment Guide:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 🆘 Need Help?

1. Check logs in `logs/` directory
2. Test health: `http://localhost:8000/health`
3. Review API docs: `docs/API_DOCUMENTATION.md`

---

**Last Updated:** March 1, 2026
