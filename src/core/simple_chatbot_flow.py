"""
Simple Chatbot Flow - Refactored
=================================
Key changes vs previous version:
- Single structured-JSON Groq call (one prompt returns intent + entities + follow-up flag)
- Clean context merge: category-switch reset, follow-up inheritance, 30-min TTL
- Fast-path short-circuit for greetings/thanks/selections (saves Groq calls)
- Atomic state file writes with thread lock
- In-memory caches for search results and history (DB-only, no Redis)
- Fixed: standalone "good"/"ভালো" no longer triggers comparison mode
- Fixed: category-switch uses category field, not title field
"""
import os
import sys
import logging
import threading
import tempfile
import shutil
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import json
import re
from enum import Enum
import requests
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from groq import Groq
except ImportError:
    Groq = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _log_api_call(api_name, method, url, request_payload, status_code, duration_ms, status, response_preview=""):
    """Write outbound API call details to daily API log file."""
    try:
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"api_calls_{datetime.now().strftime('%Y-%m-%d')}.log")
        entry = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "api_name": api_name, "method": method, "url": url,
            "request": request_payload, "status_code": status_code,
            "duration_ms": duration_ms, "result": status,
            "response_preview": (response_preview or "")[:400]
        }
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("[API_LOG] %s %s %s status=%s result=%s duration_ms=%s",
                    api_name, method, url, status_code, status, duration_ms)
    except Exception as e:
        logger.warning("API log write failed: %s", e)


class ChatMode(Enum):
    AI = "ai"
    HUMAN = "human"


AI_ACTIVE_STATUS = "AI Active"
HUMAN_SUPPORT_REQUIRED_STATUS = "Human Support Required"

# Whitelist: Groq cannot invent categories outside this set
VALID_CATEGORIES = {
    'laptop', 'desktop', 'phone', 'mobile', 'tablet', 'ac', 'tv', 'monitor',
    'mouse', 'keyboard', 'headphone', 'watch', 'smartwatch', 'printer',
    'camera', 'router', 'ssd', 'ram', 'ups', 'ips', 'speaker', 'cctv', ''
}

VALID_INTENTS = {
    'product_search', 'price_query', 'comparison', 'ordering', 'delivery',
    'greeting', 'goodbye', 'thanks', 'complaint', 'faq', 'unknown'
}

# Context expires after this duration (in seconds)
CONTEXT_TTL_SECONDS = 1800  # 30 minutes


class SimpleChatbot:
    """Refactored chatbot with structured intent extraction and clean context merging."""

    # Fast-path regex patterns (match early, skip Groq entirely)
    FAST_PATH_PATTERNS = {
        'greeting': re.compile(
            r'^\s*(hi|hello|hey|hlw|hai|salam|assalamu\s*alaikum|assalamualaikum|'
            r'হাই|হ্যালো|হেলো|সালাম|আসসালামু\s*আলাইকুম|আসসালামুয়ালাইকুম)\s*[!.?]*\s*$',
            re.IGNORECASE
        ),
        'goodbye': re.compile(
            r'^\s*(bye|goodbye|see\s*you|take\s*care|allah\s*hafez|ok\s*bye|'
            r'বিদায়|আল্লাহ\s*হাফেজ|বাই|আবার\s*দেখা\s*হবে)\s*[!.?]*\s*$',
            re.IGNORECASE
        ),
        'thanks': re.compile(
            r'^\s*(thanks?|thank\s*you|thx|thanku|thankyou|thanks\s*a\s*lot|'
            r'ধন্যবাদ|অনেক\s*ধন্যবাদ)\s*[!.?]*\s*$',
            re.IGNORECASE
        ),
        'ok_ack': re.compile(
            r'^\s*(ok|okay|okk|okey|acha|accha|ঠিক\s*আছে|আচ্ছা|ওকে)\s*[!.?]*\s*$',
            re.IGNORECASE
        ),
    }

    def __init__(self):
        self.project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        self.state_file = os.path.join(self.project_root, 'data', 'chatbot_state.json')

        # Thread-safety for state writes
        self._state_lock = threading.Lock()

        # Groq client
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key and Groq:
            self.groq_client = Groq(api_key=groq_api_key)
            self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        else:
            self.groq_client = None
            logger.warning("⚠️ Groq API not available")

        # Per-user state
        self.user_modes: Dict[str, ChatMode] = {}
        self.user_conversation_status: Dict[str, str] = {}
        self.user_product_context: Dict[str, list] = {}
        self.user_selected_product: Dict[str, Dict[str, Any]] = {}
        self.user_order_context: Dict[str, bool] = {}
        self.user_order_draft: Dict[str, Dict[str, str]] = {}
        self.user_pending_product_query: Dict[str, Dict[str, Any]] = {}
        self.user_last_intent: Dict[str, str] = {}
        self.user_intent_content: Dict[str, Dict[str, Any]] = {}

        # In-memory caches (process-local, cleared on restart — fine for this use case)
        self._search_cache: Dict[str, Tuple[float, Dict]] = {}  # {keywords: (ts, result)}
        self._search_cache_ttl = 300  # 5 min
        self._search_cache_max = 200

        self._history_cache: Dict[str, Tuple[float, str]] = {}  # {user_id: (ts, context)}
        self._history_cache_ttl = 60  # 1 min

        self._responder_cache: Dict[str, Tuple[float, Optional[str]]] = {}
        self._responder_cache_ttl = 60  # 1 min

        # BDStall config
        self.api_url = "https://www.bdstall.com/api/item/ai_search/"
        self.api_key = os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.delivery_intent_api_url = "https://www.bdstall.com/api/item/ai_template/"
        self.order_intent_api_url = "https://www.bdstall.com/api/item/ai_template/"
        self.assign_agent_api_url = os.getenv(
            'ASSIGN_AGENT_API_URL', 'https://www.bdstall.com/api/item/chatbot_assign_agent/'
        )
        self.assign_agent_api_key = os.getenv('ASSIGN_AGENT_API_KEY', self.api_key)
        self.responder_api_url = os.getenv(
            'RESPONDER_API_URL', 'https://www.bdstall.com/api/item/chatbot_responder/'
        )
        self.responder_api_key = os.getenv('RESPONDER_API_KEY', self.api_key)
        self.chatbot_history_api_url = os.getenv(
            'CHATBOT_HISTORY_API_URL', 'https://www.bdstall.com/api/item/chatbot_history/'
        )
        try:
            self.chatbot_history_limit = int(os.getenv('CHATBOT_HISTORY_LIMIT', '5'))
        except Exception:
            self.chatbot_history_limit = 5

        self._load_state()
        self.database = self._load_database()
        self.search_intent_items = self._load_search_intent_items()
        self.search_intent_items_mtime: Optional[float] = self._get_search_items_mtime()

        logger.info("✅ Simple Chatbot Initialized")
        logger.info(f"🌐 BDStall API: {self.api_url}")
        logger.info(f"📚 Database: {len(self.database)} FAQ responses loaded")
        logger.info("🧭 Search-intent items loaded: %s", len(self.search_intent_items))

    # ─────────────────────────────────────────────────────────────────
    # State persistence (atomic writes, thread-safe)
    # ─────────────────────────────────────────────────────────────────
    def _load_state(self) -> None:
        try:
            if not os.path.exists(self.state_file):
                return
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            self.user_modes = {
                uid: ChatMode(m) for uid, m in (state.get('user_modes') or {}).items()
                if m in {ChatMode.AI.value, ChatMode.HUMAN.value}
            }
            self.user_conversation_status = dict(state.get('user_conversation_status') or {})
            self.user_product_context = dict(state.get('user_product_context') or {})
            self.user_selected_product = dict(state.get('user_selected_product') or {})
            self.user_order_context = {
                uid: bool(active) for uid, active in (state.get('user_order_context') or {}).items()
            }
            self.user_order_draft = dict(state.get('user_order_draft') or {})
            self.user_pending_product_query = dict(state.get('user_pending_product_query') or {})
            self.user_last_intent = dict(state.get('user_last_intent') or {})
            self.user_intent_content = dict(state.get('user_intent_content') or {})
            logger.info("✅ Restored chatbot state for %s users", len(self.user_modes))
        except Exception as e:
            logger.error("❌ Failed to restore chatbot state: %s", e)

    def _save_state(self) -> None:
        """Atomic write with thread lock."""
        with self._state_lock:
            try:
                os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
                state = {
                    'user_modes': {uid: m.value for uid, m in self.user_modes.items()},
                    'user_conversation_status': self.user_conversation_status,
                    'user_product_context': self.user_product_context,
                    'user_selected_product': self.user_selected_product,
                    'user_order_context': self.user_order_context,
                    'user_order_draft': self.user_order_draft,
                    'user_pending_product_query': self.user_pending_product_query,
                    'user_last_intent': self.user_last_intent,
                    'user_intent_content': self.user_intent_content,
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
                logger.error("❌ Failed to persist chatbot state: %s", e)

    # ─────────────────────────────────────────────────────────────────
    # Static data loaders
    # ─────────────────────────────────────────────────────────────────
    def _load_database(self) -> list:
        try:
            import csv
            database_path = os.path.join(self.project_root, 'data', 'database.csv')
            if not os.path.exists(database_path):
                logger.warning(f"⚠️ Database file not found: {database_path}")
                return []
            db = []
            with open(database_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    question = row.get('প্রশ্ন') or row.get('প্রশ্ন ') or row.get('Question')
                    answer = row.get('উত্তর') or row.get('Answer')
                    if question and answer:
                        db.append({'question': question.strip(), 'answer': answer.strip()})
            logger.info(f"✅ Loaded {len(db)} FAQ responses")
            return db
        except Exception as e:
            logger.error(f"❌ Failed to load database: {e}")
            return []

    def _load_search_intent_items(self) -> list:
        items_path = os.path.join(self.project_root, 'data', 'search_intent_items.json')
        try:
            if not os.path.exists(items_path):
                return []
            with open(items_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            if not isinstance(payload, list):
                return []
            normalized = [str(i or '').strip().lower() for i in payload if str(i or '').strip()]
            return list(dict.fromkeys(normalized))
        except Exception as e:
            logger.warning("⚠️ Failed to load search intent items: %s", e)
            return []

    def _get_search_items_mtime(self) -> Optional[float]:
        items_path = os.path.join(self.project_root, 'data', 'search_intent_items.json')
        try:
            return os.path.getmtime(items_path) if os.path.exists(items_path) else None
        except Exception:
            return None

    def _refresh_search_intent_items_if_changed(self) -> None:
        latest = self._get_search_items_mtime()
        if latest is None:
            return
        if self.search_intent_items_mtime is None or latest > self.search_intent_items_mtime:
            self.search_intent_items = self._load_search_intent_items()
            self.search_intent_items_mtime = latest

    # ─────────────────────────────────────────────────────────────────
    # Responder API check (cached)
    # ─────────────────────────────────────────────────────────────────
    def _check_responder_type(self, user_id: str) -> Optional[str]:
        now = time.time()
        cached = self._responder_cache.get(user_id)
        if cached and (now - cached[0]) < self._responder_cache_ttl:
            return cached[1]

        try:
            url = f"{self.responder_api_url}?key={self.responder_api_key}&user_id={user_id}"
            start = time.time()
            response = requests.get(url, timeout=3)
            duration_ms = int((time.time() - start) * 1000)

            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    label = data['data'].get('responder_label', 'bot')
                    _log_api_call('responder_type_check', 'GET', url,
                                  {'user_id': user_id}, response.status_code, duration_ms, 'PASS',
                                  json.dumps(data.get('data', {}), ensure_ascii=False)[:200])
                    self._responder_cache[user_id] = (now, label)
                    return label

            _log_api_call('responder_type_check', 'GET', url,
                          {'user_id': user_id}, response.status_code, duration_ms, 'FAILED',
                          response.text[:200])
            self._responder_cache[user_id] = (now, None)
            return None
        except Exception as e:
            logger.warning(f"⚠️ Responder check error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # FAQ database search
    # ─────────────────────────────────────────────────────────────────
    def _search_database_faq(self, message: str) -> Optional[str]:
        try:
            msg_lower = message.lower().strip()

            greeting_map = {
                'hi': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hello': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hey': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hlw': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hai': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'assalamu alaikum': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'আসসালামু আলাইকুম': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম']
            }
            ordering_map = {
                'kibabe order korbo': 'অর্ডার করবো কিভাবে',
                'kivabe order korbo': 'অর্ডার করবো কিভাবে',
                'kemne order korbo': 'অর্ডার করবো কিভাবে',
                'order kivabe dibo': 'অর্ডার করবো কিভাবে',
                'order korbo kibabe': 'অর্ডার করবো কিভাবে',
                'order kivabe korbo': 'অর্ডার করবো কিভাবে',
                'how to order': 'অর্ডার করবো কিভাবে'
            }
            delivery_map = {
                'delivery koto din': 'ডেলিভারি চার্জ কত',
                'koto din lagbe': 'প্রোডাক্ট আসতে কত দিন সময় লাগবে',
                'delivery time': 'প্রোডাক্ট আসতে কত দিন সময় লাগবে',
                'koy din': 'প্রোডাক্ট আসতে কত দিন সময় লাগবে'
            }

            message_tokens = set(re.findall(r'[a-z0-9\u0980-\u09ff]+', msg_lower))
            for eng_key, bn_keys in greeting_map.items():
                if eng_key in message_tokens or eng_key in msg_lower.split():
                    for item in self.database:
                        for bn_key in bn_keys:
                            if bn_key in item['question']:
                                if self._is_blocked_automated_message(item['answer']):
                                    continue
                                return item['answer']

            for eng, bn_q in ordering_map.items():
                if eng in msg_lower:
                    for item in self.database:
                        if bn_q in item['question'] or 'অর্ডার' in item['question']:
                            return item['answer']

            if any(w in msg_lower for w in ['order', 'অর্ডার', 'korbo', 'করবো', 'kibabe', 'kivabe', 'kemne', 'কিভাবে']):
                for item in self.database:
                    q = item['question'].lower()
                    if 'অর্ডার' in q and any(w in q for w in ['কিভাবে', 'কি ভাবে']):
                        return item['answer']

            for eng, bn_q in delivery_map.items():
                if eng in msg_lower:
                    for item in self.database:
                        if bn_q in item['question'] or item['question'].lower() in bn_q.lower():
                            return item['answer']

            for item in self.database:
                q = item['question'].lower()
                if msg_lower in q or q in msg_lower:
                    if self._is_blocked_automated_message(item['answer']):
                        continue
                    return item['answer']
            return None
        except Exception as e:
            logger.error(f"❌ FAQ search failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────────
    def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        try:
            start_time = datetime.now()
            self._refresh_search_intent_items_if_changed()

            current_mode = self.user_modes.get(user_id, ChatMode.AI)
            current_status = self.user_conversation_status.get(user_id, AI_ACTIVE_STATUS)

            logger.info(f"📨 Processing message from {user_id} (Mode: {current_mode.value})")
            logger.info(f"💬 Message: {message}")

            # Block FB canned templates
            if self._is_blocked_automated_message(message):
                return self._create_response(
                    user_id=user_id, message=message, response="",
                    mode=ChatMode.AI, intent='ignored_automated_template', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=self.user_conversation_status.get(user_id, AI_ACTIVE_STATUS)
                )

            # Responder API check
            responder_type = self._check_responder_type(user_id)
            if responder_type == 'agent':
                if self._looks_like_possible_product_signal(message) or self._is_comparison_query(message):
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                else:
                    self.user_modes[user_id] = ChatMode.HUMAN
                    self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
                    self._save_state()
                    return self._create_response(
                        user_id=user_id, message=message, response="",
                        mode=ChatMode.HUMAN, intent='human_mode_active', products=None,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
                    )

            if responder_type == 'bot' and current_mode == ChatMode.HUMAN:
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                current_mode = ChatMode.AI

            if current_mode == ChatMode.HUMAN and current_status == HUMAN_SUPPORT_REQUIRED_STATUS:
                if self._looks_like_possible_product_signal(message) or self._is_comparison_query(message):
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                else:
                    return self._create_response(
                        user_id=user_id, message=message, response="",
                        mode=ChatMode.HUMAN, intent='human_support_required', products=None,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
                    )

            # ───── FAST PATH 1: product selection (numbers 1-5) ─────
            selected_index = self._extract_product_selection(message)
            user_products = self.user_product_context.get(user_id, [])
            if selected_index and user_products and len(user_products) >= selected_index:
                selected_product = user_products[selected_index - 1]
                self.user_selected_product[user_id] = selected_product
                self.user_modes[user_id] = ChatMode.AI
                return self._create_response(
                    user_id=user_id, message=message,
                    response=self._format_selected_product_response(selected_product, selected_index),
                    mode=ChatMode.AI, intent='product_selection', products=user_products,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )

            # ───── FAST PATH 2: order form submission ─────
            incoming_order_fields = self._extract_order_detail_fields(message)
            order_context_active = self.user_order_context.get(user_id, False)

            normalized_message = str(message or '').strip().lower()
            greeting_tokens = {'hi', 'hello', 'hey', 'salam', 'হাই', 'হ্যালো', 'সালাম', 'আসসালামু আলাইকুম'}

            if order_context_active and not incoming_order_fields:
                if normalized_message in greeting_tokens or self._looks_like_product_query(message):
                    self.user_order_context[user_id] = False
                    self.user_order_draft.pop(user_id, None)
                    order_context_active = False

            if incoming_order_fields or order_context_active:
                draft = dict(self.user_order_draft.get(user_id, {}))
                draft.update(incoming_order_fields)
                required = ['name', 'phone_number', 'address', 'product_name', 'quantity']
                missing = [k for k in required if not draft.get(k)]

                if not missing:
                    if not re.search(r'\d{10,15}', draft['phone_number']):
                        self.user_order_context[user_id] = True
                        self.user_order_draft[user_id] = draft
                        return self._create_response(
                            user_id=user_id, message=message,
                            response="স্যার, Phone Number টি সঠিক ফরম্যাটে দিন (১০-১৫ ডিজিট)।",
                            mode=ChatMode.AI, intent='order_details_incomplete', products=None,
                            processing_time=(datetime.now() - start_time).total_seconds()
                        )
                    self.user_order_context[user_id] = False
                    self.user_order_draft.pop(user_id, None)
                    return self._handoff_to_human(
                        user_id=user_id, message=message, start_time=start_time,
                        intent='order_details_submission',
                        response_text="ধন্যবাদ স্যার, আমাদের অন্য একজন প্রতিনিধি এসে কথা বলবে।"
                    )

                if incoming_order_fields or order_context_active:
                    self.user_order_context[user_id] = True
                    self.user_order_draft[user_id] = draft
                    return self._create_response(
                        user_id=user_id, message=message,
                        response=self._build_missing_order_fields_prompt(missing),
                        mode=ChatMode.AI, intent='order_details_incomplete', products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )

            # ───── FAST PATH 3: regex-matched simple intents ─────
            fast_intent = self._fast_path_intent(message)
            if fast_intent:
                return self._handle_fast_path(user_id, message, fast_intent, start_time)

            # ───── FAST PATH 4: order confirmation on selected product ─────
            selected_product = self.user_selected_product.get(user_id)
            if selected_product and not self._looks_like_product_query(message) and self._is_order_confirmation_message(message):
                listing_id = self._extract_listing_id_from_url(selected_product.get('url', ''))
                if listing_id:
                    order_template = self._fetch_order_intent_response(listing_id)
                    if order_template:
                        self.user_modes[user_id] = ChatMode.AI
                        return self._create_response(
                            user_id=user_id, message=message, response=order_template,
                            mode=ChatMode.AI, intent='order', products=None,
                            processing_time=(datetime.now() - start_time).total_seconds()
                        )

            # ───── MAIN PATH: structured Groq extraction + merge + search ─────
            return self._handle_main_flow(user_id, message, start_time)

        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            return self._handoff_to_human(
                user_id=user_id, message=message,
                start_time=start_time if 'start_time' in locals() else datetime.now(),
                intent='system_error', error=str(e)
            )

    # ─────────────────────────────────────────────────────────────────
    # Fast path (regex-matched, no Groq)
    # ─────────────────────────────────────────────────────────────────
    def _fast_path_intent(self, message: str) -> Optional[str]:
        msg = message.strip()
        if not msg:
            return None
        for intent_name, pattern in self.FAST_PATH_PATTERNS.items():
            if pattern.match(msg):
                return intent_name
        return None

    def _handle_fast_path(self, user_id: str, message: str, intent: str, start_time: datetime) -> Dict[str, Any]:
        self.user_modes[user_id] = ChatMode.AI
        self.user_conversation_status[user_id] = AI_ACTIVE_STATUS

        if intent == 'greeting':
            response = "আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?"
            return self._create_response(
                user_id=user_id, message=message, response=response,
                mode=ChatMode.AI, intent='greeting', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if intent == 'goodbye':
            prev = self._normalize_intent_content_payload(self.user_intent_content.get(user_id) or {})
            prev['exit'] = 1
            prev['complain'] = False
            self.user_intent_content[user_id] = prev
            return self._create_response(
                user_id=user_id, message=message, response="ধন্যবাদ স্যার, ভালো থাকবেন।",
                mode=ChatMode.AI, intent='goodbye', products=None, intent_content=prev,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if intent == 'thanks':
            return self._create_response(
                user_id=user_id, message=message, response="Most welcome",
                mode=ChatMode.AI, intent='thanks', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if intent == 'ok_ack':
            return self._create_response(
                user_id=user_id, message=message,
                response="ধন্যবাদ স্যার, আর কিভাবে আমি আপনাকে সাহায্য করতে পারি?",
                mode=ChatMode.AI, intent='conversation_finished_ack', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        return self._create_response(
            user_id=user_id, message=message, response="",
            mode=ChatMode.AI, intent='unknown', products=None,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    # ─────────────────────────────────────────────────────────────────
    # Main flow: Groq extract → merge → route
    # ─────────────────────────────────────────────────────────────────
    def _handle_main_flow(self, user_id: str, message: str, start_time: datetime) -> Dict[str, Any]:
        # Handle simple non-Groq intents first
        if self._is_later_followup_message(message) or self._is_deferred_reply_message(message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            prev = self._normalize_intent_content_payload(self.user_intent_content.get(user_id) or {})
            prev['exit'] = 1
            self.user_intent_content[user_id] = prev
            return self._create_response(
                user_id=user_id, message=message, response=self._build_later_followup_response(),
                mode=ChatMode.AI, intent='deferred_follow_up_ack', products=None, intent_content=prev,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        # Comparison queries (short-circuit, no Groq needed)
        if self._is_comparison_query(message) or self._is_comparison_followup_with_context(user_id, message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id, message=message, response=self._build_comparison_redirect_response(),
                mode=ChatMode.AI, intent='product_comparison', products=None,
                link_buttons=self._build_comparison_link_buttons(message, user_id),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if self._is_fixed_price_query(message):
            self.user_modes[user_id] = ChatMode.AI
            return self._create_response(
                user_id=user_id, message=message,
                response="জি স্যার, এগুলোর দাম ফিক্সড। বিস্তারিত জানতে ওয়েবসাইট ভিজিট করুন অথবা আমাদের কল করুন।",
                mode=ChatMode.AI, intent='fixed_price_info', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if self._looks_like_order_buy_message(message):
            self.user_modes[user_id] = ChatMode.AI
            return self._create_response(
                user_id=user_id, message=message, response=self._build_order_guide_response(),
                mode=ChatMode.AI, intent='ordering_guide', products=None,
                link_buttons=[{'text': 'Shopping Guide', 'url': 'https://www.bdstall.com/blog/safe-shopping-guide/'}],
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        # ───── Groq structured extraction (single call) ─────
        conversation_context = self._get_history_cached(user_id)
        previous_intent = self._load_previous_intent(user_id)

        groq_result = self._step1_groq_extract(message, conversation_context, previous_intent)
        intent = groq_result['intent']
        entities = groq_result['entities']

        logger.info(f"✅ Intent: {intent}, Entities: {entities}, Follow-up: {groq_result['is_followup']}")

        # ───── Context merge ─────
        merged_context = self._merge_intent_context(user_id, groq_result, previous_intent)
        self.user_intent_content[user_id] = self._intent_to_normalized(merged_context, message)

        # Clear cache if intent changed
        prev_intent_label = self.user_last_intent.get(user_id)
        if prev_intent_label and prev_intent_label != intent:
            self._clear_product_search_cache(user_id, clear_pending=True)

        # ───── Route by intent ─────
        if intent == 'complaint':
            prev = self._normalize_intent_content_payload(self.user_intent_content.get(user_id) or {})
            prev['complain'] = True
            self.user_intent_content[user_id] = prev
            return self._handoff_to_human(
                user_id=user_id, message=message, start_time=start_time,
                intent='complain_handoff',
                response_text="স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি এখনই আপনার সাথে যোগাযোগ করবেন।"
            )

        if intent == 'greeting':
            self.user_modes[user_id] = ChatMode.AI
            return self._create_response(
                user_id=user_id, message=message,
                response="আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?",
                mode=ChatMode.AI, intent='greeting', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if intent == 'goodbye':
            self.user_modes[user_id] = ChatMode.AI
            return self._create_response(
                user_id=user_id, message=message, response="ধন্যবাদ স্যার, ভালো থাকবেন।",
                mode=ChatMode.AI, intent='goodbye', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if intent == 'thanks':
            self.user_modes[user_id] = ChatMode.AI
            return self._create_response(
                user_id=user_id, message=message, response="Most welcome",
                mode=ChatMode.AI, intent='thanks', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if intent == 'ordering':
            self.user_order_context[user_id] = True
            self.user_order_draft[user_id] = {}
            self.user_modes[user_id] = ChatMode.AI
            order_template = self._get_order_info_template(
                user_id=user_id, message=message,
                intent_hint=self._resolve_order_template_intent(message)
            )
            return self._create_response(
                user_id=user_id, message=message, response=order_template,
                mode=ChatMode.AI, intent=intent, products=None,
                processing_time=(datetime.now() - start_time).total_seconds()
            )

        if intent == 'delivery':
            delivery_response = self._fetch_delivery_intent_response()
            if delivery_response:
                self.user_modes[user_id] = ChatMode.AI
                return self._create_response(
                    user_id=user_id, message=message, response=delivery_response,
                    mode=ChatMode.AI, intent=intent, products=None,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )

        # FAQ lookup for generic questions
        safe_intents = {'faq', 'comparison', 'ordering', 'delivery'}
        if intent in safe_intents and not self._looks_like_possible_product_signal(message):
            db_response = self._search_database_faq(message)
            if db_response:
                self.user_modes[user_id] = ChatMode.AI
                return self._create_response(
                    user_id=user_id, message=message, response=db_response,
                    mode=ChatMode.AI, intent=intent, products=None,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )

        # Price query (needs context)
        if intent == 'price_query':
            self.user_modes[user_id] = ChatMode.AI
            context_reply = self._reply_price_from_context(user_id)
            if context_reply:
                return self._create_response(
                    user_id=user_id, message=message, response=context_reply,
                    mode=ChatMode.AI, intent='price_from_context', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )
            return self._create_response(
                user_id=user_id, message=message, response="কোন প্রোডাক্টটি চাচ্ছেন স্যার?",
                mode=ChatMode.AI, intent='price_product_clarification', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        # Product search: category is MANDATORY
        if intent == 'product_search':
            return self._handle_product_search(user_id, message, merged_context, start_time)

        # Unknown: handoff or product-signal clarification
        if intent == 'unknown':
            if self._looks_like_possible_product_signal(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id, message=message,
                    response="জি স্যার, আমি প্রোডাক্ট খুঁজে দিতে পারি। একটু বিস্তারিত বলুন: brand/model/budget (যেমন: HP laptop 50k এর মধ্যে)।",
                    mode=ChatMode.AI, intent='product_search_clarification', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )
            return self._handoff_to_human(
                user_id=user_id, message=message, start_time=start_time, intent='unknown'
            )

        # Fallback: use Groq for general response
        ai_response = self._step4_ai_format(message, None, None, conversation_context)
        if not ai_response['success']:
            return self._handoff_to_human(user_id=user_id, message=message, start_time=start_time, intent=intent)
        self.user_modes[user_id] = ChatMode.AI
        return self._create_response(
            user_id=user_id, message=message, response=ai_response['response'],
            mode=ChatMode.AI, intent=intent, products=None,
            processing_time=(datetime.now() - start_time).total_seconds()
        )

    # ─────────────────────────────────────────────────────────────────
    # Product search handler with mandatory category
    # ─────────────────────────────────────────────────────────────────
    def _handle_product_search(self, user_id: str, message: str, merged_context: Dict, start_time: datetime) -> Dict[str, Any]:
        category = merged_context.get('category', '')
        brand = merged_context.get('brand', '')
        title = merged_context.get('title', '')
        price_max = merged_context.get('price_max')
        price_min = merged_context.get('price_min')

        # MANDATORY: category
        if not category:
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            prompt = "কোন প্রোডাক্টটি চাচ্ছেন স্যার? (যেমন: laptop, mobile, monitor, AC)"
            return self._create_response(
                user_id=user_id, message=message, response=prompt,
                mode=ChatMode.AI, intent='schema_need_category', products=None,
                intent_content=self._intent_to_normalized(merged_context, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        # Build search keywords
        search_keywords = self._build_search_keywords_from_merged(merged_context)

        # Try category-only template first if that's all we have
        if category and not brand and not title and not price_max and not price_min:
            category_response = self._fetch_category_intent_response(category)
            if category_response:
                self.user_modes[user_id] = ChatMode.AI
                return self._create_response(
                    user_id=user_id, message=message, response=category_response,
                    mode=ChatMode.AI, intent='category_search', products=None,
                    search_keywords=category, intent_content=self._intent_to_normalized(merged_context, message),
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

        # Cached search
        search_result = self._cached_search(search_keywords, price_max)

        # Retry with broader keywords if no results
        if search_result['products_found'] == 0:
            broader = self._build_broader_search_keywords(search_keywords, message)
            if broader and broader != search_keywords:
                retry = self._cached_search(broader, price_max)
                if retry['products_found'] > 0:
                    search_keywords = broader
                    search_result = retry

        if search_result['products_found'] == 0:
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            if brand or title:
                no_result = f"দুঃখিত স্যার, এই মুহূর্তে {brand} {title} স্টকে নেই। অন্য কোনো ব্র্যান্ড দেখাবো?".strip()
            else:
                no_result = "দুঃখিত স্যার, এই মুহূর্তে কোনো প্রোডাক্ট পাওয়া যায়নি।"
            return self._create_response(
                user_id=user_id, message=message, response=no_result,
                mode=ChatMode.AI, intent='no_products_found', products=None,
                search_keywords=search_keywords, intent_content=self._intent_to_normalized(merged_context, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        products = search_result['products']
        self.user_product_context[user_id] = products[:5]

        # Format final response
        response_text = self._format_product_listing(products[:3])

        self.user_modes[user_id] = ChatMode.AI
        return self._create_response(
            user_id=user_id, message=message, response=response_text,
            mode=ChatMode.AI, intent='product_search', products=products,
            search_keywords=search_keywords,
            intent_content=self._intent_to_normalized(merged_context, message),
            processing_time=(datetime.now() - start_time).total_seconds()
        )

    # ─────────────────────────────────────────────────────────────────
    # Single structured Groq extraction
    # ─────────────────────────────────────────────────────────────────
    def _step1_groq_extract(self, message: str, conversation_context: str, previous_intent: Dict) -> Dict[str, Any]:
        """One Groq call, strict JSON output, validated."""
        if not self.groq_client:
            return self._local_intent_fallback_structured(message)

        system_prompt = """You are a strict JSON extraction engine for an e-commerce chatbot (BDStall, Bangladesh).
Return ONLY valid JSON matching this exact schema. No prose, no markdown.

SCHEMA:
{
  "intent": "product_search" | "price_query" | "comparison" | "ordering" | "delivery" | "greeting" | "goodbye" | "thanks" | "complaint" | "faq" | "unknown",
  "entities": {
    "category": string,
    "brand": string,
    "title": string,
    "price_max": integer or null,
    "price_min": integer or null
  },
  "missing": array of strings,
  "is_followup": boolean,
  "confidence": number between 0 and 1
}

STRICT RULES:
1. NEVER invent values. Unsure → "" for strings, null for numbers, false for booleans.
2. "category" MUST be one of: laptop, desktop, phone, mobile, tablet, ac, tv, monitor, mouse, keyboard, headphone, watch, smartwatch, printer, camera, router, ssd, ram, ups, ips, speaker, cctv, or "".
3. "category" is the GENERIC product type, NOT a model or brand (e.g. "laptop" not "elitebook" not "hp").
4. If message is ONLY a budget refinement ("under 50k", "20k budget", "kom dame"), set intent=product_search, is_followup=true, inherit category from previous context if possible.
5. Budget parsing: "50k"=50000, "10 taka" or "10 tk" as number, "under 30k"→price_max=30000, "20-50k"→price_min=20000,price_max=50000, "kom dame"→both null.
6. Banglish intents:
   - "koto dam", "price koto", "koto taka" → price_query
   - "konta valo", "which is better" → comparison
   - "order korbo kibabe", "kivabe kinbo" → ordering
   - "delivery koto din", "koto din lagbe" → delivery
   - "refund chai", "baje product", "faltu" → complaint
7. For "hp 840 g3" style: brand="hp", title="840 g3", category="laptop" (infer from CPU/model patterns).
8. If intent=product_search and category is "", add "category" to missing[].
9. For greetings/goodbyes/thanks: all entity fields can be empty.

PREVIOUS CONTEXT (use ONLY to infer is_followup and inherit category when missing):
""" + json.dumps(previous_intent or {}, ensure_ascii=False)

        user_prompt = f"""Recent conversation (for context only):
{conversation_context or 'N/A'}

Current user message:
{message}

Return ONLY the JSON object."""

        try:
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            return self._validate_groq_schema(parsed, message)
        except json.JSONDecodeError as e:
            logger.warning(f"Groq JSON parse failed: {e}. Falling back.")
            return self._local_intent_fallback_structured(message)
        except Exception as e:
            logger.warning(f"Groq extraction failed: {e}. Falling back.")
            return self._local_intent_fallback_structured(message)

    def _validate_groq_schema(self, parsed: Dict, message: str) -> Dict[str, Any]:
        """Validate and coerce Groq output. Drop hallucinated values."""
        intent = str(parsed.get('intent', 'unknown')).lower().strip()
        if intent not in VALID_INTENTS:
            intent = 'unknown'

        entities = parsed.get('entities') or {}
        category = str(entities.get('category') or '').lower().strip()
        if category and category not in VALID_CATEGORIES:
            category = ''  # Drop hallucinated category

        brand = str(entities.get('brand') or '').lower().strip()
        title = str(entities.get('title') or '').strip()

        def _coerce_price(v):
            if v is None or v == '':
                return None
            try:
                n = int(float(v))
                return n if 0 < n < 100_000_000 else None
            except (ValueError, TypeError):
                return None

        price_max = _coerce_price(entities.get('price_max'))
        price_min = _coerce_price(entities.get('price_min'))

        missing = [str(m) for m in (parsed.get('missing') or []) if isinstance(m, str)]
        if intent == 'product_search' and not category and 'category' not in missing:
            missing.append('category')

        return {
            'intent': intent,
            'entities': {
                'category': category, 'brand': brand, 'title': title,
                'price_max': price_max, 'price_min': price_min,
            },
            'missing': missing,
            'is_followup': bool(parsed.get('is_followup', False)),
            'confidence': max(0.0, min(1.0, float(parsed.get('confidence', 0.5)))),
        }

    def _local_intent_fallback_structured(self, message: str) -> Dict[str, Any]:
        """Regex-based fallback when Groq is unavailable."""
        text = message.lower().strip()

        if self._is_comparison_query(message):
            intent = 'comparison'
        elif any(w in text for w in ['order korbo', 'kivabe order', 'kibabe order', 'অর্ডার করবো']):
            intent = 'ordering'
        elif any(w in text for w in ['delivery', 'koto din', 'ডেলিভারি']):
            intent = 'delivery'
        elif any(w in text for w in ['price koto', 'dam koto', 'koto dam', 'দাম কত']):
            intent = 'price_query'
        elif self._looks_like_product_query(message):
            intent = 'product_search'
        elif self.FAST_PATH_PATTERNS['greeting'].match(message):
            intent = 'greeting'
        else:
            intent = 'unknown'

        entities = self._extract_search_entities(message)
        category_guess = self._infer_category_from_text(message)

        return {
            'intent': intent,
            'entities': {
                'category': category_guess if category_guess in VALID_CATEGORIES else '',
                'brand': entities.get('brand') or '',
                'title': entities.get('product_name') or '',
                'price_max': entities.get('max_price'),
                'price_min': entities.get('min_price'),
            },
            'missing': ['category'] if intent == 'product_search' and not category_guess else [],
            'is_followup': False,
            'confidence': 0.5,
        }

    def _infer_category_from_text(self, message: str) -> str:
        """Map common product keywords to canonical categories."""
        text = message.lower()
        mapping = [
            (['laptop', 'ল্যাপটপ', 'notebook', 'macbook', 'elitebook', 'thinkpad', 'pavilion', 'inspiron', 'vivobook', 'probook', 'aspire'], 'laptop'),
            (['desktop', 'pc', 'ডেস্কটপ'], 'desktop'),
            (['phone', 'mobile', 'ফোন', 'মোবাইল', 'iphone', 'smartphone'], 'phone'),
            (['tablet', 'ট্যাব', 'ipad'], 'tablet'),
            (['ac ', ' ac', 'air condition', 'এসি'], 'ac'),
            (['tv', 'television', 'টিভি'], 'tv'),
            (['monitor', 'মনিটর'], 'monitor'),
            (['mouse', 'মাউস'], 'mouse'),
            (['keyboard', 'কিবোর্ড'], 'keyboard'),
            (['headphone', 'হেডফোন'], 'headphone'),
            (['smartwatch', 'smart watch'], 'smartwatch'),
            (['watch', 'ঘড়ি'], 'watch'),
            (['printer', 'প্রিন্টার'], 'printer'),
            (['camera', 'ক্যামেরা'], 'camera'),
            (['router', 'রাউটার'], 'router'),
            (['ssd'], 'ssd'),
            (['ram'], 'ram'),
            (['ups'], 'ups'),
            (['ips'], 'ips'),
            (['speaker', 'স্পিকার'], 'speaker'),
            (['cctv'], 'cctv'),
        ]
        for keywords, category in mapping:
            if any(k in text for k in keywords):
                return category

        # CPU/model → laptop
        if re.search(r'\b(core\s*i[3579]|i[3579]|ryzen|intel|amd|gen)\b', text):
            return 'laptop'
        return ''

    # ─────────────────────────────────────────────────────────────────
    # Context merge with TTL
    # ─────────────────────────────────────────────────────────────────
    def _load_previous_intent(self, user_id: str) -> Dict:
        """Load previous intent context with TTL check."""
        prev = dict(self.user_intent_content.get(user_id) or {})
        updated_at = prev.get('updated_at')
        if updated_at:
            try:
                age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
                if age > CONTEXT_TTL_SECONDS:
                    logger.info(f"Context expired (age={age}s) for {user_id}. Clearing.")
                    return {}
            except Exception:
                pass
        return prev

    def _merge_intent_context(self, user_id: str, groq_result: Dict, previous: Dict) -> Dict:
        """Merge new Groq extraction with previous context."""
        new_entities = groq_result['entities']
        is_followup = groq_result['is_followup']

        new_category = new_entities.get('category', '')
        prev_category = previous.get('category', '')

        category_switch = new_category and prev_category and new_category != prev_category

        if category_switch:
            logger.info(f"Category switch {prev_category} → {new_category}. Resetting.")
            merged = {
                'category': new_category,
                'brand': new_entities.get('brand', ''),
                'title': new_entities.get('title', ''),
                'price_max': new_entities.get('price_max'),
                'price_min': new_entities.get('price_min'),
            }
        elif is_followup or not new_category:
            # Follow-up: merge, new values override only if present
            merged = dict(previous)
            for key in ['category', 'brand', 'title']:
                new_val = new_entities.get(key, '')
                if new_val:
                    merged[key] = new_val
            for key in ['price_max', 'price_min']:
                new_val = new_entities.get(key)
                if new_val is not None:
                    merged[key] = new_val
            if not merged.get('category') and prev_category:
                merged['category'] = prev_category
        else:
            # Same category, new info
            merged = {
                'category': new_category or prev_category,
                'brand': new_entities.get('brand') or previous.get('brand', ''),
                'title': new_entities.get('title') or previous.get('title', ''),
                'price_max': new_entities.get('price_max') if new_entities.get('price_max') is not None else previous.get('price_max'),
                'price_min': new_entities.get('price_min') if new_entities.get('price_min') is not None else previous.get('price_min'),
            }

        merged['updated_at'] = datetime.now().isoformat()
        return merged

    def _intent_to_normalized(self, merged: Dict, message: str) -> Dict[str, Any]:
        """Convert merged context to the normalized intent_content shape stored/returned."""
        price_max = merged.get('price_max')
        price_min = merged.get('price_min')
        if price_min and price_max:
            price_text = f"{price_min}-{price_max}"
        elif price_max:
            price_text = f"under {price_max}"
        elif price_min:
            price_text = f"above {price_min}"
        else:
            price_text = ''

        title = merged.get('title', '') or ''
        category = merged.get('category', '') or ''
        brand = merged.get('brand', '') or ''

        full_title = title if title else category
        if brand and full_title and brand.lower() not in full_title.lower():
            full_title = f"{brand.capitalize()} {full_title}".strip()

        return {
            'buy': 'ok' if self._looks_like_order_buy_message(message) else '',
            'brand': brand,
            'price': price_text,
            'title': full_title.strip().title() if full_title else '',
            'compare': 'yes' if self._is_comparison_query(message) else 'no',
            'category': category.title() if category else '',
            'complain': False,
            'exit': 0,
            'updated_at': merged.get('updated_at', datetime.now().isoformat()),
        }

    def _normalize_intent_content_payload(self, payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Normalize stored intent_content to API contract."""
        default = {
            'buy': '', 'brand': '', 'price': '', 'title': '',
            'compare': 'no', 'category': '', 'complain': False, 'exit': 0,
        }
        if not isinstance(payload, dict):
            return default

        out = dict(default)
        out['buy'] = str(payload.get('buy') or '').strip()
        out['brand'] = str(payload.get('brand') or '').strip().lower()
        out['price'] = str(payload.get('price') or '').strip()
        out['title'] = str(payload.get('title') or '').strip()
        out['category'] = str(payload.get('category') or '').strip()
        out['compare'] = self._normalize_compare_flag(payload.get('compare'))

        complain_raw = payload.get('complain', False)
        if isinstance(complain_raw, str):
            out['complain'] = complain_raw.strip().lower() in {'true', '1', 'yes', 'y'}
        else:
            out['complain'] = bool(complain_raw)

        exit_raw = payload.get('exit', 0)
        if isinstance(exit_raw, str):
            out['exit'] = 1 if exit_raw.strip().lower() in {'1', 'true', 'yes', 'y'} else 0
        else:
            out['exit'] = 1 if bool(exit_raw) else 0
        return out

    def _normalize_compare_flag(self, value: Any) -> str:
        text = str(value or '').strip().lower()
        return 'yes' if text in {'yes', 'true', '1', 'y'} else 'no'

    # ─────────────────────────────────────────────────────────────────
    # Search keyword building
    # ─────────────────────────────────────────────────────────────────
    def _build_search_keywords_from_merged(self, merged: Dict) -> str:
        """Build search API query string from merged context."""
        parts = []
        brand = merged.get('brand', '')
        title = merged.get('title', '')
        category = merged.get('category', '')

        if brand:
            parts.append(brand)
        if title:
            parts.append(title)
        elif category:
            parts.append(category)

        price_max = merged.get('price_max')
        if price_max:
            parts.append(str(price_max))

        return ' '.join(parts).strip()

    # ─────────────────────────────────────────────────────────────────
    # Cached BDStall search
    # ─────────────────────────────────────────────────────────────────
    def _cached_search(self, keywords: str, max_price: Optional[int] = None) -> Dict[str, Any]:
        cache_key = f"{keywords}|{max_price or ''}"
        now = time.time()
        cached = self._search_cache.get(cache_key)
        if cached and (now - cached[0]) < self._search_cache_ttl:
            return cached[1]

        result = self._step2_search_database(keywords, max_price)

        self._search_cache[cache_key] = (now, result)
        if len(self._search_cache) > self._search_cache_max:
            # Remove oldest
            oldest_key = min(self._search_cache.keys(), key=lambda k: self._search_cache[k][0])
            self._search_cache.pop(oldest_key, None)
        return result

    def _step2_search_database(self, keywords: str, explicit_max_price: Optional[int] = None) -> Dict[str, Any]:
        try:
            search_term = self._normalize_search_keywords_for_api(keywords)
            params = {'term': search_term, 'key': self.api_key}
            started = datetime.now()
            response = requests.get(self.api_url, params=params, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)

            _log_api_call('ai_search', 'GET', self.api_url, params,
                          response.status_code, duration_ms,
                          "PASS" if response.status_code == 200 else "FAIL",
                          response.text)

            if response.status_code != 200:
                return {'products_found': 0, 'products': [], 'database_message': ''}

            data = response.json()
            if not data.get('getListingItem') or len(data['getListingItem']) < 2:
                return {'products_found': 0, 'products': [], 'database_message': ''}

            total_count = data['getListingItem'][0]
            products_array = data['getListingItem'][1] or []
            if not products_array:
                return {'products_found': 0, 'products': [], 'database_message': ''}

            # Resolve max price
            max_price = explicit_max_price
            if not max_price:
                pm = re.search(r'(\d+)k?', keywords.lower())
                if pm:
                    v = int(pm.group(1))
                    max_price = v * 1000 if v < 1000 else v

            query_tokens = self._extract_search_tokens(search_term)

            scored = []
            for product in products_array[:20]:
                try:
                    title = str(product.get('ListingTitle', '')).lower()
                    desc = str(product.get('ListingDescription', '')).lower()
                    haystack = f"{title} {desc}"
                    token_hits = 0
                    if query_tokens:
                        token_hits = sum(1 for t in query_tokens if t in haystack)
                        if token_hits == 0:
                            continue
                    p_price = int(product.get('app_ListingPrice', 999999))
                    if max_price and p_price > max_price:
                        continue
                    scored.append((token_hits, product))
                except Exception:
                    continue

            if query_tokens and not scored:
                return {'products_found': 0, 'products': [], 'database_message': ''}

            scored.sort(key=lambda x: x[0], reverse=True)
            filtered = [p for _, p in scored]

            if not query_tokens:
                filtered = []
                for p in products_array[:20]:
                    try:
                        p_price = int(p.get('app_ListingPrice', 999999))
                        if max_price and p_price > max_price:
                            continue
                        filtered.append(p)
                    except Exception:
                        continue

            top = filtered[:5]
            if not top:
                return {'products_found': 0, 'products': [], 'database_message': ''}

            db_msg = f"পণ্য তালিকা (মোট {total_count} পণ্য পাওয়া গেছে):\n\n"
            products_list = []
            for i, p in enumerate(top, 1):
                title = p.get('ListingTitle', 'N/A')
                price = p.get('ListingPrice', 'N/A')
                disc = p.get('ListingDiscountPercentage', 0)
                url = p.get('ListingURL', '')
                db_msg += f"{i}. {title}\n   মূল্য: {price}"
                if disc and disc > 0:
                    db_msg += f" (ছাড় {disc}%)"
                db_msg += f"\n   লিংক: {url}\n\n"
                products_list.append({
                    'title': title, 'price': price,
                    'original_price': p.get('app_ListingOriginalPrice', ''),
                    'discount': disc, 'url': url,
                    'image': p.get('ListingThumbAvator', '')
                })

            return {
                'products_found': len(top), 'total_products': total_count,
                'products': products_list, 'database_message': db_msg
            }
        except Exception as e:
            logger.error(f"❌ BDStall API search failed: {e}")
            return {'products_found': 0, 'products': [], 'database_message': ''}

    def _normalize_search_keywords_for_api(self, keywords: str) -> str:
        text = str(keywords or '').strip().lower()
        if not text:
            return ''
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', text)
        drop = {'cheap', 'low', 'budget', 'affordable', 'best', 'good',
                'কম', 'দামে', 'বাজেটে', 'সস্তা', 'ভালো', 'ভাল', 'taka', 'tk', 'টাকা'}
        kept = [t for t in tokens if t not in drop]
        return ' '.join(kept).strip() or text

    def _build_broader_search_keywords(self, keywords: str, original_message: str) -> Optional[str]:
        base = self._extract_search_tokens(keywords) or self._extract_search_tokens(original_message)
        if not base:
            return None
        product_terms = {'laptop', 'phone', 'mobile', 'iphone', 'computer', 'pc', 'monitor', 'tablet',
                         'ল্যাপটপ', 'ফোন', 'মোবাইল', 'কম্পিউটার'}
        brand_terms = {'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung', 'xiaomi',
                       'realme', 'oppo', 'vivo', 'msi', 'huawei'}
        selected = []
        brand = next((t for t in base if t in brand_terms), None)
        product = next((t for t in base if t in product_terms), None)
        if brand:
            selected.append(brand)
        if product and product not in selected:
            selected.append(product)
        for t in base:
            if t in selected:
                continue
            if len(t) > 2:
                selected.append(t)
                break
        if not selected:
            selected = base[:2]
        broader = ' '.join(selected).strip()
        if not broader or broader.lower() == keywords.strip().lower():
            return None
        return broader

    def _extract_search_tokens(self, text: str) -> list:
        normalized = self._normalize_product_query_text(text)
        if not normalized:
            return []
        normalized = normalized.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        raw = re.findall(r'[a-z0-9\u0980-\u09ff]+', normalized)
        stop = {'and', 'or', 'the', 'a', 'an', 'for', 'ase', 'ache', 'kase', 'kache',
                'apnar', 'amar', 'ami', 'amake', 'sir', 'bhai', 'please', 'need', 'ki',
                'dorkar', 'ekta', 'akta', 'taka', 'tk', 'price', 'dam',
                'আছে', 'কাছে', 'আপনার', 'আমার', 'একটা', 'দাম', 'টাকা'}
        tokens = [t for t in raw if len(t) > 1 and t not in stop]
        return list(dict.fromkeys(tokens))

    # ─────────────────────────────────────────────────────────────────
    # History (cached)
    # ─────────────────────────────────────────────────────────────────
    def _get_history_cached(self, user_id: str) -> str:
        now = time.time()
        cached = self._history_cache.get(user_id)
        if cached and (now - cached[0]) < self._history_cache_ttl:
            return cached[1]
        context = self._fetch_recent_chat_context(user_id, self.chatbot_history_limit)
        self._history_cache[user_id] = (now, context)
        return context

    def _fetch_recent_chat_context(self, user_id: str, limit: int = 5) -> str:
        if not user_id:
            return ''
        safe_limit = max(1, min(int(limit or 5), 20))
        urls = self._build_chat_history_urls(user_id, safe_limit)
        started = datetime.now()
        for url in urls:
            try:
                response = requests.get(url, timeout=8)
                duration_ms = int((datetime.now() - started).total_seconds() * 1000)
                _log_api_call('chatbot_history', 'GET', url,
                              {'user_id': str(user_id), 'limit': safe_limit, 'key': self.api_key},
                              response.status_code, duration_ms,
                              "PASS" if 200 <= response.status_code < 300 else "FAIL",
                              response.text)
                if not (200 <= response.status_code < 300):
                    continue
                payload = response.json() if response.text else {}
                lines = self._normalize_history_messages(payload)
                return '\n'.join(lines).strip()
            except Exception:
                continue
        return ''

    def _build_chat_history_urls(self, user_id: str, limit: int) -> list:
        base = str(self.chatbot_history_api_url or '').strip()
        if not base:
            return []
        tail = f"user_id={user_id}&limit={limit}&key={self.api_key}"
        base_strip = base.rstrip('/')
        candidates = [f"{base}{tail}", f"{base}?{tail}", f"{base_strip}?{tail}"]
        seen = set()
        out = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _normalize_history_messages(self, payload: Any) -> list:
        candidates = []
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict):
            for key in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
                v = payload.get(key)
                if isinstance(v, list):
                    candidates = v
                    break
            if not candidates and isinstance(payload.get('data'), dict):
                nested = payload.get('data') or {}
                for key in ['messages', 'history', 'chat_history', 'conversation', 'items']:
                    v = nested.get(key)
                    if isinstance(v, list):
                        candidates = v
                        break
        lines = []
        for item in candidates:
            if isinstance(item, str):
                t = item.strip()
                if t:
                    lines.append(f"User: {t}")
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get('message') or item.get('text') or item.get('content') or item.get('body') or '').strip()
            if not text:
                continue
            sender = str(item.get('sender_type') or '').strip()
            role = str(item.get('role') or '').strip().lower()
            if sender == '2' or role in {'assistant', 'bot', 'ai'}:
                lines.append(f"Bot: {text}")
            elif sender == '1' or role in {'agent', 'human'}:
                lines.append(f"Agent: {text}")
            else:
                lines.append(f"User: {text}")
        return lines[-10:]

    # ─────────────────────────────────────────────────────────────────
    # Helpers for detectors (kept from original, pruned)
    # ─────────────────────────────────────────────────────────────────
    def _normalize_product_query_text(self, message: str) -> str:
        text = str(message or '').strip().lower()
        if not text:
            return ''
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        text = re.sub(r'\bhat\s+ghori\b', 'hand watch', text)
        text = re.sub(r'\bhaat\s+ghori\b', 'hand watch', text)
        text = re.sub(r'\bghori\b', 'watch', text)
        text = text.replace('ঘড়ি', 'watch')
        return text

    def _looks_like_product_query(self, message: str) -> bool:
        text = self._normalize_product_query_text(message)
        if not text:
            return False
        product_terms = ['laptop', 'desktop', 'phone', 'mobile', 'pc', 'computer', 'monitor', 'mouse',
                         'keyboard', 'headphone', 'ssd', 'ram', 'printer', 'camera', 'router',
                         'watch', 'smartwatch', 'smart watch', 'macbook', 'iphone',
                         'elitebook', 'pavilion', 'thinkpad', 'inspiron', 'aspire', 'vivobook',
                         'ল্যাপটপ', 'মোবাইল', 'ফোন', 'কম্পিউটার']
        brand_terms = ['hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung', 'xiaomi',
                       'realme', 'oppo', 'vivo', 'msi', 'huawei']
        buying_cues = ['price', 'dam', 'tk', 'taka', 'budget', 'modde', 'within', 'under',
                       'ase', 'ache', 'chai', 'lagbe', 'দাম', 'টাকা', 'হাজার', 'আছে']
        has_product = any(t in text for t in product_terms)
        has_brand = any(t in text for t in brand_terms)
        has_cue = any(c in text for c in buying_cues)
        has_number = bool(re.search(r'\b\d+\s*(k|tk|taka|টাকা|হাজার)?\b', text))
        if has_product and (has_brand or has_cue or has_number):
            return True
        if has_product and len(text.split()) <= 4:
            return True
        return False

    def _looks_like_possible_product_signal(self, message: str) -> bool:
        text = self._normalize_product_query_text(message)
        if not text:
            return False
        if self._contains_configured_search_item(text) or self._looks_like_product_query(text):
            return True
        signal_terms = {'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung', 'xiaomi',
                        'laptop', 'desktop', 'mobile', 'phone', 'pc', 'computer', 'monitor',
                        'watch', 'smartwatch', 'core', 'i3', 'i5', 'i7', 'i9', 'gen', 'intel',
                        'price', 'dam', 'tk', 'taka', 'budget',
                        'দাম', 'টাকা', 'বাজেট', 'ল্যাপটপ', 'মোবাইল', 'ফোন'}
        tokens = set(re.findall(r'[a-z0-9\u0980-\u09ff]+', text))
        hits = sum(1 for t in tokens if t in signal_terms)
        return hits >= 2

    def _contains_configured_search_item(self, message: str) -> bool:
        text = self._normalize_product_query_text(message)
        if not text or not self.search_intent_items:
            return False
        nm = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', text)
        nm = re.sub(r'\s+', ' ', nm).strip()
        padded = f" {nm} "
        for item in self.search_intent_items:
            ni = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', item)
            ni = re.sub(r'\s+', ' ', ni).strip()
            if not ni:
                continue
            if f" {ni} " in padded:
                return True
        return False

    def _extract_search_entities(self, message: str) -> Dict[str, Any]:
        text = str(message or '').strip().lower()
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', text)
        brand_terms = ['hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'iphone', 'samsung',
                       'xiaomi', 'realme', 'oppo', 'vivo', 'msi', 'huawei', 'intel', 'amd']
        product_terms = ['laptop', 'desktop', 'phone', 'mobile', 'pc', 'computer', 'monitor',
                         'mouse', 'keyboard', 'headphone', 'ssd', 'ram', 'printer', 'camera',
                         'router', 'charger', 'tablet', 'elitebook', 'pavilion', 'thinkpad',
                         'inspiron', 'aspire', 'vivobook', 'macbook', 'chromebook', 'probook',
                         'ac', 'tv', 'watch', 'smartwatch', 'ips', 'ups', 'cctv']

        def _found(term):
            n = term.strip().lower()
            if not n:
                return False
            if re.fullmatch(r'[a-z0-9]+', n) and len(n) <= 3:
                return n in tokens
            return n in text

        brand = next((b for b in brand_terms if _found(b)), None)
        has_product = any(_found(t) for t in product_terms)
        product_name = next((t for t in product_terms if _found(t)), None)
        budget = self._extract_budget_range(text)
        has_price = budget.get('min_price') is not None or budget.get('max_price') is not None

        return {
            'brand': brand, 'has_product': has_product, 'product_name': product_name,
            'has_price': has_price, 'min_price': budget.get('min_price'),
            'max_price': budget.get('max_price'), 'price_text': budget.get('price_text', '')
        }

    def _extract_budget_range(self, message: str) -> Dict[str, Optional[int]]:
        text = str(message or '').strip().lower()
        if not text:
            return {'min_price': None, 'max_price': None, 'price_text': ''}
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        def _to_taka(v, u):
            val = int(float(v))
            un = (u or '').strip().lower()
            if un in {'k', 'হাজার', 'thousand'}:
                return val * 1000
            if un in {'tk', 'taka', 'টাকা'}:
                return val
            if val < 1000:
                return val * 1000
            return val

        rm = re.search(r'(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)?\s*(?:-|to|থেকে)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)?', text)
        if rm:
            mn = _to_taka(rm.group(1), rm.group(2) or rm.group(4) or '')
            mx = _to_taka(rm.group(3), rm.group(4) or rm.group(2) or '')
            if mn > mx:
                mn, mx = mx, mn
            return {'min_price': mn, 'max_price': mx, 'price_text': f"{mn}-{mx}"}

        um = re.search(r'(?:under|within|modde|modhhe|budget|er modde|এর মধ্যে|মধ্যে|below|less than)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)?', text)
        if um:
            mx = _to_taka(um.group(1), um.group(2) or '')
            return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

        gm = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)\b', text)
        if gm:
            mx = _to_taka(gm.group(1), gm.group(2) or '')
            return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

        return {'min_price': None, 'max_price': None, 'price_text': ''}

    # Comparison detection (FIXED: no standalone "good"/"ভালো" false positive)
    def _is_comparison_query(self, message: str) -> bool:
        text = self._normalize_comparison_text(message)
        if not text:
            return False

        # Must have BOTH a comparison term AND a product signal (or explicit "vs"/"compare")
        explicit_compare = ['compare', 'comparison', 'vs', 'তুলনা',
                            'which one is best', 'which one better', 'which is better',
                            'konta valo', 'konta bhalo', 'konti valo', 'konti bhalo',
                            'কোনটা ভালো', 'কোনটা ভাল', 'কোনটি ভালো', 'কোনটি ভাল']
        has_explicit = any(term in text for term in explicit_compare)
        if has_explicit:
            return True

        has_or = (' or ' in f" {text} ") or (' অথবা ' in f" {text} ")
        if has_or and (self._looks_like_possible_product_signal(message) or self._contains_configured_search_item(message)):
            return True

        return False

    def _is_comparison_followup_with_context(self, user_id: str, message: str) -> bool:
        text = self._normalize_comparison_text(message)
        if not text or len(text.split()) > 6:
            return False
        markers = ['which one', 'which is best', 'compare', 'comparison',
                   'konta valo', 'konta bhalo', 'konti valo', 'konti bhalo',
                   'কোনটা ভালো', 'কোনটা ভাল', 'তুলনা']
        if not any(m in text for m in markers):
            return False
        payload = self.user_intent_content.get(user_id) or {}
        has_context = bool(
            self.user_product_context.get(user_id)
            or str(payload.get('category') or '').strip()
            or str(payload.get('title') or '').strip()
        )
        return has_context

    def _normalize_comparison_text(self, message: str) -> str:
        text = str(message or '').strip().lower()
        if not text:
            return ''
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        text = re.sub(r'\b(vai|bhai|bro|vaiya|bhaiya|pls|plz)\b', ' ', text)
        text = re.sub(r'[!?.,;:]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _build_comparison_redirect_response(self) -> str:
        return "স্যার, আমাদের সকল প্রোডাক্টই ভালো। আপনি আমাদের ওয়েবসাইটের প্রোডাক্ট রেটিং এবং রিভিউ দেখে নিতে পারেন।"

    def _build_comparison_link_buttons(self, message: str, user_id: Optional[str] = None) -> list:
        category = self._resolve_comparison_category(message)
        if not category and user_id:
            payload = self.user_intent_content.get(user_id) or {}
            category = str(payload.get('category') or payload.get('title') or '').strip().lower()

        target_url = 'https://www.bdstall.com/'
        if category:
            slug = re.sub(r'\s+', '-', category.strip().lower())
            slug = re.sub(r'[^a-z0-9\u0980-\u09ff\-]', '', slug).strip('-')
            if slug:
                target_url = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
        return [{'text': 'View', 'url': target_url}]

    def _resolve_comparison_category(self, message: str) -> Optional[str]:
        text = self._normalize_product_query_text(message)
        if not text:
            return None
        mapping = {'laptop': 'laptop', 'ল্যাপটপ': 'laptop', 'mobile': 'mobile', 'phone': 'mobile',
                   'ফোন': 'mobile', 'মোবাইল': 'mobile', 'watch': 'watch', 'ঘড়ি': 'watch',
                   'camera': 'camera', 'computer': 'computer', 'monitor': 'monitor',
                   'tablet': 'tablet', 'printer': 'printer'}
        for term, norm in mapping.items():
            if term in text:
                return norm
        return None

    def _build_order_guide_response(self) -> str:
        return "স্যার এই লিংকে গিয়ে আপনি দেখতে পারেন কিভাবে অর্ডার অথবা বাই করা যায়"

    def _looks_like_order_buy_message(self, message: str) -> bool:
        text = str(message or '').lower()
        if not text.strip():
            return False
        markers = ['order korbo', 'kibabe order', 'kivabe order',
                   'কিভাবে অর্ডার', 'অর্ডার করবো', 'অর্ডার দিব',
                   'kinbo', 'kinte chai', 'kinte pari', 'kivabe kinbo', 'kibabe kinbo',
                   'কিনবো', 'কিনতে চাই', 'কিভাবে কিনবো']
        return any(m in text for m in markers)

    def _resolve_order_template_intent(self, message: str) -> str:
        text = str(message or '').lower()
        buy_markers = ['buy', 'kinbo', 'kinte', 'কিনবো', 'কিনতে']
        return 'buy' if any(m in text for m in buy_markers) else 'order'

    def _is_fixed_price_query(self, message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text:
            return False
        fp_terms = ['fixed dam', 'fixed price', 'fix dam', 'fix price', 'ফিক্সড দাম', 'ফিক্সড প্রাইস']
        q_markers = ['ki', 'কি', 'koto', 'কত', 'ase', 'ache']
        return any(t in text for t in fp_terms) and any(m in text for m in q_markers)

    def _is_later_followup_message(self, message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text:
            return False
        text = re.sub(r'\s+', ' ', text)
        patterns = ['i will buy later', 'will buy later', 'buy later', 'see you later',
                    'pore janbo', 'pore kinbo', 'পরে জানবো', 'পরে কিনবো']
        return any(p in text for p in patterns)

    def _is_deferred_reply_message(self, message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text:
            return False
        patterns = ['pore janabo', 'pore bolbo', 'later janabo',
                    'পরে জানাবো', 'পরে বলবো', 'পরে জানাই']
        return any(p in text for p in patterns)

    def _build_later_followup_response(self) -> str:
        return "BDStall এর সাথে থাকার জন্য ধন্যবাদ স্যার, আর কিছু লাগলে আমাকে অবশ্যই জানাবেন।"

    def _is_blocked_automated_message(self, message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text:
            return False
        blocked = ['bdstall.com-এ আপনাকে স্বাগতম',
                   'আপনার মেসেজ এর জন্য ধন্যবাদ',
                   'খুব শীঘ্রই bdstall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে']
        return sum(1 for p in blocked if p in text) >= 2

    def _is_order_confirmation_message(self, message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text or self._looks_like_product_query(text) or len(text.split()) > 4:
            return False
        positive = {'yes', 'y', 'ok', 'okay', 'hea', 'hya', 'ha', 'nibo', 'nib',
                    'dekhan', 'dekhao', 'lagbe', 'ji', 'jii', 'hmm', 'sure'}
        if text in positive:
            return True
        patterns = [r'\b(yes|ok|okay|sure|please)\b', r'\b(hea|hya|ha|ji)\b',
                    r'\b(nibo|nib|lagbe|dekhan|dekhao)\b']
        return any(re.search(p, text) for p in patterns)

    # ─────────────────────────────────────────────────────────────────
    # Product formatting
    # ─────────────────────────────────────────────────────────────────
    def _format_product_listing(self, products: list) -> str:
        text = "স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
        for i, p in enumerate(products[:3], 1):
            title = p.get('title', 'N/A')
            price = p.get('price', 'N/A')
            url = p.get('url', '')
            text += f"{i}. {title}\nমূল্য: {price}\n"
            if url:
                text += f"লিংক: {url}\n"
            text += "\n"
        text += "আরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।"
        return text

    def _format_selected_product_response(self, product: Dict, index: int) -> str:
        title = product.get('title', 'N/A')
        price = product.get('price', 'N/A')
        desc = product.get('description', '')
        url = product.get('url', '')
        text = f"দারুণ পছন্দ স্যার। আপনি {index} নম্বর প্রোডাক্টটি নির্বাচন করেছেন।\n\n"
        text += f"{index}. {title}\nমূল্য: {price}\n"
        if desc:
            text += f"বিবরণ: {desc}\n"
        if url:
            text += f"লিংক: {url}\n"
        text += "\nআপনি চাইলে আমি এখন এই প্রোডাক্টটি অর্ডার করার ধাপগুলোও বলে দিতে পারি।"
        return text

    def _extract_product_selection(self, message: str) -> Optional[int]:
        n = str(message or '').strip()
        if not n:
            return None
        if self._extract_order_detail_fields(n):
            return None
        n = n.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        nl = n.lower()
        dm = re.fullmatch(r'\s*([1-5])\s*', nl)
        if dm:
            return int(dm.group(1))
        nums = re.findall(r'\b([1-5])\b', nl)
        if len(nums) != 1:
            return None
        cues = ['number', 'no', 'option', 'choose', 'select', 'pick',
                'নম্বর', 'নাম্বার', 'পছন্দ', 'নিবো', 'নেবো']
        if len(nl.split()) <= 3 or any(c in nl for c in cues):
            return int(nums[0])
        return None

    def _extract_listing_id_from_url(self, url: str) -> Optional[str]:
        u = str(url or '').strip()
        if not u:
            return None
        m = re.search(r'-(\d+)/?$', u)
        if m:
            return m.group(1)
        m2 = re.search(r'(\d+)/?$', u)
        if m2:
            return m2.group(1)
        return None

    def _extract_order_detail_fields(self, message: str) -> Dict[str, str]:
        text = str(message or '').strip()
        if not text:
            return {}
        label_to_key = [
            (r'product\s*name', 'product_name'), (r'phone\s*number', 'phone_number'),
            (r'quantity', 'quantity'), (r'address', 'address'),
            (r'mobile', 'phone_number'), (r'phone', 'phone_number'), (r'qty', 'quantity'),
            (r'পণ্যের\s*নাম', 'product_name'), (r'প্রোডাক্ট', 'product_name'),
            (r'ঠিকানা', 'address'), (r'নাম্বার', 'phone_number'), (r'নম্বর', 'phone_number'),
            (r'পরিমাণ', 'quantity'), (r'name', 'name')
        ]
        regex = "|".join(lbl for lbl, _ in label_to_key)
        pat = re.compile(rf'(?i)(?P<label>{regex})\s*[:;=\-]\s*', re.DOTALL)
        matches = list(pat.finditer(text))
        if not matches:
            return {}
        out = {}
        for i, m in enumerate(matches):
            lbl = m.group('label').strip().lower()
            s = m.end()
            e = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            val = re.sub(r'\s+', ' ', text[s:e]).strip()
            if not val:
                continue
            key = None
            for lr, k in label_to_key:
                if re.fullmatch(lr, lbl, flags=re.IGNORECASE):
                    key = k
                    break
            if key and key not in out:
                out[key] = val
        return out

    def _build_missing_order_fields_prompt(self, missing: list) -> str:
        labels = {'name': 'Name', 'phone_number': 'Phone Number', 'address': 'Address',
                  'product_name': 'Product Name', 'quantity': 'Quantity'}
        lines = "\n".join(f"{labels[k]}:" for k in missing if k in labels)
        return f"অর্ডার সম্পন্ন করতে শুধু বাকি তথ্যগুলো দিন:\n\n{lines}\n\nধন্যবাদ।"

    # ─────────────────────────────────────────────────────────────────
    # Price from context
    # ─────────────────────────────────────────────────────────────────
    def _reply_price_from_context(self, user_id: str) -> Optional[str]:
        selected = self.user_selected_product.get(user_id) or {}
        if selected:
            title = selected.get('title') or 'এই প্রোডাক্টটির'
            price = selected.get('price') or ''
            if price and str(price).strip().upper() != 'N/A':
                return f"জি স্যার, {title} এর দাম {price}।"
            return "স্যার, এই প্রোডাক্টটির দাম এখন দেখাতে পারছি না।"

        products = self.user_product_context.get(user_id, []) or []
        if not products:
            return None
        if len(products) == 1:
            p = products[0]
            title = p.get('title') or 'এই প্রোডাক্টটির'
            price = p.get('price') or ''
            if price and str(price).strip().upper() != 'N/A':
                return f"জি স্যার, {title} এর দাম {price}।"
            return "স্যার, এই প্রোডাক্টটির দাম এখন দেখাতে পারছি না।"

        lines = ["স্যার, আপনি যে প্রোডাক্টগুলো দেখেছেন সেগুলোর দাম:"]
        for i, p in enumerate(products[:5], 1):
            title = str(p.get('title') or f'প্রোডাক্ট {i}').strip()
            price = str(p.get('price') or 'N/A').strip()
            if not price or price.upper() == 'N/A':
                price = 'দাম পাওয়া যায়নি'
            lines.append(f"{i}. {title} - {price}")
        lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────
    # Template APIs (delivery, order, category)
    # ─────────────────────────────────────────────────────────────────
    def _fetch_delivery_intent_response(self) -> Optional[str]:
        params = {'intent': 'delivery', 'key': self.api_key}
        return self._fetch_template(params, 'ai_template_delivery')

    def _fetch_category_intent_response(self, category: str) -> Optional[str]:
        cat = str(category or '').strip().lower()
        if not cat:
            return None
        # Try direct URL construction first
        slug = re.sub(r'\s+', '-', cat)
        slug = re.sub(r'[^a-z0-9\u0980-\u09ff\-]', '', slug).strip('-')
        if slug:
            return f"আপনি {cat} ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন।\nএই লিংকে ক্লিক করুন:\nhttps://www.bdstall.com/{quote(slug, safe='-')}/"
        # Fallback to API
        params = {'intent': 'category', 'category': cat, 'key': self.api_key}
        return self._fetch_template(params, 'ai_template_category')

    def _fetch_order_intent_response(self, listing_id: str, template_intent: str = 'order') -> Optional[str]:
        ni = str(template_intent or 'order').strip().lower()
        if ni not in {'order', 'buy'}:
            ni = 'order'
        url = f"{self.order_intent_api_url}intent={ni}&id={listing_id}&key={self.api_key}"
        started = datetime.now()
        try:
            response = requests.get(url, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call('ai_template_order', 'GET', url,
                          {'intent': ni, 'id': listing_id, 'key': self.api_key},
                          response.status_code, duration_ms,
                          "PASS" if response.status_code == 200 else "FAIL",
                          response.text)
            if response.status_code != 200:
                return None
            return self._parse_template_response(response.json() if response.text else {})
        except Exception as e:
            logger.warning("Order template API failed: %s", e)
            return None

    def _fetch_template(self, params: Dict, api_label: str) -> Optional[str]:
        started = datetime.now()
        try:
            response = requests.get(self.delivery_intent_api_url, params=params, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(api_label, 'GET', self.delivery_intent_api_url, params,
                          response.status_code, duration_ms,
                          "PASS" if response.status_code == 200 else "FAIL",
                          response.text)
            if response.status_code != 200:
                return None
            return self._parse_template_response(response.json() if response.text else {})
        except Exception as e:
            logger.warning(f"{api_label} failed: %s", e)
            return None

    def _parse_template_response(self, data: Any) -> Optional[str]:
        if isinstance(data, str):
            return data.strip() or None
        if isinstance(data, dict):
            if data.get('success') is False:
                return None
            for k in ['response', 'message', 'template', 'text', 'content', 'data']:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            if len(data) == 1:
                v = next(iter(data.values()))
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return None

    def _get_order_info_template(self, user_id: str, message: str, intent_hint: str = 'order') -> str:
        listing_id = self._resolve_order_listing_id(user_id, message)
        if listing_id:
            tmpl = self._fetch_order_intent_response(listing_id, intent_hint)
            if tmpl:
                return tmpl
        return "আপনি কোন প্রোডাক্টটি অর্ডার/বাই করতে চান তার লিংক বা প্রোডাক্ট নম্বর দিন।"

    def _resolve_order_listing_id(self, user_id: str, message: str) -> Optional[str]:
        msg = str(message or '').strip()
        direct = self._extract_listing_id_from_url(msg)
        if direct:
            return direct
        selected = self.user_selected_product.get(user_id) or {}
        sid = self._extract_listing_id_from_url(str(selected.get('url') or ''))
        if sid:
            return sid
        products = self.user_product_context.get(user_id) or []
        if products:
            fid = self._extract_listing_id_from_url(str(products[0].get('url') or ''))
            if fid:
                return fid
        return None

    # ─────────────────────────────────────────────────────────────────
    # AI formatting for general queries
    # ─────────────────────────────────────────────────────────────────
    def _step4_ai_format(self, original_message: str, database_message: Optional[str],
                         products: Optional[list], conversation_context: str = '') -> Dict[str, Any]:
        if database_message and products:
            return {'success': True, 'response': self._format_product_listing(products)}

        if not self.groq_client:
            return {'success': False, 'error': 'Groq not available'}

        prompt = f"""তুমি একজন বন্ধুত্বপূর্ণ বাংলা চ্যাটবট। BDStall.com এর হয়ে উত্তর দাও।

Recent chat context:
{conversation_context or 'N/A'}

Latest user message:
{original_message}

সংক্ষিপ্ত, স্পষ্ট এবং সহায়ক বাংলা উত্তর দাও।
"""
        try:
            r = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=500
            )
            return {'success': True, 'response': r.choices[0].message.content.strip()}
        except Exception as e:
            logger.error(f"❌ AI formatting failed: {e}")
            if products:
                return {'success': True, 'response': self._format_product_listing(products)}
            return {'success': False, 'error': str(e)}

    # ─────────────────────────────────────────────────────────────────
    # Handoff to human
    # ─────────────────────────────────────────────────────────────────
    def _handoff_to_human(self, user_id: str, message: str, start_time: datetime,
                          intent: Optional[str], products: Optional[list] = None,
                          response_text: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        # Guard: product signals should never be hard-handed off
        if self._looks_like_possible_product_signal(message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id, message=message,
                response="জি স্যার, আমি প্রোডাক্ট সার্চ করে দেখছি। ব্র্যান্ড/মডেল/বাজেট দিলে আরও ভালো ফল পাবেন।",
                mode=ChatMode.AI, intent='product_search_clarification', products=products,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error=error, conversation_status=AI_ACTIVE_STATUS
            )

        self.user_modes[user_id] = ChatMode.HUMAN
        self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
        self.user_order_context[user_id] = False
        self.user_order_draft.pop(user_id, None)
        self.user_pending_product_query.pop(user_id, None)
        self._notify_assign_agent(user_id)

        return self._create_response(
            user_id=user_id, message=message,
            response=response_text or "স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
            mode=ChatMode.HUMAN, intent=intent, products=products,
            processing_time=(datetime.now() - start_time).total_seconds(),
            error=error, conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
        )

    def _notify_assign_agent(self, user_id: str) -> bool:
        payload = {"key": self.assign_agent_api_key, "user_id": str(user_id)}
        started = datetime.now()
        try:
            response = requests.post(self.assign_agent_api_url, json=payload, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            status = "PASS" if 200 <= response.status_code < 300 else "FAIL"
            _log_api_call('chatbot_assign_agent', 'POST', self.assign_agent_api_url,
                          payload, response.status_code, duration_ms, status, response.text)
            return status == "PASS"
        except Exception as e:
            logger.warning("⚠️ assign-agent API failed: %s", e)
            return False

    def _clear_product_search_cache(self, user_id: str, clear_pending: bool = True) -> None:
        self.user_product_context.pop(user_id, None)
        self.user_selected_product.pop(user_id, None)
        if clear_pending:
            self.user_pending_product_query.pop(user_id, None)

    # ─────────────────────────────────────────────────────────────────
    # Link buttons
    # ─────────────────────────────────────────────────────────────────
    def _build_link_buttons(self, products: Optional[list]) -> list:
        if not products:
            return []
        buttons = []
        seen = set()
        for i, p in enumerate(products[:5], 1):
            p = p or {}
            url = str(p.get('url') or '').strip()
            if not url or url in seen:
                continue
            seen.add(url)
            buttons.append({
                'index': i,
                'title': str(p.get('title') or 'Product').strip(),
                'price': str(p.get('price') or '').strip(),
                'text': 'View Product',
                'url': url
            })
        return buttons

    # ─────────────────────────────────────────────────────────────────
    # Response builder
    # ─────────────────────────────────────────────────────────────────
    def _create_response(self, user_id: str, message: str, response: str, mode: ChatMode,
                         intent: Optional[str], products: Optional[list],
                         search_keywords: Optional[str] = None,
                         link_buttons: Optional[list] = None,
                         intent_content: Optional[Dict] = None,
                         processing_time: float = 0.0,
                         error: Optional[str] = None,
                         conversation_status: Optional[str] = None) -> Dict[str, Any]:
        if intent:
            self.user_last_intent[user_id] = str(intent)
        self._save_state()
        trimmed = products[:5] if products else None
        resolved_content = self._normalize_intent_content_payload(
            intent_content or self.user_intent_content.get(user_id) or {}
        )
        return {
            "success": mode == ChatMode.AI,
            "user_id": user_id,
            "message": message,
            "response": response,
            "mode": mode.value,
            "intent": intent,
            "search_keywords": search_keywords,
            "products_found": len(products) if products else 0,
            "products": trimmed,
            "link_buttons": link_buttons if link_buttons is not None else self._build_link_buttons(trimmed),
            "intent_content": resolved_content,
            "conversation_status": conversation_status or self.user_conversation_status.get(
                user_id,
                HUMAN_SUPPORT_REQUIRED_STATUS if mode == ChatMode.HUMAN else AI_ACTIVE_STATUS
            ),
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "error": error
        }

    # ─────────────────────────────────────────────────────────────────
    # Public helpers (kept for API compatibility)
    # ─────────────────────────────────────────────────────────────────
    def switch_to_human(self, user_id: str):
        self.user_modes[user_id] = ChatMode.HUMAN
        self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
        self._save_state()
        self._notify_assign_agent(user_id)
        logger.info(f"👤 User {user_id} switched to HUMAN mode")

    def switch_to_ai(self, user_id: str):
        self.user_modes[user_id] = ChatMode.AI
        self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
        self.user_order_context[user_id] = False
        self.user_order_draft.pop(user_id, None)
        self.user_pending_product_query.pop(user_id, None)
        self._save_state()
        logger.info(f"🤖 User {user_id} switched to AI mode")

    def get_user_mode(self, user_id: str) -> str:
        return self.user_modes.get(user_id, ChatMode.AI).value
