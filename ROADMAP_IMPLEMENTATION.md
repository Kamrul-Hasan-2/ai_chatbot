# 🚀 Your Chatbot Roadmap - Implementation Guide

## Overview

This is the **SIMPLE** implementation following your exact roadmap. All complex code is removed - this is clean and easy to understand.

---

## 📋 Your Roadmap (Implemented)

### **Step 1: Message → Groq API**
✅ **Any message goes to Groq API first**
- User sends: "amake ekta 10k er modde laptop dekhan"
- Groq detects intent: `laptop_search`
- Groq extracts keywords: `laptop 10000 taka`

### **Step 2: Intent → Search API**
✅ **Search database with keywords**
- Keywords: "laptop 10000 taka"
- Search database for matching products
- Filter by price if specified (10k = 10000 taka)

### **Step 3: Results → Database Format**
✅ **Format results as database message**
```
পণ্য তালিকা:

1. HP Pavilion 15
   উত্তর: ৫৫,০০০ টাকা
   বিভাগ: Laptop

2. Lenovo IdeaPad
   উত্তর: ৫২,০০০ টাকা
   বিভাগ: Laptop
```

### **Step 4: Database → AI**
✅ **AI formats the final response**
- Takes: Database message + Original question
- Returns: Friendly Bengali response
- Groq AI creates natural conversation

### **Step 5: Track AI/HUMAN Mode**
✅ **System tracks mode for each user**
- **AI Mode**: Bot responds automatically
- **HUMAN Mode**: Bot says "একজন প্রতিনিধি যোগাযোগ করবে"

**When to switch to HUMAN:**
- Groq fails (can't understand)
- No products found
- AI formatting fails
- Too many failures

### **Step 6: API JSON Shows Mode**
✅ **Every response shows current mode**
```json
{
  "success": true,
  "mode": "ai",     ← Always shows: "ai" or "human"
  "response": "...",
  "products_found": 3,
  "intent": "laptop_search"
}
```

---

## 🎯 API Endpoints

### **1. POST /chat** (Main endpoint)

**Request:**
```json
{
  "user_id": "user123",
  "message": "amake ekta 10k er modde laptop dekhan"
}
```

**Response (AI Mode):**
```json
{
  "success": true,
  "user_id": "user123",
  "message": "amake ekta 10k er modde laptop dekhan",
  "response": "আপনার জন্য ১০,০০০ টাকার মধ্যে কিছু ভাল ল্যাপটপ রয়েছে:\n\n1. HP Pavilion 15 - ৫৫,০০০ টাকা\n2. Lenovo IdeaPad - ৫২,০০০ টাকা\n\nকোনটি সম্পর্কে জানতে চান?",
  "mode": "ai",
  "intent": "laptop_search",
  "search_keywords": "laptop 10000 taka",
  "products_found": 2,
  "products": [
    {
      "question": "HP Pavilion 15 কত টাকা?",
      "answer": "৫৫,০০০ টাকা",
      "category": "Laptop"
    }
  ],
  "processing_time_seconds": 1.23,
  "timestamp": "2026-03-01T15:30:00"
}
```

**Response (HUMAN Mode):**
```json
{
  "success": false,
  "user_id": "user123",
  "message": "something unclear",
  "response": "দুঃখিত, আমি বুঝতে পারছি না। একজন প্রতিনিধি শীঘ্রই যোগাযোগ করবে।",
  "mode": "human",     ← Mode switched to HUMAN
  "intent": null,
  "products_found": 0,
  "products": null
}
```

---

### **2. GET /health**

Check if system is running.

**Response:**
```json
{
  "status": "healthy",
  "chatbot_loaded": true,
  "database_products": 150,
  "groq_available": true
}
```

---

### **3. GET /mode/:user_id**

Get current mode for a user.

**Example:** `GET /mode/user123`

**Response:**
```json
{
  "user_id": "user123",
  "mode": "ai"
}
```

---

### **4. POST /mode/:user_id/human**

Manually switch user to HUMAN mode.

**Example:** `POST /mode/user123/human`

**Response:**
```json
{
  "user_id": "user123",
  "mode": "human",
  "message": "User switched to HUMAN mode"
}
```

---

### **5. POST /mode/:user_id/ai**

Switch user back to AI mode.

**Example:** `POST /mode/user123/ai`

**Response:**
```json
{
  "user_id": "user123",
  "mode": "ai",
  "message": "User switched back to AI mode"
}
```

---

## 🚀 How to Run

### **Method 1: Simple Start**
```powershell
cd C:\Users\BLG\Desktop\ai_chatbot
python run.py
```

### **Method 2: Direct**
```powershell
python src/api/app_simple.py
```

---

## 🧪 Test Examples

### **Example 1: Laptop Search**

**Request:**
```powershell
$body = @{
    user_id = "test_user"
    message = "amake ekta 10k er modde laptop dekhan"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/chat" -Method Post -Body $body -ContentType "application/json"
```

**Expected Flow:**
1. ✅ Message → Groq: Intent = `laptop_search`, Keywords = `laptop 10000`
2. ✅ Search database for laptops under 10000
3. ✅ Format results as database message
4. ✅ AI creates friendly response
5. ✅ Return with `mode: "ai"`

---

### **Example 2: Unclear Message**

**Request:**
```powershell
$body = @{
    user_id = "test_user"
    message = "xyz abc random stuff"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/chat" -Method Post -Body $body -ContentType "application/json"
```

**Expected:**
- Groq tries to understand
- If fails or no products → Switch to `mode: "human"`
- Response: "একজন প্রতিনিধি যোগাযোগ করবে"

---

### **Example 3: Check Mode**

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/mode/test_user" -Method Get
```

**Response:**
```json
{
  "user_id": "test_user",
  "mode": "ai"
}
```

---

### **Example 4: Force Human Mode**

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/mode/test_user/human" -Method Post
```

Now all responses for `test_user` will have `mode: "human"`

---

## 📊 Mode Logic

### **AI Mode (Default)**
- User sends message
- System processes through full roadmap
- Returns AI response
- Mode stays `"ai"`

### **Switch to HUMAN Mode When:**
1. **Groq fails** - Can't detect intent
2. **No products found** - Database search returns 0 results
3. **AI fails** - Can't format response
4. **Error occurs** - System error

### **HUMAN Mode**
- User in human mode
- System shows: "প্রতিনিধি যোগাযোগ করবে"
- Mode shows `"human"`
- Can manually switch back to AI

---

## 📁 Files Created

1. **`src/core/simple_chatbot_flow.py`** - Main roadmap implementation
2. **`src/api/app_simple.py`** - Simple Flask API
3. **`run.py`** - Updated to use simple version
4. **This file** - Documentation

---

## 🎯 Key Features

✅ **Clean Code**: Easy to read and understand
✅ **Your Roadmap**: Exactly follows your 6 steps
✅ **Mode Tracking**: Always shows AI or HUMAN in JSON
✅ **Auto Switch**: Switches to HUMAN on failures
✅ **Manual Control**: Can force mode changes
✅ **Database Search**: Searches with keywords and price
✅ **Groq Integration**: Uses Groq for intent and formatting
✅ **Bengali Support**: All responses in Bengali

---

## 🔍 Flow Diagram

```
User Message
    ↓
[Step 1] Groq API
    ↓
Intent + Keywords
    ↓
[Step 2] Search Database
    ↓
Products Found?
    ↓ Yes          ↓ No
[Step 3]        Switch to
Database        HUMAN mode
Format             ↓
    ↓           Return JSON
[Step 4]        with mode:
AI Format       "human"
    ↓
[Step 5]
Track Mode
    ↓
[Step 6]
Return JSON
with mode:
"ai"
```

---

## 🛠️ Configuration

Edit `.env` file:

```env
# Groq API (Required)
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Server Port
PORT=5000
```

---

## 📖 API Documentation URL

Start server and visit:
```
http://localhost:5000/
```

Shows:
- Roadmap steps
- Available endpoints
- Quick reference

---

## 💡 Tips

1. **Check Mode First**: Use `GET /mode/:user_id` to check current mode
2. **Reset to AI**: Use `POST /mode/:user_id/ai` to reset after human interaction
3. **Monitor Logs**: Watch console for step-by-step processing
4. **Test with curl**: Easy to test with PowerShell or curl

---

## 🎉 That's It!

Your chatbot now:
- ✅ Follows your exact roadmap
- ✅ Shows mode in every response
- ✅ Auto-switches to human on errors
- ✅ Simple and clean code

**Start the server:**
```powershell
python run.py
```

**Test it:**
```powershell
$body = @{message = "10k laptop"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/chat" -Method Post -Body $body -ContentType "application/json"
```

Enjoy! 🚀
