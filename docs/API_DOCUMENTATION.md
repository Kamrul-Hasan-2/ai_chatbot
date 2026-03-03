# AI Chatbot API Documentation

Version: 1.0  
Base URL: `http://localhost:8000` (or your deployed URL)

## Table of Contents
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Chat Endpoints](#chat-endpoints)
  - [Facebook Messenger](#facebook-messenger)
  - [System Management](#system-management)
  - [Analytics & Monitoring](#analytics--monitoring)
- [Request/Response Examples](#requestresponse-examples)
- [Error Handling](#error-handling)

---

## Authentication

Currently, the API does not require authentication for most endpoints. Facebook Messenger endpoints use token-based verification.

**Facebook Messenger Configuration:**
- `PAGE_ACCESS_TOKEN` - Your Facebook Page Access Token
- `VERIFY_TOKEN` - Webhook verification token

---

## Endpoints

### Chat Endpoints

#### POST /chat
Send a message to the chatbot (Web interface).

**Request:**
```json
{
  "user_id": "web_user",
  "message": "What laptops do you have?"
}
```

**Response:**
```json
{
  "response": "We have laptops from HP, Dell, Lenovo...",
  "user_id": "web_user",
  "processing_info": {
    "intent": "product_search",
    "entities": ["laptop"],
    "confidence": 0.95
  },
  "success": true
}
```

**Error Response:**
```json
{
  "error": "No message provided",
  "success": false
}
```

---

#### POST /test
Test endpoint for quick message testing.

**Request:**
```json
{
  "user_id": "test_user",
  "message": "Show me laptops under 50000 taka"
}
```

**Response:**
```json
{
  "user_id": "test_user",
  "message": "Show me laptops under 50000 taka",
  "response": "Here are laptops under 50000 taka...",
  "success": true,
  "processing_info": {
    "intent": "product_search",
    "entities": ["laptop", "50000"],
    "budget": 50000
  },
  "system_info": "BDStall Chatbot System v1.0"
}
```

---

#### POST /process
Process message with detailed response information.

**Request:**
```json
{
  "user_id": "api_user",
  "message": "I want to order a laptop",
  "channel": "api",
  "metadata": {
    "source": "mobile_app",
    "version": "1.2.3"
  }
}
```

**Response:**
```json
{
  "success": true,
  "response": "Great! Which laptop would you like to order?",
  "user_id": "api_user",
  "processing_info": {
    "intent": "order",
    "entities": ["laptop"],
    "confidence": 0.92,
    "context": {
      "state": "order_initiation",
      "items": []
    }
  },
  "handover": false
}
```

---

#### POST /clear_history
Clear conversation history for a specific user.

**Request:**
```json
{
  "user_id": "web_user"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "History cleared"
}
```

---

### Facebook Messenger

#### GET /webhook
Verify Facebook Messenger webhook.

**Query Parameters:**
- `hub.mode` - Should be "subscribe"
- `hub.verify_token` - Your verification token
- `hub.challenge` - Challenge string from Facebook

**Response:**
Returns the challenge string if verification succeeds.

---

#### POST /webhook
Receive messages from Facebook Messenger.

**Request (from Facebook):**
```json
{
  "object": "page",
  "entry": [
    {
      "messaging": [
        {
          "sender": {"id": "USER_ID"},
          "recipient": {"id": "PAGE_ID"},
          "timestamp": 1234567890,
          "message": {
            "mid": "MESSAGE_ID",
            "text": "Hello"
          }
        }
      ]
    }
  ]
}
```

**Response:**
Returns "OK" with status 200 if processed successfully.

---

### System Management

#### GET /health
Quick health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "chatbot_loaded": true,
  "components": {
    "channel_adapter": "operational",
    "intent_detector": "operational",
    "context_router": "operational",
    "business_rules": "operational",
    "decision_router": "operational",
    "response_composer": "operational",
    "ai_model": "operational"
  }
}
```

---

#### GET /system_health
Comprehensive system health information.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-01T14:30:00Z",
  "components": {
    "channel_adapter": "operational",
    "intent_detector": "operational",
    "context_router": "operational",
    "business_rules": "operational",
    "decision_router": "operational",
    "response_composer": "operational",
    "ai_model": "operational"
  },
  "uptime": "2:30:15",
  "active_users": 5
}
```

---

#### GET /stats
Get basic chatbot statistics (legacy endpoint).

**Response:**
```json
{
  "chatbot_loaded": true,
  "system_health": {
    "status": "healthy",
    "components": {...}
  }
}
```

---

### Analytics & Monitoring

#### GET /analytics
Get system analytics and usage statistics.

**Response:**
```json
{
  "status": "success",
  "analytics": {
    "total_messages": 1523,
    "total_users": 87,
    "average_response_time": 0.45,
    "intent_distribution": {
      "product_search": 456,
      "price_inquiry": 234,
      "order": 123,
      "general": 710
    },
    "channel_distribution": {
      "web": 823,
      "facebook": 650,
      "api": 50
    },
    "success_rate": 0.95
  },
  "timestamp": "2026-03-01T14:30:00Z"
}
```

---

#### GET /conversation_history/:user_id
Get conversation history for a specific user.

**Parameters:**
- `user_id` - User identifier

**Response:**
```json
{
  "user_id": "web_user",
  "conversation_history": [
    {
      "timestamp": "2026-03-01T14:25:00Z",
      "user_message": "Show me laptops",
      "bot_response": "Here are our available laptops...",
      "intent": "product_search"
    },
    {
      "timestamp": "2026-03-01T14:26:30Z",
      "user_message": "What about gaming laptops?",
      "bot_response": "Our gaming laptops include...",
      "intent": "product_search"
    }
  ],
  "message_count": 2
}
```

---

#### GET /
Serve web chat interface.

Returns an HTML page with embedded chat interface for testing.

---

## Request/Response Examples

### Example 1: Product Search

**Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "message": "I need a laptop under 60000 taka"
  }'
```

**Response:**
```json
{
  "response": "আমাদের কাছে ৬০০০০ টাকার মধ্যে নিম্নলিখিত ল্যাপটপ রয়েছে:\n\n1. HP Pavilion 15 - ৫৫,০০০ টাকা\n2. Lenovo IdeaPad - ৫২,০০০ টাকা\n3. Dell Inspiron 15 - ৫৮,০০০ টাকা\n\nকোনটি সম্পর্কে বিস্তারিত জানতে চান?",
  "user_id": "user_123",
  "processing_info": {
    "intent": "product_search",
    "entities": ["laptop", "60000"],
    "budget": 60000,
    "confidence": 0.96
  },
  "success": true
}
```

---

### Example 2: Order Placement

**Request:**
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_456",
    "message": "I want to order HP Pavilion 15",
    "channel": "web"
  }'
```

**Response:**
```json
{
  "success": true,
  "response": "দারুণ! আপনি HP Pavilion 15 অর্ডার করতে চান। দয়া করে আপনার ডেলিভারি ঠিকানা দিন।",
  "user_id": "user_456",
  "processing_info": {
    "intent": "order",
    "entities": ["HP Pavilion 15"],
    "confidence": 0.94,
    "context": {
      "state": "collecting_address",
      "item": "HP Pavilion 15",
      "price": 55000
    }
  },
  "handover": false
}
```

---

### Example 3: Health Check

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "chatbot_loaded": true,
  "components": {
    "channel_adapter": "operational",
    "intent_detector": "operational",
    "context_router": "operational",
    "business_rules": "operational",
    "decision_router": "operational",
    "response_composer": "operational",
    "ai_model": "operational"
  }
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "error": "Error message description",
  "success": false
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Missing or invalid parameters |
| 403 | Forbidden - Invalid verification token |
| 500 | Internal Server Error - System error occurred |

### Common Errors

**Missing Message:**
```json
{
  "error": "No message provided",
  "success": false
}
```

**System Error:**
```json
{
  "error": "Failed to process message",
  "response": "দুঃখিত, আমি এই মুহূর্তে আপনার বার্তা প্রসেস করতে পারছি না।",
  "success": false
}
```

---

## Rate Limiting

Currently, there are no rate limits implemented. Consider implementing rate limiting for production use.

---

## WebSocket Support

WebSocket support is not currently available but can be added for real-time bidirectional communication.

---

## SDK Examples

### Python
```python
import requests

# Send a message
response = requests.post(
    'http://localhost:8000/chat',
    json={
        'user_id': 'python_user',
        'message': 'Show me laptops'
    }
)

data = response.json()
print(data['response'])
```

### JavaScript
```javascript
// Send a message
fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        user_id: 'js_user',
        message: 'Show me laptops'
    })
})
.then(response => response.json())
.then(data => console.log(data.response));
```

### cURL
```bash
# Simple chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "Hello"}'

# Get health status
curl http://localhost:8000/health

# Clear history
curl -X POST http://localhost:8000/clear_history \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test"}'
```

---

## Environment Variables

Required environment variables (in `.env` file):

```env
# Facebook Messenger
PAGE_ACCESS_TOKEN=your_page_access_token
VERIFY_TOKEN=your_verify_token

# Server
PORT=8000

# Model Configuration
GROQ_API_KEY=your_groq_api_key
MODEL_TYPE=groq
GROQ_MODEL=llama-3.1-8b-instant

# RAG Configuration
ENABLE_RAG=true
RAG_TOP_K=3

# Data
DATA_FILE=data/admin_data.json
```

---

## Postman Collection

Import this collection URL to Postman for testing:
```
https://www.postman.com/collections/your-collection-id
```

Or manually create requests using the examples above.

---

## Testing

### Quick Test
```bash
# Start server
python src/api/app.py

# Test in another terminal
curl -X POST http://localhost:8000/test \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

### Web Interface
Open browser: `http://localhost:8000`

### Facebook Messenger Testing
1. Set up webhook: `https://your-domain.com/webhook`
2. Send message to your Facebook Page
3. Check logs for webhook data

---

## Support

For issues or questions:
- Check logs: `logs/` directory
- Review documentation: `docs/` folder
- System health: `GET /health`

---

## Changelog

### Version 1.0 (2026-03-01)
- Initial API release
- Facebook Messenger integration
- Web chat interface
- Multi-language support (English/Bengali)
- RAG-enabled responses
- Analytics and monitoring endpoints

---

**Last Updated:** March 1, 2026
