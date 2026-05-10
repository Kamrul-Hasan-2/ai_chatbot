"""
src/models/chatbot_config.py — constants, enums, API keys/URLs, Groq prompt.
All configurable values live here. Nothing else imports os.getenv directly.
"""
import os
import json
import logging
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Enums & status strings ───────────────────────────────────────────────────

class ChatMode(Enum):
    AI    = "ai"
    HUMAN = "human"

AI_ACTIVE_STATUS             = "AI Active"
HUMAN_SUPPORT_REQUIRED_STATUS = "Human Support Required"

# ── Valid Groq intents ────────────────────────────────────────────────────────

VALID_INTENTS = {
    'product_search', 'price_query', 'comparison', 'ordering', 'delivery',
    'greeting', 'goodbye', 'thanks', 'complaint', 'faq', 'human_request',
    'buy', 'exit', 'technical_advice', 'hate_speech', 'product_link',
    'seller_query', 'unknown',
}

PRODUCT_RELATED_INTENTS = {'product_search', 'price_query', 'comparison', 'ordering'}

# ── Context TTL ───────────────────────────────────────────────────────────────

CONTEXT_TTL_SECONDS = 1800

# ── Category prompt ───────────────────────────────────────────────────────────

CATEGORY_PROMPT = (
    "স্যার, আপনি কোন ক্যাটাগরির প্রোডাক্ট খুঁজছেন? "
    "(যেমন: mobile, laptop, AC, fridge, TV ইত্যাদি)"
)

# ── Loop-back suffix appended to informational responses ─────────────────────

LOOP_BACK = "\n\nআর কোনো প্রোডাক্ট বা বিষয়ে সাহায্য করতে পারি? 😊"

# ── API credentials & URLs ────────────────────────────────────────────────────

API_KEY           = os.getenv('BDSTALL_API_KEY',         'mkh677ddd2sxxkkdjff')
SEARCH_URL        = os.getenv('SEARCH_API_URL',          'https://www.bdstall.com/api/chatbot/ai_search/')
DELIVERY_URL      = os.getenv('DELIVERY_API_URL',        'https://www.bdstall.com/api/chatbot/ai_template/')
ASSIGN_AGENT_URL  = os.getenv('ASSIGN_AGENT_API_URL',    'https://www.bdstall.com/api/chatbot/chatbot_assign_agent/')
ASSIGN_AGENT_KEY  = os.getenv('ASSIGN_AGENT_API_KEY',    os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff'))
ASSIGN_BOT_URL    = os.getenv('ASSIGN_BOT_API_URL',      'https://www.bdstall.com/api/chatbot/chatbot_assign_bot/')
RESPONDER_URL     = os.getenv('RESPONDER_API_URL',       'https://www.bdstall.com/api/chatbot/chatbot_responder/')
RESPONDER_KEY     = os.getenv('RESPONDER_API_KEY',       os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff'))
HISTORY_URL       = os.getenv('CHATBOT_HISTORY_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_history/')
SAVE_MESSAGE_URL  = os.getenv('SAVE_MESSAGE_API_URL',    'https://www.bdstall.com/api/chatbot/chatbot_save_message/')
SAVE_MESSAGE_KEY  = os.getenv('SAVE_MESSAGE_API_KEY',    os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff'))
CAT_LIST_URL      = os.getenv('CATLIST_API_URL',         'https://www.bdstall.com/api/chatbot/cat_list/')

try:
    HISTORY_LIMIT = max(1, min(int(os.getenv('CHATBOT_HISTORY_LIMIT', '5')), 20))
except Exception:
    HISTORY_LIMIT = 5

GROQ_API_KEY      = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL        = os.getenv('GROQ_MODEL',        'llama-3.3-70b-versatile')
GROQ_ANSWER_MODEL = os.getenv('GROQ_ANSWER_MODEL', 'llama-3.3-70b-versatile')

# ── Groq system prompt template ───────────────────────────────────────────────

GROQ_SYSTEM_PROMPT_TEMPLATE = """You are a strict JSON extractor for a Bangladeshi e-commerce chatbot (BDStall).
The user may write in English, Bangla, or Banglish (romanised Bangla). Understand all three equally.
SPELLING TOLERANCE: Users frequently mistype. Always interpret the closest plausible product/brand/category:
- "laptp", "leptop", "labtop", "laptoop" → laptop
- "mobilr", "moble", "mobail" → mobile
- "avobe", "abov", "abobe" → above
- "undr", "undre" → under
- "samsng", "samsun", "samsubg" → samsung
- "delll", "del" → dell
- "assus", "asuss" → asus
- "lenovoo", "lenvo" → lenovo
- Apply the same logic to any other misspelled brand, category, or keyword.
Return ONLY valid JSON. No prose, no markdown, no explanation.

SCHEMA:
{{
  "intent": string,
  "entities": {{
    "category": string,
    "brand": string,
    "title": string,
    "price_max": integer or null,
    "price_min": integer or null
  }},
  "missing": array of strings,
  "is_followup": boolean,
  "confidence": number 0-1
}}

INTENT VALUES (pick exactly one):
product_search | price_query | comparison | buy | exit | delivery | greeting | goodbye | thanks | complaint | faq | human_request | technical_advice | hate_speech | seller_query | unknown

INTENT DEFINITIONS:
- product_search    : user wants to see, find, or browse products. Key Banglish signals: "ase" (আছে = is available), "dekhan" (দেখান = show me), "lagbe" (লাগবে = I need), "chai" (চাই = I want), "kono X ase?" (do you have X?). If user mentions a product type + any of these words → product_search.
- price_query       : user is asking about price or cost of a product/category
- comparison        : user asks WHICH product is better or compares options. Key signals: "konti valo", "konta valo", "konti bhalo", "konta bhalo", "which is better", "কোনটা ভালো", "কোনটি ভালো", "সেরা কোনটা", "best konti", "suggest korben"
- buy               : user wants to know HOW to buy or place an order (process question).
- exit              : user is leaving, says later / not now / will come back
- delivery          : user asks about delivery time, charge, or process
- greeting          : hello / hi / salam with no product intent
- goodbye           : farewell with no product intent
- thanks            : thank you messages
- complaint         : refund, scam, broken product, bad experience
- faq               : general questions about the site or policies
- human_request     : user wants to speak to a human agent
- technical_advice  : user asks about a product CAPABILITY, COMPATIBILITY, UPGRADE potential, or PERFORMANCE.
- seller_query      : user wants to SELL products, list items, open a shop, register as vendor
- hate_speech       : abusive language, insults, threats
- unknown           : truly cannot determine

CATEGORY EXTRACTION:
Known examples (not exhaustive): {sample_str}
- If the message contains a recognisable product type word → ALWAYS set category to that word.
- If the model/title is a well-known product (e.g. iPhone=mobile, RTX 4060=graphics card), infer the category.
- Only leave category="" if truly cannot determine.

BRAND vs CATEGORY:
- brand = manufacturer name (samsung, hp, dell, apple, walton, asus, acer, lenovo).
- category = product type (laptop, mobile, AC, fridge, television, tablet).

is_followup: true ONLY when message has NO product type word AND depends entirely on previous context.

BUDGET PARSING: "50k"=50000, "30 hazar"=30000, "under 20k"→price_max=20000. null if absent.

PREVIOUS CONTEXT (is_followup detection only — do NOT copy into entities):
{previous_intent}
"""

# ── API call logger ───────────────────────────────────────────────────────────

def _log_api_call(api_name: str, method: str, url: str, request_payload,
                  status_code: int, duration_ms: int, status: str,
                  response_preview: str = "") -> None:
    try:
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"api_calls_{datetime.now().strftime('%Y-%m-%d')}.log")
        entry = {
            "timestamp":        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "api_name":         api_name,
            "method":           method,
            "url":              url,
            "request":          request_payload,
            "status_code":      status_code,
            "duration_ms":      duration_ms,
            "result":           status,
            "response_preview": str(response_preview or "")[:400],
        }
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("API log write failed: %s", e)
