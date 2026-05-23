"""
src/repositories/state_repository.py — load/save per-user context.

DB/API is the single source of truth for intent_content (Rule 14).
Local state holds only in-session product data and last intent.

Public functions:
  load_context(user_id)               → dict  (from DB via api_client_service)
  save_last_intent(user_id, intent)   → None
  get_last_intent(user_id)            → str
  set_product_context(user_id, list)  → None
  get_product_context(user_id)        → list
  set_product_url(user_id, url)       → None
  get_product_url(user_id)            → str
  clear_product_state(user_id)        → None
  set_session_category(user_id, cat)  → None
  get_session_category(user_id)       → str
  load_user_profile(user_id)          → UserProfile
  save_user_profile(user_id, profile) → None
  load_faq_db()                       → list[dict]
  search_faq(message, db)             → str | None
"""
import os
import json
import logging
import shutil
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.chatbot_config import CONTEXT_TTL_SECONDS
from services.api_client_service import fetch_intent_from_history

logger = logging.getLogger(__name__)

# ── Per-user in-session state ─────────────────────────────────────────────────

_product_context:   Dict[str, List] = {}
_product_url:       Dict[str, str]  = {}
_last_intent:       Dict[str, str]  = {}
_session_category:  Dict[str, str]  = {}  # persisted so restarts don't lose category
_pending_question:  Dict[str, str]  = {}  # message that triggered a clarification prompt
_pending_budget:    Dict[str, Dict] = {}  # category/brand/title waiting for a budget reply
_search_pool:      Dict[str, List] = {}  # full 15-product result pool per user
_search_offset:    Dict[str, int]  = {}  # next-page offset into _search_pool
_search_key:       Dict[str, str]  = {}  # cache key (keywords|min|max) for the pool
_user_profile:     Dict[str, Dict] = {}  # per-user behavioural profile (JSON dict form)
_knowledge_count:  Dict[str, Dict] = {}  # per-user knowledge calls today: {user_id: {date: 'YYYY-MM-DD', count: int}}
_state_lock = threading.Lock()

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
_STATE_FILE   = os.path.join(_PROJECT_ROOT, 'data', 'chatbot_state.json')


def _load_local_state() -> None:
    try:
        if not os.path.exists(_STATE_FILE):
            return
        with open(_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        _product_context.update(state.get('user_product_context') or {})
        _last_intent.update(state.get('user_last_intent') or {})
        _session_category.update(state.get('user_session_category') or {})
        _user_profile.update(state.get('user_profile') or {})
        _knowledge_count.update(state.get('user_knowledge_count') or {})
    except Exception as e:
        logger.warning("_load_local_state failed: %s", e)


def _save_local_state() -> None:
    with _state_lock:
        try:
            os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
            state = {
                'user_product_context':  _product_context,
                'user_last_intent':      _last_intent,
                'user_session_category': _session_category,
                'user_profile':          _user_profile,
                'user_knowledge_count':  _knowledge_count,
            }
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_STATE_FILE), suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False)
                shutil.move(tmp, _STATE_FILE)
            except Exception:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
        except Exception as e:
            logger.error("_save_local_state failed: %s", e)


_load_local_state()


# ── Context load from DB ──────────────────────────────────────────────────────

def load_context(user_id: str) -> Dict:
    """Fetch last intent_content from DB. Normalise and return."""
    try:
        prev = dict(fetch_intent_from_history(user_id) or {})
    except Exception as e:
        logger.warning("load_context DB fetch failed: %s", e)
        return {}

    if not prev:
        return {}

    # Context TTL — only enforce when no category is saved
    if not prev.get('cat') and not prev.get('category'):
        updated_at = prev.get('updated_at')
        if updated_at:
            try:
                age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
                if age > CONTEXT_TTL_SECONDS:
                    logger.info("Context expired for %s (%.0fs)", user_id, age)
                    return {}
            except Exception:
                pass

    # Normalise cat/category
    if prev.get('cat') and not prev.get('category'):
        prev['category'] = prev['cat']

    # Carry previous values for merge logic
    prev['prev_cat']   = prev.get('cat', '')
    prev['prev_brand'] = prev.get('brand', '')
    prev['prev_title'] = prev.get('title', '')

    for field in ('price_max', 'price_min'):
        try:
            v = int(prev[field]) if field in prev else None
            prev[field] = v if v and v > 0 else None
        except (ValueError, TypeError):
            prev[field] = None
        prev[f'prev_{field}'] = prev[field]

    return prev


# ── Last intent ───────────────────────────────────────────────────────────────

def save_last_intent(user_id: str, intent: str) -> None:
    _last_intent[user_id] = intent
    _save_local_state()


def get_last_intent(user_id: str) -> str:
    return _last_intent.get(user_id, '')


def set_pending_question(user_id: str, question: str) -> None:
    """Save the message that triggered a product_clarification prompt."""
    _pending_question[user_id] = question


def get_pending_question(user_id: str) -> str:
    """Return and clear the pending question (one-shot — consumed on read)."""
    return _pending_question.pop(user_id, '')


def set_pending_budget(user_id: str, ctx: Dict) -> None:
    """Save category/brand/title context while waiting for user's budget reply."""
    _pending_budget[user_id] = dict(ctx)


def get_pending_budget(user_id: str) -> Dict:
    """Return and clear the pending budget context (one-shot — consumed on read)."""
    return _pending_budget.pop(user_id, {})


# ── In-session product state ──────────────────────────────────────────────────

def set_product_context(user_id: str, products: List) -> None:
    _product_context[user_id] = products


def get_product_context(user_id: str) -> List:
    return _product_context.get(user_id, [])


def set_product_url(user_id: str, url: str) -> None:
    _product_url[user_id] = url


def get_product_url(user_id: str) -> str:
    return _product_url.get(user_id, '')


def clear_product_state(user_id: str) -> None:
    _product_context.pop(user_id, None)
    _product_url.pop(user_id, None)
    _search_pool.pop(user_id, None)
    _search_offset.pop(user_id, None)
    _search_key.pop(user_id, None)


def set_search_pool(user_id: str, key: str, pool: List) -> None:
    _search_pool[user_id] = pool
    _search_key[user_id] = key
    _search_offset[user_id] = 0


def get_search_pool(user_id: str) -> tuple:
    """Return (pool, key, offset). Empty pool=[] if none cached."""
    return (
        _search_pool.get(user_id, []),
        _search_key.get(user_id, ''),
        _search_offset.get(user_id, 0),
    )


def advance_search_offset(user_id: str, by: int = 3) -> int:
    """Bump and return the new offset."""
    new_off = _search_offset.get(user_id, 0) + by
    _search_offset[user_id] = new_off
    return new_off


def set_session_category(user_id: str, category: str) -> None:
    _session_category[user_id] = category
    _save_local_state()


def get_session_category(user_id: str) -> str:
    return _session_category.get(user_id, '')


# ── User profile ──────────────────────────────────────────────────────────────

def load_user_profile(user_id: str):
    """Return a UserProfile (always — empty for a new user)."""
    from utils.user_profile import UserProfile
    return UserProfile.from_dict(_user_profile.get(user_id))


def save_user_profile(user_id: str, profile) -> None:
    """Persist a UserProfile to the JSON state file."""
    if profile is None:
        return
    _user_profile[user_id] = profile.to_dict()
    _save_local_state()


# ── Knowledge intent rate limiting (Groq-backed answers, max 5/user/day) ─────

def get_knowledge_count(user_id: str) -> int:
    """Return today's Groq-backed knowledge answer count for this user (0 if new day)."""
    today = datetime.now().strftime('%Y-%m-%d')
    rec = _knowledge_count.get(user_id)
    if not rec or rec.get('date') != today:
        return 0
    return int(rec.get('count', 0))


def increment_knowledge_count(user_id: str) -> int:
    """Bump and return today's knowledge count. Auto-resets at midnight."""
    today = datetime.now().strftime('%Y-%m-%d')
    rec = _knowledge_count.get(user_id) or {}
    if rec.get('date') != today:
        rec = {'date': today, 'count': 0}
    rec['count'] = int(rec.get('count', 0)) + 1
    _knowledge_count[user_id] = rec
    _save_local_state()
    return rec['count']


# ── FAQ database ──────────────────────────────────────────────────────────────

def load_faq_db() -> List[Dict]:
    try:
        import csv
        path = os.path.join(_PROJECT_ROOT, 'data', 'database.csv')
        if not os.path.exists(path):
            return []
        db = []
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                q = row.get('প্রশ্ন') or row.get('প্রশ্ন ') or row.get('Question')
                a = row.get('উত্তর') or row.get('Answer')
                if q and a:
                    db.append({'question': q.strip(), 'answer': a.strip()})
        return db
    except Exception as e:
        logger.error("load_faq_db failed: %s", e)
        return []


_BN_TO_EN = {
    'ট্র্যাক': 'track', 'ট্র্যাকিং': 'tracking', 'ট্র্যাক করবো': 'track',
    'অর্ডার': 'order', 'পেমেন্ট': 'payment', 'ডেলিভারি': 'delivery',
    'রিটার্ন': 'return', 'রিফান্ড': 'refund', 'ক্যান্সেল': 'cancel',
    'রেজিস্ট্রেশন': 'registration', 'অ্যাকাউন্ট': 'account',
    'পাসওয়ার্ড': 'password', 'লগইন': 'login', 'বিল': 'bill',
    'ইনভয়েস': 'invoice', 'ওয়ারেন্টি': 'warranty', 'গ্যারান্টি': 'guarantee',
}


def search_faq(message: str, db: List[Dict]) -> Optional[str]:
    msg = message.lower().strip()
    if not msg or not db:
        return None

    # Expand Bangla terms to their English equivalents so they score against
    # question_en fields (e.g. "ট্র্যাক" → "track").
    expanded = msg
    for bn, en in _BN_TO_EN.items():
        if bn in expanded:
            expanded = expanded + ' ' + en

    msg_words = [w for w in expanded.split() if len(w) >= 3]

    best_score = 0
    best_answer = None

    for item in db:
        # API format: question_bn / answer_bn
        if 'question_bn' in item:
            q_bn = (item.get('question_bn') or '').lower()
            q_en = (item.get('question_en') or '').lower()
            score = sum(1 for w in msg_words if w in q_bn or w in q_en)
            threshold = max(1, len([w for w in msg.split() if len(w) >= 3]) // 2)
            if score >= threshold and score > best_score:
                best_score = score
                best_answer = item.get('answer_bn') or item.get('answer_en') or ''
        else:
            # Legacy CSV format: question / answer
            q = (item.get('question') or '').lower()
            if msg in q or q in msg:
                return item.get('answer', '')

    return best_answer
