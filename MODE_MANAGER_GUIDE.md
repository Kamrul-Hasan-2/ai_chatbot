# 🎛️ Bot & Human Mode Manager

## Overview

Manage your Facebook chatbot with **two modes**:

### 🤖 **BOT MODE** (AI responds)
- AI automatically answers customer messages
- Fast, 24/7 automated support
- Handles common questions, product search, orders
- Uses Bengali database + BDStall API

### 👤 **HUMAN MODE** (Human responds)  
- AI stops responding completely
- Human agent manually responds via Facebook
- All messages queued for human review
- For complex issues, complaints, special requests

---

## 🚀 Quick Start

### Run the Mode Manager:

```powershell
python mode_manager.py
```

You'll see an interactive menu:

```
🎛️  BOT & HUMAN MODE MANAGER
═══════════════════════════════════════════════════════════════════

Commands:
1. status          - View all conversation modes
2. bot <user_id>   - Switch user to BOT MODE
3. human <user_id> - Switch user to HUMAN MODE
4. messages        - View all pending messages
5. cleanup         - Remove inactive sessions
6. help            - Show detailed help
7. quit            - Exit manager

Enter command:
```

---

## 📊 Commands

### 1. View Status

```bash
> status
```

Shows all users and their current modes:

```
🤖 BOT MODE (2 users)
  👤 User: 1234567890
     Last activity: 2026-03-01 14:30:00
     Failed attempts: 0

👤 HUMAN MODE (1 user)
  👤 User: 9876543210
     Activated: 2026-03-01 14:25:00
     Last activity: 2026-03-01 14:28:00
```

---

### 2. Switch to BOT MODE

```bash
> bot 1234567890
```

Result:
- ✅ User switches to BOT MODE
- ✅ AI will automatically respond to messages
- ✅ User can chat with AI normally

---

### 3. Switch to HUMAN MODE

```bash
> human 1234567890
```

Result:
- ✅ User switches to HUMAN MODE
- ✅ AI stops responding
- ✅ Human agent must respond via Facebook
- ✅ All messages are queued

---

### 4. View Pending Messages

```bash
> messages
```

Shows all pending messages across all users.

**For specific user:**
```bash
> messages 1234567890
```

---

### 5. Cleanup Inactive Sessions

```bash
> cleanup
```

Removes sessions that have been inactive for 30+ minutes.

---

## 🔄 Typical Workflow

### Scenario 1: AI Handles Everything (Normal)

```
User: "অর্ডার করবো কিভাবে?"
  ↓
🤖 AI responds automatically (BOT MODE)
  ↓
User: "ধন্যবাদ!"
  ↓
🤖 AI responds
```

No admin action needed! ✅

---

### Scenario 2: AI Can't Understand (Auto Handoff)

```
User: "blah blah unclear message"
  ↓
🤖 AI tries... can't understand
  ↓
⏳ Auto-switches to PENDING HANDOFF
  ↓
📧 User receives: "একজন প্রতিনিধি শীঘ্রই যোগাযোগ করবে..."
  ↓
Admin runs: > status
  ↓
Sees user in PENDING HANDOFF
  ↓
Admin runs: > human 1234567890
  ↓
👤 Now in HUMAN MODE
  ↓
Human agent responds via Facebook Messenger
  ↓
After resolved, admin runs: > bot 1234567890
  ↓
🤖 Back to BOT MODE
```

---

### Scenario 3: Admin Manually Switches to Human

```
User: "I have a complex refund issue"
  ↓
Admin sees message and runs:
> human 1234567890
  ↓
👤 Switched to HUMAN MODE
  ↓
Human agent handles the issue
  ↓
After resolved:
> bot 1234567890
  ↓
🤖 Back to normal AI support
```

---

## 🎯 When to Use Each Mode

### Use BOT MODE (🤖) for:
- ✅ Common questions (order, delivery, payment)
- ✅ Product searches
- ✅ FAQ responses
- ✅ 24/7 automated support
- ✅ Bengali language queries
- ✅ High volume, simple queries

### Use HUMAN MODE (👤) for:
- ✅ Complex issues
- ✅ Complaints
- ✅ Refunds/Returns
- ✅ Special requests
- ✅ Unclear AI responses
- ✅ Sensitive matters
- ✅ VIP customers

---

## 💡 Pro Tips

### 1. Monitor Pending Handoffs

Regularly check:
```bash
> status
```

Look for users in **PENDING HANDOFF** - they need attention!

---

### 2. Quick Mode Switch

Create shortcuts:
```bash
> bot user123      # Quick bot mode
> human user123    # Quick human mode
```

---

### 3. View Recent Messages

```bash
> messages user123
```

See what the user has been asking before you switch modes.

---

### 4. Batch Operations

Switch multiple users:
```bash
> bot user1
> bot user2
> bot user3
```

---

### 5. Regular Cleanup

Run daily:
```bash
> cleanup
```

Removes old inactive sessions to keep system fast.

---

## 🖥️ Run Alongside Chatbot

**Terminal 1: Run Chatbot**
```powershell
python app_integrated.py
```

**Terminal 2: Run Mode Manager**
```powershell
python mode_manager.py
```

**Terminal 3: Run ngrok**
```powershell
ngrok http 5000
```

Now you can:
- Chatbot handles messages automatically
- Admin controls modes in real-time
- Switch between bot/human as needed

---

## 📋 Status Indicators

```
🤖 BOT MODE         - AI is responding
⏳ PENDING HANDOFF  - Waiting for human to activate
👤 HUMAN MODE       - Human agent is handling
```

---

## 🔐 Access Control

**Who Should Use Mode Manager:**
- ✅ Customer support admins
- ✅ Team leads
- ✅ Human agents managing conversations

**Not needed for:**
- ❌ End users (they just chat)
- ❌ Developers (unless testing)

---

## 📊 Example Session

```powershell
PS> python mode_manager.py

🎛️  BOT & HUMAN MODE MANAGER
═══════════════════════════════════════════════════════════════════

Enter command: status

📊 CONVERSATION MODE STATUS
═══════════════════════════════════════════════════════════════════

🤖 BOT MODE (3 users)
  👤 User: user_1
  👤 User: user_2
  👤 User: user_3

⏳ PENDING HANDOFF (1 user)
  👤 User: user_4
     Reason: no_match_found
     Pending messages: 2

👤 HUMAN MODE (0 users)

Enter command: human user_4

🔄 Switching user user_4 to HUMAN MODE...
✅ User user_4 is now in HUMAN MODE
   AI will NOT respond - human agent must reply

Enter command: status

👤 HUMAN MODE (1 user)
  👤 User: user_4

[After handling the issue...]

Enter command: bot user_4

🔄 Switching user user_4 to BOT MODE...
✅ User user_4 is now in BOT MODE
   AI will automatically respond to their messages

Enter command: quit

👋 Goodbye!
```

---

## 🔧 Integration with Chatbot

The mode manager works with your running chatbot:

1. **Chatbot** (`app_integrated.py`) handles messages
2. **Mode Manager** (`mode_manager.py`) controls modes
3. When in **BOT MODE**: Chatbot responds automatically
4. When in **HUMAN MODE**: Chatbot stays silent

They share the same session data through `HumanHandoffManager`.

---

## 🆘 Troubleshooting

### Issue: Mode manager shows "No active conversations"

**Cause:** No users have messaged yet

**Solution:** Wait for users to send messages to your Facebook page

---

### Issue: Can't switch user to human mode

**Cause:** User ID might be wrong

**Solution:** Check exact user ID from status output

---

### Issue: Changes not taking effect

**Cause:** Chatbot and mode manager not using same data

**Solution:** Make sure both are running in same directory

---

## 🎓 Advanced Usage

### Python API

```python
from mode_manager import ModeManager

manager = ModeManager()

# Switch modes programmatically
manager.switch_to_human_mode("user_123")
manager.switch_to_bot_mode("user_456")

# Check status
manager.show_status()

# View messages
manager.view_pending_messages("user_123")
```

---

## 📞 Quick Reference

| Command | What It Does |
|---------|--------------|
| `status` | Show all users and their modes |
| `bot <id>` | Switch user to AI responses |
| `human <id>` | Switch user to human responses |
| `messages` | View all pending messages |
| `messages <id>` | View messages for one user |
| `cleanup` | Remove inactive sessions |
| `help` | Show detailed help |
| `quit` | Exit manager |

---

## ✨ Summary

Your Facebook chatbot now has **two clear modes**:

1. 🤖 **BOT MODE**: AI handles everything automatically
2. 👤 **HUMAN MODE**: Human agents take over manually

Use the **Mode Manager** to switch between them in real-time!

**Start managing modes:**
```powershell
python mode_manager.py
```
