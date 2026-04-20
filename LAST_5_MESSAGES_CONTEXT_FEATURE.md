# Last 5 Messages Context Feature - Documentation

## Overview
When a messenger sends a reply to you, the system **automatically reads the last 5 messages** and **uses that context to generate a better response**. This feature is **already fully implemented** in your chatbot.

## How It Works

### Step 1: Message Flow in Messenger Webhook
```
Messenger sends message
    ↓
/webhook endpoint receives it
    ↓
_process_user_message() is called
    ↓
SimpleChatbot.process_message() is called
```

### Step 2: Fetch Last 5 Messages
**File:** `src/core/simple_chatbot_flow.py` (Line 821)
```python
conversation_context = self._fetch_recent_chat_context(
    user_id=user_id,
    limit=self.chatbot_history_limit  # Default: 5 messages
)
```

### Step 3: Build Context From History
**Function:** `_fetch_recent_chat_context()` (Line 1447)
- Makes API call to: `https://www.bdstall.com/api/item/chatbot_history/`
- Fetches the last 5 messages for that user
- Formats them as readable conversation text
- Returns context like:
```
User: laptop koto taka?
Bot: Laptop prices vary based on specs
User: 10k budget
Bot: Let me search for you
User: thanks
```

### Step 4: Use Context for Intent Detection
**Function:** `_step1_groq_intent()` (Line 1192)

The conversation context is passed to Groq API in the prompt:
```python
prompt = f"""Analyze this message and extract:
1. Intent 
2. Search keywords

Recent conversation context (oldest to newest):
{conversation_context or 'N/A'}

Message: {message}
...
"""
```

Groq API uses this context to:
- ✅ Understand follow-up messages better
- ✅ Recognize when user is asking about a previously discussed product
- ✅ Avoid asking redundant questions
- ✅ Provide more accurate intent detection

## Configuration

### Limit Configuration
**File:** `.env`
```
CHATBOT_HISTORY_LIMIT=5  # Can be changed to fetch more messages (max 20)
```

### API Configuration
**File:** `src/core/simple_chatbot_flow.py` (Line 143-149)
```python
self.chatbot_history_api_url = os.getenv(
    'CHATBOT_HISTORY_API_URL',
    'https://www.bdstall.com/api/item/chatbot_history/'
)
```

## Example Conversation Flow

### Without Context (Old Way)
```
User: laptop 10k
Bot: Which brand?

User: hp
Bot: Search results... [generic response]
```

### With Context (Current Way - Your Implementation)
```
User: laptop 10k
Bot: HP laptops under 10k...

User: hp  ← Bot reads the last 5 messages
Bot: Here are HP laptops under 10k [contextual, not generic]
```

## Key Features

✅ **Automatic**: No manual setup needed - it's already active  
✅ **Configurable**: Change limit in `.env`  
✅ **Fast**: 8-second timeout for API calls  
✅ **Fallback**: Returns empty context if API fails (doesn't break responses)  
✅ **Smart**: Only fetches when needed (during intent detection)  

## Message Processing Pipeline

```
1. Messenger sends reply
   ↓
2. Fetch last 5 messages from BDStall API
   ↓
3. Format as conversation context
   ↓
4. Send to Groq API with context
   ↓
5. Groq detects intent using context
   ↓
6. Search for products/info
   ↓
7. Return contextual response
   ↓
8. Send to messenger
```

## Logging

You can see this feature in action in your logs:
```
🚀 STEP 1: Sending to Groq API for intent detection...
🧠 [HISTORY_CONTEXT] user_id=123456 lines=5
```

## Files Involved

- **Messenger Webhook**: `src/api/app_simple.py` (Line 650+)
- **Message Processing**: `src/core/simple_chatbot_flow.py`
- **Context Fetching**: `_fetch_recent_chat_context()` (Line 1447)
- **Intent Detection**: `_step1_groq_intent()` (Line 1192)

## Testing

To test this feature:

1. Start your chatbot:
```bash
python run.py
```

2. Send messages via messenger:
```
Message 1: "laptop dekhaen"
Message 2: "10k budget"
Message 3: "hp brand" ← Bot will understand this is about HP laptops under 10k
```

3. Check logs for:
```
🧠 [HISTORY_CONTEXT] user_id=XXX lines=5
```

## Summary

Your chatbot **already fully implements** the feature to:
1. ✅ Read last 5 messages when receiving a reply
2. ✅ Use that context to understand the conversation
3. ✅ Provide better, more contextual responses

The implementation is production-ready and actively working!
