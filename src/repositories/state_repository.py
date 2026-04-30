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

_product_context: Dict[str, List]    = {}
_product_url:     Dict[str, str]     = {}
_last_intent:     Dict[str, str]     = {}
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
    except Exception as e:
        logger.warning("_load_local_state failed: %s", e)


def _save_local_state() -> None:
    with _state_lock:
        try:
            os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
            state = {
                'user_product_context': _product_context,
                'user_last_intent':     _last_intent,
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


def search_faq(message: str, db: List[Dict]) -> Optional[str]:
    msg = message.lower().strip()
    if not msg:
        return None
    for item in db:
        q = item['question'].lower()
        if msg in q or q in msg:
            return item['answer']
    if any(w in msg for w in ['order', 'অর্ডার', 'kibabe', 'kivabe', 'কিভাবে']):
        for item in db:
            if 'অর্ডার' in item['question'] and 'কিভাবে' in item['question']:
                return item['answer']
    if any(w in msg for w in ['delivery', 'ডেলিভারি', 'koto din']):
        for item in db:
            if 'ডেলিভারি' in item['question'] or 'কত দিন' in item['question']:
                return item['answer']
    return None
