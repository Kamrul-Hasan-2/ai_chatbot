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
    fetch_history, fetch_categories, fetch_return_policy, fetch_faq_db,
    invalidate_user_cache,
)
from repositories.state_repository import (
    load_context, save_last_intent, get_last_intent,
    get_product_url, clear_product_state, load_faq_db,
    set_session_category, get_session_category,
    load_user_profile, save_user_profile,
    set_pending_question, get_pending_question,
)
from services.intent_service import (
    detect_intent, merge_context,
    resolve_category, normalize_payload,
    apply_post_groq_overrides, resolve_category_from_message,
)
from services.intent_handlers_service import (
    handle_greeting, handle_goodbye, handle_thanks, handle_exit,
    handle_buy, handle_comparison, handle_delivery, handle_faq,
    handle_technical_advice, handle_product_search, handle_price_query,
    handle_url_message, handle_product_detail_followup, handle_fallback,
    handle_clarification_selection, handle_product_spec_query,
    handle_order_status,
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
    _faq_db     = fetch_faq_db()   # live from API, falls back to [] on failure
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

# Once an intent is detected, responses are emitted from formatted templates
# only — Groq is reserved for the knowledge (technical_advice) intent. The
# humanizer is intentionally disabled.

def _build_response(user_id: str, handler_result: Dict,
                    mode: ChatMode, conversation_status: str,
                    processing_time: float,
                    user_message: str = '',
                    profile=None) -> Dict[str, Any]:
    save_last_intent(user_id, handler_result.get('intent', 'unknown'))

    response_text = handler_result.get('response', '')
    intent = handler_result.get('intent', 'unknown')

    result: Dict[str, Any] = {
        'response':            response_text,
        'mode':                mode.value,
        'intent':              intent,
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


def _observe_and_save(user_id: str, profile, message: str,
                      intent: str, ctx: Dict) -> None:
    """Update the rolling user profile from one turn and persist it.

    Never raises — profile updates must not break the user-facing reply.
    """
    try:
        profile.observe_message(
            message=message,
            intent=intent or None,
            category=(ctx.get('category') or ctx.get('cat') or '') if ctx else '',
            price_min=ctx.get('price_min') if ctx else None,
            price_max=ctx.get('price_max') if ctx else None,
        )
        save_user_profile(user_id, profile)
    except Exception as e:
        logger.warning("profile observe/save failed: %s", e)


# ── Main entry ────────────────────────────────────────────────────────────────

def process_message(user_id: str, message: str) -> Dict[str, Any]:
    start_time = datetime.now()
    logger.info("user=%s msg=%r", user_id, message)

    # Load profile up-front — every code path below benefits from it
    # (humanization, prompt injection, observation update on the way out).
    profile = load_user_profile(user_id)

    try:
        # ── STEP 1: load_context (single DB round-trip for the whole request) ──
        prev_ctx = load_context(user_id)

        # Blocked automated template
        if _is_automated(message):
            _observe_and_save(user_id, profile, message, 'ignored_automated_template', {})
            ic = normalize_payload(prev_ctx)
            return _build_response(user_id,
                {'response': '', 'intent': 'ignored_automated_template',
                 'intent_content': ic, 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # Human mode check
        if check_responder_type(user_id) == 'agent':
            _observe_and_save(user_id, profile, message, 'human_mode_active', {})
            ic = normalize_payload(prev_ctx)
            return _build_response(user_id,
                {'response': '', 'intent': 'human_mode_active',
                 'intent_content': ic, 'products': []},
                ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Order flow pump ──────────────────────────────────────────────────
        # If the user is mid-order (collecting name/mobile/address/city/area/qty,
        # or at the final confirm step), every incoming message must go through
        # the order handler so we don't kick them back into Groq routing.
        from services.order_handler import is_in_order_flow, continue_order_flow
        if is_in_order_flow(user_id):
            order_result = continue_order_flow(user_id, message)
            if order_result is not None:
                _observe_and_save(user_id, profile, message,
                                  order_result.get('intent', 'order_flow'), {})
                return _build_response(user_id, order_result,
                                       ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)

        # ── Advance payment intercept ────────────────────────────────────────
        # Groq often mislabels "অগ্রিম টাকা দিতে হবে?" as product_search.
        # Catch it deterministically before Groq.
        _ADVANCE_SIGNALS = (
            'অগ্রিম', 'agrim', 'ogrim', 'ogram', 'ogrim', 'আগাম', 'আগে টাকা', 'আগে পেমেন্ট',
            'upfront', 'prepaid', 'prepay', 'advance pay', 'advance dite',
            'age taka', 'age payment', 'age dite', 'age pathate',
        )
        if any(s in message.lower() for s in _ADVANCE_SIGNALS):
            from services.intent_handlers_service import handle_delivery as _hd
            _adv_ctx = normalize_payload(prev_ctx)
            _adv_result = _hd(_adv_ctx, user_id, message, [])
            _observe_and_save(user_id, profile, message, 'delivery', {})
            return _build_response(user_id, _adv_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # ── Order status lookup intercept ────────────────────────────────────
        # Catch messages like "order status 17805593641", "অর্ডার চেক 17805…",
        # "track order 17805…" before Groq sends them to the generic delivery
        # FAQ. Requires a status-related keyword AND an order-no-shaped number
        # so a plain price or phone number doesn't accidentally trigger it.
        _ORDER_STATUS_SIGNALS = (
            'order status', 'order track', 'track order', 'order check',
            'order kothay', 'order koi', 'order id', 'order no',
            'অর্ডার স্ট্যাটাস', 'অর্ডার চেক', 'অর্ডার ট্র্যাক', 'অর্ডার কোথায়',
            'অর্ডার নম্বর', 'অর্ডার আইডি', 'অর্ডার দেখান', 'অর্ডার আপডেট',
            'check my order', 'where is my order', 'status of my order',
        )
        _msg_l_os = message.lower()
        if any(s in _msg_l_os for s in _ORDER_STATUS_SIGNALS):
            os_ctx = normalize_payload(prev_ctx)
            os_result = handle_order_status(os_ctx, user_id, message)
            if os_result is not None:
                _observe_and_save(user_id, profile, message,
                                  os_result.get('intent', 'order_status'), {})
                return _build_response(user_id, os_result,
                                       ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)

        # Deterministic greeting intercept — short hi/hello/salam messages should
        # never depend on Groq. Without this a Groq outage hands every new user
        # to a human via the strict-handoff policy.
        _GREETING_PHRASES = {
            'hi', 'hii', 'hiii', 'hello', 'helo', 'hey', 'hlw', 'hloo',
            'salam', 'assalamualaikum', 'asalamualaikum', 'assalam', 'slm',
            'হাই', 'হ্যালো', 'হেলো', 'সালাম', 'আসসালামু আলাইকুম', 'আসসালামুয়ালাইকুম',
        }
        _msg_norm = message.strip().lower().rstrip('.?!।,')
        if _msg_norm in _GREETING_PHRASES:
            greet_result = handle_greeting(normalize_payload(prev_ctx), user_id, message)
            _observe_and_save(user_id, profile, message, 'greeting', {})
            return _build_response(user_id, greet_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # URL in message
        url_match = re.search(r'https?://[^\s]+', message)
        if url_match:
            ic_ctx = normalize_payload(prev_ctx)
            flat_ctx = {
                'category':  ic_ctx.get('cat', ''),
                'brand':     ic_ctx.get('brand', ''),
                'title':     ic_ctx.get('title', ''),
                'price_max': ic_ctx.get('price_max'),
                'price_min': ic_ctx.get('price_min'),
            }
            # Extract any budget the user mentioned alongside the URL.
            # extract_budget_range returns 'max_price'/'min_price' (not 'price_*').
            from services.intent_service import extract_budget_range
            url_budget = extract_budget_range(message)
            if url_budget.get('max_price') is not None:
                flat_ctx['price_max'] = url_budget['max_price']
            if url_budget.get('min_price') is not None:
                flat_ctx['price_min'] = url_budget['min_price']
            result = handle_url_message(flat_ctx, user_id, message, url_match.group(0))
            _observe_and_save(user_id, profile, message, result.get('intent', ''), flat_ctx)
            return _build_response(user_id, result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Self-reference buy: "এইটা/এটা/this order dite chaicchi" with cached products
        # → skip Groq/budget, go straight to buy handler with the cached product.
        from repositories.state_repository import get_product_context as _gpc_buy
        _cached_buy = _gpc_buy(user_id)
        _msg_lower_buy = message.lower()
        _BUY_SELF_REF = {'এইটা', 'এটা', 'oita', 'eita', 'eta', 'this', 'এইটাই', 'এটাই'}
        _BUY_ORDER_WORDS = {'order', 'kinbo', 'নেবো', 'নিতে চাই', 'kinte chai', 'order dite',
                            'কিনতে চাই', 'অর্ডার', 'buy', 'purchase'}
        _has_self_ref = any(w in _msg_lower_buy for w in _BUY_SELF_REF)
        _has_buy_word = any(w in _msg_lower_buy for w in _BUY_ORDER_WORDS)
        if _has_self_ref and _has_buy_word and _cached_buy:
            from services.intent_service import normalize_payload as _np_buy
            _buy_ctx = normalize_payload(prev_ctx)
            _buy_ctx['category'] = (_cached_buy[0].get('category') or
                                    prev_ctx.get('cat') or prev_ctx.get('category') or '')
            buy_result = handle_buy(_buy_ctx, user_id, message)
            # If handle_buy returned a "which one?" prompt, remember the original
            # buy phrase so the next turn (e.g. "1") routes to the order flow.
            if buy_result.get('intent') == 'product_clarification':
                set_pending_question(user_id, message)
            _observe_and_save(user_id, profile, message, 'buy', _buy_ctx)
            return _build_response(user_id, buy_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Generic buy/order intent intercept — short messages like
        # "ami order korte chai", "kinte chai", "buy korbo" are purchase-process
        # questions, not new product searches. Groq sometimes mislabels them as
        # product_search and re-shows cached products. Catch them deterministically.
        _BUY_PHRASES = (
            'order korte chai', 'order korbo', 'order dibo', 'order dite chai',
            'order korte chacchi', 'order dite chacchi', 'অর্ডার করতে চাই',
            'অর্ডার করব', 'অর্ডার দিব', 'অর্ডার দিতে চাই',
            'kinte chai', 'kinbo', 'kinte chacchi', 'কিনতে চাই', 'কিনব',
            'buy korbo', 'buy korte chai', 'purchase korbo',
        )
        _msg_stripped = _msg_lower_buy.strip().rstrip('.?!।')
        if any(p in _msg_lower_buy for p in _BUY_PHRASES) and len(_msg_stripped) <= 40:
            _buy_ctx = normalize_payload(prev_ctx)
            if _cached_buy:
                _buy_ctx['category'] = (_cached_buy[0].get('category') or
                                        prev_ctx.get('cat') or prev_ctx.get('category') or '')
            buy_result = handle_buy(_buy_ctx, user_id, message)
            if buy_result.get('intent') == 'product_clarification':
                set_pending_question(user_id, message)
            _observe_and_save(user_id, profile, message, 'buy', _buy_ctx)
            return _build_response(user_id, buy_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Clarification selection — user picks a numbered product after clarification prompt.
        # Must run BEFORE handle_product_detail_followup, otherwise the followup
        # intercept treats "1" as a stray query about cached products and answers
        # with the wrong handler (spec-fallback instead of routing to the original
        # pending question, e.g. buy → order flow).
        if get_last_intent(user_id) == 'product_clarification':
            pending_q = get_pending_question(user_id)
            selected = handle_clarification_selection(
                user_id, message,
                pending_question=pending_q,
                groq_client=_groq_client,
                groq_model=GROQ_ANSWER_MODEL,
            )
            if selected:
                _observe_and_save(user_id, profile, message, selected.get('intent', ''), {})
                return _build_response(user_id, selected, ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)
            # User typed a product name instead of a number — do a fresh search
            # for that product, then answer the pending condition/spec question.
            if pending_q:
                from services.api_client_service import search_products as _sp
                from repositories.state_repository import set_product_context as _spc
                from services.intent_handlers_service import _handle_condition_question, handle_product_spec_query
                _CONDITION_Q2 = {
                    'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
                    'condition', 'কন্ডিশন', 'fresh',
                    'intake', 'original intake', 'non intake', 'ইনটেক', 'নন ইনটেক',
                }
                pq_lower = pending_q.lower()
                has_condition_q = any(w in pq_lower for w in _CONDITION_Q2)
                has_spec_q = any(w in pq_lower for w in ('ram', 'gb', 'processor', 'display', 'battery', 'camera', 'storage', 'spec'))
                if has_condition_q or has_spec_q:
                    fresh = _sp(message)
                    if fresh['products_found'] > 0:
                        _spc(user_id, fresh['products'][:5])
                        # Now re-route to condition or spec handler with new cache
                        if has_condition_q:
                            from services.intent_handlers_service import _handle_condition_question
                            cond = _handle_condition_question(user_id, pending_q)
                            if cond:
                                _observe_and_save(user_id, profile, message, cond.get('intent', ''), {})
                                return _build_response(user_id, cond, ChatMode.AI, AI_ACTIVE_STATUS,
                                                       (datetime.now() - start_time).total_seconds(),
                                                       user_message=message, profile=profile)
                        if has_spec_q:
                            from repositories.state_repository import get_product_context as _gpc2
                            _fresh_prods = _gpc2(user_id)
                            _spec_ctx = {'category': '', 'brand': '', 'title': (_fresh_prods[0].get('title', '') if _fresh_prods else '')}
                            spec_r = handle_product_spec_query(_spec_ctx, user_id, pending_q, _groq_client, GROQ_ANSWER_MODEL)
                            _observe_and_save(user_id, profile, message, spec_r.get('intent', ''), {})
                            return _build_response(user_id, spec_r, ChatMode.AI, AI_ACTIVE_STATUS,
                                                   (datetime.now() - start_time).total_seconds(),
                                                   user_message=message, profile=profile)

        # Product detail follow-up.
        # Fire when either: (a) a specific product URL was pinned via set_product_url,
        # or (b) products from a search result are cached — use the first result's URL.
        # Runs AFTER the clarification-selection check so a numbered reply ("1")
        # routes through the correct pending-question handler (e.g. buy → order
        # flow) instead of being misread as a stray product question.
        from repositories.state_repository import get_product_context as _gpc_early
        _cached_products_early = _gpc_early(user_id)
        product_url = (get_product_url(user_id)
                       or prev_ctx.get('product_url', '')
                       or (_cached_products_early[0].get('url', '')
                           if _cached_products_early else ''))
        if product_url:
            detail = handle_product_detail_followup(prev_ctx, user_id, message, product_url,
                                                     _groq_client, GROQ_ANSWER_MODEL)
            if detail:
                # When the followup handler asks the user to pick a product by number,
                # save the original message so the selection turn can answer WHAT was asked.
                if detail.get('intent') == 'product_clarification':
                    set_pending_question(user_id, message)
                _observe_and_save(user_id, profile, message, detail.get('intent', ''), prev_ctx)
                return _build_response(user_id, detail, ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)

        # ── STEP 2: detect_intent ────────────────────────────────────────────
        history     = fetch_history(user_id)
        cat_names   = [c['category_name'] for c in _categories]
        groq_result = detect_intent(message, history, prev_ctx,
                                    cat_names, _groq_client, GROQ_MODEL,
                                    user_profile_block=profile.to_prompt_block())

        # Apply deterministic post-Groq corrections (budget refinement,
        # over/under signals, search/comparison/buy overrides).
        # Must run BEFORE the category scan so _is_pure_budget_msg is known.
        override_result = apply_post_groq_overrides(groq_result, message, dict(prev_ctx))
        groq_result = override_result['groq_result']
        prev_ctx = override_result['prev_ctx']
        _is_pure_budget_msg = override_result['is_pure_budget_msg']

        # Resolve extracted category against canonical list.
        # Skip the message-scan fallback for pure budget messages — words like
        # "modde" (meaning "within") would otherwise fuzzy-match modem/WiFi categories.
        raw_cat = groq_result['entities'].get('category', '')
        if raw_cat:
            resolved = resolve_category(raw_cat, _categories)
            groq_result['entities']['category'] = resolved
        elif not _is_pure_budget_msg:
            # Groq missed category — scan message directly
            scanned = resolve_category_from_message(message, _categories)
            if scanned:
                groq_result['entities']['category'] = scanned
                # Promote unknown → product_search when we found a category
                if groq_result['intent'] == 'unknown':
                    groq_result['intent'] = 'product_search'

        # Clear filler titles BEFORE merge so they never overwrite a real prev title.
        _FILLER_WORDS = {
            'khujtasi', 'khujchi', 'lagbe', 'chai', 'ase', 'nibo', 'dekhan',
            'dekhao', 'bolun', 'jani', 'bolen', 'please', 'kindly',
            'apnader', 'apnar', 'amader', 'amra', 'ami', 'apni',
        }
        _raw_title = (groq_result['entities'].get('title') or '').lower().strip()
        if _raw_title:
            _title_words = set(_raw_title.split())
            if _title_words and _title_words.issubset(_FILLER_WORDS):
                groq_result['entities']['title'] = ''

        logger.info("Intent=%s entities=%s followup=%s confidence=%.2f",
                    groq_result['intent'], groq_result['entities'],
                    groq_result['is_followup'], groq_result.get('confidence', 0.0))

        # Strict policy: if Groq cannot classify (intent='unknown') or returns
        # very low confidence with no usable entities, hand the conversation off
        # to a human agent instead of guessing.
        _conf = float(groq_result.get('confidence') or 0.0)
        _has_entity = any(groq_result['entities'].get(k) for k in
                          ('category', 'brand', 'title', 'price_max', 'price_min'))
        if (groq_result['intent'] == 'unknown'
                or (_conf < 0.55 and not _has_entity
                    and not groq_result.get('is_followup'))):
            logger.info("Strict handoff — intent=%s conf=%.2f entities=%s",
                        groq_result['intent'], _conf, groq_result['entities'])
            try:
                assign_agent(user_id, 'unknown_intent')
            except Exception as e:
                logger.warning("assign_agent on unknown intent failed: %s", e)
            ic = normalize_payload(prev_ctx)
            handler_result = {
                'response': ("স্যার, আপনার মেসেজটি আমি ঠিকমতো বুঝতে পারিনি। "
                             "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"),
                'intent': 'unknown_handoff',
                'intent_content': ic,
                'products': [],
            }
            _observe_and_save(user_id, profile, message, 'unknown_handoff', {})
            return _build_response(user_id, handler_result,
                                   ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # ── STEP 3: merge_context ────────────────────────────────────────────
        def _clear():
            clear_product_state(user_id)

        # Greeting is an explicit session reset. Clear category from prev_ctx NOW
        # so merge_context and the inheritance block below can't pull the old
        # category back from the DB snapshot on this turn.
        if groq_result['intent'] == 'greeting':
            prev_ctx['category'] = ''
            prev_ctx['cat'] = ''
            prev_ctx['prev_cat'] = ''

        # Category switch: when the user explicitly names a different category,
        # clear ALL stale state BEFORE merge_context so the old category can't
        # bleed in through prev_ctx inheritance.
        _fresh_cat = groq_result['entities'].get('category', '')
        if _fresh_cat and _fresh_cat != get_session_category(user_id):
            clear_product_state(user_id)
            invalidate_user_cache(user_id)
            set_session_category(user_id, _fresh_cat)
            # Wipe the old category from prev_ctx so merge can't inherit it
            for _k in ('category', 'cat', 'prev_cat'):
                prev_ctx[_k] = ''

        # Intent change: when the current intent differs from the last bot turn,
        # treat the previous conversation context as not applicable. Drop cached
        # products so a new intent never gets answered using stale product state.
        # Skipped for follow-ups (is_followup=true) — those depend on context.
        _prev_intent = get_last_intent(user_id)
        _cur_intent  = groq_result['intent']
        _NON_RESET_INTENTS = {
            'greeting', 'goodbye', 'thanks', 'exit',
            'product_clarification',  # mid-flow selection
        }
        if (_prev_intent and _cur_intent
                and _prev_intent != _cur_intent
                and _cur_intent not in _NON_RESET_INTENTS
                and not groq_result.get('is_followup')):
            logger.info("intent change %s -> %s — clearing product context",
                        _prev_intent, _cur_intent)
            clear_product_state(user_id)

        merged = merge_context(groq_result, prev_ctx, groq_result['intent'], _clear)

        # Inherit category for non-product intents when still empty.
        # Greeting resets the session, so never re-inherit on the turn after a greeting.
        # FAQ doesn't benefit from an inherited category — it just pollutes intent_content.
        _INHERIT_INTENTS = {
            'comparison', 'technical_advice', 'price_query',
            'unknown', 'seller_query', 'product_search',
        }
        if not merged.get('category') and groq_result['intent'] in _INHERIT_INTENTS:
            # Session memory is more reliable than DB (DB may have stale category)
            inherited = (get_session_category(user_id)
                         or prev_ctx.get('category') or prev_ctx.get('cat', ''))
            if inherited:
                merged['category'] = inherited

        # Promote unknown → product_search when category is now known
        if groq_result['intent'] == 'unknown' and merged.get('category'):
            groq_result['intent'] = 'product_search'

        # Save known category to session memory whenever we have one
        if merged.get('category'):
            set_session_category(user_id, merged['category'])

        # Pure budget refinement: clear any stale title the merge may have inherited.
        if _is_pure_budget_msg:
            stale = merged.get('title') or merged.get('prev_title')
            if stale:
                logger.info("Pure budget refinement — clearing stale merged title %r", stale)
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
        handler_result = _dispatch(groq_result['intent'], merged, user_id, message, prev_ctx)

        # When a handler asks the user to pick a product by number, save the
        # current message as the pending question so the selection turn can
        # answer it correctly (spec / condition / whatever was originally asked).
        if handler_result.get('intent') == 'product_clarification':
            set_pending_question(user_id, message)

        # Update the rolling user profile from this turn's observations.
        # Use groq_result['entities'] (what the user actually said this turn),
        # not merged (which inherits previous-turn values and would corrupt the profile).
        _observe_and_save(user_id, profile, message,
                          handler_result.get('intent', groq_result['intent']),
                          groq_result['entities'])

        # ── STEP 5: build and return (persistence done by caller) ────────────
        # Handoff intents flip the mode to human so the next message bypasses AI.
        _HANDOFF_INTENT_NAMES = {
            'unknown_handoff', 'knowledge_limit_exceeded',
            'seller_query', 'hate_speech', 'explicit_human_request',
            'complaint_handoff',
        }
        _intent_out = handler_result.get('intent', '')
        if _intent_out in _HANDOFF_INTENT_NAMES:
            return _build_response(user_id, handler_result,
                                   ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)
        return _build_response(user_id, handler_result, ChatMode.AI, AI_ACTIVE_STATUS,
                               (datetime.now() - start_time).total_seconds(),
                               user_message=message, profile=profile)

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


def _dispatch(intent: str, ctx: Dict, user_id: str, message: str,
              prev_ctx: Optional[Dict] = None) -> Dict:
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
            ic = normalize_payload(prev_ctx or load_context(user_id))
            return {'response': _SHOWROOM_RESPONSE + LOOP_BACK,
                    'intent': 'faq_showroom', 'intent_content': ic, 'products': []}

    # Return / refund complaint — fetch policy from API, no agent handoff needed
    if intent == 'complaint':
        msg_l = (message or '').lower()
        _RETURN_SIGNALS = (
            'return', 'ফেরত', 'ferot', 'ferat', 'refund',
            'bhanga', 'ভাঙা', 'nosto', 'নষ্ট', 'broken', 'damaged', 'problem',
            'call dore na', 'call dhore na', 'call dhorena', 'seller nai',
            'pathaise', 'পাঠাইছে', 'wrong product', 'wrong item',
        )
        if any(s in msg_l for s in _RETURN_SIGNALS):
            ic = normalize_payload(prev_ctx or load_context(user_id))
            policy_text = fetch_return_policy()
            # Formatted answer only — no Groq summarization. Trim to a clean
            # sentence boundary to fit a Messenger reply.
            if policy_text:
                trimmed = policy_text.strip()
                if len(trimmed) > 600:
                    cut = trimmed[:600].rsplit('।', 1)[0] or trimmed[:600].rsplit(' ', 1)[0]
                    summary = cut + '…'
                else:
                    summary = trimmed
            else:
                summary = "প্রোডাক্ট রিটার্ন বা সমস্যার ক্ষেত্রে আমাদের রিটার্ন পলিসি অনুযায়ী পদক্ষেপ নিন।"
            reply = "স্যার, অসুবিধার জন্য আন্তরিকভাবে দুঃখিত। 😔\n\n" + summary
            return {
                'response':       reply + LOOP_BACK,
                'intent':         'complaint_return',
                'intent_content': ic,
                'products':       [],
                'link_buttons':   [],
            }

    if intent in _HANDOFF_MAP:
        text, handoff_intent = _HANDOFF_MAP[intent]
        assign_agent(user_id, handoff_intent)
        ic = normalize_payload(prev_ctx or load_context(user_id))
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
    if intent in ('buy', 'ordering'):
        return handle_buy(ctx, user_id, message)
    if intent == 'comparison':
        return handle_comparison(ctx, user_id, message)
    if intent == 'delivery':
        return handle_delivery(ctx, user_id, message, fetch_faq_db())
    if intent == 'faq':
        return handle_faq(ctx, user_id, message, fetch_faq_db())
    if intent == 'product_spec_query':
        return handle_product_spec_query(ctx, user_id, message,
                                         _groq_client, GROQ_ANSWER_MODEL)
    if intent == 'technical_advice':
        return handle_technical_advice(ctx, user_id, message,
                                       _categories, _groq_client, GROQ_ANSWER_MODEL)
    if intent == 'price_query':
        return handle_price_query(ctx, user_id, message)
    if intent == 'product_search':
        # Re-route to comparison when: products are already cached AND the message
        # contains an explicit "which one is better" phrase. This catches follow-up
        # comparison questions that Groq labels product_search (e.g. "samsung dekhao
        # konti valo?") without affecting fresh first-time searches.
        from repositories.state_repository import get_product_context as _gpc
        _EXPLICIT_CMP = {
            'konti valo', 'konta valo', 'konti bhalo', 'konta bhalo',
            'কোনটা ভালো', 'কোনটি ভালো', 'valo hobe', 'bhalo hobe',
            'ভালো হবে', 'which one is better', 'which is better',
        }
        msg_l = (message or '').lower()
        if _gpc(user_id) and any(w in msg_l for w in _EXPLICIT_CMP):
            return handle_comparison(ctx, user_id, message)
        return handle_product_search(ctx, user_id, message)

    # Strict policy: no recognised intent → hand the conversation to a human.
    logger.info("Unrecognised intent %r — handing off to human agent", intent)
    try:
        assign_agent(user_id, 'unknown_intent')
    except Exception as e:
        logger.warning("assign_agent on unknown intent failed: %s", e)
    ic = normalize_payload(prev_ctx or load_context(user_id))
    return {
        'response': ("স্যার, আপনার মেসেজটি আমি ঠিকমতো বুঝতে পারিনি। "
                     "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"),
        'intent': 'unknown_handoff',
        'intent_content': ic,
        'products': [],
    }


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
