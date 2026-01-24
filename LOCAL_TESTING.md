# Testing Your Chatbot Locally

There are several ways to test your chatbot locally without Facebook Messenger:

## Method 1: Interactive Console (RECOMMENDED) ⭐

Run the interactive tester for a chat-like experience:

```bash
python test_local.py
```

This provides:
- Interactive chat interface
- Type messages and get responses instantly
- Commands: `quit`, `clear`, `stats`
- Full RAG support

**Example session:**
```
You: Hello, what can you help me with?
Bot: [AI response]

You: What is your refund policy?
Bot: [RAG-enhanced response from knowledge base]

You: stats
📊 RAG Statistics:
   enabled: True
   total_documents: 150
   ...

You: quit
👋 Goodbye!
```

---

## Method 2: Flask Test Endpoint

Start the Flask server and use the `/test` endpoint:

### Step 1: Start the server
```bash
python app.py
```

### Step 2: Test with curl
```bash
curl -X POST http://localhost:5000/test -H "Content-Type: application/json" -d "{\"user_id\": \"test123\", \"message\": \"What are your products?\"}"
```

### Step 3: Or use PowerShell
```powershell
$body = @{
    user_id = "test_user"
    message = "What are your products?"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:5000/test -Method POST -Body $body -ContentType "application/json"
```

---

## Method 3: Unit Test Script

Run the basic test script:

```bash
python test_chatbot.py
```

This runs predefined test messages and shows responses.

---

## Method 4: RAG Examples

Test RAG functionality specifically:

```bash
python rag_example.py
```

This demonstrates:
- Loading documents
- RAG retrieval
- Sample queries with RAG-enhanced responses

---

## Method 5: Python Script

Create your own test script:

```python
# my_test.py
from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data

# Initialize
chatbot = AdminChatbot(enable_rag=True)
initialize_rag_with_data(chatbot)

# Test
response = chatbot.get_response("user123", "What is your refund policy?")
print(response)
```

Run it:
```bash
python my_test.py
```

---

## Method 6: Python Interactive Shell

```bash
python
```

Then in the Python shell:
```python
>>> from chatbot import AdminChatbot
>>> from knowledge_loader import initialize_rag_with_data
>>> 
>>> # Initialize
>>> bot = AdminChatbot(enable_rag=True)
>>> initialize_rag_with_data(bot)
>>> 
>>> # Test queries
>>> bot.get_response("user1", "Hello!")
>>> bot.get_response("user1", "What are your products?")
>>> bot.get_response("user1", "What is your refund policy?")
>>> 
>>> # Check stats
>>> bot.get_rag_stats()
```

---

## Quick Comparison

| Method | Interactive | RAG Support | Best For |
|--------|------------|-------------|----------|
| **test_local.py** ⭐ | ✅ Yes | ✅ Yes | Quick testing, conversation |
| Flask `/test` endpoint | ❌ No | ✅ Yes | API testing |
| test_chatbot.py | ❌ No | ⚠️ Depends | Quick validation |
| rag_example.py | ❌ No | ✅ Yes | RAG demonstration |
| Python script | ❌ No | ✅ Yes | Custom testing |
| Python shell | ✅ Yes | ✅ Yes | Debugging |

---

## Recommended Testing Workflow

### 1. First Time Setup
```bash
# Verify RAG installation
python test_rag.py

# Test basic functionality
python test_chatbot.py
```

### 2. Interactive Testing (Daily Use)
```bash
# Best for conversation testing
python test_local.py
```

### 3. API Testing
```bash
# Terminal 1: Start server
python app.py

# Terminal 2: Send requests
curl -X POST http://localhost:5000/test -H "Content-Type: application/json" -d "{\"user_id\":\"user1\",\"message\":\"Hello\"}"
```

---

## Testing Tips

### Test Different Scenarios

```python
# Test general questions
"Hello, how are you?"

# Test knowledge base (RAG)
"What is your refund policy?"
"What products do you offer?"
"What are your support hours?"

# Test conversation history
"What did I just ask?"
"Can you elaborate on that?"

# Test edge cases
"" (empty message)
"?????" (unclear input)
```

### Monitor Logs

Check conversation logs:
```bash
# View today's conversations
cat logs/conversations_2026-01-24.log

# Or on Windows
type logs\conversations_2026-01-24.log
```

### Check RAG Performance

```python
# In test_local.py, type:
stats

# Or programmatically:
from chatbot import AdminChatbot
bot = AdminChatbot(enable_rag=True)
print(bot.get_rag_stats())
```

---

## Troubleshooting

### Issue: Model download is slow
- **First run takes time** (downloads ~5GB model)
- Be patient, it only happens once
- Models are cached for future runs

### Issue: Out of memory
- Close other applications
- Use CPU mode: Set `DEVICE=cpu` in `.env`

### Issue: RAG not finding documents
- Check documents are in `data/knowledge/`
- Run: `python test_rag.py` to verify
- Check stats with `bot.get_rag_stats()`

---

## Example: Full Local Test Session

```bash
# 1. Verify everything works
python test_rag.py

# 2. Run interactive test
python test_local.py

# Example interaction:
# You: Hello!
# Bot: Hello! How can I help you today?
# 
# You: What products do you offer?
# Bot: [RAG retrieves product info and responds]
# 
# You: What is your refund policy?
# Bot: [RAG retrieves policy and responds]
# 
# You: stats
# 📊 RAG Statistics:
#    enabled: True
#    total_documents: 156
#    embedding_model: all-MiniLM-L6-v2
#    embedding_dimension: 384
#    index_size: 156
# 
# You: quit
# 👋 Goodbye!
```

---

## Ready to Test!

**Quick start:**
```bash
python test_local.py
```

Then just type your messages and press Enter! 🚀
