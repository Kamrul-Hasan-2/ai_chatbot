"""
Chatbot configuration — constants, enums, and API call logger.
"""
import os
import json
import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ChatMode(Enum):
    AI = "ai"
    HUMAN = "human"


AI_ACTIVE_STATUS = "AI Active"
HUMAN_SUPPORT_REQUIRED_STATUS = "Human Support Required"

VALID_INTENTS = {
    'product_search', 'price_query', 'comparison', 'ordering', 'delivery',
    'greeting', 'goodbye', 'thanks', 'complaint', 'faq', 'human_request',
    'buy', 'exit', 'technical_advice', 'hate_speech', 'product_link',
    'seller_query', 'unknown'
}

PRODUCT_RELATED_INTENTS = {'product_search', 'price_query', 'comparison', 'ordering'}

CONTEXT_TTL_SECONDS = 1800

CATEGORY_PROMPT = (
    "Apni kon category khujchen sir? "
    "(যেমন: mobile, laptop, AC, fridge ইত্যাদি)"
)


GROQ_SYSTEM_PROMPT_TEMPLATE = """You are a strict JSON extractor for a Bangladeshi e-commerce chatbot (BDStall).
The user may write in English, Bangla, or Banglish (romanised Bangla). Understand all three equally.
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
- product_search    : user wants to see, find, or browse products.
- price_query       : user is asking about price or cost of a product/category
- comparison        : user asks WHICH product is better or compares options. Key signals: "konti valo", "konta valo", "which is better"
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
Known examples (not exhaustive): {{sample_str}}
- If the message contains a recognisable product type word → ALWAYS set category to that word.
- If the model/title is a well-known product (e.g. iPhone=mobile, RTX 4060=graphics card), infer the category.
- Only leave category="" if truly cannot determine.

BRAND vs CATEGORY:
- brand = manufacturer name (samsung, hp, dell, apple, walton, asus, acer, lenovo).
- category = product type (laptop, mobile, AC, fridge, television, tablet).

is_followup: true ONLY when message has NO product type word AND depends entirely on previous context.

BUDGET PARSING: "50k"=50000, "30 hazar"=30000, "under 20k"→price_max=20000. null if absent.

PREVIOUS CONTEXT (is_followup detection only — do NOT copy into entities):
{{previous_intent}}
"""


def _log_api_call(api_name: str, method: str, url: str, request_payload,
                  status_code: int, duration_ms: int, status: str,
                  response_preview: str = "") -> None:
    try:
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(
            logs_dir, f"api_calls_{datetime.now().strftime('%Y-%m-%d')}.log"
        )
        entry = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "api_name": api_name, "method": method, "url": url,
            "request": request_payload, "status_code": status_code,
            "duration_ms": duration_ms, "result": status,
            "response_preview": (response_preview or "")[:400]
        }
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("API log write failed: %s", e)
