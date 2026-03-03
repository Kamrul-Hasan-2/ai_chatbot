# 🚀 Simple Chatbot - Your Roadmap

## Quick Start (1 Minute)

```powershell
# 1. Run the server
python run.py

# 2. Test it
python test_roadmap.py
```

That's it! 🎉

---

## 📋 Your Roadmap (Implemented)

✅ **Step 1:** Message → Groq API (Intent Detection)  
✅ **Step 2:** Intent → Search API (Find products)  
✅ **Step 3:** Results → Database Format  
✅ **Step 4:** Database → AI (Final response)  
✅ **Step 5:** Track Mode: AI or HUMAN  
✅ **Step 6:** API JSON shows mode  

---

## 🧪 Quick Test

```powershell
# Start server in one terminal
python run.py

# Test in another terminal
$body = @{
    user_id = "test123"
    message = "amake ekta 10k er modde laptop dekhan"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/chat" -Method Post -Body $body -ContentType "application/json"
```

**Response:**
```json
{
  "success": true,
  "mode": "ai",        ← Always shows: "ai" or "human"
  "response": "...",
  "products_found": 3,
  "intent": "laptop_search"
}
```

---

## 📖 Documentation

- **Full Guide:** [ROADMAP_IMPLEMENTATION.md](ROADMAP_IMPLEMENTATION.md)
- **API Docs:** http://localhost:5000/ (when running)
- **Code:** 
  - `src/core/simple_chatbot_flow.py` - Main logic
  - `src/api/app_simple.py` - API endpoints

---

## 🎯 Key Features

### Mode Tracking
Every response shows current mode:
- `"mode": "ai"` - Bot is responding
- `"mode": "human"` - Human agent needed

### Auto Switch to Human
System automatically switches to HUMAN mode when:
- Can't understand message
- No products found
- AI fails
- Error occurs

### Manual Control
```powershell
# Check mode
GET /mode/user123

# Force human mode
POST /mode/user123/human

# Back to AI mode
POST /mode/user123/ai
```

---

## 🔍 Example Flow

```
User: "amake ekta 10k er modde laptop dekhan"
   ↓
Step 1: Groq detects intent = "laptop_search"
        Keywords = "laptop 10000 taka"
   ↓
Step 2: Search database for laptops under 10000
   ↓
Step 3: Format: "পণ্য তালিকা: 1. HP... 2. Lenovo..."
   ↓
Step 4: AI creates friendly Bengali response
   ↓
Step 5: Mode = "ai" (success)
   ↓
Step 6: Return JSON with mode
```

---

## ⚙️ Configuration

Edit `.env`:
```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant
PORT=5000
```

---

## 🛠️ Troubleshooting

**Server won't start?**
```powershell
pip install -r requirements.txt
```

**Groq not working?**
- Check GROQ_API_KEY in .env
- Make sure `groq` package is installed

**Database empty?**
- Check `data/database.csv` exists
- Add your products there

---

## 📚 Project Structure

```
ai_chatbot/
├── run.py                          ← Start here
├── test_roadmap.py                 ← Test script
├── ROADMAP_IMPLEMENTATION.md       ← Full docs
├── .env                            ← Config
│
├── src/
│   ├── core/
│   │   └── simple_chatbot_flow.py  ← Main logic
│   └── api/
│       └── app_simple.py           ← API
│
└── data/
    └── database.csv                ← Products
```

---

## 🎉 Done!

Your chatbot:
- ✅ Follows your exact roadmap
- ✅ Tracks AI/HUMAN mode
- ✅ Shows mode in every JSON response
- ✅ Auto-switches to human on errors
- ✅ Simple, clean code

**Start now:**
```powershell
python run.py
```

---

**Need help?** Read [ROADMAP_IMPLEMENTATION.md](ROADMAP_IMPLEMENTATION.md) for complete guide.
