# AI Template Category Search Endpoint

## Overview
This document describes the new `/api/item/ai_template/` endpoint that integrates with BDStall's search system to provide category-based product searches.

## Endpoint Details

### URL Format
```
GET /api/item/ai_template/?intent=category&category=<CATEGORY>&key=<API_KEY>
```

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `intent` | string | ✅ Yes | Operation type. Currently only supports `category` |
| `category` | string | ✅ Yes | Product category name to search for (e.g., "Laptop", "Desktop PC") |
| `key` | string | ✅ Yes | API key for authentication. Valid keys: `mkh677ddd2sxxk`, `mkh677ddd2sxxkkdjff` |

## Response Formats

### Success Response (Category Found)
```json
{
    "success": true,
    "data": "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/laptop/"
}
```

**Status Code:** `200 OK`

### Error Response (Category Not Found)
```json
{
    "success": false,
    "error": "Category 'invalid_category' not found",
    "message": "Please search with a valid category name"
}
```

**Status Code:** `404 Not Found`

### Error Response (Invalid API Key)
```json
{
    "success": false,
    "error": "Invalid API key"
}
```

**Status Code:** `401 Unauthorized`

### Error Response (Missing Required Parameter)
```json
{
    "success": false,
    "error": "Category parameter is required"
}
```

**Status Code:** `400 Bad Request`

### Error Response (Invalid Intent)
```json
{
    "success": false,
    "error": "Intent 'invalid' not supported. Use 'intent=category'",
    "supported_intents": ["category"]
}
```

**Status Code:** `400 Bad Request`

## Usage Examples

### Example 1: Search for "Laptop" category
```
GET /api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk
```

**Response:**
```json
{
    "success": true,
    "data": "আপনি Laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/laptop/"
}
```

### Example 2: Search for "Desktop PC" category
```
GET /api/item/ai_template/?intent=category&category=Desktop%20PC&key=mkh677ddd2sxxk
```

**Response:**
```json
{
    "success": true,
    "data": "আপনি Desktop PC ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/desktop-pc/"
}
```

### Example 3: Search for "Used Laptop" category
```
GET /api/item/ai_template/?intent=category&category=Used%20Laptop&key=mkh677ddd2sxxk
```

**Response:**
```json
{
    "success": true,
    "data": "আপনি Used Laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/used-laptop/"
}
```

## Features

### 1. **Case-Insensitive Category Matching**
The endpoint normalizes category names for comparison, so it works with:
- `Laptop` ✅
- `laptop` ✅
- `LAPTOP` ✅

### 2. **Category Database**
The endpoint searches against `data/search_intent_items.json` which contains 602+ verified product categories including:
- Laptop variants (Laptop, Used Laptop, cheap Laptop, etc.)
- Desktop products (Desktop PC, Mini PC, etc.)
- Computer components (Processor, RAM, SSD, etc.)
- Peripherals (Mouse, Keyboard, Webcam, etc.)
- Networking equipment (Router, WiFi Adapter, etc.)
- And many more...

### 3. **Automatic URL Generation**
The endpoint automatically generates BDStall URLs by:
- Converting category names to lowercase
- Replacing spaces with hyphens
- Appending to base URL (https://www.bdstall.com/)

### 4. **API Key Validation**
Requests are authenticated using API keys. Valid keys:
- `mkh677ddd2sxxk`
- `mkh677ddd2sxxkkdjff`
- Custom keys via `BDSTALL_API_KEY` environment variable

### 5. **Bengali Language Support**
Responses include Bengali messages with proper formatting and encoding.

## Implementation Details

### Located in
- **File:** `src/api/app_simple.py`
- **Route:** `/api/item/ai_template/`
- **Method:** GET

### Key Functions
- `load_search_intent_items()` - Loads categories from JSON file
- `normalize_category()` - Normalizes category names for comparison
- `find_category_in_list()` - Searches for category in list (case-insensitive)
- `get_category_url()` - Generates BDStall category URL

### Configuration
- **Search Intent File:** `data/search_intent_items.json`
- **Valid API Keys:** Configurable in app_simple.py or via environment variables

## Testing

### Run Tests
```bash
cd c:\Users\BLG\Desktop\ai_chatbot
python tests/test_ai_template_endpoint.py
```

### Test Coverage
- ✅ Valid category search (multiple variations)
- ✅ Case-insensitive matching
- ✅ Multi-word categories
- ✅ Invalid category handling
- ✅ Invalid API key handling
- ✅ Missing parameter handling
- ✅ Invalid intent handling
- ✅ URL format verification

All 8 tests pass successfully!

## API Integration Flow

```
1. Client sends GET request with parameters
   ↓
2. Endpoint validates API key
   ↓
3. Endpoint validates required parameters
   ↓
4. Endpoint validates intent type
   ↓
5. Load search_intent_items.json
   ↓
6. Normalize and search for category
   ✓ If found: Return Bengali message with category URL
   ✗ If not found: Return 404 Not Found error
```

## Error Handling

| Scenario | Status Code | Response |
|----------|------------|----------|
| Invalid API key | 401 | `{"success": false, "error": "Invalid API key"}` |
| Missing category | 400 | `{"success": false, "error": "Category parameter is required"}` |
| Invalid intent | 400 | `{"success": false, "error": "Intent not supported"}` |
| Category not found | 404 | `{"success": false, "error": "Category not found"}` |
| Server error | 500 | `{"success": false, "error": "error message"}` |

## Environment Variables

Optional environment variables:
- `BDSTALL_API_KEY` - Custom API key for authentication

## Notes

- The endpoint logs all activity (successful and failed requests) for debugging
- Category searches are case-insensitive and trimmed of whitespace
- URLs are automatically generated with proper formatting
- All responses include UTF-8 encoding for Bengali text support

## Future Enhancements

Potential for extending the endpoint:
- `intent=search` - Full-text search across categories
- `intent=autocomplete` - Category name auto-completion
- `intent=products` - Return actual product data for category
- Pagination support for large result sets
- Caching mechanism for frequently accessed categories
