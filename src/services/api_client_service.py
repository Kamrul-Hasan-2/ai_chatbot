"""
src/services/api_client_service.py — ALL external HTTP calls live here.
No other file calls requests directly.

Public functions:
  check_responder_type(user_id)               → 'agent' | 'bot' | None
  assign_agent(user_id, intent)               → None
  assign_bot(user_id)                         → None
  search_products(keywords, max, min)         → {products_found, products}
  fetch_history(user_id)                      → str
  fetch_intent_from_history(user_id)          → dict
  fetch_delivery_template()                   → str | None
  save_message(user_id, sender, text, ...)    → bool
  fetch_categories()                          → list[dict]
  fetch_faq_db()                              → list[dict]
  fetch_return_policy()                       → str | None
"""
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from models.chatbot_config import (
    API_KEY, SEARCH_URL, DELIVERY_URL, CONDITION_URL,
    ASSIGN_AGENT_URL, ASSIGN_AGENT_KEY,
    ASSIGN_BOT_URL, RESPONDER_URL, RESPONDER_KEY,
    HISTORY_URL, HISTORY_LIMIT,
    SAVE_MESSAGE_URL, SAVE_MESSAGE_KEY,
    CAT_LIST_URL, SPEC_URL, PRODUCT_DETAILS_URL, CATEGORY_FILTERS_URL, KNOWLEDGE_URL,
    CITY_LIST_URL, AREA_LIST_URL, PLACE_ORDER_URL, ORDER_STATUS_URL,
    SELLER_REQUEST_URL, SUPPORT_CONTACT_URL,
    _log_api_call,
)

logger = logging.getLogger(__name__)

# ── Simple in-memory caches ───────────────────────────────────────────────────

_search_cache:  Dict[str, tuple] = {}
_history_cache: Dict[str, tuple] = {}   # keyed by user_id → (timestamp, text)
_intent_cache:  Dict[str, tuple] = {}   # keyed by user_id → (timestamp, dict)
_SEARCH_TTL  = 300
_HISTORY_TTL = 60
_SEARCH_MAX  = 200


_responder_cache: Dict[str, tuple] = {}  # user_id → (timestamp, label)
_RESPONDER_TTL_BOT   = 30   # cache 'bot' result — safe to reuse briefly
_RESPONDER_TTL_AGENT = 0    # never cache 'agent' — always do a live check


def invalidate_user_cache(user_id: str) -> None:
    """Drop all per-user caches — called when the user switches category."""
    _history_cache.pop(user_id, None)
    _intent_cache.pop(user_id, None)


# ── Responder / mode ──────────────────────────────────────────────────────────

def check_responder_type(user_id: str) -> Optional[str]:
    now = time.time()
    cached = _responder_cache.get(user_id)
    # Only use cache for 'bot' results — never cache 'agent' to avoid stale silencing
    if cached and cached[1] == 'bot' and (now - cached[0]) < _RESPONDER_TTL_BOT:
        return 'bot'
    try:
        started = time.time()
        url = f"{RESPONDER_URL}?key={RESPONDER_KEY}&user_id={user_id}"
        resp = requests.get(url, timeout=3)
        duration_ms = int((time.time() - started) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('data'):
                label = data['data'].get('responder_label', 'bot')
                _log_api_call('responder_type_check', 'GET', url, {'user_id': user_id},
                              resp.status_code, duration_ms, 'PASS',
                              str(data.get('data', {}))[:200])
                if label == 'bot':
                    _responder_cache[user_id] = (now, 'bot')
                else:
                    # Don't cache agent status — always re-check live
                    _responder_cache.pop(user_id, None)
                return label
        # On API failure default to 'bot' — never silently drop messages
        _responder_cache[user_id] = (now, 'bot')
        return 'bot'
    except Exception as e:
        logger.warning("check_responder_type failed: %s", e)
        _responder_cache[user_id] = (now, 'bot')
        return 'bot'


def assign_agent(user_id: str, intent: str) -> None:
    try:
        started = datetime.now()
        payload = {'key': ASSIGN_AGENT_KEY, 'user_id': user_id, 'intent': intent}
        resp = requests.post(ASSIGN_AGENT_URL, json=payload, timeout=5)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        _log_api_call('assign_agent', 'POST', ASSIGN_AGENT_URL, payload,
                      resp.status_code, duration_ms,
                      'PASS' if resp.status_code == 200 else 'FAIL', resp.text[:400])
    except Exception as e:
        logger.warning("assign_agent failed: %s", e)


def assign_bot(user_id: str) -> None:
    try:
        requests.post(ASSIGN_BOT_URL, json={'key': API_KEY, 'user_id': user_id}, timeout=5)
        _responder_cache.pop(user_id, None)  # force fresh check next message
    except Exception as e:
        logger.warning("assign_bot failed: %s", e)


# ── Product search ────────────────────────────────────────────────────────────

def search_products(keywords: str, price_max: Optional[int] = None,
                    price_min: Optional[int] = None) -> Dict[str, Any]:
    cache_key = f"{keywords}|{price_min or ''}|{price_max or ''}"
    now = time.time()
    cached = _search_cache.get(cache_key)
    if cached and (now - cached[0]) < _SEARCH_TTL:
        return cached[1]
    result, failed = _do_search(keywords, price_max, price_min)
    # A timeout/HTTP-error result looks identical to a genuine "0 products"
    # result ({'products_found': 0, 'products': []}) — caching it would tell
    # every user searching this query "not found" for the full TTL even
    # though the API recovers seconds later. Only cache real outcomes. (#H12)
    if not failed:
        _search_cache[cache_key] = (now, result)
        if len(_search_cache) > _SEARCH_MAX:
            oldest = min(_search_cache, key=lambda k: _search_cache[k][0])
            _search_cache.pop(oldest, None)
    return result


def _do_search(keywords: str, price_max: Optional[int],
               price_min: Optional[int]) -> tuple:
    """Returns (result, failed). failed=True means the call itself broke
    (timeout/HTTP/parse error) — as opposed to a genuine zero-result search —
    so the caller knows not to cache it as if it were a real answer."""
    try:
        params = {'term': keywords.strip(), 'key': API_KEY}
        if price_min and price_min > 0:
            params['minPrice'] = price_min
        if price_max and price_max > 0:
            params['maxPrice'] = price_max
        started = datetime.now()
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        _log_api_call('ai_search', 'GET', SEARCH_URL, params, resp.status_code,
                      duration_ms, 'PASS' if resp.status_code == 200 else 'FAIL', resp.text[:400])
        if resp.status_code != 200:
            return {'products_found': 0, 'products': []}, True
        data = resp.json()
        if not data.get('getListingItem') or len(data['getListingItem']) < 2:
            return {'products_found': 0, 'products': []}, False
        total = int(data['getListingItem'][0] or 0)
        raw   = data['getListingItem'][1] or []
        if total == 0 or not raw:
            return {'products_found': 0, 'products': []}, False
        top = raw[:15]
        products = [{
            'title':          p.get('ListingTitle', 'N/A'),
            'price':          p.get('ListingPrice', 'N/A'),
            'original_price': p.get('app_ListingOriginalPrice', ''),
            'discount':       p.get('ListingDiscountPercentage', 0),
            'url':            p.get('ListingURL', ''),
            'image':          p.get('ListingThumbAvator', ''),
        } for p in top if isinstance(p, dict)]
        return {'products_found': len(products), 'total_products': total, 'products': products}, False
    except Exception as e:
        logger.error("_do_search failed: %s", e)
        return {'products_found': 0, 'products': []}, True


# ── Chat history ──────────────────────────────────────────────────────────────

def fetch_history(user_id: str) -> str:
    now = time.time()
    cached = _history_cache.get(user_id)
    if cached and (now - cached[0]) < _HISTORY_TTL:
        return cached[1]
    text = _fetch_history_raw(user_id)
    _history_cache[user_id] = (now, text)
    return text


def _fetch_history_raw(user_id: str) -> str:
    if not user_id:
        return ''
    url = f"{HISTORY_URL.rstrip('/')}?user_id={user_id}&limit={HISTORY_LIMIT}&key={API_KEY}"
    try:
        resp = requests.get(url, timeout=8)
        if not (200 <= resp.status_code < 300):
            return ''
        payload = resp.json() if resp.text else {}
        lines = _normalize_history(payload)
        return '\n'.join(lines).strip()
    except Exception as e:
        logger.warning("fetch_history failed: %s", e)
        return ''


def _normalize_history(payload: Any) -> List[str]:
    candidates = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for k in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
            v = payload.get(k)
            if isinstance(v, list):
                candidates = v
                break
    lines = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        text = str(item.get('message') or item.get('text') or
                   item.get('content') or item.get('body') or '').strip()
        if not text:
            continue
        # sender_type may arrive as int or str — normalise to str for comparison.
        sender = str(item.get('sender_type') if item.get('sender_type') is not None else '').strip()
        role   = str(item.get('role') or '').strip().lower()
        if sender == '2' or role in {'assistant', 'bot', 'ai'}:
            lines.append(f"Bot: {text}")
        elif sender == '1' or role in {'agent', 'human'}:
            lines.append(f"Agent: {text}")
        elif sender == '3' or role in {'user', 'visitor', 'customer'}:
            lines.append(f"User: {text}")
        else:
            lines.append(f"User: {text}")
    return lines[-10:]


# ── Intent content from history (Rule 14) ────────────────────────────────────

def fetch_intent_from_history(user_id: str) -> Dict:
    """Pull last saved intent_content from history — DB is source of truth.

    Cached for up to _HISTORY_TTL seconds across requests (not just within one
    request cycle) to cut down on live HTTP calls. save_message() invalidates
    this on every successful save, so a bot reply's new intent_content is
    always visible to the very next load_context() for this user — the TTL
    only covers the case where nothing was saved in between. (#H11)
    """
    now = time.time()
    cached = _intent_cache.get(user_id)
    if cached and (now - cached[0]) < _HISTORY_TTL:
        return cached[1]

    url = f"{HISTORY_URL.rstrip('/')}?user_id={user_id}&limit=10&key={API_KEY}"
    try:
        resp = requests.get(url, timeout=8)
        if not (200 <= resp.status_code < 300):
            _intent_cache[user_id] = (now, {})
            return {}
        data = resp.json() if resp.text else {}
        candidates: List = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            for k in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
                v = data.get(k)
                if isinstance(v, list):
                    candidates = v
                    break
        for item in reversed(candidates):
            if not isinstance(item, dict):
                continue
            if str(item.get('sender_type') if item.get('sender_type') is not None else '').strip() != '2':
                continue
            ic = item.get('intent_content')
            if isinstance(ic, str):
                try:
                    ic = json.loads(ic)
                except Exception:
                    continue
            # Return the most recent bot intent_content dict — filtering by field
            # presence is business logic that belongs in the repository, not here.
            if isinstance(ic, dict):
                _intent_cache[user_id] = (now, ic)
                return ic
    except Exception as e:
        logger.warning("fetch_intent_from_history failed: %s", e)
    _intent_cache[user_id] = (now, {})
    return {}


# ── Delivery template ─────────────────────────────────────────────────────────

def fetch_delivery_template() -> Optional[str]:
    try:
        resp = requests.get(DELIVERY_URL,
                            params={'intent': 'delivery', 'key': API_KEY}, timeout=10)
        if resp.status_code != 200:
            return None
        return _parse_template(resp.json() if resp.text else {})
    except Exception as e:
        logger.warning("fetch_delivery_template failed: %s", e)
        return None


_support_contact_cache: Optional[tuple] = None
_SUPPORT_CONTACT_TTL = 300  # 5 min — phone number rarely changes, short enough to pick up an update


def fetch_support_contact() -> Optional[str]:
    """Fetch BDStall's support/WhatsApp contact number.

    Returns the phone number string on success, or None on failure /
    missing data — callers fall back to the static contact response.
    """
    global _support_contact_cache
    now = time.time()
    if _support_contact_cache and (now - _support_contact_cache[0]) < _SUPPORT_CONTACT_TTL:
        return _support_contact_cache[1]
    try:
        resp = requests.get(SUPPORT_CONTACT_URL, params={'key': API_KEY}, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.text else {}
        if not isinstance(data, dict) or data.get('success') is False:
            return None
        phone = str((data.get('data') or {}).get('phone') or '').strip()
        if not phone:
            return None
        _support_contact_cache = (now, phone)
        return phone
    except Exception as e:
        logger.warning("fetch_support_contact failed: %s", e)
        return None


_category_template_cache: Dict[str, tuple] = {}
_CATEGORY_TEMPLATE_TTL = 300  # 5 min — short enough that API-shape changes don't stick


def fetch_category_template(category: str) -> Optional[Dict[str, str]]:
    """Fetch the category landing page from ai_template?intent=category.

    Returns {'text': str, 'link': str} on success, or None when the category
    isn't recognised by BDStall. The API returns `data` (text) and `link`
    as separate fields.

    A result is only cached when BOTH `text` and `link` are present — partial
    results (e.g. text only, missing link) re-fetch on the next call so a
    transient API-shape glitch can't silently degrade the button card for an
    extended period.
    """
    if not category:
        return None
    key = category.lower().strip()
    now = time.time()
    cached = _category_template_cache.get(key)
    if cached and (now - cached[0]) < _CATEGORY_TEMPLATE_TTL:
        return cached[1]
    try:
        resp = requests.get(DELIVERY_URL,
                            params={'intent': 'category', 'category': category, 'key': API_KEY},
                            timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.text else {}
        if not isinstance(data, dict) or data.get('success') is False:
            _category_template_cache[key] = (now, None)
            return None
        text = str(data.get('data') or '').strip()
        link = str(data.get('link') or '').strip()
        if not text:
            _category_template_cache[key] = (now, None)
            return None
        result = {'text': text, 'link': link}
        # Only cache when both fields populated — avoids long-lived
        # half-results from a transient upstream blip.
        if link:
            _category_template_cache[key] = (now, result)
        return result
    except Exception as e:
        logger.warning("fetch_category_template failed: %s", e)
        return None


def _parse_template(data: Any) -> Optional[str]:
    if isinstance(data, str):
        return data.strip() or None
    if isinstance(data, dict):
        if data.get('success') is False:
            return None
        for k in ['response', 'message', 'template', 'text', 'content', 'data']:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


# ── Buy template (decides ecommerce vs classified flow) ──────────────────────

_buy_template_cache: Dict[str, tuple] = {}
_BUY_TEMPLATE_TTL = 600  # 10 min — listing type rarely flips


def fetch_buy_template(product_id: str) -> Optional[Dict[str, str]]:
    """Fetch the buy template for a listing.

    Returns:
        {'data': str, 'market_place_type': 'ecommerce'|'classified'|...}
        or None on failure / missing id.

    The chatbot uses `market_place_type` to decide whether to start the
    multi-step order flow (`ecommerce`) or just show the `data` text with
    the seller-contact link (`classified`).
    """
    if not product_id:
        return None
    key = str(product_id)
    now = time.time()
    cached = _buy_template_cache.get(key)
    if cached and (now - cached[0]) < _BUY_TEMPLATE_TTL:
        return cached[1]
    try:
        started = datetime.now()
        resp = requests.get(DELIVERY_URL,
                            params={'intent': 'buy', 'id': product_id, 'key': API_KEY},
                            timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        _log_api_call('buy_template', 'GET', DELIVERY_URL,
                      {'intent': 'buy', 'id': product_id}, resp.status_code,
                      duration_ms, 'PASS' if resp.status_code == 200 else 'FAIL',
                      resp.text[:400])
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.text else {}
        if not isinstance(data, dict) or data.get('success') is False:
            _buy_template_cache[key] = (now, None)
            return None
        result = {
            'data':              str(data.get('data') or '').strip(),
            'market_place_type': str(data.get('market_place_type') or '').strip().lower(),
        }
        _buy_template_cache[key] = (now, result)
        return result
    except Exception as e:
        logger.warning("fetch_buy_template failed: %s", e)
        return None


# ── Condition template ────────────────────────────────────────────────────────

def fetch_condition_template(product_id: str) -> Optional[str]:
    """Fetch product condition info (new/used) from ai_template API."""
    try:
        resp = requests.get(CONDITION_URL,
                            params={'intent': 'condition', 'id': product_id, 'key': API_KEY},
                            timeout=10)
        if resp.status_code != 200:
            return None
        return _parse_template(resp.json() if resp.text else {})
    except Exception as e:
        logger.warning("fetch_condition_template failed: %s", e)
        return None


# ── Save message ──────────────────────────────────────────────────────────────

def save_message(user_id: str, sender_type: int, message: str,
                 user_name: Optional[str] = None,
                 intent_content: Optional[Dict] = None) -> bool:
    if not message:
        return False
    payload: Dict[str, Any] = {
        'key':         SAVE_MESSAGE_KEY,
        'user_id':     str(user_id),
        'sender_type': int(sender_type),
        'message':     message,
    }
    if user_name:
        payload['user_name'] = str(user_name)
    if isinstance(intent_content, dict) and intent_content:
        payload['intent_content'] = intent_content

    form_payload = dict(payload)
    if isinstance(form_payload.get('intent_content'), dict):
        form_payload['intent_content'] = json.dumps(
            form_payload['intent_content'], ensure_ascii=False)

    for mode, fn in [
        ('json', lambda: requests.post(SAVE_MESSAGE_URL, json=payload, timeout=10)),
        ('form', lambda: requests.post(SAVE_MESSAGE_URL, data=form_payload, timeout=10)),
    ]:
        started = datetime.now()
        try:
            resp = fn()
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            ok = 200 <= resp.status_code < 300
            if ok:
                try:
                    d = resp.json()
                    if isinstance(d, dict) and 'success' in d:
                        ok = bool(d.get('success'))
                except Exception:
                    pass
            _log_api_call('save_message', f'POST[{mode}]', SAVE_MESSAGE_URL,
                          payload, resp.status_code, duration_ms,
                          'PASS' if ok else 'FAIL', resp.text[:400])
            if ok:
                # This message (possibly a new intent_content) just changed
                # what history/intent_content look like in the DB — drop the
                # cached pre-save copies so the very next load_context() for
                # this user sees it instead of serving a stale hit for up to
                # _HISTORY_TTL seconds. (#H11)
                invalidate_user_cache(str(user_id))
                return True
        except Exception as e:
            logger.warning("save_message[%s] failed: %s", mode, e)
    return False


# ── Product spec (list_details) ───────────────────────────────────────────────

_spec_cache: Dict[str, tuple] = {}   # keyed by listing_id → (timestamp, dict)
_SPEC_TTL = 600                      # 10 min — specs rarely change


def fetch_product_spec(listing_id: str) -> Optional[Dict]:
    """Fetch structured specs for a single listing from list_details API.

    Returns:
        {
          'title':    str,
          'features': {'RAM': '2 GB', 'Display': '5 Inch', ...},
          'review':   str   ← plain text, HTML stripped — fallback for Groq
        }
        or None on failure.
    """
    if not listing_id:
        return None
    now = time.time()
    cached = _spec_cache.get(listing_id)
    if cached and (now - cached[0]) < _SPEC_TTL:
        return cached[1]

    try:
        started = datetime.now()
        resp = requests.get(SPEC_URL, params={'lid': listing_id, 'key': API_KEY}, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        _log_api_call('fetch_product_spec', 'GET', SPEC_URL,
                      {'lid': listing_id}, resp.status_code, duration_ms,
                      'PASS' if resp.status_code == 200 else 'FAIL', resp.text[:400])
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.text else {}
        details = data.get('list_details') or []
        if not details or not isinstance(details[0], dict):
            return None
        item = details[0]

        # Build {ItemFeatureName: best_value} — prefer ItemFeatureValueName,
        # fall back to ItemFeatureDescription when the short value is missing.
        features: Dict[str, str] = {}
        for feat in (item.get('ListingFeatures') or []):
            if not isinstance(feat, dict):
                continue
            name = str(feat.get('ItemFeatureName') or '').strip()
            val  = str(feat.get('ItemFeatureValueName') or '').strip()
            desc = str(feat.get('ItemFeatureDescription') or '').strip()
            if name:
                features[name] = val or desc

        # Strip HTML tags from Review for the Groq fallback
        import re as _re
        raw_review = str(item.get('Review') or item.get('ListingDescription') or '').strip()
        plain_review = _re.sub(r'<[^>]+>', ' ', raw_review).strip()
        plain_review = _re.sub(r'\s+', ' ', plain_review)

        result = {
            'title':    str(item.get('ListingTitle') or '').strip(),
            'price':    str(item.get('ListingPrice') or '').strip(),
            'features': features,
            'review':   plain_review,
        }
        _spec_cache[listing_id] = (now, result)
        return result
    except Exception as e:
        logger.error("fetch_product_spec failed: %s", e)
        return None


# ── Product details (chatbot-specific, richer than list_details) ──────────────

_product_details_cache: Dict[str, tuple] = {}   # keyed by listing_id → (timestamp, dict)
_PRODUCT_DETAILS_TTL = 600                       # 10 min — matches _SPEC_TTL


def fetch_product_details(listing_id: str) -> Optional[Dict]:
    """Fetch full product details from the chatbot-specific product_details API.

    Richer than fetch_product_spec (brand, category, condition, discount,
    in_stock, description, seller list) — used to ground webchat page-context
    answers (src/api/webchat_routes.py). Returns a dict shaped compatibly
    with the product-context dict search_products()/fetch_product_spec()
    already produce elsewhere ({'title', 'price', 'original_price',
    'discount', 'url', 'image'}), plus extra fields, or None on failure/not
    found — callers should fall back to the existing fetch_product_spec path
    on None, exactly as if this function didn't exist.
    """
    if not listing_id:
        return None
    now = time.time()
    cached = _product_details_cache.get(listing_id)
    if cached and (now - cached[0]) < _PRODUCT_DETAILS_TTL:
        return cached[1]

    try:
        started = datetime.now()
        resp = requests.get(PRODUCT_DETAILS_URL, params={'id': listing_id, 'key': API_KEY}, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        payload = resp.json() if resp.text else {}
        passed = resp.status_code == 200 and bool(payload.get('success'))
        _log_api_call('fetch_product_details', 'GET', PRODUCT_DETAILS_URL,
                      {'id': listing_id}, resp.status_code, duration_ms,
                      'PASS' if passed else 'FAIL', resp.text[:400])
        if not passed:
            return None

        d = payload.get('data') or {}
        title = str(d.get('title') or '').strip()
        if not title:
            return None

        def _to_float(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        price = _to_float(d.get('price'))
        discount_price = _to_float(d.get('discount_price'))
        effective_price = _to_float(d.get('effective_price')) or (price - discount_price) or price
        discount_pct = round((discount_price / price) * 100) if price and discount_price else 0

        def _format_taka(amount: float) -> str:
            """৳ + thousand separators, matching the '৳ 18,500' style used
            elsewhere (search_products/fetch_product_spec return
            pre-formatted price strings from BDStall directly; this API
            returns bare numbers, so format them the same way here)."""
            return f"৳ {int(amount):,}" if amount else ''

        result = {
            'title': title,
            'price': _format_taka(effective_price) or str(d.get('price') or ''),
            'original_price': _format_taka(price),
            'discount': discount_pct,
            'url': str(d.get('url') or '').strip(),
            'image': '',
            'brand': str(d.get('brand') or '').strip(),
            'category': str(d.get('category') or '').strip(),
            'condition': str(d.get('condition') or '').strip(),
            'in_stock': bool(d.get('in_stock')),
            'description': str(d.get('description') or '').strip(),
        }
        _product_details_cache[listing_id] = (now, result)
        return result
    except Exception as e:
        logger.error("fetch_product_details failed: %s", e)
        return None


# ── Category filters (price range, brands, spec options) ──────────────────────

_category_filters_cache: Dict[str, tuple] = {}   # keyed by category (lowercased) → (timestamp, dict)
_CATEGORY_FILTERS_TTL = 600                       # 10 min — matches _SPEC_TTL


def fetch_category_filters(category: str) -> Optional[Dict]:
    """Fetch available filters (price range, brand list, spec options) for a
    whole category from the chatbot-specific category_filters API.

    Used to answer category-level questions like "price range koto?" (used by
    src/api/webchat_routes.py — webchat only, nothing else calls this).

    Returns:
        {
          'category': str,
          'url':      str,
          'price_min': str,
          'price_max': str,
          'brands':   [{'name': str, 'count': str}, ...],
        }
        or None on failure/not found.
    """
    category = (category or '').strip()
    if not category:
        return None
    cache_key = category.lower()
    now = time.time()
    cached = _category_filters_cache.get(cache_key)
    if cached and (now - cached[0]) < _CATEGORY_FILTERS_TTL:
        return cached[1]

    try:
        started = datetime.now()
        resp = requests.get(CATEGORY_FILTERS_URL, params={'category': category, 'key': API_KEY}, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        payload = resp.json() if resp.text else {}
        passed = resp.status_code == 200 and bool(payload.get('success'))
        _log_api_call('fetch_category_filters', 'GET', CATEGORY_FILTERS_URL,
                      {'category': category}, resp.status_code, duration_ms,
                      'PASS' if passed else 'FAIL', resp.text[:400])
        if not passed:
            return None

        d = payload.get('data') or {}
        if not d.get('price_min') and not d.get('price_max'):
            return None

        result = {
            'category': str(d.get('category') or category).strip(),
            'url': str(d.get('url') or '').strip(),
            'price_min': str(d.get('price_min') or '').strip(),
            'price_max': str(d.get('price_max') or '').strip(),
            'brands': [
                {'name': str(b.get('name') or '').strip(), 'count': str(b.get('count') or '').strip()}
                for b in (d.get('brands') or []) if isinstance(b, dict)
            ],
        }
        _category_filters_cache[cache_key] = (now, result)
        return result
    except Exception as e:
        logger.error("fetch_category_filters failed: %s", e)
        return None


# ── Category list ─────────────────────────────────────────────────────────────

def fetch_categories() -> List[Dict]:
    try:
        resp = requests.get(CAT_LIST_URL, params={'key': API_KEY}, timeout=8)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not isinstance(data, list):
            return []
        return [
            {
                'category_id':      str(e.get('category_id', '')).strip(),
                'category_name':    str(e.get('category_name', '')).strip(),
                'bn_category_name': str(e.get('bn_category_name', '')).strip(),
                'cat_url':          str(e.get('cat_url', '')).strip(),
            }
            for e in data
            if isinstance(e, dict) and e.get('category_name')
        ]
    except Exception as e:
        logger.warning("fetch_categories failed: %s", e)
        return []


# ── FAQ from API ──────────────────────────────────────────────────────────────

_faq_api_cache: Optional[tuple] = None
_FAQ_API_TTL = 3600  # 1 hour


def fetch_faq_db() -> List[Dict]:
    """Fetch FAQ list from knowledge API (?intent=faqs).

    Returns list of dicts with keys: question_bn, answer_bn, question_en, answer_en.
    Cached for 1 hour. Falls back to empty list on failure.
    """
    global _faq_api_cache
    now = time.time()
    if _faq_api_cache and (now - _faq_api_cache[0]) < _FAQ_API_TTL:
        return _faq_api_cache[1]
    try:
        resp = requests.get(KNOWLEDGE_URL, params={'intent': 'faqs', 'key': API_KEY}, timeout=10)
        if resp.status_code != 200:
            logger.warning("fetch_faq_db HTTP %s", resp.status_code)
            return _faq_api_cache[1] if _faq_api_cache else []
        data = resp.json()
        items = [
            {
                'question_bn': str(d.get('question_bn') or '').strip(),
                'answer_bn':   str(d.get('answer_bn')   or '').strip(),
                'question_en': str(d.get('question_en') or '').strip(),
                'answer_en':   str(d.get('answer_en')   or '').strip(),
            }
            for d in (data.get('data') or [])
            if d.get('question_bn') or d.get('question_en')
        ]
        _faq_api_cache = (now, items)
        logger.info("fetch_faq_db: loaded %d FAQ items from API", len(items))
        return items
    except Exception as e:
        logger.error("fetch_faq_db failed: %s", e)
        return _faq_api_cache[1] if _faq_api_cache else []


# ── Knowledge / Return policy ─────────────────────────────────────────────────

_knowledge_cache: Dict[str, tuple] = {}
_KNOWLEDGE_TTL = 3600  # 1 hour — policy text rarely changes


# ── City / Area / Place Order (order flow) ────────────────────────────────────

_city_list_cache: Optional[tuple] = None
_area_list_cache: Optional[tuple] = None
_CITY_AREA_TTL = 86400  # 24h — city/area lists rarely change


def fetch_city_list() -> List[Dict]:
    """Fetch city list. Returns list of {'city_id', 'city_name'}."""
    global _city_list_cache
    now = time.time()
    if _city_list_cache and (now - _city_list_cache[0]) < _CITY_AREA_TTL:
        return _city_list_cache[1]
    try:
        started = datetime.now()
        resp = requests.get(CITY_LIST_URL, params={'key': API_KEY}, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        _log_api_call('city_list', 'GET', CITY_LIST_URL, {'key': '***'},
                      resp.status_code, duration_ms,
                      'PASS' if resp.status_code == 200 else 'FAIL', resp.text[:200])
        if resp.status_code != 200:
            return _city_list_cache[1] if _city_list_cache else []
        data = resp.json() if resp.text else {}
        rows = data.get('data') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return _city_list_cache[1] if _city_list_cache else []
        items = [
            {'city_id': str(r.get('city_id', '')).strip(),
             'city_name': str(r.get('city_name', '')).strip()}
            for r in rows if isinstance(r, dict) and r.get('city_id') and r.get('city_name')
        ]
        _city_list_cache = (now, items)
        return items
    except Exception as e:
        logger.warning("fetch_city_list failed: %s", e)
        return _city_list_cache[1] if _city_list_cache else []


def fetch_area_list() -> List[Dict]:
    """Fetch area list. Returns list of {'area_id', 'area_name', 'city_id'}."""
    global _area_list_cache
    now = time.time()
    if _area_list_cache and (now - _area_list_cache[0]) < _CITY_AREA_TTL:
        return _area_list_cache[1]
    try:
        started = datetime.now()
        resp = requests.get(AREA_LIST_URL, params={'key': API_KEY}, timeout=15)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        _log_api_call('area_list', 'GET', AREA_LIST_URL, {'key': '***'},
                      resp.status_code, duration_ms,
                      'PASS' if resp.status_code == 200 else 'FAIL', resp.text[:200])
        if resp.status_code != 200:
            return _area_list_cache[1] if _area_list_cache else []
        data = resp.json() if resp.text else {}
        rows = data.get('data') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return _area_list_cache[1] if _area_list_cache else []
        items = [
            {'area_id':   str(r.get('area_id', '')).strip(),
             'area_name': str(r.get('area_name', '')).strip(),
             'city_id':   str(r.get('city_id', '')).strip()}
            for r in rows if isinstance(r, dict) and r.get('area_id') and r.get('area_name')
        ]
        _area_list_cache = (now, items)
        return items
    except Exception as e:
        logger.warning("fetch_area_list failed: %s", e)
        return _area_list_cache[1] if _area_list_cache else []


def place_order(name: str, mobile: str, address: str,
                listing_id, qty: int, city_id, area_id) -> Dict[str, Any]:
    """POST to chatbot_place_order. Returns {'success': bool, 'message': str, 'raw': dict|str}."""
    payload = {
        'key':        API_KEY,
        'name':       str(name or '').strip(),
        'mobile':     str(mobile or '').strip(),
        'address':    str(address or '').strip(),
        'listing_id': int(listing_id) if str(listing_id).isdigit() else listing_id,
        'qty':        int(qty) if qty else 1,
        'city_id':    int(city_id) if str(city_id).isdigit() else city_id,
        'area_id':    int(area_id) if str(area_id).isdigit() else area_id,
    }
    try:
        started = datetime.now()
        resp = requests.post(PLACE_ORDER_URL, json=payload, timeout=15)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        ok = 200 <= resp.status_code < 300
        body: Any = resp.text
        try:
            body = resp.json()
            if isinstance(body, dict) and 'success' in body:
                ok = bool(body.get('success'))
        except Exception:
            pass
        # Mask API key in logs
        log_payload = dict(payload)
        log_payload['key'] = '***'
        _log_api_call('place_order', 'POST', PLACE_ORDER_URL, log_payload,
                      resp.status_code, duration_ms,
                      'PASS' if ok else 'FAIL', resp.text[:400])
        message  = ''
        order_id = ''
        order_no = ''
        if isinstance(body, dict):
            message = str(body.get('message') or '').strip()
            data = body.get('data') if isinstance(body.get('data'), dict) else {}
            order_id = str(data.get('order_id') or '').strip()
            order_no = str(data.get('order_no') or '').strip()
        return {'success': ok, 'message': message,
                'order_id': order_id, 'order_no': order_no, 'raw': body}
    except Exception as e:
        logger.error("place_order failed: %s", e)
        return {'success': False, 'message': str(e),
                'order_id': '', 'order_no': '', 'raw': None}


def fetch_order_status(order_no: str) -> Dict[str, Any]:
    """Look up an order by its order_no.

    Returns:
        On success: {'success': True, 'data': {...full order dict...}}
        On failure: {'success': False, 'message': str, 'data': {}}
    """
    if not order_no:
        return {'success': False, 'message': 'order_no required', 'data': {}}
    try:
        started = datetime.now()
        resp = requests.get(ORDER_STATUS_URL,
                            params={'order_no': str(order_no).strip(),
                                    'key': API_KEY},
                            timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        ok = 200 <= resp.status_code < 300
        body: Any = resp.text
        try:
            body = resp.json()
        except Exception:
            pass
        if isinstance(body, dict) and 'success' in body:
            ok = bool(body.get('success'))
        _log_api_call('order_status', 'GET', ORDER_STATUS_URL,
                      {'order_no': order_no}, resp.status_code, duration_ms,
                      'PASS' if ok else 'FAIL', resp.text[:400])
        if not isinstance(body, dict):
            return {'success': False, 'message': 'Unexpected response', 'data': {}}
        return {
            'success': bool(body.get('success')),
            'message': str(body.get('message') or '').strip(),
            'data':    body.get('data') or {},
        }
    except Exception as e:
        logger.error("fetch_order_status failed: %s", e)
        return {'success': False, 'message': str(e), 'data': {}}


def submit_seller_request(name: str, mobile: str, note: str) -> Dict[str, Any]:
    payload = {
        'key':    API_KEY,
        'name':   str(name or '').strip(),
        'mobile': str(mobile or '').strip(),
        'note':   str(note or '').strip(),
    }
    log_payload = {**payload, 'key': '***'}
    logger.info("submit_seller_request payload: %s", log_payload)

    # ── Attempt 1: standard JSON (same as working Postman call) ───────────────
    try:
        started = datetime.now()
        resp = requests.post(SELLER_REQUEST_URL, json=payload, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        ok = 200 <= resp.status_code < 300
        _log_api_call('seller_request', 'POST', SELLER_REQUEST_URL, log_payload,
                      resp.status_code, duration_ms, 'PASS' if ok else 'FAIL',
                      resp.text[:400])
        logger.info("submit_seller_request JSON: status=%d body=%.300s",
                    resp.status_code, resp.text)
        if ok:
            return {'success': True, 'raw': resp.text}
        logger.warning("submit_seller_request JSON non-2xx: %d %s",
                       resp.status_code, resp.text[:300])
    except Exception as e:
        logger.error("submit_seller_request JSON failed: %s", e)

    # ── Attempt 2: form-data fallback ─────────────────────────────────────────
    try:
        started = datetime.now()
        resp = requests.post(SELLER_REQUEST_URL, data=payload, timeout=10)
        duration_ms = int((datetime.now() - started).total_seconds() * 1000)
        ok = 200 <= resp.status_code < 300
        _log_api_call('seller_request_form', 'POST', SELLER_REQUEST_URL, log_payload,
                      resp.status_code, duration_ms, 'PASS' if ok else 'FAIL',
                      resp.text[:400])
        logger.info("submit_seller_request FORM: status=%d body=%.300s",
                    resp.status_code, resp.text)
        if ok:
            return {'success': True, 'raw': resp.text}
        return {'success': False, 'raw': resp.text}
    except Exception as e:
        logger.error("submit_seller_request FORM failed: %s", e)
        return {'success': False, 'raw': str(e)}


def fetch_return_policy() -> Optional[str]:
    """Fetch the Buying Terms & Refund Policy section from the knowledge API.

    Returns plain text (HTML stripped) of the Bangla return/refund policy,
    or None on failure.
    """
    import re as _re
    now = time.time()
    cached = _knowledge_cache.get('return_policy')
    if cached and (now - cached[0]) < _KNOWLEDGE_TTL:
        return cached[1]

    try:
        resp = requests.get(KNOWLEDGE_URL, params={'intent': 'terms', 'key': API_KEY}, timeout=10)
        if resp.status_code != 200:
            logger.warning("fetch_return_policy HTTP %s", resp.status_code)
            return None
        data = resp.json()
        items = data.get('data') or []
        text = None
        for item in items:
            name = item.get('term_type_name', '')
            if 'Buying' in name or 'Refund' in name or 'Return' in name:
                raw = item.get('term_bn') or item.get('term_en') or ''
                plain = _re.sub(r'<[^>]+>', ' ', raw)
                plain = _re.sub(r'\s+', ' ', plain).strip()
                text = plain
                break
        _knowledge_cache['return_policy'] = (now, text)
        return text
    except Exception as e:
        logger.error("fetch_return_policy failed: %s", e)
        return None
