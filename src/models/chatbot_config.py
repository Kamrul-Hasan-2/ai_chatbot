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
    'seller_query', 'product_spec_query', 'unknown',
}

PRODUCT_RELATED_INTENTS = {'product_search', 'price_query', 'comparison', 'ordering'}

# ── Context TTL ───────────────────────────────────────────────────────────────

CONTEXT_TTL_SECONDS = 1800

# ── Knowledge intent (Groq-backed answers) rate limit ────────────────────────
# Knowledge questions (technical_advice) consume Groq tokens. Cap at 5/day per
# user; once exceeded the user is handed off to a human agent.
KNOWLEDGE_DAILY_LIMIT = int(os.getenv('KNOWLEDGE_DAILY_LIMIT', '5'))

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
CONDITION_URL     = os.getenv('CONDITION_API_URL',       'https://www.bdstall.com/api/chatbot/ai_template/')
ASSIGN_AGENT_URL  = os.getenv('ASSIGN_AGENT_API_URL',    'https://www.bdstall.com/api/chatbot/chatbot_assign_agent/')
ASSIGN_AGENT_KEY  = os.getenv('ASSIGN_AGENT_API_KEY',    os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff'))
ASSIGN_BOT_URL    = os.getenv('ASSIGN_BOT_API_URL',      'https://www.bdstall.com/api/chatbot/chatbot_assign_bot/')
RESPONDER_URL     = os.getenv('RESPONDER_API_URL',       'https://www.bdstall.com/api/chatbot/chatbot_responder/')
RESPONDER_KEY     = os.getenv('RESPONDER_API_KEY',       os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff'))
HISTORY_URL       = os.getenv('CHATBOT_HISTORY_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_history/')
SAVE_MESSAGE_URL  = os.getenv('SAVE_MESSAGE_API_URL',    'https://www.bdstall.com/api/chatbot/chatbot_save_message/')
SAVE_MESSAGE_KEY  = os.getenv('SAVE_MESSAGE_API_KEY',    os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff'))
CAT_LIST_URL      = os.getenv('CATLIST_API_URL',         'https://www.bdstall.com/api/chatbot/cat_list/')
SPEC_URL          = os.getenv('SPEC_API_URL',            'https://www.bdstall.com/api/item/list_details/')
KNOWLEDGE_URL     = os.getenv('KNOWLEDGE_API_URL',       'https://www.bdstall.com/api/chatbot/knowledge/')
CITY_LIST_URL     = os.getenv('CITY_LIST_API_URL',       'https://www.bdstall.com/api/chatbot/city_list/')
AREA_LIST_URL     = os.getenv('AREA_LIST_API_URL',       'https://www.bdstall.com/api/chatbot/area_list/')
PLACE_ORDER_URL      = os.getenv('PLACE_ORDER_API_URL',      'https://www.bdstall.com/api/chatbot/chatbot_place_order/')
ORDER_STATUS_URL     = os.getenv('ORDER_STATUS_API_URL',     'https://www.bdstall.com/api/chatbot/chatbot_order_status/')
SELLER_REQUEST_URL   = os.getenv('SELLER_REQUEST_API_URL',   'https://www.bdstall.com/api/chatbot/seller_request/')
SUPPORT_CONTACT_URL  = os.getenv('SUPPORT_CONTACT_API_URL',  'https://www.bdstall.com/api/chatbot/support_contact/')

try:
    HISTORY_LIMIT = max(1, min(int(os.getenv('CHATBOT_HISTORY_LIMIT', '5')), 20))
except Exception:
    HISTORY_LIMIT = 5

GROQ_API_KEY      = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL        = os.getenv('GROQ_MODEL',        'llama-3.3-70b-versatile')
GROQ_ANSWER_MODEL = os.getenv('GROQ_ANSWER_MODEL', 'llama-3.3-70b-versatile')
# Vision-capable model for reading customer product photos. Override via env
# if Groq renames/deprecates this model — check the current model list at
# https://console.groq.com/docs/models before assuming this default is stale.
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'meta-llama/llama-4-scout-17b-16e-instruct')

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
product_search | price_query | comparison | buy | exit | delivery | greeting | goodbye | thanks | complaint | faq | human_request | technical_advice | product_spec_query | hate_speech | seller_query | unknown

INTENT DEFINITIONS:
- product_search    : user wants to see, find, or browse products. Key Banglish signals: "ase" (আছে = is available), "dekhan" (দেখান = show me), "lagbe" (লাগবে = I need), "chai" (চাই = I want), "kono X ase?" (do you have X?). If user mentions a product type + any of these words → product_search.
- price_query       : user is asking about price or cost of a product/category
- comparison        : user asks WHICH product is better or compares options. Key signals: "konti valo", "konta valo", "konti bhalo", "konta bhalo", "which is better", "কোনটা ভালো", "কোনটি ভালো", "সেরা কোনটা", "best konti", "suggest korben"
- buy               : user wants to know HOW to buy or place an order (process question). CRITICAL: "kibabe kinbo", "kivabe kinbo", "kibhabe kinbo", "kinte chai", "order korbo kivabe", "payment method", "cash on delivery", "cod", "কিভাবে কিনবো", "কিনতে চাই" → ALWAYS "buy". Never "product_search" for these phrases.
- exit              : user is leaving or deferring — will buy/check later. CRITICAL signals: "pore kinbo", "pore janabo", "pore nibo", "পরে কিনবো", "পরে জানাবো", "ekhon na", "এখন না", "later", "not now", "abar ashbo". Even if "kinbo" appears, if "pore" precedes it → ALWAYS "exit", never "buy".
- delivery          : user asks about delivery time, charge, or process
- greeting          : hello / hi / salam with no product intent
- goodbye           : farewell with no product intent
- thanks            : thank you messages
- complaint         : refund, return, broken/damaged product, seller not responding, wrong item received, bad experience. Key signals: "return korbo", "ফেরত দেবো", "bhanga", "nosto", "seller call dore na", "pathaise", "refund chai"
- faq               : general questions about the site or policies
- human_request     : user wants to speak to a human agent
- technical_advice  : user asks about a product CAPABILITY, COMPATIBILITY, UPGRADE potential, or PERFORMANCE. e.g. "ram upgrade kora jabe ki", "i7 vs i5 difference", "gaming er jonno valo ki". ALSO use this when user sends a PC build spec list (Processor/Motherboard/RAM/Storage/PSU components) asking for advice or confirmation.
- product_spec_query: user asks about a SPECIFIC TECHNICAL SPEC of the product currently on screen. Key signals: "koto gb ram", "ram koto", "display koto", "battery koto mah", "processor ki", "storage koto", "camera koto mp", "weight koto", "specs ki", "full spec", "configuration ki", "কত জিবি র‍্যাম", "ডিসপ্লে কত ইঞ্চি". is_followup=true always. ONLY use this when a product is already on screen — if no product context, use technical_advice instead.
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
- title = specific model name or number ONLY (e.g. "iPhone 15", "RTX 4060", "Galaxy S24"). NEVER put Bengali words, Banglish filler words (khujtasi, lagbe, chai, ase, dekhan), or general descriptions in title. Leave title="" if no specific model is mentioned.

is_followup: true ONLY when message has NO product type word AND depends entirely on previous context.

BUDGET PARSING: "50k"=50000, "30 hazar"=30000, "under 20k"→price_max=20000. null if absent.

FEW-SHOT EXAMPLES (treat as ground truth — match these patterns):

Example 1 — "kibhabe kinbo" → buy (asking the purchase process, never product_search)
{{"intent":"buy","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.95}}

Example 2 — "konti valo hobe" → comparison (asking which is better, not greeting)
{{"intent":"comparison","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":true,"confidence":0.92}}

Example 3 — "samsung phone dekhao 20k modde" → product_search with budget
{{"intent":"product_search","entities":{{"category":"mobile","brand":"samsung","title":"","price_max":20000,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.95}}

Example 4 — "20k upore" (pure budget refinement) → product_search, NO title
{{"intent":"product_search","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":20000}},"missing":[],"is_followup":true,"confidence":0.9}}

Example 5 — "30k er modde laptop chai" → product_search under budget
{{"intent":"product_search","entities":{{"category":"laptop","brand":"","title":"","price_max":30000,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.95}}

Example 6 — "hello phone dekhao" → product_search (NOT greeting — has search words + product)
{{"intent":"product_search","entities":{{"category":"mobile","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.9}}

Example 7 — "amar budget 25000" (just a number, no product type) → product_search, is_followup=true
{{"intent":"product_search","entities":{{"category":"","brand":"","title":"","price_max":25000,"price_min":null}},"missing":[],"is_followup":true,"confidence":0.85}}

Example 8 — "order korbo kivabe" → buy
{{"intent":"buy","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.95}}

Example 9 — "shera konta" (which is the best) → comparison
{{"intent":"comparison","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":true,"confidence":0.9}}

Example 10 — "ami sell korte chai" → seller_query
{{"intent":"seller_query","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.95}}

Example 11 — "Galaxy A55 ase ki?" → product_search with title
{{"intent":"product_search","entities":{{"category":"mobile","brand":"samsung","title":"Galaxy A55","price_max":null,"price_min":null}},"missing":[],"is_followup":false,"confidence":0.95}}

Example 12 — "khujchi" alone (filler, no product) → unknown
{{"intent":"unknown","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":["product"],"is_followup":false,"confidence":0.5}}

Example 13 — "eita te koto gb ram ase" (product on screen, asking spec) → product_spec_query
{{"intent":"product_spec_query","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":true,"confidence":0.95}}

Example 14 — "display size koto" (product on screen) → product_spec_query
{{"intent":"product_spec_query","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":true,"confidence":0.95}}

Example 15 — "ram upgrade kora jabe ki" → technical_advice (capability question, not a spec lookup)
{{"intent":"technical_advice","entities":{{"category":"","brand":"","title":"","price_max":null,"price_min":null}},"missing":[],"is_followup":true,"confidence":0.9}}

USER PROFILE (use ONLY to disambiguate vague follow-ups — never copy into entities):
{user_profile_block}

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
