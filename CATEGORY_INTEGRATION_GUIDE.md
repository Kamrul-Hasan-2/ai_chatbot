# Category Templates Integration Guide

## For SimpleChatbot Flow

### Option 1: Automatic Integration (Recommended)

If ProductLinkHandler is already used in your message processing pipeline:

```python
# In messenger_webhook.py or simple_chatbot_flow.py

from src.utils.product_link_handler import get_link_handler
from src.handlers.messenger_handler import send_facebook_message

# Inside your message processing function:
def process_bot_response(user_id: str, message_text: str):
    
    # Get the link handler (already handles categories!)
    link_handler = get_link_handler()
    
    # This automatically detects and enhances categories
    template = link_handler.create_category_template(message_text)
    
    # If it's a category, template will be enhanced
    # If not, template will be the fallback text message
    send_facebook_message(user_id, template)
```

**That's it!** Category detection happens automatically.

---

### Option 2: Manual Integration

If you want explicit control:

```python
from src.utils.category_product_handler import get_category_handler
from src.handlers.messenger_handler import send_facebook_message

def handle_bot_response(user_id: str, bot_message: str):
    
    handler = get_category_handler()
    
    # Try to convert category message to template
    is_category, result = handler.convert_category_message_to_template(bot_message)
    
    if is_category and result['success']:
        # Send enhanced template
        template = result['template']
    else:
        # Send as regular text
        template = {'messaging_type': 'RESPONSE', 'message': {'text': bot_message}}
    
    send_facebook_message(user_id, template)
```

---

### Option 3: Direct API Integration

If using external service:

```bash
# Server receives bot response mentioning category
message = "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন"

# Call your API
curl -X POST "http://localhost:5000/api/category/template/user_123" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$message\"}"

# Receives template with products
# Send to Messenger
```

---

## Where to Add (Code Locations)

### Current Flow:

```
user sends message
  ↓
SimpleChatbot processes
  ↓
BOT generates response
  ↓
[ADD HERE] → Check for category
  ↓
Send to Messenger
  ↓
User sees enhanced template or text
```

### Find This Code:

**If using `src/core/simple_chatbot_flow.py`:**
```python
# Around line where bot response is created
response = chatbot.get_response(user_message, user_id)

# ADD THIS:
template = link_handler.create_category_template(response)
send_facebook_message(user_id, template)
```

**If using `src/api/app_simple.py` webhook:**
```python
@app.route('/webhook', methods=['POST'])
def webhook():
    # ... existing code ...
    
    # When sending bot response:
    bot_message = simple_chatbot.get_response(user_message, user_id)
    
    # ADD THIS:
    template = link_handler.create_category_template(bot_message)
    send_facebook_message(user_id, template)
    
    # ... rest of code ...
```

---

## Testing After Integration

### Test 1: Start Server
```bash
python run.py
```

### Test 2: Test via API
```bash
curl -X POST "http://localhost:5000/api/category/template/test_user" \
  -H "Content-Type: application/json" \
  -d '{"message": "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন"}'
```

Expected response with product carousel.

### Test 3: Test with Real Messenger
Send a message to your bot that mentions a category.

Expected: Beautiful product cards appear in chat!

---

## Debugging

### If not working:

**Check 1: Is the handler initialized?**
```python
from src.utils.product_link_handler import get_link_handler
handler = get_link_handler()
print(handler)  # Should show handler instance
```

**Check 2: Is category being detected?**
```python
message = "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন"
category = handler.category_handler.extract_category_from_message(message)
print(category)  # Should print: "laptop"
```

**Check 3: Are products being fetched?**
```python
products = handler.category_handler.fetch_category_products('laptop')
print(len(products))  # Should be > 0
```

**Check 4: Is template being created?**
```python
template = handler.create_category_template(message)
print(template.keys())  # Should have: messaging_type, message
```

---

## Common Issues

### Issue 1: Category not detected
- Check if message contains one of the patterns
- Add logging: `print(f"Message: {message}")`
- Verify pattern regex in `category_product_handler.py`

### Issue 2: No products fetched
- Check network connection
- Verify BDStall API is up
- Try manually: `curl https://www.bdstall.com/api/item/search/\?term=laptop`

### Issue 3: Template not sending to Messenger
- Verify `send_facebook_message()` function works
- Check Messenger API token
- Review logs for errors

### Issue 4: Fallback to text instead of template
- Check error logs
- Might be timeout (10 seconds)
- Check API quota

---

## Examples of Messages That Work

✅ Bengali:
- "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন"
- "আমাদের phone ক্যাটাগরিতে অনেক পণ্য আছে"
- "camera ক্যাটাগরিতে নতুন পণ্য এসেছে"

✅ English:
- "You can see products in laptop category"
- "We have many phones in the phone category"
- "Check our watch category for new items"

✅ URLs:
- "https://www.bdstall.com/laptop/"
- "https://www.bdstall.com/camera/"
- "https://www.bdstall.com/phone/"

✅ Mixed:
- "Check https://www.bdstall.com/watch/ for great deals"
- "Our laptop ক্যাটাগরিতে সেরা দাম"

---

## Performance Tips

1. **Use caching** - Already enabled by default (1 hour)
2. **Batch requests** - If fetching multiple categories, do in parallel
3. **Set limit** - Use `limit=5` instead of fetching all products
4. **Monitor logs** - Check for slow API calls

---

## Monitoring

Add to your logging:

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def handle_bot_response(user_id: str, bot_message: str):
    start = datetime.now()
    
    template = link_handler.create_category_template(bot_message)
    
    elapsed = (datetime.now() - start).total_seconds()
    
    if 'attachment' in template['message']:
        logger.info(f"Category template created in {elapsed}s for user {user_id}")
    else:
        logger.info(f"Text message sent in {elapsed}s for user {user_id}")
    
    send_facebook_message(user_id, template)
```

---

## Summary

### To Enable Category Templates:

1. **Nothing needed!** If already using ProductLinkHandler
2. **Or** add 3 lines of code as shown in Option 1
3. **Or** use the API endpoints directly

### What Users Will See:

**Before:**
```
Bot: "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য। Link: [url]"
```

**After:**
```
Bot: "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য"

[Product 1] [Product 2] [Product 3]
[Image]     [Image]     [Image]
Title       Title       Title
৳ Price     ৳ Price     ৳ Price
[View][Add] [View][Add] [View][Add]
```

### Files You Might Need to Modify:

- `src/core/simple_chatbot_flow.py` - If using SimpleChatbot
- `src/handlers/messenger_handler.py` - If webhook handling bot responses
- `src/api/app_simple.py` - If you want to add custom logic to endpoints

---

## Questions?

Check these files for reference:
- `CATEGORY_TEMPLATES_COMPLETE.md` - Full documentation
- `tests/test_category_handler.py` - Working examples
- `src/utils/category_product_handler.py` - Source code
- `src/utils/product_link_handler.py` - Integration point

**Everything is tested and working!** 🎉
