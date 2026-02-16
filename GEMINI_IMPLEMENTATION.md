# Gemini API Chatbot Implementation Guide

## ✅ What's Been Implemented

### 1. **Gemini API Integration**
- Switched from Qwen2-VL (local model) to Google Gemini API
- Using `gemini-2.0-flash` for faster and better responses
- Proper error handling and user-friendly error messages

### 2. **Human-Like Conversations**
- Improved system prompts for natural, friendly responses
- Warm personality traits (helpful, patient, conversational)
- Appropriate use of Bengali language and emojis
- Proper addressing with "স্যার/ভাই" and "আপা/ম্যাম"

### 3. **Fallback Response System**
- Automatic fallback when Gemini API is unavailable
- Intelligent keyword-based responses
- Covers common queries: greetings, orders, delivery, payment, returns, support
- Seamlessly integrated into the chatbot

### 4. **Improved Error Handling**
- Specific error detection (quota exceeded, invalid API key, etc.)
- User-friendly Bengali error messages
- Graceful degradation to fallback responses

## 🔧 Configuration

### `.env` File
```dotenv
GEMINI_API_KEY=AIzaSyBL4Qfi-giS0wU-spbCSiY66oXo8DDpL14
MODEL_TYPE=gemini
GEMINI_MODEL=gemini-2.0-flash
```

### Key Files
- `gemini_model.py` - Gemini API handler with human-like responses
- `fallback_handler.py` - Keyword-based fallback responses
- `chatbot.py` - Updated to use both Gemini and fallback
- `requirements.txt` - Updated dependencies (google-genai)

## 🚀 How It Works

### Response Flow:
1. **CSV Database** - Check for exact matches first (fastest)
2. **RAG Store** - Retrieve relevant context from knowledge base
3. **Gemini API** - Generate intelligent, human-like responses
4. **Fallback** - If API fails, use keyword-based responses

### Example Conversations:

**User:** "আলাইকুম!"
**Bot:** "আসসালামু আলাইকুম! 👋 স্বাগতম BDStall.com এ। আমি কীভাবে আপনাকে সাহায্য করতে পারি?"

**User:** "অর্ডার করব কিভাবে?"
**Bot:** "অর্ডার করা খুবই সহজ! 😊 আপনি অ্যাপ বা ওয়েবসাইট থেকে পণ্য নির্বাচন করুন এবং চেকআউট করুন। ✓"

**User:** "ডেলিভারি কত সময়?"
**Bot:** "আমরা ঢাকায় ২৪ ঘণ্টার মধ্যে এবং দেশব্যাপী ৩-৫ দিনে ডেলিভারি দিই। 🎁"

## ⚠️ API Quota Note

The free tier Gemini API has usage limits. If you see "সার্ভার মোমেন্টে ব্যস্ত" (Server is busy), it means:

**Option 1: Wait for Quota Reset**
- Free tier resets every 24 hours
- Wait a few hours and try again

**Option 2: Set Up Paid API**
1. Go to https://ai.google.dev/pricing
2. Set up billing with a credit card
3. Your quota will increase significantly
4. Much more reliable for production use

**Option 3: Use Fallback Mode**
- The fallback handler still works during API downtime
- Provides good responses for common questions
- Ensures your chatbot stays operational

## 🧪 Testing

### Test the Fallback Handler:
```bash
python -c "
from fallback_handler import FallbackResponder
responder = FallbackResponder()
print(responder.get_response('আমি অর্ডার করব কিভাবে?'))
"
```

### Test with Gemini:
```bash
python app.py
```

### Test Responses:
- Try: "আলাইকুম" (greeting)
- Try: "অর্ডার করব কিভাবে?" (order question)
- Try: "ডেলিভারি কত দিন?" (delivery question)
- Try: "পেমেন্ট অপশন?" (payment question)

## 📊 Fallback Keywords Covered

| Category | Keywords Detected |
|----------|-------------------|
| **Greetings** | আলাইকুম, হ্যালো, নমস্কার, হাই |
| **Orders** | অর্ডার, কিনব, কিনতে, কেনাকাটা |
| **Delivery** | ডেলিভারি, পাঠান, কখন আসবে |
| **Payment** | পেমেন্ট, পে, টাকা, মূল্য |
| **Returns** | রিটার্ন, রিফান্ড, পরিবর্তন |
| **Support** | সাপোর্ট, সমস্যা, সাহায্য, যোগাযোগ |

## 🎯 Next Steps

1. **For Better Responses**: Set up paid Gemini API with billing
2. **For More Keywords**: Add to `fallback_handler.py`
3. **For Custom Logic**: Update `chatbot.py`'s `get_response()` method
4. **For RAG Improvement**: Update knowledge base in `data/knowledge/`

## 📞 Support

If the chatbot still isn't working:
1. Check `.env` file has correct API key
2. Verify internet connection
3. Check logs for error messages
4. Try fallback responses work (they should always work)
5. Consider setting up paid API tier

---

**Last Updated:** February 14, 2026
**Status:** ✅ Ready for Production (with API quota consideration)
