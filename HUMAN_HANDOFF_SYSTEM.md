# 🤖 Human Handoff System Documentation

## Overview

The Human Handoff System automatically switches from AI responses to human agent mode when the AI doesn't understand or can't handle a query. This ensures users always get proper support.

## Key Features

✅ **Automatic Detection** - AI detects when it doesn't understand
✅ **Smart Triggering** - Handoff based on confidence, failures, or user request
✅ **Mode Tracking** - Tracks conversation state (AI mode vs Human mode)
✅ **No AI Responses in Human Mode** - Once handed off, only humans respond
✅ **Bengali Support** - All handoff messages in Bengali
✅ **Admin Controls** - Easy to return conversations back to AI

---

## How It Works

### 1. Normal Flow (AI Mode)
```
User: "অর্ডার করবো কিভাবে?"
  ↓
AI: [High confidence match found]
  ↓
AI responds with answer ✅
```

### 2. Handoff Flow (AI → Human)
```
User: "blah blah unclear message"
  ↓
AI: [Cannot understand - low confidence]
  ↓
System: Trigger handoff to human
  ↓
User receives: "একজন প্রতিনিধি শীঘ্রই সাহায্য করবে..."
  ↓
Conversation enters HUMAN MODE
```

### 3. Human Mode Active
```
User: "অর্ডার করবো কিভাবে?" [Even valid query]
  ↓
AI: [Checks mode → Human Mode]
  ↓
AI: Does NOT respond (waits for human) 🚫
  ↓
Human agent responds instead
```

---

## Handoff Triggers

The system triggers handoff to human agent when:

### 1. **Low Confidence** (< 60%)
```python
confidence = 0.3  # Below threshold
→ Handoff triggered
```

### 2. **No Match Found**
```python
database_search_result = False
→ Handoff triggered
```

### 3. **Repeated Failures** (Default: 3 attempts)
```python
failed_attempts >= 3
→ Handoff triggered
```

### 4. **User Requests Human**
```python
User: "I want to talk to a human agent"
User: "মানুষের সাথে কথা বলতে চাই"
→ Handoff triggered immediately
```

---

## Configuration

### Initialize with Custom Settings

```python
from human_handoff_manager import HumanHandoffManager

manager = HumanHandoffManager(
    confidence_threshold=0.5,      # Trigger below 50% confidence
    max_failed_attempts=3,          # Handoff after 3 failures
    session_timeout_minutes=30      # Session expires after 30 min
)
```

### Integration in Chatbot

```python
from bdstall_chatbot_system import BDStallChatbotSystem

chatbot = BDStallChatbotSystem()
# Handoff manager automatically initialized

result = chatbot.process_message(
    user_id="user123",
    message="unclear query",
    channel="web"
)

if result.get('handoff_triggered'):
    print("Conversation handed to human agent")
    print(f"Reason: {result['processing_info']['handoff_reason']}")
```

---

## API Usage

### Check if User in Human Mode

```python
is_human_mode = chatbot.handoff_manager.is_in_human_mode("user123")
# Returns: True or False
```

### Get Pending Conversations

```python
pending = chatbot.handoff_manager.get_pending_conversations()
# Returns list of all conversations waiting for human response

for conv in pending:
    print(f"User: {conv['user_id']}")
    print(f"Reason: {conv['handoff_reason']}")
    print(f"Messages: {len(conv['pending_messages'])}")
```

### Return User to AI Mode

```python
# After human agent resolves the issue
chatbot.handoff_manager.return_to_ai("user123")
# User can now interact with AI again
```

### Get Session Information

```python
info = chatbot.handoff_manager.get_session_info("user123")
# Returns:
# {
#   'user_id': 'user123',
#   'mode': 'human_mode',
#   'handoff_reason': 'low_confidence',
#   'failed_attempts': 3,
#   'last_activity': '2026-03-01T12:00:00'
# }
```

---

## Handoff Messages

### No Match Found
```
মিঠুন চন্দ্র বর্মন, BDStall.com-এ আপনাকে স্বাগতম। 
আপনার মেসেজ এর জন্য ধন্যবাদ। 
খুব শীঘ্রই BDStall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে। 
(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)
জরুরী প্রয়োজনে কল করুন: 01612378255
```

### Low Confidence
```
দুঃখিত, আমি সঠিকভাবে বুঝতে পারছি না। 
একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবে। 
(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)
জরুরী প্রয়োজনে কল করুন: 01612378255
```

### User Requested
```
অবশ্যই! একজন প্রতিনিধি শীঘ্রই আপনার সাথে কথা বলবে। 
(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)
জরুরী প্রয়োজনে কল করুন: 01612378255
```

---

## Testing

### Run Demo
```bash
python demo_handoff.py
```

### Run Full Test Suite
```bash
python test_human_handoff.py
```

### Test Handoff Manager Only
```bash
python human_handoff_manager.py
```

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User Message                         │
└────────────────────┬────────────────────────────────────┘
                     ↓
            ┌────────────────────┐
            │  Check User Mode   │
            └────────┬───────────┘
                     ↓
          ┌──────────┴──────────┐
          │                     │
    [AI Mode]            [Human Mode]
          │                     │
          ↓                     ↓
┌─────────────────────┐  ┌──────────────────┐
│  Process with AI    │  │ No AI Response   │
│  - Database Search  │  │ Wait for Human   │
│  - Product Search   │  │                  │
│  - NLP Processing   │  │                  │
└──────────┬──────────┘  └──────────────────┘
           ↓
   ┌───────────────────┐
   │ Check Confidence  │
   └───────┬───────────┘
           ↓
    ┌──────┴──────┐
    │             │
[High]       [Low / No Match / Failed]
    │             │
    ↓             ↓
┌─────────┐  ┌──────────────────────┐
│ AI      │  │  Trigger Handoff     │
│ Responds│  │  → Switch to Human   │
└─────────┘  └──────────────────────┘
```

---

## Admin Dashboard Example

```python
def admin_dashboard():
    """Example admin dashboard for managing handoffs"""
    
    chatbot = BDStallChatbotSystem()
    manager = chatbot.handoff_manager
    
    # Get all pending conversations
    pending = manager.get_pending_conversations()
    
    print(f"📋 Pending Conversations: {len(pending)}")
    
    for conv in pending:
        print(f"\n👤 User: {conv['user_id']}")
        print(f"   Reason: {conv['handoff_reason']}")
        print(f"   Time: {conv['handoff_triggered_at']}")
        print(f"   Messages: {len(conv['pending_messages'])}")
        
        # Show messages
        for msg in conv['pending_messages']:
            print(f"   - {msg['message']}")
    
    # After human agent handles it, return to AI
    # manager.return_to_ai("user123")
```

---

## Best Practices

### 1. **Monitor Handoff Rate**
Track how often handoffs occur to improve AI training:
```python
total_queries = 1000
handoff_count = 50
handoff_rate = (handoff_count / total_queries) * 100
# Target: < 10% handoff rate
```

### 2. **Review Failed Queries**
Analyze queries that triggered handoff to add to database:
```python
pending = manager.get_pending_conversations()
failed_queries = [msg['message'] for conv in pending 
                  for msg in conv['pending_messages']]
# Add these to training data
```

### 3. **Set Appropriate Thresholds**
- **High traffic sites**: Lower threshold (0.7) - fewer handoffs
- **Critical support**: Higher threshold (0.4) - more handoffs
- **Testing phase**: Start high, gradually lower

### 4. **Session Timeout**
- **Default**: 30 minutes
- **High volume**: 15 minutes (cleanup faster)
- **Low volume**: 60 minutes (patient users)

---

## Files

| File | Description |
|------|-------------|
| `human_handoff_manager.py` | Core handoff manager |
| `bdstall_chatbot_system.py` | Integrated chatbot with handoff |
| `demo_handoff.py` | Simple demonstration |
| `test_human_handoff.py` | Full test suite |
| `HUMAN_HANDOFF_SYSTEM.md` | This documentation |

---

## Example Integration with Web App

```python
from flask import Flask, request, jsonify
from bdstall_chatbot_system import BDStallChatbotSystem

app = Flask(__name__)
chatbot = BDStallChatbotSystem()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data['user_id']
    message = data['message']
    
    result = chatbot.process_message(
        user_id=user_id,
        message=message,
        channel='web'
    )
    
    response = {
        'message': result['response'],
        'handoff_triggered': result.get('handoff_triggered', False),
        'in_human_mode': result.get('in_human_mode', False)
    }
    
    if result.get('handoff_triggered'):
        # Notify human agents
        notify_human_agents(user_id)
    
    return jsonify(response)

@app.route('/admin/pending', methods=['GET'])
def get_pending():
    """Admin endpoint to see pending conversations"""
    pending = chatbot.handoff_manager.get_pending_conversations()
    return jsonify({'pending': pending})

@app.route('/admin/return-to-ai', methods=['POST'])
def return_to_ai():
    """Admin endpoint to return user to AI mode"""
    user_id = request.json['user_id']
    chatbot.handoff_manager.return_to_ai(user_id)
    return jsonify({'success': True})
```

---

## Troubleshooting

### Issue: Too many handoffs
**Solution**: Lower the confidence threshold or add more training data

### Issue: Not triggering handoff when it should
**Solution**: Increase confidence threshold or reduce max_failed_attempts

### Issue: Sessions not expiring
**Solution**: Reduce session_timeout_minutes or call cleanup_expired_sessions()

### Issue: Handoff messages not in Bengali
**Solution**: Check handoff_messages dictionary in HumanHandoffManager

---

## Contact & Support

For issues or questions:
- Check logs: Look for "🔔 Handoff triggered" messages
- Phone: 01612378255
- Hours: 10 AM - 6 PM

---

## License & Credits

Part of BDStall Chatbot System
Created: March 2026
