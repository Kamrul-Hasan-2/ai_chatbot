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
import contextlib
from datetime import datetime
from typing import Any, Dict, List, Optional

# Cross-process advisory file lock primitives (recheck #1). Best-effort: if the
# platform module is missing or locking fails, we degrade to the in-process lock.
try:
    import fcntl as _fcntl          # POSIX
except ImportError:
    _fcntl = None
try:
    import msvcrt as _msvcrt        # Windows
except ImportError:
    _msvcrt = None

from models.chatbot_config import CONTEXT_TTL_SECONDS
from services.api_client_service import fetch_intent_from_history

logger = logging.getLogger(__name__)

# ── Per-user in-session state ─────────────────────────────────────────────────

_product_context:   Dict[str, List] = {}
_product_url:       Dict[str, str]  = {}
_last_intent:       Dict[str, str]  = {}
_session_category:  Dict[str, str]  = {}  # persisted so restarts don't lose category
_session_category_ts: Dict[str, str] = {}  # user_id → ISO ts when session category last set (TTL)
_pending_question:  Dict[str, str]  = {}  # message that triggered a clarification prompt
_pending_budget:    Dict[str, Dict] = {}  # category/brand/title waiting for a budget reply
_search_pool:      Dict[str, List] = {}  # full 15-product result pool per user
_search_offset:    Dict[str, int]  = {}  # next-page offset into _search_pool
_search_key:       Dict[str, str]  = {}  # cache key (keywords|min|max) for the pool
_user_profile:     Dict[str, Dict] = {}  # per-user behavioural profile (JSON dict form)
_knowledge_count:  Dict[str, Dict] = {}  # per-user knowledge calls today: {user_id: {date: 'YYYY-MM-DD', count: int}}
_order_flow:       Dict[str, Dict] = {}  # per-user in-progress order: {step, name, mobile, address, qty, city_id, area_id, listing_id, product_title, product_url}
_last_seen:        Dict[str, str]  = {}  # user_id → ISO ts of last state write (retention pruning)
_state_lock = threading.Lock()

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
_STATE_FILE   = os.path.join(_PROJECT_ROOT, 'data', 'chatbot_state.json')

# Per-user state retention — abandoned entries (incl. order mobile/address PII)
# are pruned after this window so chatbot_state.json stays bounded. (recheck #5)
try:
    _STATE_RETENTION_SECONDS = max(3600, int(os.getenv('STATE_RETENTION_SECONDS', str(7 * 24 * 3600))))
except Exception:
    _STATE_RETENTION_SECONDS = 7 * 24 * 3600

# Run stale-state pruning at most this often at runtime (recheck #3 — not just
# at boot). Each worker prunes independently based on the on-disk last-seen.
_PRUNE_INTERVAL_SECONDS = 3600
_last_prune_ts = None

# (disk_key, in-memory dict) for every persisted per-user dict.
_MEM_MAP = (
    ('user_product_context',  _product_context),
    ('user_product_url',      _product_url),
    ('user_last_intent',      _last_intent),
    ('user_session_category', _session_category),
    ('user_session_category_ts', _session_category_ts),
    ('user_pending_question', _pending_question),
    ('user_pending_budget',   _pending_budget),
    ('user_search_pool',      _search_pool),
    ('user_search_offset',    _search_offset),
    ('user_search_key',       _search_key),
    ('user_profile',          _user_profile),
    ('user_knowledge_count',  _knowledge_count),
    ('user_order_flow',       _order_flow),
    ('user_last_seen',        _last_seen),
)


@contextlib.contextmanager
def _interprocess_lock():
    """Best-effort advisory cross-process lock around state read-modify-write so
    two Gunicorn workers can't interleave and lose each other's update. (#1)
    Degrades to a no-op if the platform lock is unavailable/fails."""
    lock_path = _STATE_FILE + '.lock'
    fh = None
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        fh = open(lock_path, 'a+')
    except Exception:
        fh = None
    try:
        if fh is not None:
            try:
                if _fcntl is not None:
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
                elif _msvcrt is not None:
                    fh.seek(0)
                    _msvcrt.locking(fh.fileno(), _msvcrt.LK_LOCK, 1)
            except Exception as e:
                logger.debug("interprocess lock acquire failed: %s", e)
        yield
    finally:
        if fh is not None:
            try:
                if _fcntl is not None:
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
                elif _msvcrt is not None:
                    fh.seek(0)
                    _msvcrt.locking(fh.fileno(), _msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass


def _read_disk_state() -> Dict:
    try:
        if os.path.exists(_STATE_FILE):
            with open(_STATE_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception as e:
        logger.warning("read state file failed: %s", e)
    return {}


def _atomic_write(state: Dict) -> None:
    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_STATE_FILE), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        shutil.move(tmp, _STATE_FILE)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _load_local_state() -> None:
    state = _read_disk_state()
    for key, mem in _MEM_MAP:
        v = state.get(key)
        if isinstance(v, dict):
            mem.update(v)
    # Backfill last-seen for legacy users so retention also applies to them.
    now_iso = datetime.now().isoformat()
    seen_uids = set()
    for key, mem in _MEM_MAP:
        if mem is not _last_seen:
            seen_uids.update(mem.keys())
    for uid in seen_uids:
        _last_seen.setdefault(uid, now_iso)
    # Legacy session categories (written before timestamps existed) have no ts
    # and would never TTL-expire — stamp them as already-stale so they expire on
    # next access instead of resurrecting an old category. (recheck #1)
    for uid in list(_session_category.keys()):
        _session_category_ts.setdefault(uid, '1970-01-01T00:00:00')
    _prune_stale_state()


def _prune_stale_state() -> None:
    """Remove per-user state for users inactive beyond the retention window, from
    BOTH memory and disk, via a per-user read-modify-write under the cross-process
    lock so other workers' fresh state is preserved (NOT a full overwrite, which
    would re-introduce the clobber). Driven by the authoritative on-disk last-seen
    timestamps. (recheck #5 / #3)"""
    now = datetime.now()
    stale = []
    with _state_lock:
        with _interprocess_lock():
            disk = _read_disk_state()
            seen = disk.get('user_last_seen') or {}
            for uid, ts in seen.items():
                try:
                    if (now - datetime.fromisoformat(ts)).total_seconds() > _STATE_RETENTION_SECONDS:
                        stale.append(uid)
                except Exception:
                    continue
            if not stale:
                return
            for uid in stale:
                for _key, mem in _MEM_MAP:
                    mem.pop(uid, None)            # in-memory
                    d = disk.get(_key)
                    if isinstance(d, dict):
                        d.pop(uid, None)          # on-disk
            _atomic_write(disk)
    logger.info("Pruned %d stale user-state entries (>%ds)", len(stale), _STATE_RETENTION_SECONDS)


def _maybe_prune() -> None:
    """Throttled runtime pruning (recheck #3) — at most once per interval, so a
    long-running worker eventually drops abandoned order PII without a restart."""
    global _last_prune_ts
    now = datetime.now()
    if _last_prune_ts is not None and (now - _last_prune_ts).total_seconds() < _PRUNE_INTERVAL_SECONDS:
        return
    try:
        _prune_stale_state()
        _last_prune_ts = now   # only mark done on success → retry next save on failure (#2)
    except Exception as e:
        logger.warning("periodic prune failed (will retry): %s", e)


def reload_user_state(user_id: str) -> None:
    """Refresh THIS user's in-memory state from the shared JSON file before a turn.

    Best-effort cross-worker convergence (finding #6): under multiple Gunicorn
    workers each holds its own in-memory copy, so state written by worker A is
    invisible to worker B until B re-reads it. Only the current user's keys are
    touched. If the user was REMOVED on disk (e.g. another worker called
    clear_product_state), the stale in-memory copy is dropped too. (recheck #4)
    NOTE: a mitigation, not full safety — true multi-worker correctness needs a
    shared store (Redis/DB) or a single worker (GUNICORN_WORKERS=1).
    """
    if not user_id:
        return
    state = _read_disk_state()
    if not state:
        return
    for key, mem in _MEM_MAP:
        if key not in state:
            continue   # key absent on a partial/old file — don't wipe memory
        disk = state.get(key) or {}
        if user_id in disk:
            mem[user_id] = disk[user_id]
        else:
            mem.pop(user_id, None)


def _save_local_state(user_id: Optional[str] = None) -> None:
    """Persist state. With a user_id (the normal path) this does a per-user
    read-modify-write under a cross-process advisory lock: only THAT user's keys
    change on disk and the read-modify-write is serialised across workers, so a
    concurrent worker can't lose another's update. (recheck #3, #1). Without a
    user_id, overlays all in-memory users onto disk. The lock is best-effort —
    if the platform primitive is unavailable it degrades to the in-process lock,
    so GUNICORN_WORKERS=1 remains the simplest guarantee."""
    with _state_lock:
        with _interprocess_lock():
            try:
                if user_id is not None:
                    _last_seen[user_id] = datetime.now().isoformat()
                disk = _read_disk_state()
                for key, mem in _MEM_MAP:
                    d = disk.get(key)
                    if not isinstance(d, dict):
                        d = {}
                    if user_id is not None:
                        if user_id in mem:
                            d[user_id] = mem[user_id]
                        else:
                            d.pop(user_id, None)
                    else:
                        d.update(mem)
                    disk[key] = d
                _atomic_write(disk)
            except Exception as e:
                logger.error("_save_local_state failed: %s", e)
    # Runtime retention pruning (outside the lock to avoid re-entrancy). (#3)
    _maybe_prune()


_load_local_state()
_last_prune_ts = datetime.now()   # boot prune just ran inside _load_local_state


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

    # Context TTL — expire stale context (INCLUDING a saved category) after
    # inactivity, so e.g. Monday's "laptop" search isn't silently reused on
    # Friday. Previously the category branch skipped TTL entirely. (finding #7)
    updated_at = prev.get('updated_at')
    if updated_at:
        try:
            age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
            if age > CONTEXT_TTL_SECONDS:
                logger.info("Context expired for %s (%.0fs)", user_id, age)
                # Also clear session memory + product state so the expired
                # category can't be resurrected via get_session_category()
                # downstream (which is checked before the DB ctx). (recheck #1)
                _session_category.pop(user_id, None)
                _session_category_ts.pop(user_id, None)
                clear_product_state(user_id)   # also persists the session clear
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
    _save_local_state(user_id)


def get_last_intent(user_id: str) -> str:
    return _last_intent.get(user_id, '')


def set_pending_question(user_id: str, question: str) -> None:
    """Save the message that triggered a product_clarification prompt."""
    _pending_question[user_id] = question
    _save_local_state(user_id)


def get_pending_question(user_id: str) -> str:
    """Return and clear the pending question (one-shot — consumed on read)."""
    val = _pending_question.pop(user_id, '')
    if val:
        _save_local_state(user_id)
    return val


def set_pending_budget(user_id: str, ctx: Dict) -> None:
    """Save category/brand/title context while waiting for user's budget reply."""
    _pending_budget[user_id] = dict(ctx)
    _save_local_state(user_id)


def get_pending_budget(user_id: str) -> Dict:
    """Return and clear the pending budget context (one-shot — consumed on read)."""
    val = _pending_budget.pop(user_id, {})
    if val:
        _save_local_state(user_id)
    return val


# ── In-session product state ──────────────────────────────────────────────────

def set_product_context(user_id: str, products: List) -> None:
    _product_context[user_id] = products
    _save_local_state(user_id)


def get_product_context(user_id: str) -> List:
    return _product_context.get(user_id, [])


def set_product_url(user_id: str, url: str) -> None:
    _product_url[user_id] = url
    _save_local_state(user_id)


def get_product_url(user_id: str) -> str:
    return _product_url.get(user_id, '')


def clear_product_state(user_id: str) -> None:
    _product_context.pop(user_id, None)
    _product_url.pop(user_id, None)
    _search_pool.pop(user_id, None)
    _search_offset.pop(user_id, None)
    _search_key.pop(user_id, None)
    _save_local_state(user_id)


def set_search_pool(user_id: str, key: str, pool: List) -> None:
    _search_pool[user_id] = pool
    _search_key[user_id] = key
    _search_offset[user_id] = 0
    _save_local_state(user_id)


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
    _save_local_state(user_id)
    return new_off


def set_session_category(user_id: str, category: str) -> None:
    _session_category[user_id] = category
    _session_category_ts[user_id] = datetime.now().isoformat()
    _save_local_state(user_id)


def get_session_category(user_id: str) -> str:
    """Return the saved session category, but self-expire it after
    CONTEXT_TTL_SECONDS of inactivity. This closes the category-bleed bug for
    BOTH the stale-DB and EMPTY-DB paths (load_context returns early on empty
    history, so it can't clear this) — session memory was the only copy without
    its own TTL. (recheck #2)"""
    cat = _session_category.get(user_id, '')
    if not cat:
        return ''
    ts = _session_category_ts.get(user_id)
    if ts:
        try:
            if (datetime.now() - datetime.fromisoformat(ts)).total_seconds() > CONTEXT_TTL_SECONDS:
                _session_category.pop(user_id, None)
                _session_category_ts.pop(user_id, None)
                _save_local_state(user_id)
                return ''
        except Exception:
            pass
    return cat


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
    _save_local_state(user_id)


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
    _save_local_state(user_id)
    return rec['count']


# ── Order flow (multi-step purchase) ──────────────────────────────────────────

def get_order_flow(user_id: str) -> Dict:
    """Return current order-flow state dict for user, or {} if none."""
    return dict(_order_flow.get(user_id) or {})


def set_order_flow(user_id: str, state: Dict) -> None:
    """Persist the in-progress order state (step + collected fields)."""
    _order_flow[user_id] = dict(state or {})
    _save_local_state(user_id)


def clear_order_flow(user_id: str) -> None:
    """Drop any in-progress order state for this user."""
    if user_id in _order_flow:
        _order_flow.pop(user_id, None)
        _save_local_state(user_id)


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
