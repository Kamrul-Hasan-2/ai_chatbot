# Mode Reset API - AI/HUMAN Mode Management

## 🔄 Reset Mode (Switch Back to AI)

**Endpoint:** `POST /mode/{user_id}/ai`

**Description:** Reset user from HUMAN mode back to AI mode

### cURL Example:
```bash
curl -X POST http://localhost:5000/mode/user123/ai
```

### PowerShell Example:
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/mode/user123/ai" -Method POST
```

### Response:
```json
{
  "user_id": "user123",
  "mode": "ai",
  "message": "User switched back to AI mode"
}
```

---

## 📋 All Mode Management Endpoints

### 1️⃣ Get Current Mode
**GET** `/mode/{user_id}`

```bash
curl http://localhost:5000/mode/user123
```

**Response:**
```json
{
  "user_id": "user123",
  "mode": "ai"
}
```

---

### 2️⃣ Switch to HUMAN Mode
**POST** `/mode/{user_id}/human`

```bash
curl -X POST http://localhost:5000/mode/user123/human
```

**Response:**
```json
{
  "user_id": "user123",
  "mode": "human",
  "message": "User switched to HUMAN mode"
}
```

---

### 3️⃣ Switch to AI Mode (Reset)
**POST** `/mode/{user_id}/ai`

```bash
curl -X POST http://localhost:5000/mode/user123/ai
```

**Response:**
```json
{
  "user_id": "user123",
  "mode": "ai",
  "message": "User switched back to AI mode"
}
```

---

## 💬 Chat Endpoint (Main)

**POST** `/chat`

**Request:**
```json
{
  "user_id": "user123",
  "message": "amake ekta 10k er modde laptop dekhan"
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "user123",
  "message": "amake ekta 10k er modde laptop dekhan",
  "response": "আপনার জন্য ১০,০০০ টাকার মধ্যে ল্যাপটপ...",
  "mode": "ai",
  "intent": "laptop_search",
  "products_found": 5,
  "products": [...]
}
```

---

## 🏥 Health Check

**GET** `/health`

```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "chatbot_loaded": true,
  "api_configured": true,
  "groq_available": true
}
```

---

## 🔥 Quick Test Examples

### Test 1: Check Current Mode
```bash
curl http://localhost:5000/mode/test_user
```

### Test 2: Reset to AI Mode
```bash
curl -X POST http://localhost:5000/mode/test_user/ai
```

### Test 3: Send Message
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"test_user\",\"message\":\"laptop dekhan\"}"
```

### Test 4: Switch to Human
```bash
curl -X POST http://localhost:5000/mode/test_user/human
```

---

## 📖 Full API Info

**GET** `/`

```bash
curl http://localhost:5000/
```

Shows all available endpoints and roadmap.

---

## 💡 Use Cases

### Scenario 1: User wants human agent, then comes back
```bash
# User requests human
curl -X POST http://localhost:5000/mode/user123/human

# Later, admin resets to AI
curl -X POST http://localhost:5000/mode/user123/ai
```

### Scenario 2: Check if user is in AI or HUMAN mode
```bash
curl http://localhost:5000/mode/user123
# Returns: {"mode": "ai"} or {"mode": "human"}
```

### Scenario 3: Force AI mode before testing
```bash
# Reset all test users to AI
curl -X POST http://localhost:5000/mode/test_user_1/ai
curl -X POST http://localhost:5000/mode/test_user_2/ai
curl -X POST http://localhost:5000/mode/test_user_3/ai
```

---

## 🌐 Server Info

- **URL:** http://localhost:5000
- **Status:** Running ✅
- **API Version:** 1.0
- **BDStall API:** Integrated ✅
- **Groq AI:** Available ✅

---

## 🛠️ PowerShell Functions

Add these to your PowerShell profile for quick access:

```powershell
# Reset user to AI mode
function Reset-ChatbotMode {
    param([string]$UserId = "web_user")
    Invoke-RestMethod -Uri "http://localhost:5000/mode/$UserId/ai" -Method POST
}

# Check user mode
function Get-ChatbotMode {
    param([string]$UserId = "web_user")
    Invoke-RestMethod -Uri "http://localhost:5000/mode/$UserId"
}

# Send test message
function Send-ChatMessage {
    param(
        [string]$Message,
        [string]$UserId = "web_user"
    )
    $body = @{
        user_id = $UserId
        message = $Message
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "http://localhost:5000/chat" -Method POST -Body $body -ContentType "application/json"
}
```

**Usage:**
```powershell
Reset-ChatbotMode -UserId "user123"
Get-ChatbotMode -UserId "user123"
Send-ChatMessage -Message "laptop dekhan" -UserId "user123"
```
