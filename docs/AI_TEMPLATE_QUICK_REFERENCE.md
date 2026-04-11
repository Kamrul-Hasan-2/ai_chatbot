# AI Template Endpoint - Quick Reference

## 🚀 Quick Start

### Basic Request
```
GET /api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk
```

### Success Response
```json
{
    "success": true,
    "data": "আপনি Laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/laptop/"
}
```

## 📋 Parameters

| Name | Required | Example | Notes |
|------|----------|---------|-------|
| `intent` | ✅ | `category` | Only value supported: `category` |
| `category` | ✅ | `Laptop` | Case-insensitive, supports spaces |
| `key` | ✅ | `mkh677ddd2sxxk` | API authentication key |

## 🎯 Common Categories

| Category | Works? | Example |
|----------|--------|---------|
| Laptop | ✅ | https://www.bdstall.com/laptop/ |
| Desktop PC | ✅ | https://www.bdstall.com/desktop-pc/ |
| Used Laptop | ✅ | https://www.bdstall.com/used-laptop/ |
| Mouse | ✅ | https://www.bdstall.com/mouse/ |
| Mobile Phone | ✅ | https://www.bdstall.com/mobile-phone/ |
| Graphics Card | ✅ | https://www.bdstall.com/graphics-card/ |

👉 Browse [data/search_intent_items.json](../data/search_intent_items.json) for all 602 supported categories

## 🔑 Valid API Keys

```
mkh677ddd2sxxk
mkh677ddd2sxxkkdjff
```

## ✅ Success Conditions

- ✅ Category found in database
- ✅ Status code: **200 OK**
- ✅ Returns Bengali message with category URL

## ❌ Error Codes

| Code | Reason | Solution |
|------|--------|----------|
| **400** | Missing/invalid parameter | Check intent, category, key parameters |
| **401** | Invalid API key | Use valid API key |
| **404** | Category not found | Verify category name in search_intent_items.json |
| **500** | Server error | Check server logs |

## 💡 Usage Tips

### 1. URL Encoding
Spaces must be encoded as `%20`:
```
category=Desktop%20PC
```

### 2. Case-Insensitive
All these work:
- `Laptop` ✅
- `laptop` ✅
- `LAPTOP` ✅
- `LaPtOp` ✅

### 3. Category with Numbers
Works fine:
```
category=laptop%20under%2010k
```

### 4. Using cURL
```bash
curl "http://localhost:5000/api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk"
```

### 5. Using Python
```python
import requests

url = "http://localhost:5000/api/item/ai_template/"
params = {
    "intent": "category",
    "category": "Laptop",
    "key": "mkh677ddd2sxxk"
}
response = requests.get(url, params=params)
data = response.json()
print(data['data'])  # Bengali message with link
```

### 6. Using JavaScript/Fetch
```javascript
fetch('/api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk')
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            console.log(data.data);  // Bengali message
        }
    });
```

## 📊 Response Examples

### ✅ Found: Laptop
```json
{
    "success": true,
    "data": "আপনি Laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/laptop/"
}
```

### ✅ Found: Desktop PC
```json
{
    "success": true,
    "data": "আপনি Desktop PC ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/desktop-pc/"
}
```

### ❌ Not Found
```json
{
    "success": false,
    "error": "Category 'InvalidCategory' not found",
    "message": "Please search with a valid category name"
}
```

### ❌ Invalid API Key
```json
{
    "success": false,
    "error": "Invalid API key"
}
```

### ❌ Missing Category
```json
{
    "success": false,
    "error": "Category parameter is required"
}
```

## 🔧 Testing

### Run Python Tests
```bash
cd c:\Users\BLG\Desktop\ai_chatbot
python tests/test_ai_template_endpoint.py
```

### Run PowerShell Tests
```powershell
cd c:\Users\BLG\Desktop\ai_chatbot
.\tests\test_ai_template_curl.ps1
```

## 📚 Full Documentation
See [AI_TEMPLATE_ENDPOINT.md](AI_TEMPLATE_ENDPOINT.md) for complete documentation

## 🔍 Supported Categories

The endpoint supports 602+ categories including:
- **Laptops:** Laptop, Used Laptop, cheap Laptop, laptop under 10k-60k
- **Desktops:** Desktop PC, Mini PC, PC Builder
- **Components:** Processor, Motherboard, RAM, SSD, Graphics Card, etc.
- **Peripherals:** Mouse, Keyboard, Monitor, Webcam, etc.
- **Networking:** Router, WiFi Adapter, Network Switch, etc.
- **Mobile:** Mobile Phone, Tablet, Smartphone accessories
- **And 500+ more...**

## 🎓 Examples

### Search Laptop
```
/api/item/ai_template/?intent=category&category=Laptop&key=mkh677ddd2sxxk
```

### Search Mobile Phone
```
/api/item/ai_template/?intent=category&category=Mobile%20Phone&key=mkh677ddd2sxxk
```

### Search Graphics Card
```
/api/item/ai_template/?intent=category&category=Graphics%20Card&key=mkh677ddd2sxxk
```

## 📝 HTTP Verbs

- **GET** ✅ Supported
- **POST** ❌ Not supported
- **PUT** ❌ Not supported
- **DELETE** ❌ Not supported

## 🌐 Deployment

- **Host:** BDStall API server
- **Base Path:** `/api/item/ai_template/`
- **Method:** GET only
- **Authentication:** API key via `key` parameter

## 📞 Support

For issues or questions, refer to:
1. [AI_TEMPLATE_ENDPOINT.md](AI_TEMPLATE_ENDPOINT.md) - Full documentation
2. [app_simple.py](../src/api/app_simple.py) - Source code
3. [test_ai_template_endpoint.py](test_ai_template_endpoint.py) - Test examples
