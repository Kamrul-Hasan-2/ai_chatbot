# API Quick Reference

## Base URL
```
http://localhost:8000
```

## Quick Test
```bash
curl -X POST http://localhost:8000/test \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me laptops"}'
```

---

## Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Send message (web interface) |
| `POST` | `/test` | Test endpoint |
| `POST` | `/process` | Detailed message processing |
| `POST` | `/webhook` | Facebook Messenger webhook |
| `GET` | `/webhook` | Verify Facebook webhook |
| `POST` | `/clear_history` | Clear user history |
| `GET` | `/health` | Health check |
| `GET` | `/system_health` | Full system status |
| `GET` | `/stats` | Basic statistics |
| `GET` | `/analytics` | Usage analytics |
| `GET` | `/conversation_history/:user_id` | User history |
| `GET` | `/` | Web chat interface |

---

## Examples

### Chat Message
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "What laptops under 50000?"
  }'
```

### Check Health
```bash
curl http://localhost:8000/health
```

### Get Analytics
```bash
curl http://localhost:8000/analytics
```

### Clear History
```bash
curl -X POST http://localhost:8000/clear_history \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}'
```

---

## Response Format

### Success
```json
{
  "response": "Message response",
  "user_id": "user123",
  "success": true,
  "processing_info": {...}
}
```

### Error
```json
{
  "error": "Error description",
  "success": false
}
```

---

## Status Codes
- `200` - Success
- `400` - Bad Request
- `403` - Forbidden
- `500` - Server Error

---

**Full Documentation:** [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
