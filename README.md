# 🤖 AI Chatbot System

A sophisticated multi-channel chatbot system with Facebook Messenger integration, RAG capabilities, and comprehensive NLP processing.

## ⚡ Quick Start

### 1️⃣ Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2️⃣ Run the Server

**Option A: Double-click (Windows)**
- Double-click `START_SERVER.bat`

**Option B: PowerShell**
```powershell
python run.py
```

**Option C: PowerShell Script**
```powershell
.\start_server.ps1
```

### 3️⃣ Test the API

Open your browser: **http://localhost:8000**

Or test with PowerShell:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

---

## 📋 System Requirements

- **Python:** 3.8 or higher
- **OS:** Windows, Linux, macOS
- **RAM:** 2GB minimum
- **Dependencies:** See `requirements.txt`

---

## 🎯 Key Features

- ✅ Multi-channel support (Web, Facebook Messenger, API)
- ✅ Bengali & English language support
- ✅ Intent detection and entity extraction
- ✅ Product search and order management
- ✅ RAG-enabled responses
- ✅ Context-aware conversations
- ✅ Human handoff system
- ✅ Analytics and monitoring

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [RUN_GUIDE.md](RUN_GUIDE.md) | Complete setup and run instructions |
| [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | Full API reference |
| [docs/API_QUICK_REFERENCE.md](docs/API_QUICK_REFERENCE.md) | Quick API cheatsheet |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Project organization |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment guide |
| [docs/WEBCHAT_API.md](docs/WEBCHAT_API.md) | Website webchat API — integration contract for the frontend team |

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web chat interface |
| `/chat` | POST | Send chat message |
| `/test` | POST | Test endpoint |
| `/health` | GET | Health check |
| `/analytics` | GET | System analytics |
| `/webhook` | POST | Facebook Messenger |
| `/api/webchat/message` | POST | Website webchat message (frontend team integration — see docs/WEBCHAT_API.md) |
| `/docs` | GET | Rendered website webchat API docs (browsable) |

**Full API docs:** [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

---

## 🌐 Facebook Messenger Setup

1. **Start the server:**
   ```powershell
   python run.py
   ```

2. **Expose with ngrok:**
   ```powershell
   ngrok http 8000
   ```

3. **Configure webhook:**
   - URL: `https://your-ngrok-url.ngrok.io/webhook`
   - Verify Token: `my_verify_token_12345`

**Detailed guide:** [docs/FACEBOOK_SETUP_GUIDE.md](docs/FACEBOOK_SETUP_GUIDE.md)

---

## 📁 Project Structure

```
ai_chatbot/
├── run.py                  # Main launcher
├── START_SERVER.bat        # Windows quick start
├── start_server.ps1        # PowerShell launcher
├── requirements.txt        # Dependencies
├── .env                    # Configuration
│
├── src/                    # Source code
│   ├── api/               # Flask application
│   ├── core/              # Core components
│   ├── models/            # AI models
│   ├── handlers/          # Message handlers
│   └── utils/             # Utilities
│
├── tests/                 # Test files
├── docs/                  # Documentation
├── config/                # Configuration files
├── scripts/               # Utility scripts
├── data/                  # Data files
└── static/                # Static assets
```

---

## 🧪 Testing

### Web Interface
```
http://localhost:8000/
```

### Health Check
```powershell
curl http://localhost:8000/health
```

### Send Test Message
```powershell
$body = @{message = "Show me laptops"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/test" -Method Post -Body $body -ContentType "application/json"
```

### Postman Collection
Import `docs/Postman_Collection.json` into Postman for complete API testing.

---

## ⚙️ Configuration

Edit `.env` file:

```env
# Facebook Messenger
PAGE_ACCESS_TOKEN=your_token
VERIFY_TOKEN=my_verify_token_12345

# Server
PORT=8000

# AI Model
GROQ_API_KEY=your_groq_key
MODEL_TYPE=groq
GROQ_MODEL=llama-3.1-8b-instant

# Features
ENABLE_RAG=true
RAG_TOP_K=3
```

---

## 🐛 Troubleshooting

### Server won't start
```powershell
# Check dependencies
pip install -r requirements.txt

# Check .env file exists
dir .env

# Check port availability
netstat -an | findstr :8000
```

### Import errors
```powershell
# Run from root directory
cd C:\Users\BLG\Desktop\ai_chatbot
python run.py
```

### Module not found
```powershell
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Full troubleshooting:** [RUN_GUIDE.md](RUN_GUIDE.md)

---

## 🚀 Deployment

### Local Development
```powershell
python run.py
```

### Production (Linux)
```bash
# Using systemd
sudo systemctl start chatbot

# Using Docker
docker-compose up -d
```

**Deployment guide:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 📊 Monitoring

- **Health Status:** http://localhost:8000/health
- **System Health:** http://localhost:8000/system_health
- **Analytics:** http://localhost:8000/analytics
- **Logs:** `logs/` directory

---

## 🤝 Support

- 📖 **Documentation:** Check the `docs/` folder
- 🐛 **Issues:** Review logs in `logs/` directory
- 💬 **Questions:** See troubleshooting in [RUN_GUIDE.md](RUN_GUIDE.md)

---

## 📝 License

See LICENSE file for details.

---

## 🎉 Getting Started

1. **Clone/Download** the project
2. **Install dependencies:** `pip install -r requirements.txt`
3. **Run:** `python run.py` or double-click `START_SERVER.bat`
4. **Open:** http://localhost:8000
5. **Test:** Send a message and enjoy! 🚀

---

**Version:** 1.0  
**Last Updated:** March 1, 2026
