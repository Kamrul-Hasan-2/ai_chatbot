"""
Simple Chatbot Flow — refactored with separated intent handlers.
=================================================================
Rules:
- Rule 1:  NO HARDCODING — categories/brands/products come only from APIs/runtime
- Rule 2:  API-only — no static fallback data
- Rule 3:  every bot reply returns intent_content; saving is done by the API layer
- Rule 4:  category mandatory for product/price/compare/order intents
- Rule 5:  category validated via CategoryValidator (cat_list API)
- Rule 6:  category switch → FULL reset
- Rule 7:  post-merge category guard — empty category → ask user
- Rule 8:  separated handlers per intent
- Rule 9:  comparison/buy intents return fixed messages
- Rule 10: short message + previous context = follow-up (category must still exist)
- Rule 11: human handoff only on explicit request or complaint
- Rule 12: intent_content schema = {title, cat, brand, price, compare, buy}
- Rule 13: mode NEVER stored in memory — responder API is sole source of truth
"""
import os
import sys
import logging
import threading
import tempfile
import shutil
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
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

try:
    from .category_validator import CategoryValidator
except ImportError:
    from category_validator import CategoryValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _log_api_call(api_name, method, url, request_payload, status_code,
                  duration_ms, status, response_preview=""):
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


class ChatMode(Enum):
    AI = "ai"
    HUMAN = "human"


AI_ACTIVE_STATUS = "AI Active"
HUMAN_SUPPORT_REQUIRED_STATUS = "Human Support Required"

VALID_INTENTS = {
    'product_search', 'price_query', 'comparison', 'ordering', 'delivery',
    'greeting', 'goodbye', 'thanks', 'complaint', 'faq', 'human_request',
    'buy', 'exit', 'unknown'
}

PRODUCT_RELATED_INTENTS = {'product_search', 'price_query', 'comparison', 'ordering'}

CONTEXT_TTL_SECONDS = 1800

CATEGORY_PROMPT = (
    "Apni kon category khujchen sir? "
    "(যেমন: mobile, laptop, AC, fridge ইত্যাদি)"
)


class SimpleChatbot:
    """Refactored chatbot — fully dynamic, API-driven, separated intent handlers."""

    FAST_PATH_PATTERNS = {
        'greeting': re.compile(
            r'^\s*(hi|hello|hey|hlw|hai|salam|assalamu\s*alaikum|assalamualaikum|'
            r'হাই|হ্যালো|হেলো|সালাম|আসসালামু\s*আলাইকুম|আসসালামুয়ালাইকুম)\s*[!.?]*\s*$',
            re.IGNORECASE,
        ),
        'goodbye': re.compile(
            r'^\s*(bye|goodbye|see\s*you|take\s*care|allah\s*hafez|ok\s*bye|'
            r'বিদায়|আল্লাহ\s*হাফেজ|বাই|আবার\s*দেখা\s*হবে)\s*[!.?]*\s*$',
            re.IGNORECASE,
        ),
        'thanks': re.compile(
            r'^\s*(thanks?|thank\s*you|thx|thanku|thankyou|thanks\s*a\s*lot|'
            r'ধন্যবাদ|অনেক\s*ধন্যবাদ)\s*[!.?]*\s*$',
            re.IGNORECASE,
        ),
        'ok_ack': re.compile(
            r'^\s*(ok|okay|okk|okey|acha|accha|ঠিক\s*আছে|আচ্ছা|ওকে)\s*[!.?]*\s*$',
            re.IGNORECASE,
        ),
        'human_request': re.compile(
            r'\b(human|agent|representative|talk\s*to\s*(?:a\s*)?(?:human|person)|'
            r'manus|manush|customer\s*support|live\s*chat|'
            r'মানুষ|প্রতিনিধি|কাস্টমার|এজেন্ট)\b',
            re.IGNORECASE,
        ),
        'buy': re.compile(
            r'\b(how\s*to\s*buy|how\s*to\s*order|how\s*to\s*purchase|'
            r'kivabe\s*(buy|order|kini|purchase)|'
            r'কিভাবে\s*(কিনবো|কিনব|অর্ডার|বাই)|'
            r'order\s*process|buy\s*process|buying\s*guide)\b',
            re.IGNORECASE,
        ),
        'exit': re.compile(
            r'\b(pore\s*kinbo|pore\s*janabo|pore\s*nebo|pore\s*dekhbo|ekhon\s*na|'
            r'later|পরে\s*কিনবো|পরে\s*জানাবো|পরে\s*নেবো|পরে\s*দেখবো|'
            r'এখন\s*লাগবে\s*না|পরে\s*হবে|notun\s*kichu\s*lagbe\s*na)\b',
            re.IGNORECASE,
        ),
    }

    COMPLAINT_PATTERNS = re.compile(
        r'\b(refund|complain|complaint|scam|fraud|cheat|fake|defect|broken|'
        r'baje|faltu|kharap|useless|worst|stupid|boka|gali|abuse|'
        r'বাজে|ফালতু|খারাপ|প্রতারণা|স্ক্যাম|রিফান্ড|অভিযোগ|গালি)\b',
        re.IGNORECASE,
    )

    def __init__(self):
        self.project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        self.state_file = os.path.join(self.project_root, 'data', 'chatbot_state.json')
        self._state_lock = threading.Lock()

        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key and Groq:
            self.groq_client = Groq(api_key=groq_api_key)
            self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        else:
            self.groq_client = None
            logger.warning("⚠️ Groq API not available")

        # Per-user state — NO mode/status here (Rule 13)
        self.user_product_context: Dict[str, list] = {}
        self.user_selected_product: Dict[str, Dict[str, Any]] = {}
        self.user_order_context: Dict[str, bool] = {}
        self.user_order_draft: Dict[str, Dict[str, str]] = {}
        self.user_pending_product_query: Dict[str, Dict[str, Any]] = {}
        self.user_last_intent: Dict[str, str] = {}
        self.user_intent_content: Dict[str, Dict[str, Any]] = {}

        # Caches (no responder cache — must always be live)
        self._search_cache: Dict[str, Tuple[float, Dict]] = {}
        self._search_cache_ttl = 300
        self._search_cache_max = 200
        self._history_cache: Dict[str, Tuple[float, str]] = {}
        self._history_cache_ttl = 60

        # BDStall config
        self.api_url = "https://www.bdstall.com/api/item/ai_search/"
        self.api_key = os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.delivery_intent_api_url = "https://www.bdstall.com/api/item/ai_template/"
        self.assign_agent_api_url = os.getenv(
            'ASSIGN_AGENT_API_URL', 'https://www.bdstall.com/api/item/chatbot_assign_agent/'
        )
        self.assign_agent_api_key = os.getenv('ASSIGN_AGENT_API_KEY', self.api_key)
        self.assign_bot_api_url = os.getenv(
            'ASSIGN_BOT_API_URL', 'https://www.bdstall.com/api/item/chatbot_assign_bot/'
        )
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

        self.category_validator = CategoryValidator(
            cat_list_url=os.getenv(
                'CATLIST_API_URL',
                'https://www.bdstall.com/api/chatbot/cat_list/'
            ),
            api_key=self.api_key,
        )

        self._load_state()
        self.database = self._load_database()

        logger.info("✅ SimpleChatbot initialized")
        logger.info("📚 Loaded %d FAQ rows", len(self.database))
        logger.info("📂 Loaded %d categories", len(self.category_validator.names_english()))

    # ─────────────────────────────────────────────────────────────
    # State persistence — mode/status excluded (Rule 13)
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
            self.user_intent_content = dict(state.get('user_intent_content') or {})
        except Exception as e:
            logger.error("❌ State restore failed: %s", e)

    def _save_state(self) -> None:
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
                logger.error("❌ State save failed: %s", e)

    # ─────────────────────────────────────────────────────────────
    # FAQ DB
    # ─────────────────────────────────────────────────────────────
    def _load_database(self) -> list:
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

    def _search_database_faq(self, message: str) -> Optional[str]:
        msg = message.lower().strip()
        if not msg:
            return None
        try:
            for item in self.database:
                q = item['question'].lower()
                if msg in q or q in msg:
                    if self._is_blocked_automated_message(item['answer']):
                        continue
                    return item['answer']
            if any(w in msg for w in ['order', 'অর্ডার', 'kibabe', 'kivabe', 'কিভাবে']):
                for item in self.database:
                    q = item['question'].lower()
                    if 'অর্ডার' in q and 'কিভাবে' in q:
                        return item['answer']
            if any(w in msg for w in ['delivery', 'ডেলিভারি', 'koto din']):
                for item in self.database:
                    if 'ডেলিভারি' in item['question'] or 'কত দিন' in item['question']:
                        return item['answer']
        except Exception as e:
            logger.warning("FAQ search failed: %s", e)
        return None

    # ─────────────────────────────────────────────────────────────
    # Responder API — always live, never cached (Rule 13)
    # ─────────────────────────────────────────────────────────────
    def _check_responder_type(self, user_id: str) -> Optional[str]:
        now = time.time()
        try:
            url = f"{self.responder_api_url}?key={self.responder_api_key}&user_id={user_id}"
            resp = requests.get(url, timeout=3)
            duration_ms = int((time.time() - now) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') and data.get('data'):
                    label = data['data'].get('responder_label', 'bot')
                    _log_api_call(
                        'responder_type_check', 'GET', url,
                        {'user_id': user_id}, resp.status_code,
                        duration_ms, 'PASS',
                        json.dumps(data.get('data', {}), ensure_ascii=False)[:200]
                    )
                    return label
            return None
        except Exception as e:
            logger.warning("Responder check error: %s", e)
            return None

    # ─────────────────────────────────────────────────────────────
    # Public mode helpers (for API layer compatibility)
    # ─────────────────────────────────────────────────────────────
    def get_user_mode(self, user_id: str) -> str:
        responder_type = self._check_responder_type(user_id)
        return 'human' if responder_type == 'agent' else 'ai'

    def switch_to_human(self, user_id: str) -> None:
        try:
            requests.post(
                self.assign_agent_api_url,
                json={'key': self.assign_agent_api_key, 'user_id': user_id, 'intent': 'manual_switch'},
                timeout=5
            )
        except Exception as e:
            logger.warning("switch_to_human failed: %s", e)

    def switch_to_ai(self, user_id: str) -> None:
        try:
            requests.post(
                self.assign_bot_api_url,
                json={'key': self.api_key, 'user_id': user_id},
                timeout=5
            )
        except Exception as e:
            logger.warning("switch_to_ai failed: %s", e)

    # ═════════════════════════════════════════════════════════════
    # MAIN ENTRY
    # ═════════════════════════════════════════════════════════════
    def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        try:
            start_time = datetime.now()
            logger.info("📨 user=%s msg=%r", user_id, message)

            if self._is_blocked_automated_message(message):
                return self._create_response(
                    user_id=user_id, message=message, response="",
                    mode=ChatMode.AI, intent='ignored_automated_template', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            # Mode derived live from responder API — never from memory (Rule 13)
            responder_type = self._check_responder_type(user_id)
            if responder_type == 'agent':
                return self._create_response(
                    user_id=user_id, message=message, response="",
                    mode=ChatMode.HUMAN, intent='human_mode_active', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
                )

            # FAST PATH: explicit human request
            if self.FAST_PATH_PATTERNS['human_request'].search(message):
                return self._handoff_to_human(
                    user_id, message, start_time,
                    intent='explicit_human_request',
                    response_text="স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।"
                )

            # FAST PATH: complaint
            if self.COMPLAINT_PATTERNS.search(message):
                prev = self._normalize_intent_content_payload(
                    self.user_intent_content.get(user_id) or {}
                )
                prev['complain'] = True
                self.user_intent_content[user_id] = prev
                return self._handoff_to_human(
                    user_id, message, start_time, intent='complaint_handoff',
                    response_text="স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি এখনই আপনার সাথে যোগাযোগ করবেন।"
                )

            # FAST PATH: product selection (1-5)
            selected_index = self._extract_product_selection(message)
            user_products = self.user_product_context.get(user_id, [])
            if selected_index and user_products and len(user_products) >= selected_index:
                selected = user_products[selected_index - 1]
                self.user_selected_product[user_id] = selected
                self._reset_clarification_counter(user_id)
                return self._create_response(
                    user_id=user_id, message=message,
                    response=self._format_selected_product_response(selected, selected_index),
                    mode=ChatMode.AI, intent='product_selection', products=user_products,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )

            # FAST PATH: order form
            order_response = self._maybe_handle_order_flow(user_id, message, start_time)
            if order_response is not None:
                return order_response

            # FAST PATH: regex-matched simple intents
            fast_intent = self._fast_path_intent(message)
            if fast_intent:
                return self._handle_fast_path(user_id, message, fast_intent, start_time)

            # MAIN PATH: Groq → resolve → merge → route
            return self._handle_main_flow(user_id, message, start_time)

        except Exception as e:
            logger.error("❌ Unhandled error: %s", e, exc_info=True)
            return {
                'response': "দুঃখিত স্যার, একটি সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।",
                'mode': 'ai',
                'intent': 'system_error',
                'intent_content': {},
                'conversation_status': AI_ACTIVE_STATUS,
                'products': [],
                'processing_time': 0.0,
                'error': str(e)
            }

    # ─────────────────────────────────────────────────────────────
    # Fast path (regex, no Groq)
    # ─────────────────────────────────────────────────────────────
    def _fast_path_intent(self, message: str) -> Optional[str]:
        msg = message.strip()
        if not msg:
            return None
        for name in ('greeting', 'goodbye', 'thanks', 'ok_ack', 'buy', 'exit'):
            pat = self.FAST_PATH_PATTERNS[name]
            if name in ('buy', 'exit'):
                if pat.search(msg):
                    return name
            else:
                if pat.match(msg):
                    return name
        return None

    def _handle_fast_path(self, user_id: str, message: str, intent: str,
                          start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)

        if intent == 'greeting':
            return self._create_response(
                user_id=user_id, message=message,
                response="আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?",
                mode=ChatMode.AI, intent='greeting', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )
        if intent == 'goodbye':
            prev = self._normalize_intent_content_payload(
                self.user_intent_content.get(user_id) or {}
            )
            prev['exit'] = 1
            self.user_intent_content[user_id] = prev
            return self._create_response(
                user_id=user_id, message=message,
                response="ধন্যবাদ স্যার, ভালো থাকবেন।",
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
        if intent == 'buy':
            return self.handle_buy(user_id, message, start_time)
        if intent == 'exit':
            return self.handle_exit(user_id, message, start_time)
        # ok_ack / catch-all
        return self._create_response(
            user_id=user_id, message=message,
            response="ধন্যবাদ স্যার, আর কিভাবে আমি আপনাকে সাহায্য করতে পারি?",
            mode=ChatMode.AI, intent='conversation_finished_ack', products=None,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    # ═════════════════════════════════════════════════════════════
    # MAIN flow
    # ═════════════════════════════════════════════════════════════
    def _handle_main_flow(self, user_id: str, message: str,
                        start_time: datetime) -> Dict[str, Any]:
        conversation_context = self._get_history_cached(user_id)
        previous_intent = self._load_previous_intent(user_id)
        groq_result = self._step1_groq_extract(message, conversation_context, previous_intent)
        intent = groq_result['intent']
        entities = groq_result['entities']

        # Validate category — only if Groq explicitly returned one
        resolved_cat = None
        if entities.get('category'):
            resolved_cat = self.category_validator.resolve(entities['category'])
        entities['category'] = resolved_cat['category_name'] if resolved_cat else ''

        logger.info("✅ Intent=%s entities=%s followup=%s resolved=%s",
                    intent, entities, groq_result['is_followup'],
                    resolved_cat['category_name'] if resolved_cat else None)

        merged = self._merge_intent_context(user_id, groq_result, previous_intent, intent)
        self.user_intent_content[user_id] = self._intent_to_normalized(merged, message)

        if intent == 'comparison':
            return self.handle_comparison(user_id, message, merged, start_time)
        if intent in ('ordering', 'buy'):
            return self.handle_buy(user_id, message, start_time)
        if intent == 'exit':
            return self.handle_exit(user_id, message, start_time)
        if intent in ('greeting', 'goodbye', 'thanks'):
            self._reset_clarification_counter(user_id)
            return self._handle_fast_path(user_id, message, intent, start_time)
        if intent == 'delivery':
            return self.handle_delivery(user_id, message, merged, start_time)
        if intent == 'faq':
            return self.handle_faq(user_id, message, merged, start_time)
        if intent == 'price_query':
            return self.handle_price_query(user_id, message, merged, start_time)
        if intent == 'product_search':
            return self.handle_product_search(user_id, message, merged, start_time)

        # Safety net: Groq returned unknown but message matches buy/exit/comparison patterns
        if self.FAST_PATH_PATTERNS['buy'].search(message):
            return self.handle_buy(user_id, message, start_time)
        if self.FAST_PATH_PATTERNS['exit'].search(message):
            return self.handle_exit(user_id, message, start_time)
        msg_lower = message.lower()
        if any(w in msg_lower for w in ['konta valo', 'konta bhalo', 'konti valo', 'which is better',
                                        'কোনটা ভালো', 'কোনটা ভাল', 'তুলনা']):
            return self.handle_comparison(user_id, message, merged, start_time)

        return self.handle_fallback(user_id, message, merged, start_time)

    # ═════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═════════════════════════════════════════════════════════════

    def handle_product_search(self, user_id: str, message: str, merged: Dict,
                              start_time: datetime) -> Dict[str, Any]:
        if not merged.get('category'):
            return self._ask_for_category(user_id, message, merged, start_time)

        self._reset_clarification_counter(user_id)
        category = merged['category']
        brand = merged.get('brand', '')
        title = merged.get('title', '')
        price_max = merged.get('price_max')

        keywords = self._build_search_keywords_from_merged(merged)
        result = self._cached_search(keywords, price_max)

        if result['products_found'] == 0:
            broader = self._build_broader_search_keywords(merged)
            if broader and broader != keywords:
                retry = self._cached_search(broader, price_max)
                if retry['products_found'] > 0:
                    keywords = broader
                    result = retry

        if result['products_found'] == 0:
            label = ' '.join([v for v in [brand, title, category] if v]) or category
            no_result = (
                f"দুঃখিত স্যার, এই মুহূর্তে {label} স্টকে নেই। "
                "অন্য কোনো ব্র্যান্ড বা মডেল দেখাবো?"
            )
            return self._create_response(
                user_id=user_id, message=message, response=no_result,
                mode=ChatMode.AI, intent='no_products_found', products=None,
                search_keywords=keywords,
                intent_content=self._intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        products = result['products']
        self.user_product_context[user_id] = products[:5]

        listing_text, listing_buttons = self._format_product_listing(products[:3])
        return self._create_response(
            user_id=user_id, message=message,
            response=listing_text,
            mode=ChatMode.AI, intent='product_search', products=products,
            search_keywords=keywords,
            link_buttons=listing_buttons,
            intent_content=self._intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds()
        )

    def handle_price_query(self, user_id: str, message: str, merged: Dict,
                           start_time: datetime) -> Dict[str, Any]:
        if not merged.get('category'):
            return self._ask_for_category(user_id, message, merged, start_time)

        ctx_reply = self._reply_price_from_context(user_id)
        if ctx_reply:
            self._reset_clarification_counter(user_id)
            return self._create_response(
                user_id=user_id, message=message, response=ctx_reply,
                mode=ChatMode.AI, intent='price_from_context', products=None,
                intent_content=self._intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        return self.handle_product_search(user_id, message, merged, start_time)


    def handle_comparison(self, user_id: str, message: str, merged: Dict,
                        start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)
        return self._create_response(
            user_id=user_id, message=message,
            response=self._build_comparison_redirect_response(),
            mode=ChatMode.AI, intent='comparison', products=None,
            link_buttons=self._build_comparison_link_buttons(merged),
            intent_content=self._intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_buy(self, user_id: str, message: str,
                   start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)
        return self._create_response(
            user_id=user_id, message=message,
            response="স্যার এই লিংকে গিয়ে আপনি দেখতে পারেন কিভাবে অর্ডার অথবা বাই করা যায়",
            mode=ChatMode.AI, intent='buy', products=None,
            link_buttons=[{
                'text': 'Shopping Guide',
                'url': 'https://www.bdstall.com/blog/safe-shopping-guide/'
            }],
            intent_content=self._normalize_intent_content_payload(
                self.user_intent_content.get(user_id) or {}
            ),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_exit(self, user_id: str, message: str,
                    start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)
        prev = self._normalize_intent_content_payload(
            self.user_intent_content.get(user_id) or {}
        )
        prev['exit'] = 1
        self.user_intent_content[user_id] = prev
        return self._create_response(
            user_id=user_id, message=message,
            response="সাথে থাকার জন্য ধন্যবাদ।",
            mode=ChatMode.AI, intent='exit', products=None,
            intent_content=prev,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_delivery(self, user_id: str, message: str, merged: Dict,
                        start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)
        tmpl = self._fetch_delivery_intent_response()
        if tmpl:
            return self._create_response(
                user_id=user_id, message=message, response=tmpl,
                mode=ChatMode.AI, intent='delivery', products=None,
                intent_content=self._intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        faq = self._search_database_faq(message)
        if faq:
            return self._create_response(
                user_id=user_id, message=message, response=faq,
                mode=ChatMode.AI, intent='delivery', products=None,
                intent_content=self._intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        return self.handle_fallback(user_id, message, merged, start_time)

    def handle_faq(self, user_id: str, message: str, merged: Dict,
                   start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)
        faq = self._search_database_faq(message)
        if faq:
            return self._create_response(
                user_id=user_id, message=message, response=faq,
                mode=ChatMode.AI, intent='faq', products=None,
                intent_content=self._intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        return self.handle_fallback(user_id, message, merged, start_time)

    def handle_fallback(self, user_id: str, message: str, merged: Dict,
                        start_time: datetime) -> Dict[str, Any]:
        # If category already known, search products
        if merged.get('category'):
            return self.handle_product_search(user_id, message, merged, start_time)

        # Try to resolve the message itself as a category reply
        resolved = self.category_validator.resolve(message.strip())
        if resolved:
            merged['category'] = resolved['category_name']
            self._reset_clarification_counter(user_id)
            return self.handle_product_search(user_id, message, merged, start_time)

        # Safety net: delivery-related messages never need a category
        msg_lower = message.lower()
        delivery_hints = [
            'delivery', 'ডেলিভারি', 'koto din', 'কত দিন', 'deliver',
            'shipping', 'পাঠাবে', 'পাবো কবে', 'dibo kobe', 'lagbe koto din',
            'charge koto', 'চার্জ কত',
        ]
        if any(h in msg_lower for h in delivery_hints):
            return self.handle_delivery(user_id, message, merged, start_time)

        # Safety net: buy/comparison/exit never need a category
        if self.FAST_PATH_PATTERNS['buy'].search(message):
            return self.handle_buy(user_id, message, start_time)
        if self.FAST_PATH_PATTERNS['exit'].search(message):
            return self.handle_exit(user_id, message, start_time)
        if any(w in msg_lower for w in ['konta valo', 'konti valo', 'konta bhalo',
                                        'which is better', 'কোনটা ভালো', 'কোনটি ভালো']):
            return self.handle_comparison(user_id, message, merged, start_time)

        return self._ask_for_category(user_id, message, merged, start_time)






    # ─────────────────────────────────────────────────────────────
    # Ask for category
    # ─────────────────────────────────────────────────────────────
    def _ask_for_category(self, user_id: str, message: str, merged: Dict,
                          start_time: datetime) -> Dict[str, Any]:
        return self._create_response(
            user_id=user_id, message=message, response=CATEGORY_PROMPT,
            mode=ChatMode.AI, intent='need_category', products=None,
            intent_content=self._intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def _reset_clarification_counter(self, user_id: str) -> None:
        pass  # Counter removed — human handoff handled by responder API

    # ─────────────────────────────────────────────────────────────
    # Groq extraction
    # ─────────────────────────────────────────────────────────────
    def _step1_groq_extract(self, message: str, conversation_context: str,
                            previous_intent: Dict) -> Dict[str, Any]:
        if not self.groq_client:
            return self._minimal_fallback(message)

        sample_categories = self.category_validator.names_english()[:30]
        sample_str = ", ".join(sample_categories) if sample_categories else "(none loaded yet)"

        system_prompt = f"""You are a strict JSON extractor for a Bangladeshi e-commerce chatbot (BDStall).
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
product_search | price_query | comparison | buy | exit | delivery | greeting | goodbye | thanks | complaint | faq | human_request | unknown

INTENT DEFINITIONS:
- product_search : user wants to see, find, or browse products
- price_query    : user is asking about price or cost of a product/category
- comparison     : user wants to compare products or know which is better
- buy            : user wants to know HOW to buy or place an order (process question)
- exit           : user is leaving, says later / not now / will come back
- delivery       : user asks about delivery time, charge, or process
- greeting       : hello / hi / salam with no product intent
- goodbye        : farewell with no product intent
- thanks         : thank you messages
- complaint      : refund, scam, broken product, bad experience
- faq            : general questions about the site or policies
- human_request  : user wants to speak to a human agent
- unknown        : truly cannot determine

CATEGORY EXTRACTION — most important rule:
A "category" is a generic product type. Known examples (not exhaustive): {sample_str}
RULES:
- If the message contains a recognisable product type word → ALWAYS set category to that word.
- A single word that is a product type (e.g. "laptop", "mobile", "AC", "fridge") → category = that word, intent = product_search.
- "laptop price" / "laptop dam koto" / "laptop er dam" → category="laptop", intent=price_query.
- "hp laptop" → brand="hp", category="laptop".
- "hp 840 g3" → brand="hp", title="840 g3", category="" (no product type word — add "category" to missing[]).
- NEVER leave category="" if a product type word exists anywhere in the message.
- "smart watch ache", "laptop ache", "mobile ache" → category=the product word, intent=product_search. "ache" means "available/do you have" — it is NOT a category word.


BRAND vs CATEGORY:
- brand = manufacturer name (samsung, hp, dell, apple, walton, asus, acer, lenovo).
- category = product type (laptop, mobile, phone, AC, fridge, television, tablet).
- "samsung" alone → brand="samsung", category="" (missing).
- "samsung mobile" → brand="samsung", category="mobile".

is_followup RULE:
- true ONLY when message has NO product type word AND depends entirely on previous context.
- If any product type word is present → is_followup = false.
- "hp 840 g3" → is_followup=true (no product type, relies on context for category).
- "laptop price" → is_followup=false (product type "laptop" is present).

MISSING ARRAY:
- Add "category" to missing[] when intent is product_search, price_query, or comparison AND category="".
- All other intents: missing=[].

BUDGET PARSING: "50k"=50000, "30 hazar"=30000, "under 20k"→price_max=20000. null if absent.

BANGLISH / BANGLA QUICK REFERENCE:
- "pore kinbo", "pore janabo", "ekhon na", "পরে জানাবো", "এখন লাগবে না" → exit
- "kivabe order korbo", "how to buy"                                       → buy
- "konta valo", "which is better", "কোনটা ভালো"                           → comparison
- "delivery koto din", "delivery charge"                                   → delivery
- "refund chai", "baje", "faltu", "kharap"                                 → complaint
- "human chai", "agent er sathe kotha"                                     → human_request
- "X ache", "X ki ache", "X paoa jabe" → product_search with category=X (ache = is available/do you have)       → human_request
- "order korbo kivabe", "kivabe order korbo", "how to buy", "order process" → buy (no category needed)
- "konti valo", "konta valo", "konta bhalo", "which is better", "কোনটা ভালো", "কোনটি ভালো" → comparison (no category needed)
- "delivery koto din", "delivery charge", "koto din lagbe", "delivery kobe dibe" → delivery
- "কত দিন লাগবে", "ডেলিভারি কত দিন", "কত দিনে পাবো", "ডেলিভারি চার্জ"        → delivery

PREVIOUS CONTEXT (is_followup detection only — do NOT copy into entities):
{json.dumps(previous_intent or {}, ensure_ascii=False)}
"""

        user_prompt = f"""Recent conversation:
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
                temperature=0.0,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            return self._validate_groq_schema(parsed)
        except json.JSONDecodeError as e:
            logger.warning("Groq JSON parse failed: %s", e)
            return self._minimal_fallback(message)
        except Exception as e:
            logger.warning("Groq call failed: %s", e)
            return self._minimal_fallback(message)

    def _validate_groq_schema(self, parsed: Dict) -> Dict[str, Any]:
        intent = str(parsed.get('intent', 'unknown')).lower().strip()
        if intent not in VALID_INTENTS:
            intent = 'unknown'

        entities = parsed.get('entities') or {}
        category = str(entities.get('category') or '').strip()
        brand = str(entities.get('brand') or '').strip().lower()
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

    def _minimal_fallback(self, message: str) -> Dict[str, Any]:
        """Emergency fallback — only when Groq is unavailable."""
        budget = self._extract_budget_range(message)

        if self.FAST_PATH_PATTERNS['greeting'].match(message):
            intent = 'greeting'
        elif self.FAST_PATH_PATTERNS['goodbye'].match(message):
            intent = 'goodbye'
        elif self.FAST_PATH_PATTERNS['thanks'].match(message):
            intent = 'thanks'
        elif self.FAST_PATH_PATTERNS['exit'].search(message):
            intent = 'exit'
        elif self.FAST_PATH_PATTERNS['buy'].search(message):
            intent = 'buy'
        elif self.FAST_PATH_PATTERNS['human_request'].search(message):
            intent = 'human_request'
        elif self.COMPLAINT_PATTERNS.search(message):
            intent = 'complaint'
        else:
            intent = 'unknown'

        return {
            'intent': intent,
            'entities': {
                'category': '', 'brand': '', 'title': '',
                'price_max': budget.get('max_price'),
                'price_min': budget.get('min_price'),
            },
            'missing': [],
            'is_followup': False,
            'confidence': 0.3,
        }

    # ─────────────────────────────────────────────────────────────
    # Context merge (Rules 6, 7, 10)
    # ─────────────────────────────────────────────────────────────
    def _load_previous_intent(self, user_id: str) -> Dict:
        prev = dict(self.user_intent_content.get(user_id) or {})

        # If nothing in memory, pull from DB (covers server restart / first message)
        if not prev or not prev.get('cat'):
            db_prev = self._fetch_intent_content_from_db(user_id)
            if db_prev:
                prev = db_prev

        updated_at = prev.get('updated_at')
        if updated_at:
            try:
                age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
                if age > CONTEXT_TTL_SECONDS:
                    logger.info("Context expired for %s (age=%.0fs)", user_id, age)
                    return {}
            except Exception:
                pass

        # Translate stored 'cat' back to 'category' for merge logic
        if prev.get('cat') and not prev.get('category'):
            prev['category'] = prev['cat']
        return prev

    def _fetch_intent_content_from_db(self, user_id: str) -> Dict:
        """
        Pull the last saved intent_content from the chat history API.
        Used to restore category context after server restart or on first message.
        """
        try:
            urls = self._build_chat_history_urls(user_id, 10)
            for url in urls:
                try:
                    resp = requests.get(url, timeout=5)
                    if not (200 <= resp.status_code < 300):
                        continue
                    data = resp.json() if resp.text else {}

                    # Normalise to a list of message dicts
                    candidates = []
                    if isinstance(data, list):
                        candidates = data
                    elif isinstance(data, dict):
                        for k in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
                            v = data.get(k)
                            if isinstance(v, list):
                                candidates = v
                                break

                    # Walk newest-first looking for a bot message with intent_content
                    for item in reversed(candidates):
                        if not isinstance(item, dict):
                            continue
                        # Only look at bot messages (sender_type=2)
                        sender = str(item.get('sender_type') or '').strip()
                        if sender != '2':
                            continue
                        ic = item.get('intent_content')
                        if isinstance(ic, str):
                            try:
                                ic = json.loads(ic)
                            except Exception:
                                continue
                        if isinstance(ic, dict) and ic.get('cat'):
                            logger.info("[INTENT_DB] Restored intent_content for %s: %s", user_id, ic)
                            return ic
                except Exception:
                    continue
        except Exception as e:
            logger.warning("_fetch_intent_content_from_db failed: %s", e)
        return {}

    def _merge_intent_context(self, user_id: str, groq_result: Dict,
                            previous: Dict, intent: str = '') -> Dict:
        new_entities = groq_result['entities']
        new_category = new_entities.get('category', '')
        prev_category = previous.get('category', '')
        is_followup = groq_result.get('is_followup', False)

        # Rule 6: explicit category switch → full reset
        if new_category and prev_category and new_category.lower() != prev_category.lower():
            logger.info("🔄 Category switch %s → %s. Full reset.", prev_category, new_category)
            self._clear_product_search_cache(user_id, clear_pending=True)
            return {
                'category': new_category,
                'brand': new_entities.get('brand', ''),
                'title': new_entities.get('title', ''),
                'price_max': new_entities.get('price_max'),
                'price_min': new_entities.get('price_min'),
                'updated_at': datetime.now().isoformat(),
            }

        # Only carry previous category forward when Groq explicitly says it's a follow-up.
        # If Groq found no category but also did NOT mark it as a follow-up,
        # the category is genuinely missing — do NOT bleed previous category in.
        if new_category:
            effective_category = new_category
        elif is_followup:
            effective_category = prev_category
        else:
            # Groq found no category and said it's not a follow-up → ask user
            effective_category = ''

        # If category changed to empty from a non-empty previous, clear product cache
        if prev_category and not effective_category:
            self._clear_product_search_cache(user_id, clear_pending=False)

        return {
            'category': effective_category,
            'brand': new_entities.get('brand') or previous.get('brand', ''),
            'title': new_entities.get('title') or previous.get('title', ''),
            'price_max': (new_entities.get('price_max')
                        if new_entities.get('price_max') is not None
                        else previous.get('price_max')),
            'price_min': (new_entities.get('price_min')
                        if new_entities.get('price_min') is not None
                        else previous.get('price_min')),
            'updated_at': datetime.now().isoformat(),
        }


    def _intent_to_normalized(self, merged: Dict, message: str) -> Dict[str, Any]:
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

        return {
            'title': str(merged.get('title') or '').strip(),
            'cat': str(merged.get('category') or '').strip(),
            'brand': str(merged.get('brand') or '').strip().lower(),
            'price': price_text,
            'compare': '',
            'buy': '',
            'updated_at': merged.get('updated_at', datetime.now().isoformat()),
        }

    def _normalize_intent_content_payload(self, payload: Optional[Dict] = None) -> Dict[str, Any]:
        default = {
            'title': '', 'cat': '', 'brand': '', 'price': '', 'compare': '', 'buy': '',
        }
        if not isinstance(payload, dict):
            return default
        out = dict(default)
        out['title'] = str(payload.get('title') or '').strip()
        out['cat'] = str(payload.get('cat') or payload.get('category') or '').strip()
        out['brand'] = str(payload.get('brand') or '').strip().lower()
        out['price'] = str(payload.get('price') or '').strip()
        out['compare'] = str(payload.get('compare') or '').strip()
        out['buy'] = str(payload.get('buy') or '').strip()
        if 'complain' in payload:
            out['complain'] = bool(payload['complain'])
        if 'exit' in payload:
            try:
                out['exit'] = 1 if int(payload['exit']) else 0
            except Exception:
                out['exit'] = 0
        return out

    # ─────────────────────────────────────────────────────────────
    # Search
    # ─────────────────────────────────────────────────────────────
    def _build_search_keywords_from_merged(self, merged: Dict) -> str:
        parts = []
        if merged.get('brand'):
            parts.append(merged['brand'])
        if merged.get('title'):
            parts.append(merged['title'])
        elif merged.get('category'):
            parts.append(merged['category'])
        if merged.get('price_max'):
            parts.append(str(merged['price_max']))
        return ' '.join(parts).strip()

    def _build_broader_search_keywords(self, merged: Dict) -> Optional[str]:
        parts = []
        if merged.get('brand'):
            parts.append(merged['brand'])
        if merged.get('category'):
            parts.append(merged['category'])
        elif merged.get('title'):
            parts.append(merged['title'])
        broad = ' '.join(parts).strip()
        return broad or None

    def _extract_budget_range(self, message: str) -> Dict[str, Optional[int]]:
        text = str(message or '').strip().lower()
        if not text:
            return {'min_price': None, 'max_price': None, 'price_text': ''}
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        def _to_taka(v, u):
            val = int(float(v))
            un = (u or '').strip().lower()
            if un in {'k', 'হাজার', 'hazar', 'thousand'}:
                return val * 1000
            if un in {'tk', 'taka', 'টাকা'}:
                return val
            if val < 1000:
                return val * 1000
            return val

        rm = re.search(
            r'(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?\s*(?:-|to|থেকে)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?',
            text)
        if rm:
            mn = _to_taka(rm.group(1), rm.group(2) or rm.group(4) or '')
            mx = _to_taka(rm.group(3), rm.group(4) or rm.group(2) or '')
            if mn > mx:
                mn, mx = mx, mn
            return {'min_price': mn, 'max_price': mx, 'price_text': f"{mn}-{mx}"}

        um = re.search(
            r'(?:under|within|modde|modhhe|budget|er modde|এর মধ্যে|মধ্যে|below|less than)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?',
            text)
        if um:
            mx = _to_taka(um.group(1), um.group(2) or '')
            return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

        gm = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)\b', text)
        if gm:
            mx = _to_taka(gm.group(1), gm.group(2) or '')
            return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

        return {'min_price': None, 'max_price': None, 'price_text': ''}

    def _cached_search(self, keywords: str, max_price: Optional[int] = None) -> Dict[str, Any]:
        cache_key = f"{keywords}|{max_price or ''}"
        now = time.time()
        cached = self._search_cache.get(cache_key)
        if cached and (now - cached[0]) < self._search_cache_ttl:
            return cached[1]
        result = self._do_search(keywords, max_price)
        self._search_cache[cache_key] = (now, result)
        if len(self._search_cache) > self._search_cache_max:
            oldest = min(self._search_cache.keys(), key=lambda k: self._search_cache[k][0])
            self._search_cache.pop(oldest, None)
        return result

    def _do_search(self, keywords: str, explicit_max_price: Optional[int] = None) -> Dict[str, Any]:
        try:
            params = {'term': keywords.strip(), 'key': self.api_key}
            started = datetime.now()
            response = requests.get(self.api_url, params=params, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call('ai_search', 'GET', self.api_url, params,
                          response.status_code, duration_ms,
                          "PASS" if response.status_code == 200 else "FAIL",
                          response.text)
            if response.status_code != 200:
                return {'products_found': 0, 'products': []}

            data = response.json()
            if not data.get('getListingItem') or len(data['getListingItem']) < 2:
                return {'products_found': 0, 'products': []}

            total_count = data['getListingItem'][0]
            products_array = data['getListingItem'][1] or []
            if not products_array:
                return {'products_found': 0, 'products': []}

            max_price = explicit_max_price
            filtered = []
            for p in products_array[:20]:
                try:
                    pp = int(p.get('app_ListingPrice', 999999))
                    if max_price and pp > max_price:
                        continue
                    filtered.append(p)
                except Exception:
                    continue

            top = filtered[:5]
            if not top:
                return {'products_found': 0, 'products': []}

            products_list = [{
                'title': p.get('ListingTitle', 'N/A'),
                'price': p.get('ListingPrice', 'N/A'),
                'original_price': p.get('app_ListingOriginalPrice', ''),
                'discount': p.get('ListingDiscountPercentage', 0),
                'url': p.get('ListingURL', ''),
                'image': p.get('ListingThumbAvator', ''),
            } for p in top]

            return {
                'products_found': len(top),
                'total_products': total_count,
                'products': products_list,
            }
        except Exception as e:
            logger.error("Search failed: %s", e)
            return {'products_found': 0, 'products': []}

    # ─────────────────────────────────────────────────────────────
    # History
    # ─────────────────────────────────────────────────────────────
    def _get_history_cached(self, user_id: str) -> str:
        now = time.time()
        cached = self._history_cache.get(user_id)
        if cached and (now - cached[0]) < self._history_cache_ttl:
            return cached[1]
        ctx = self._fetch_recent_chat_context(user_id, self.chatbot_history_limit)
        self._history_cache[user_id] = (now, ctx)
        return ctx

    def _fetch_recent_chat_context(self, user_id: str, limit: int = 5) -> str:
        if not user_id:
            return ''
        safe_limit = max(1, min(int(limit or 5), 20))
        urls = self._build_chat_history_urls(user_id, safe_limit)
        for url in urls:
            try:
                resp = requests.get(url, timeout=8)
                if not (200 <= resp.status_code < 300):
                    continue
                payload = resp.json() if resp.text else {}
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
        bs = base.rstrip('/')
        cands = [f"{base}{tail}", f"{base}?{tail}", f"{bs}?{tail}"]
        seen, out = set(), []
        for u in cands:
            if u not in seen:
                seen.add(u); out.append(u)
        return out

    def _normalize_history_messages(self, payload: Any) -> list:
        candidates = []
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict):
            for k in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
                v = payload.get(k)
                if isinstance(v, list):
                    candidates = v; break
            if not candidates and isinstance(payload.get('data'), dict):
                nested = payload.get('data') or {}
                for k in ['messages', 'history', 'chat_history', 'conversation', 'items']:
                    v = nested.get(k)
                    if isinstance(v, list):
                        candidates = v; break
        lines = []
        for item in candidates:
            if isinstance(item, str):
                t = item.strip()
                if t: lines.append(f"User: {t}")
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get('message') or item.get('text') or
                       item.get('content') or item.get('body') or '').strip()
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

    # ─────────────────────────────────────────────────────────────
    # Order flow
    # ─────────────────────────────────────────────────────────────
    def _maybe_handle_order_flow(self, user_id: str, message: str,
                                 start_time: datetime) -> Optional[Dict[str, Any]]:
        incoming = self._extract_order_detail_fields(message)
        active = self.user_order_context.get(user_id, False)
        if not incoming and not active:
            return None

        if active and not incoming:
            if self._fast_path_intent(message) or \
               self.category_validator.resolve_from_message(message):
                self.user_order_context[user_id] = False
                self.user_order_draft.pop(user_id, None)
                return None

        draft = dict(self.user_order_draft.get(user_id, {}))
        draft.update(incoming)
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
                user_id, message, start_time,
                intent='order_details_submission',
                response_text="ধন্যবাদ স্যার, আমাদের অন্য একজন প্রতিনিধি এসে কথা বলবে।"
            )

        self.user_order_context[user_id] = True
        self.user_order_draft[user_id] = draft
        return self._create_response(
            user_id=user_id, message=message,
            response=self._build_missing_order_fields_prompt(missing),
            mode=ChatMode.AI, intent='order_details_incomplete', products=None,
            processing_time=(datetime.now() - start_time).total_seconds()
        )

    def _extract_order_detail_fields(self, message: str) -> Dict[str, str]:
        text = str(message or '').strip()
        if not text:
            return {}
        label_to_key = [
            (r'product\s*name', 'product_name'),
            (r'phone\s*number', 'phone_number'),
            (r'quantity', 'quantity'),
            (r'address', 'address'),
            (r'mobile', 'phone_number'),
            (r'phone', 'phone_number'),
            (r'qty', 'quantity'),
            (r'পণ্যের\s*নাম', 'product_name'),
            (r'প্রোডাক্ট', 'product_name'),
            (r'ঠিকানা', 'address'),
            (r'নাম্বার', 'phone_number'),
            (r'নম্বর', 'phone_number'),
            (r'পরিমাণ', 'quantity'),
            (r'name', 'name'),
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
                    key = k; break
            if key and key not in out:
                out[key] = val
        return out

    def _build_missing_order_fields_prompt(self, missing: list) -> str:
        labels = {
            'name': 'Name', 'phone_number': 'Phone Number',
            'address': 'Address', 'product_name': 'Product Name',
            'quantity': 'Quantity'
        }
        lines = "\n".join(f"{labels[k]}:" for k in missing if k in labels)
        return f"অর্ডার সম্পন্ন করতে শুধু বাকি তথ্যগুলো দিন:\n\n{lines}\n\nধন্যবাদ।"

    # ─────────────────────────────────────────────────────────────
    # Product selection helpers
    # ─────────────────────────────────────────────────────────────
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

    def _format_selected_product_response(self, product: Dict, index: int) -> str:
        title = product.get('title', 'N/A')
        price = product.get('price', 'N/A')
        url = product.get('url', '')
        text = f"দারুণ পছন্দ স্যার। আপনি {index} নম্বর প্রোডাক্টটি নির্বাচন করেছেন।\n\n"
        text += f"{index}. {title}\nমূল্য: {price}\n"
        if url:
            text += f"লিংক: {url}\n"
        text += "\nআপনি চাইলে আমি অর্ডার করার ধাপগুলোও বলে দিতে পারি।"
        return text

    def _format_product_listing(self, products: list) -> Tuple[str, List[Dict]]:
        text = "স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
        link_buttons = []
        for i, p in enumerate(products[:3], 1):
            title = p.get('title', 'N/A')
            price = p.get('price', 'N/A')
            url = p.get('url', '')
            text += f"{i}. {title}\nমূল্য: {price}\n\n"
            if url:
                link_buttons.append({
                    'text': f"{i}. View",
                    'url': url,
                    'title': title,
                    'price': price,
                })
        text += "আরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।"
        return text, link_buttons
    def _reply_price_from_context(self, user_id: str) -> Optional[str]:
        selected = self.user_selected_product.get(user_id) or {}
        if selected:
            title = selected.get('title') or 'এই প্রোডাক্টটির'
            price = selected.get('price') or ''
            if price and str(price).strip().upper() != 'N/A':
                return f"জি স্যার, {title} এর দাম {price}।"
            return "স্যার, এই প্রোডাক্টটির দাম এখন দেখাতে পারছি না।"
        products = self.user_product_context.get(user_id) or []
        if not products:
            return None
        if len(products) == 1:
            p = products[0]
            title = p.get('title') or 'এই প্রোডাক্টটির'
            price = p.get('price') or ''
            if price and str(price).strip().upper() != 'N/A':
                return f"জি স্যার, {title} এর দাম {price}।"
        lines = ["স্যার, আপনার দেখা প্রোডাক্টগুলোর দাম:"]
        for i, p in enumerate(products[:5], 1):
            t = str(p.get('title') or f'প্রোডাক্ট {i}').strip()
            pr = str(p.get('price') or 'N/A').strip()
            if not pr or pr.upper() == 'N/A':
                pr = 'দাম পাওয়া যায়নি'
            lines.append(f"{i}. {t} - {pr}")
        lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────
    # Fixed messages
    # ─────────────────────────────────────────────────────────────
    def _build_comparison_redirect_response(self) -> str:
        return ("স্যার, আমাদের সকল প্রোডাক্টই ভালো। "
                "আপনি আমাদের ওয়েবসাইটের রেটিং ও রিভিউ দেখে নিতে পারেন।")

    def _build_comparison_link_buttons(self, merged: Dict) -> list:
        category = merged.get('category', '')
        target = 'https://www.bdstall.com/'
        if category:
            slug = re.sub(r'\s+', '-', category.strip().lower())
            slug = re.sub(r'[^a-z0-9\-]', '', slug).strip('-')
            if slug:
                target = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
        return [{'text': 'View', 'url': target}]

    def _build_order_guide_response(self) -> str:
        return "স্যার এই লিংকে গিয়ে আপনি দেখতে পারেন কিভাবে অর্ডার অথবা বাই করা যায়"

    # ─────────────────────────────────────────────────────────────
    # Template APIs
    # ─────────────────────────────────────────────────────────────
    def _fetch_delivery_intent_response(self) -> Optional[str]:
        try:
            resp = requests.get(
                self.delivery_intent_api_url,
                params={'intent': 'delivery', 'key': self.api_key},
                timeout=10
            )
            if resp.status_code != 200:
                return None
            return self._parse_template_response(resp.json() if resp.text else {})
        except Exception as e:
            logger.warning("delivery template failed: %s", e)
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

    # ─────────────────────────────────────────────────────────────
    # Misc
    # ─────────────────────────────────────────────────────────────
    def _is_blocked_automated_message(self, message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text:
            return False
        blocked = [
            'bdstall.com-এ আপনাকে স্বাগতম',
            'আপনার মেসেজ এর জন্য ধন্যবাদ',
            'খুব শীঘ্রই bdstall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে',
        ]
        return sum(1 for p in blocked if p in text) >= 2

    # ─────────────────────────────────────────────────────────────
    # Cache helpers
    # ─────────────────────────────────────────────────────────────
    def _clear_product_search_cache(self, user_id: str, clear_pending: bool = False) -> None:
        self.user_product_context.pop(user_id, None)
        self.user_selected_product.pop(user_id, None)
        if clear_pending:
            self.user_pending_product_query.pop(user_id, None)
            self.user_order_context.pop(user_id, None)
            self.user_order_draft.pop(user_id, None)

    # ─────────────────────────────────────────────────────────────
    # Human handoff
    # ─────────────────────────────────────────────────────────────
    def _handoff_to_human(
        self,
        user_id: str,
        message: str,
        start_time: datetime,
        intent: str = 'human_handoff',
        response_text: str = "স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।",
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            started = datetime.now()
            payload = {
                'key': self.assign_agent_api_key,
                'user_id': user_id,
                'intent': intent,
            }
            resp = requests.post(self.assign_agent_api_url, json=payload, timeout=5)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                'assign_agent', 'POST', self.assign_agent_api_url,
                payload, resp.status_code, duration_ms,
                'PASS' if resp.status_code == 200 else 'FAIL',
                resp.text[:400] if resp.text else '',
            )
        except Exception as e:
            logger.warning("assign_agent call failed: %s", e)

        intent_content = self._normalize_intent_content_payload(
            self.user_intent_content.get(user_id) or {}
        )
        if error:
            intent_content['error'] = str(error)[:200]

        return self._create_response(
            user_id=user_id,
            message=message,
            response=response_text,
            mode=ChatMode.HUMAN,
            intent=intent,
            products=None,
            intent_content=intent_content,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS,
        )

    # ─────────────────────────────────────────────────────────────
    # _create_response — single exit point
    # Saving is done by the API layer (ai_simple_chat.py)
    # ─────────────────────────────────────────────────────────────
    def _create_response(
        self,
        user_id: str,
        message: str,
        response: str,
        mode: ChatMode,
        intent: str,
        products: Optional[List[Dict]],
        processing_time: float = 0.0,
        search_keywords: str = '',
        intent_content: Optional[Dict[str, Any]] = None,
        link_buttons: Optional[List[Dict]] = None,
        conversation_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        if conversation_status is None:
            conversation_status = AI_ACTIVE_STATUS

        if intent_content is None:
            intent_content = self._normalize_intent_content_payload(
                self.user_intent_content.get(user_id) or {}
            )
        else:
            intent_content = self._normalize_intent_content_payload(intent_content)

        # Update local state only — no mode/status stored (Rule 13)
        self.user_intent_content[user_id] = intent_content
        self.user_last_intent[user_id] = intent
        self._save_state()

        result: Dict[str, Any] = {
            'response': response,
            'mode': mode.value,
            'intent': intent,
            'intent_content': intent_content,
            'conversation_status': conversation_status,
            'products': products or [],
            'processing_time': round(processing_time, 3),
        }
        if search_keywords:
            result['search_keywords'] = search_keywords
        if link_buttons:
            result['link_buttons'] = link_buttons
        return result
