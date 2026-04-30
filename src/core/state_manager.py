"""
State persistence and FAQ database for SimpleChatbot.
Handles load/save of per-user product/order state and CSV FAQ lookup.
"""
import os
import json
import logging
import shutil
import tempfile
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class StateManager:
    """Manages file-backed chatbot state and FAQ CSV database."""

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root
        self.state_file = os.path.join(project_root, 'data', 'chatbot_state.json')
        self._state_lock = threading.Lock()

        # Per-user product/order state — NO mode, NO intent_content (Rules 13, 14)
        self.user_product_context: Dict[str, list] = {}
        self.user_selected_product: Dict[str, Dict[str, Any]] = {}
        self.user_product_url: Dict[str, str] = {}
        self.user_order_context: Dict[str, bool] = {}
        self.user_order_draft: Dict[str, Dict[str, str]] = {}
        self.user_pending_product_query: Dict[str, Dict[str, Any]] = {}
        self.user_last_intent: Dict[str, str] = {}

        self._load_state()

    # ─────────────────────────────────────────────────────────────
    # State persistence
    # ─────────────────────────────────────────────────────────────
    def _load_state(self) -> None:
        try:
            if not os.path.exists(self.state_file):
                return
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            self.user_product_context = dict(state.get('user_product_context') or {})
            self.user_selected_product = dict(state.get('user_selected_product') or {})
            self.user_order_context = {
                uid: bool(a) for uid, a in (state.get('user_order_context') or {}).items()
            }
            self.user_order_draft = dict(state.get('user_order_draft') or {})
            self.user_pending_product_query = dict(state.get('user_pending_product_query') or {})
            self.user_last_intent = dict(state.get('user_last_intent') or {})
        except Exception as e:
            logger.error("❌ State restore failed: %s", e)

    def save_state(self) -> None:
        with self._state_lock:
            try:
                os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
                state = {
                    'user_product_context': self.user_product_context,
                    'user_selected_product': self.user_selected_product,
                    'user_order_context': self.user_order_context,
                    'user_order_draft': self.user_order_draft,
                    'user_pending_product_query': self.user_pending_product_query,
                    'user_last_intent': self.user_last_intent,
                }
                dir_name = os.path.dirname(self.state_file)
                tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
                try:
                    with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                        json.dump(state, f, ensure_ascii=False)
                    shutil.move(tmp_path, self.state_file)
                except Exception:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    raise
            except Exception as e:
                logger.error("❌ State save failed: %s", e)

    def clear_product_search_cache(self, user_id: str, clear_pending: bool = False) -> None:
        self.user_product_context.pop(user_id, None)
        self.user_selected_product.pop(user_id, None)
        self.user_product_url.pop(user_id, None)
        if clear_pending:
            self.user_pending_product_query.pop(user_id, None)
            self.user_order_context.pop(user_id, None)
            self.user_order_draft.pop(user_id, None)

    # ─────────────────────────────────────────────────────────────
    # FAQ database
    # ─────────────────────────────────────────────────────────────
    def load_database(self) -> list:
        try:
            import csv
            path = os.path.join(self.project_root, 'data', 'database.csv')
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
            logger.error("❌ FAQ load failed: %s", e)
            return []

    def search_faq(self, message: str, database: list,
                   is_blocked_fn=None) -> Optional[str]:
        msg = message.lower().strip()
        if not msg:
            return None
        try:
            for item in database:
                q = item['question'].lower()
                if msg in q or q in msg:
                    if is_blocked_fn and is_blocked_fn(item['answer']):
                        continue
                    return item['answer']
            if any(w in msg for w in ['order', 'অর্ডার', 'kibabe', 'kivabe', 'কিভাবে']):
                for item in database:
                    q = item['question'].lower()
                    if 'অর্ডার' in q and 'কিভাবে' in q:
                        return item['answer']
            if any(w in msg for w in ['delivery', 'ডেলিভারি', 'koto din']):
                for item in database:
                    if 'ডেলিভারি' in item['question'] or 'কত দিন' in item['question']:
                        return item['answer']
        except Exception as e:
            logger.warning("FAQ search failed: %s", e)
        return None
