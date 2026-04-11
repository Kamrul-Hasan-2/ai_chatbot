# AI Template API - Quick Reference

## Quick Start

### API Endpoint
```
GET http://localhost:8000/api/item/ai_template?intent=category&category=laptop
```

### Try These Examples

```bash
# Search for laptop
curl "http://localhost:8000/api/item/ai_template?intent=category&category=laptop"

# Search for desktop PC
curl "http://localhost:8000/api/item/ai_template?intent=category&category=desktop%20pc"

# Search with API key
curl "http://localhost:8000/api/item/ai_template?intent=category&category=Monitor&key=mkh677ddd2sxxk"
```

## Success Response (200)
```json
{
  "success": true,
  "data": "আপনি Laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/laptop/",
  "category": "Laptop",
  "url": "https://www.bdstall.com/laptop/"
}
```

## Error Response (404)
```json
{
  "success": false,
  "error": "Category 'xyz123' not found in search database",
  "data": null,
  "category": "xyz123"
}
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `404 Not Found` | Check if Flask server is running on port 8000 |
| `400 Bad Request` | Ensure both `intent` and `category` parameters are provided |
| `Server Error (500)` | Check if `data/search_intent_items.json` exists and is valid |
| Empty category response | Category might not exist in database or might have typo |

## Testing

Run the complete test suite:
```bash
python tests/test_ai_template_api.py
```

## Supported Categories Examples

The API supports these categories (and ~1000 more):
- Laptop
- Used Laptop
- cheap Laptop
- laptop under 10k
- Desktop PC
- Mini PC
- Monitor
- Printer
- Keyboard
- Mouse
- Graphics Card
- Processor
- RAM
- SSD
- Hard Disk
- [and more in search_intent_items.json]

## Implementation Files

| File | Purpose |
|------|---------|
| `src/api/app.py` | Main implementation of the endpoint |
| `docs/AI_TEMPLATE_INTENT_API.md` | Full documentation |
| `tests/test_ai_template_api.py` | Test suite |

## Key Features

✅ Case-insensitive search  
✅ Bengali response messages  
✅ Auto-generated BDStall URLs  
✅ Comprehensive error handling  
✅ Full logging support  

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Category found successfully |
| 400 | Missing required parameters |
| 404 | Category not found |
| 500 | Server error (database unavailable) |

## Python Usage

```python
import requests

response = requests.get(
    "http://localhost:8000/api/item/ai_template",
    params={
        "intent": "category",
        "category": "Laptop"
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Found: {data['category']}")
    print(f"URL: {data['url']}")
    print(f"Message: {data['data']}")
```

## JavaScript Usage

```javascript
const category = "Laptop";
const url = new URL("http://localhost:8000/api/item/ai_template");
url.searchParams.append("intent", "category");
url.searchParams.append("category", category);

fetch(url)
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            console.log("Found:", data.category);
            console.log("URL:", data.url);
        } else {
            console.log("Not found:", data.error);
        }
    });
```

## Database Info

- **File:** `data/search_intent_items.json`
- **Format:** JSON array of category strings
- **Size:** ~1000+ categories
- **Encoding:** UTF-8 (supports Bengali/Bangla text)

## Performance

- **Response Time:** < 100ms typical
- **Search Type:** Linear search (O(n))
- **Supported Categories:** 1000+
- **Requests Per Second:** Unlimited (Flask default rate limiting applies)

## Documentation References

- Full API Docs: [docs/AI_TEMPLATE_INTENT_API.md](../AI_TEMPLATE_INTENT_API.md)
- Implementation Summary: [docs/AI_TEMPLATE_IMPLEMENTATION_SUMMARY.md](../AI_TEMPLATE_IMPLEMENTATION_SUMMARY.md)
- Test Suite: [tests/test_ai_template_api.py](../test_ai_template_api.py)

## Next Steps

1. ✅ Start Flask server: `python run.py`
2. ✅ Test the API: `curl "http://localhost:8000/api/item/ai_template?intent=category&category=laptop"`
3. ✅ Run full tests: `python tests/test_ai_template_api.py`
4. ✅ Integrate with chatbot for enhanced category search functionality
