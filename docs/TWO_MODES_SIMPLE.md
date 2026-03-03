# 🎛️ TWO MODES: BOT vs HUMAN

Your Facebook chatbot has **2 simple modes**:

---

## 🤖 MODE 1: BOT MODE (AI Responds)

**What happens:**
- AI automatically answers messages
- Fast, instant responses
- 24/7 automated support
- Uses Bengali database + product search

**When to use:**
- ✅ Normal customer questions
- ✅ Common inquiries (order, delivery, price)
- ✅ Product searches
- ✅ Most conversations (90%+)

**Example:**
```
Customer: "অর্ডার করবো কিভাবে?"
AI Bot: "অর্ডার করতে আমাদের ওয়েবসাইটে যান..." ✅
```

---

## 👤 MODE 2: HUMAN MODE (You Respond)

**What happens:**
- AI **stops responding completely**
- Human agent must reply manually via Facebook
- All messages are saved for you to see
- You control the conversation

**When to use:**
- ✅ Complex problems
- ✅ Complaints
- ✅ Special requests
- ✅ When AI doesn't understand

**Example:**
```
Customer: "I have a special bulk order request"
AI: [Stays silent - doesn't respond]
You: [Respond manually via Facebook Messenger] ✅
```

---

## 🔄 How to Switch Modes

### Option 1: Automatic Switching

AI automatically switches to Human Mode when:
- Customer message is unclear (after 3 tries)
- AI confidence is low
- Customer says "I want to talk to human"

**You'll see:**
```
Customer receives: "একজন প্রতিনিধি শীঘ্রই যোগাযোগ করবে..."
```

---

### Option 2: Manual Control (You Choose)

**Run the Mode Manager:**

```powershell
python mode_manager.py
```

OR double-click: **`MANAGE_MODES.bat`**

**Then use commands:**

```bash
# See who is in which mode
> status

# Switch someone to BOT MODE (AI responds)
> bot 1234567890

# Switch someone to HUMAN MODE (you respond)
> human 1234567890
```

---

## 📊 Visual Guide

### BOT MODE Active:
```
Customer → Message → 🤖 AI Bot → Instant Response
```

### HUMAN MODE Active:
```
Customer → Message → 👤 You (via Facebook) → Manual Response
```

---

## 🎯 Quick Setup

### Terminal 1: Run Chatbot
```powershell
python app_integrated.py
```
(Handles all messages)

### Terminal 2: Run Mode Manager (Optional)
```powershell
python mode_manager.py
```
(Control who gets AI vs human responses)

### Terminal 3: Run ngrok
```powershell
ngrok http 5000
```
(Expose to Facebook)

---

## 💡 Real World Examples

### Example 1: Normal Day
```
10 customers message your page
↓
All in BOT MODE
↓
AI handles all 10 automatically ✅
(No human needed!)
```

---

### Example 2: Complex Issue
```
Customer: "Your product broke, I want refund!"
↓
You run: > human 1234567890
↓
Now in HUMAN MODE
↓
You handle via Facebook manually ✅
↓
After resolved: > bot 1234567890
↓
Back to AI handling ✅
```

---

### Example 3: AI Can't Understand
```
Customer: "asdfghjkl blah blah"
↓
AI tries... can't understand
↓
Auto-switches to HUMAN MODE ⚠️
↓
You get notified
↓
You respond manually ✅
```

---

## 🔍 Check Current Modes

Run mode manager and type:
```bash
> status
```

You'll see:
```
🤖 BOT MODE (5 users)
  - user_1
  - user_2
  - user_3
  - user_4
  - user_5

👤 HUMAN MODE (1 user)
  - user_6 (needs your attention!)
```

---

## 🎮 Simple Commands

| Command | What It Does |
|---------|--------------|
| `status` | Show who's in bot vs human mode |
| `bot <id>` | Let AI handle this person |
| `human <id>` | I'll handle this person |
| `messages` | Show pending messages |

---

## ✅ That's It!

**Two simple modes:**
1. 🤖 **BOT MODE** - AI does the work
2. 👤 **HUMAN MODE** - You do the work

**Switch anytime with:**
```powershell
python mode_manager.py
```

---

## 📞 Quick Reference

**Start chatbot:**
```powershell
python app_integrated.py
```

**Manage modes:**
```powershell
python mode_manager.py
```

**Switch to bot mode:**
```bash
> bot user_id
```

**Switch to human mode:**
```bash
> human user_id
```

**That's all you need to know!** 🎉

Most people stay in BOT MODE (AI handles 90%+ of messages). Only switch to HUMAN MODE when needed for special cases.
