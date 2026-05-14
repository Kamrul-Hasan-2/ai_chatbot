"""
src/services/chatbot_service.py — orchestrator.

Flow (strict order):
  1. load_context(user_id)
  2. detect_intent(message, ...)
  3. merge_context(groq_result, prev_ctx, ...)
  4. handle_intent(intent, ctx, ...)
  5. Response built and returned (caller's save_message does persistence)

Entry point: process_message(user_id, message) → dict
"""
import os
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

from models.chatbot_config import (
    ChatMode, AI_ACTIVE_STATUS, HUMAN_SUPPORT_REQUIRED_STATUS,
    GROQ_API_KEY, GROQ_MODEL, GROQ_ANSWER_MODEL, LOOP_BACK,
)
from services.api_client_service import (
    check_responder_type, assign_agent, assign_bot,
    fetch_history, fetch_categories,
)
from repositories.state_repository import (
    load_context, save_last_intent, get_last_intent,
    get_product_url, clear_product_state, load_faq_db,
    set_session_category, get_session_category,
)
from services.intent_service import (
    detect_intent, merge_context,
    resolve_category, normalize_payload,
)
from services.intent_handlers_service import (
    handle_greeting, handle_goodbye, handle_thanks, handle_exit,
    handle_buy, handle_comparison, handle_delivery, handle_faq,
    handle_technical_advice, handle_product_search, handle_price_query,
    handle_url_message, handle_product_detail_followup, handle_fallback,
    handle_clarification_selection,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Startup: Groq client, categories, FAQ DB ──────────────────────────────────

_groq_client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq) else None
if not _groq_client:
    logger.warning("Groq not available — fallback mode active")

_categories: List[Dict] = []
_faq_db:     List[Dict] = []


def _boot() -> None:
    global _categories, _faq_db
    _categories = fetch_categories()
    _faq_db     = load_faq_db()
    logger.info("Booted — %d categories, %d FAQ rows", len(_categories), len(_faq_db))


_boot()

# ── Blocked automated message guard ──────────────────────────────────────────

_BLOCKED_PHRASES = [
    'bdstall.com-এ আপনাকে স্বাগতম',
    'আপনার মেসেজ এর জন্য ধন্যবাদ',
    'খুব শীঘ্রই bdstall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে',
]


def _is_automated(message: str) -> bool:
    text = str(message or '').strip().lower()
    return sum(1 for p in _BLOCKED_PHRASES if p in text) >= 2


# ── Response builder ──────────────────────────────────────────────────────────

def _build_response(user_id: str, handler_result: Dict,
                    mode: ChatMode, conversation_status: str,
                    processing_time: float) -> Dict[str, Any]:
    save_last_intent(user_id, handler_result.get('intent', 'unknown'))
    result: Dict[str, Any] = {
        'response':            handler_result.get('response', ''),
        'mode':                mode.value,
        'intent':              handler_result.get('intent', 'unknown'),
        'intent_content':      handler_result.get('intent_content', {}),
        'conversation_status': conversation_status,
        'products':            handler_result.get('products', []),
        'processing_time':     round(processing_time, 3),
    }
    link_buttons = handler_result.get('link_buttons')
    if link_buttons:
        result['link_buttons'] = link_buttons
    return result


def _handoff(user_id: str, intent_name: str, response_text: str,
             start_time: datetime) -> Dict[str, Any]:
    assign_agent(user_id, intent_name)
    ic = normalize_payload(load_context(user_id))
    handler_result = {'response': response_text, 'intent': intent_name,
                      'intent_content': ic, 'products': []}
    return _build_response(user_id, handler_result,
                           ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                           (datetime.now() - start_time).total_seconds())


# ── Main entry ────────────────────────────────────────────────────────────────

def process_message(user_id: str, message: str) -> Dict[str, Any]:
    start_time = datetime.now()
    logger.info("user=%s msg=%r", user_id, message)

    try:
        # Blocked automated template
        if _is_automated(message):
            ic = normalize_payload(load_context(user_id))
            return _build_response(user_id,
                {'response': '', 'intent': 'ignored_automated_template',
                 'intent_content': ic, 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds())

        # Human mode check
        if check_responder_type(user_id) == 'agent':
            ic = normalize_payload(load_context(user_id))
            return _build_response(user_id,
                {'response': '', 'intent': 'human_mode_active',
                 'intent_content': ic, 'products': []},
                ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                (datetime.now() - start_time).total_seconds())

        # URL in message
        url_match = re.search(r'https?://[^\s]+', message)
        if url_match:
            prev   = load_context(user_id)
            ic_ctx = normalize_payload(prev)
            flat_ctx = {
                'category':  ic_ctx.get('cat', ''),
                'brand':     ic_ctx.get('brand', ''),
                'title':     ic_ctx.get('title', ''),
                'price_max': ic_ctx.get('price_max'),
                'price_min': ic_ctx.get('price_min'),
            }
            result = handle_url_message(flat_ctx, user_id, message, url_match.group(0))
            return _build_response(user_id, result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds())

        # Product detail follow-up
        product_url = get_product_url(user_id)
        if not product_url:
            prev = load_context(user_id)
            product_url = prev.get('product_url', '')
        if product_url:
            detail = handle_product_detail_followup({}, user_id, message, product_url)
            if detail:
                return _build_response(user_id, detail, ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds())

        # Clarification selection — user picks a numbered product after clarification prompt
        if get_last_intent(user_id) == 'product_clarification':
            selected = handle_clarification_selection(user_id, message)
            if selected:
                return _build_response(user_id, selected, ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds())

        # ── STEP 1: load_context ─────────────────────────────────────────────
        prev_ctx = load_context(user_id)

        # ── STEP 2: detect_intent ────────────────────────────────────────────
        history     = fetch_history(user_id)
        cat_names   = [c['category_name'] for c in _categories]
        groq_result = detect_intent(message, history, prev_ctx,
                                    cat_names, _groq_client, GROQ_MODEL)

        # Resolve extracted category against canonical list
        raw_cat = groq_result['entities'].get('category', '')
        if raw_cat:
            resolved = resolve_category(raw_cat, _categories)
            groq_result['entities']['category'] = resolved
        else:
            # Groq missed category — scan message directly
            from services.intent_service import resolve_category_from_message
            scanned = resolve_category_from_message(message, _categories)
            if scanned:
                groq_result['entities']['category'] = scanned
                # Promote unknown → product_search when we found a category
                if groq_result['intent'] == 'unknown':
                    groq_result['intent'] = 'product_search'

        msg_lower = message.lower().strip()

        # Budget post-correction: Groq sometimes flips over→max. Re-run regex
        # extraction and override when the message has explicit over/under signals.
        from services.intent_service import extract_budget_range
        _OVER_SIGNALS = ('upore', 'উপরে', 'beshi', 'বেশি', 'above', 'over',
                         'more than', 'er upore', 'er beshi', 'minimum',
                         'theke beshi', 'theke upore', 'avobe')
        _UNDER_SIGNALS = ('under', 'within', 'modde', 'মধ্যে', 'এর মধ্যে',
                          'below', 'less than', 'er modde', 'er vitor', 'vitor')
        has_over = any(s in msg_lower for s in _OVER_SIGNALS)
        has_under = any(s in msg_lower for s in _UNDER_SIGNALS)
        if has_over or has_under:
            regex_budget = extract_budget_range(message)
            r_min, r_max = regex_budget.get('min_price'), regex_budget.get('max_price')
            if has_over and r_min is not None:
                groq_result['entities']['price_min'] = r_min
                groq_result['entities']['price_max'] = None
            elif has_under and r_max is not None:
                groq_result['entities']['price_max'] = r_max
                groq_result['entities']['price_min'] = None

        # Hard override: search words + brand/category = product_search, never greeting
        _SEARCH_OVERRIDE_WORDS = {
            'dekhan', 'dekhao', 'দেখান', 'দেখাও', 'lagbe', 'লাগবে',
            'ase', 'আছে', 'chai', 'চাই', 'khujchi', 'khujtasi', 'show me',
        }
        if groq_result['intent'] == 'greeting' and any(w in msg_lower for w in _SEARCH_OVERRIDE_WORDS):
            groq_result['intent'] = 'product_search'

        # Hard override: comparison/recommendation words → comparison, never greeting
        _COMPARISON_OVERRIDE_WORDS = {
            'konti', 'konta', 'kunti', 'kunta', 'কোনটা', 'কোনটি',
            'konti valo', 'konta valo', 'konti bhalo', 'konta bhalo',
            'কোনটা ভালো', 'কোনটি ভালো', 'valo hobe', 'bhalo hobe',
            'ভালো হবে', 'better', 'best', 'which one', 'recommend',
            'suggest', 'shera', 'সেরা',
        }
        if (groq_result['intent'] in ('greeting', 'unknown')
                and any(w in msg_lower for w in _COMPARISON_OVERRIDE_WORDS)):
            groq_result['intent'] = 'comparison'

        # Hard override: buy-process keywords always → buy, regardless of Groq
        _BUY_SIGNALS = {
            'how to buy', 'how to order', 'how to purchase',
            'kibabe kinbo', 'kivabe kinbo', 'kibhabe kinbo',
            'kibabe order', 'kivabe order', 'order korbo kibabe', 'order korbo kivabe',
            'kinte chai', 'kinbo kibabe', 'kinbo kivabe',
            'কিভাবে কিনবো', 'কিনতে চাই', 'কিভাবে অর্ডার',
            'payment method', 'cash on delivery', ' cod ',
        }
        if any(sig in msg_lower for sig in _BUY_SIGNALS):
            groq_result['intent'] = 'buy'

        logger.info("Intent=%s entities=%s followup=%s",
                    groq_result['intent'], groq_result['entities'],
                    groq_result['is_followup'])

        # ── STEP 3: merge_context ────────────────────────────────────────────
        def _clear():
            clear_product_state(user_id)

        merged = merge_context(groq_result, prev_ctx, groq_result['intent'], _clear)

        # Inherit category for non-product intents when still empty
        if not merged.get('category'):
            # Session memory is more reliable than DB (DB may have stale category)
            inherited = (get_session_category(user_id)
                         or prev_ctx.get('category') or prev_ctx.get('cat', ''))
            if inherited and groq_result['intent'] in (
                'comparison', 'technical_advice', 'price_query',
                'faq', 'unknown', 'seller_query', 'product_search',
            ):
                merged['category'] = inherited

        # Promote unknown → product_search when category is now known
        if groq_result['intent'] == 'unknown' and merged.get('category'):
            groq_result['intent'] = 'product_search'

        # Clear title if it IS a Banglish filler word (whole-word match only)
        _FILLER_WORDS = {
            'khujtasi', 'khujchi', 'lagbe', 'chai', 'ase', 'nibo', 'dekhan',
            'dekhao', 'bolun', 'jani', 'bolen', 'please', 'kindly',
            'apnader', 'apnar', 'amader', 'amra', 'ami', 'apni',
        }
        title_val = (merged.get('title') or '').lower().strip()
        # Split title into words and check if ALL words are filler — not substring match
        if title_val:
            title_words = set(title_val.split())
            if title_words and title_words.issubset(_FILLER_WORDS):
                merged['title'] = ''

        # Save known category to session memory whenever we have one
        if merged.get('category'):
            set_session_category(user_id, merged['category'])

        # Pure budget refinement: if the current message is essentially just a
        # budget phrase (no new product description), drop the stale inherited
        # title so the search isn't locked to the previous turn's specifics.
        _budget_only_re = re.compile(
            r'^[\s\W]*(?:'
            r'(?:under|within|modde|budget|er modde|er vitor|vitor|মধ্যে|এর মধ্যে|below|less than|'
            r'over|above|avobe|upore|উপরে|বেশি|beshi|more than|er upore|er beshi|minimum|'
            r'amar budget|budget|দাম|price|taka|টাকা|takar|টাকার)'
            r'[\s\W]*)*'
            r'(?:\d+(?:\.\d+)?)\s*'
            r'(?:k|tk|taka|হাজার|টাকা|hazar|lakh|lac|lacs|lakhs|লাখ|লক্ষ|takar|টাকার)?\s*'
            r'(?:upore|উপরে|beshi|বেশি|above|over|er upore|er beshi|'
            r'modde|vitor|মধ্যে|এর মধ্যে|er modde|er vitor|within|under|below|'
            r'taka|টাকা|takar|টাকার)?'
            r'[\s\W]*$',
            re.IGNORECASE,
        )
        if _budget_only_re.match(msg_lower):
            stale = merged.get('title') or merged.get('prev_title')
            if stale:
                logger.info("Pure budget refinement — clearing stale title %r", stale)
            merged['title'] = ''
            merged['prev_title'] = ''

        # Budget follow-up: inherit prev category and force fresh product_search
        has_budget = (merged.get('price_max') is not None or merged.get('price_min') is not None)
        if has_budget and not merged.get('category'):
            # Session memory first (most reliable), then DB context
            prev_cat = (get_session_category(user_id)
                        or prev_ctx.get('category') or prev_ctx.get('cat', ''))
            if not prev_cat:
                from repositories.state_repository import get_product_context
                cached_products = get_product_context(user_id)
                if cached_products:
                    first_title = (cached_products[0].get('title') or '').lower()
                    for cat_rec in _categories:
                        cname = cat_rec['category_name'].lower()
                        if len(cname) >= 4 and cname in first_title:
                            prev_cat = cat_rec['category_name']
                            break
            if prev_cat:
                merged['category'] = prev_cat
        if has_budget and merged.get('category') and groq_result['intent'] not in ('buy', 'greeting', 'goodbye', 'thanks', 'exit', 'delivery', 'faq', 'complaint', 'human_request', 'seller_query', 'hate_speech'):
            groq_result['intent'] = 'product_search'

        # ── STEP 4: handle_intent ────────────────────────────────────────────
        handler_result = _dispatch(groq_result['intent'], merged, user_id, message)

        # ── STEP 5: build and return (persistence done by caller) ────────────
        return _build_response(user_id, handler_result, ChatMode.AI, AI_ACTIVE_STATUS,
                               (datetime.now() - start_time).total_seconds())

    except Exception as e:
        logger.error("process_message error: %s", e, exc_info=True)
        return {
            'response': "দুঃখিত স্যার, একটি সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।" + LOOP_BACK,
            'mode': 'ai', 'intent': 'system_error', 'intent_content': {},
            'conversation_status': AI_ACTIVE_STATUS, 'products': [],
            'processing_time': round((datetime.now() - start_time).total_seconds(), 3),
            'error': str(e),
        }


# ── Intent dispatch ───────────────────────────────────────────────────────────

_HANDOFF_MAP = {
    'seller_query':  (
        "স্যার, বিক্রয় সংক্রান্ত বিষয়ে আমাদের একজন প্রতিনিধি আপনাকে সাহায্য করবেন।",
        'seller_query'),
    'hate_speech':   (
        "স্যার, অনুগ্রহ করে ভদ্র ভাষায় কথা বলুন। আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।",
        'hate_speech'),
    'human_request': (
        "স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।" + LOOP_BACK,
        'explicit_human_request'),
    'complaint':     (
        "স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি এখনই আপনার সাথে যোগাযোগ করবেন।",
        'complaint_handoff'),
}


def _dispatch(intent: str, ctx: Dict, user_id: str, message: str) -> Dict:
    # Downgrade misclassified seller_query: a buyer asking "where is X sold" is
    # a location/marketplace question, not a seller-onboarding request.
    if intent == 'seller_query':
        msg_l = (message or '').lower()
        _BUYER_LOCATION_SIGNALS = (
            'কোথায়', 'kothay', 'kothai', 'where',
            'কোন জায়গায়', 'kon jaygay', 'kon jayga',
        )
        if any(s in msg_l for s in _BUYER_LOCATION_SIGNALS):
            from services.intent_handlers_service import _SHOWROOM_RESPONSE
            ic = normalize_payload(load_context(user_id))
            return {'response': _SHOWROOM_RESPONSE + LOOP_BACK,
                    'intent': 'faq_showroom', 'intent_content': ic, 'products': []}

    if intent in _HANDOFF_MAP:
        text, handoff_intent = _HANDOFF_MAP[intent]
        assign_agent(user_id, handoff_intent)
        ic = normalize_payload(load_context(user_id))
        return {'response': text, 'intent': handoff_intent,
                'intent_content': ic, 'products': []}

    if intent == 'greeting':
        return handle_greeting(ctx, user_id, message)
    if intent == 'goodbye':
        return handle_goodbye(ctx, user_id, message)
    if intent == 'thanks':
        return handle_thanks(ctx, user_id, message)
    if intent == 'exit':
        return handle_exit(ctx, user_id, message)
    if intent == 'buy':
        return handle_buy(ctx, user_id, message)
    if intent == 'comparison':
        return handle_comparison(ctx, user_id, message)
    if intent == 'delivery':
        return handle_delivery(ctx, user_id, message, _faq_db)
    if intent == 'faq':
        return handle_faq(ctx, user_id, message, _faq_db)
    if intent == 'technical_advice':
        return handle_technical_advice(ctx, user_id, message,
                                       _categories, _groq_client, GROQ_ANSWER_MODEL)
    if intent == 'price_query':
        return handle_price_query(ctx, user_id, message)
    if intent == 'product_search':
        return handle_product_search(ctx, user_id, message)

    return handle_fallback(ctx, user_id, message, _faq_db)


# ── Convenience wrappers (used by app_simple.py / controllers) ────────────────

def get_user_mode(user_id: str) -> str:
    return 'human' if check_responder_type(user_id) == 'agent' else 'ai'


def switch_to_human(user_id: str) -> None:
    assign_agent(user_id, 'manual_switch')


def switch_to_ai(user_id: str) -> None:
    assign_bot(user_id)


# ── Compatibility shim ────────────────────────────────────────────────────────

class SimpleChatbot:
    """Thin wrapper around module-level functions for legacy callers."""

    def __init__(self):
        from models.chatbot_config import SEARCH_URL
        self.api_url = SEARCH_URL
        self.groq_client = _groq_client

    @property
    def database(self):
        return _faq_db

    def process_message(self, user_id: str, message: str) -> dict:
        return process_message(user_id, message)

    def get_user_mode(self, user_id: str) -> str:
        return get_user_mode(user_id)

    def switch_to_human(self, user_id: str) -> None:
        switch_to_human(user_id)

    def switch_to_ai(self, user_id: str) -> None:
        switch_to_ai(user_id)
