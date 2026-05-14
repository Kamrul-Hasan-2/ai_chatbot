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
    CAT_LIST_URL,
    _log_api_call,
)

logger = logging.getLogger(__name__)

# ── Simple in-memory caches ───────────────────────────────────────────────────

_search_cache:  Dict[str, tuple] = {}
_history_cache: Dict[str, tuple] = {}
_SEARCH_TTL  = 300
_HISTORY_TTL = 60
_SEARCH_MAX  = 200


# ── Responder / mode ──────────────────────────────────────────────────────────

def check_responder_type(user_id: str) -> Optional[str]:
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
                return label
        return None
    except Exception as e:
        logger.warning("check_responder_type failed: %s", e)
        return None


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
    result = _do_search(keywords, price_max, price_min)
    _search_cache[cache_key] = (now, result)
    if len(_search_cache) > _SEARCH_MAX:
        oldest = min(_search_cache, key=lambda k: _search_cache[k][0])
        _search_cache.pop(oldest, None)
    return result


def _do_search(keywords: str, price_max: Optional[int],
               price_min: Optional[int]) -> Dict[str, Any]:
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
            return {'products_found': 0, 'products': []}
        data = resp.json()
        if not data.get('getListingItem') or len(data['getListingItem']) < 2:
            return {'products_found': 0, 'products': []}
        total = data['getListingItem'][0]
        raw   = data['getListingItem'][1] or []
        top = raw[:15]
        products = [{
            'title':          p.get('ListingTitle', 'N/A'),
            'price':          p.get('ListingPrice', 'N/A'),
            'original_price': p.get('app_ListingOriginalPrice', ''),
            'discount':       p.get('ListingDiscountPercentage', 0),
            'url':            p.get('ListingURL', ''),
            'image':          p.get('ListingThumbAvator', ''),
        } for p in top]
        return {'products_found': len(top), 'total_products': total, 'products': products}
    except Exception as e:
        logger.error("_do_search failed: %s", e)
        return {'products_found': 0, 'products': []}


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
        sender = str(item.get('sender_type') or '').strip()
        role   = str(item.get('role') or '').strip().lower()
        if sender == '2' or role in {'assistant', 'bot', 'ai'}:
            lines.append(f"Bot: {text}")
        elif sender == '1' or role in {'agent', 'human'}:
            lines.append(f"Agent: {text}")
        else:
            lines.append(f"User: {text}")
    return lines[-10:]


# ── Intent content from history (Rule 14) ────────────────────────────────────

def fetch_intent_from_history(user_id: str) -> Dict:
    """Pull last saved intent_content from history — DB is source of truth."""
    url = f"{HISTORY_URL.rstrip('/')}?user_id={user_id}&limit=10&key={API_KEY}"
    try:
        resp = requests.get(url, timeout=2)
        if not (200 <= resp.status_code < 300):
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
            if str(item.get('sender_type') or '').strip() != '2':
                continue
            ic = item.get('intent_content')
            if isinstance(ic, str):
                try:
                    ic = json.loads(ic)
                except Exception:
                    continue
            if isinstance(ic, dict) and (ic.get('cat') or ic.get('brand')
                                         or ic.get('title') or ic.get('product_url')):
                return ic
    except Exception as e:
        logger.warning("fetch_intent_from_history failed: %s", e)
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
                return True
        except Exception as e:
            logger.warning("save_message[%s] failed: %s", mode, e)
    return False


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
            }
            for e in data
            if isinstance(e, dict) and e.get('category_id') and e.get('category_name')
        ]
    except Exception as e:
        logger.warning("fetch_categories failed: %s", e)
        return []
