"""
Simple Chatbot Flow — refactored with separated intent handlers.
=================================================================
Rules enforced:
- Rule 1:  NO HARDCODING — all data from APIs/runtime
- Rule 2:  API-only — no static fallback data
- Rule 3:  intent_content returned on every response; saving done by API layer
- Rule 4:  category mandatory for product/price/compare/order intents
- Rule 5:  category validated via CategoryValidator (cat_list API)
- Rule 6:  category switch → FULL reset
- Rule 7:  post-merge category guard — empty category → ask user
- Rule 8:  separated handlers per intent
- Rule 9:  comparison/buy intents return fixed messages
- Rule 10: short message + previous context = follow-up
- Rule 11: human handoff only on explicit request or complaint
- Rule 12: intent_content schema = {title, cat, brand, price, compare, buy}
- Rule 13: mode NEVER stored in memory — responder API is sole source of truth
- Rule 14: intent_content NEVER stored in local memory — always read from DB via API
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
    'buy', 'exit', 'technical_advice', 'hate_speech', 'unknown'
}

PRODUCT_RELATED_INTENTS = {'product_search', 'price_query', 'comparison', 'ordering'}

CONTEXT_TTL_SECONDS = 1800

CATEGORY_PROMPT = (
    "Apni kon category khujchen sir? "
    "(যেমন: mobile, laptop, AC, fridge ইত্যাদি)"
)


class SimpleChatbot:



    def __init__(self):
        self.project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        self.state_file = os.path.join(self.project_root, 'data', 'chatbot_state.json')
        self._state_lock = threading.Lock()

        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key and Groq:
            self.groq_client = Groq(api_key=groq_api_key)
            self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
            self.groq_answer_model = os.getenv('GROQ_ANSWER_MODEL', 'llama-3.3-70b-versatile')
        else:
            self.groq_client = None
            self.groq_model = None
            self.groq_answer_model = None
            logger.warning("⚠️ Groq API not available")

        # Per-user product/order state only — NO mode, NO intent_content (Rules 13, 14)
        self.user_product_context: Dict[str, list] = {}
        self.user_selected_product: Dict[str, Dict[str, Any]] = {}
        self.user_order_context: Dict[str, bool] = {}
        self.user_order_draft: Dict[str, Dict[str, str]] = {}
        self.user_pending_product_query: Dict[str, Dict[str, Any]] = {}
        self.user_last_intent: Dict[str, str] = {}

        # Caches — no responder cache (must always be live), no intent_content cache
        self._search_cache: Dict[str, Tuple[float, Dict]] = {}
        self._search_cache_ttl = 300
        self._search_cache_max = 200
        self._history_cache: Dict[str, Tuple[float, str]] = {}
        self._history_cache_ttl = 60

        # BDStall config
        self.api_url = "https://www.bdstall.com/api/chatbot/ai_search/"
        self.api_key = os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.delivery_intent_api_url = "https://www.bdstall.com/api/chatbot/ai_template/"
        self.assign_agent_api_url = os.getenv(
            'ASSIGN_AGENT_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_assign_agent/'
        )
        self.assign_agent_api_key = os.getenv('ASSIGN_AGENT_API_KEY', self.api_key)
        self.assign_bot_api_url = os.getenv(
            'ASSIGN_BOT_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_assign_bot/'
        )
        self.responder_api_url = os.getenv(
            'RESPONDER_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_responder/'
        )
        self.responder_api_key = os.getenv('RESPONDER_API_KEY', self.api_key)
        self.chatbot_history_api_url = os.getenv(
            'CHATBOT_HISTORY_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_history/'
        )
        try:
            self.chatbot_history_limit = int(os.getenv('CHATBOT_HISTORY_LIMIT', '5'))
        except Exception:
            self.chatbot_history_limit = 5

        self.category_validator = CategoryValidator(
            cat_list_url=os.getenv(
                'CATLIST_API_URL', 'https://www.bdstall.com/api/chatbot/cat_list/'
            ),
            api_key=self.api_key,
        )

        self._load_state()
        self.database = self._load_database()

        logger.info("✅ SimpleChatbot initialized")
        logger.info("📚 Loaded %d FAQ rows", len(self.database))
        logger.info("📂 Loaded %d categories", len(self.category_validator.names_english()))

    # ─────────────────────────────────────────────────────────────
    # State persistence — mode and intent_content excluded (Rules 13, 14)
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

    # ─────────────────────────────────────────────────────────────
    # Intent content — always read from DB (Rule 14)
    # ─────────────────────────────────────────────────────────────
    def _fetch_intent_content_from_db(self, user_id: str) -> Dict:
        """
        Pull the last saved intent_content from the chat history API.
        This is the sole source of truth for previous category/brand/price context.
        """
        try:
            urls = self._build_chat_history_urls(user_id, 10)
            for url in urls:
                try:
                    resp = requests.get(url, timeout=2)
                    if not (200 <= resp.status_code < 300):
                        continue
                    data = resp.json() if resp.text else {}
                    candidates = []
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
                        sender = str(item.get('sender_type') or '').strip()
                        if sender != '2':
                            continue
                        ic = item.get('intent_content')
                        if isinstance(ic, str):
                            try:
                                ic = json.loads(ic)
                            except Exception:
                                continue
                        if isinstance(ic, dict) and (ic.get('cat') or ic.get('brand') or ic.get('title')):
                            logger.info("[INTENT_DB] Restored for %s: cat=%s brand=%s title=%s",
                                        user_id, ic.get('cat'), ic.get('brand'), ic.get('title'))
                            return ic
                except Exception:
                    continue
        except Exception as e:
            logger.warning("_fetch_intent_content_from_db failed: %s", e)
        return {}

    def _load_previous_intent(self, user_id: str) -> Dict:
        """Always fetch from DB — never from local memory (Rule 14)."""
        try:
            prev = dict(self._fetch_intent_content_from_db(user_id) or {})
        except Exception as e:
            logger.warning("_load_previous_intent failed: %s", e)
            return {}

        updated_at = prev.get('updated_at')
        if updated_at:
            try:
                age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
                if age > CONTEXT_TTL_SECONDS:
                    logger.info("Context expired for %s (age=%.0fs)", user_id, age)
                    return {}
            except Exception:
                pass

        if prev.get('cat') and not prev.get('category'):
            prev['category'] = prev['cat']
        return prev

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

            # ALL intents — classified by Groq
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

    # ═════════════════════════════════════════════════════════════
    # MAIN flow — all intents classified by Groq
    # ═════════════════════════════════════════════════════════════
    def _handle_main_flow(self, user_id: str, message: str,
                          start_time: datetime) -> Dict[str, Any]:
        conversation_context = self._get_history_cached(user_id)
        previous_intent = self._load_previous_intent(user_id)
        groq_result = self._step1_groq_extract(message, conversation_context, previous_intent)
        intent = groq_result['intent']
        entities = groq_result['entities']

        # Validate category — only if Groq explicitly returned one (Rule 5)
        resolved_cat = None
        if entities.get('category'):
            resolved_cat = self.category_validator.resolve(entities['category'])
        entities['category'] = resolved_cat['category_name'] if resolved_cat else ''

        logger.info("✅ Intent=%s entities=%s followup=%s resolved=%s",
                    intent, entities, groq_result['is_followup'],
                    resolved_cat['category_name'] if resolved_cat else None)

        merged = self._merge_intent_context(user_id, groq_result, previous_intent, intent)

        if intent == 'hate_speech':
            return self._handoff_to_human(
                user_id, message, start_time,
                intent='hate_speech',
                response_text="স্যার, অনুগ্রহ করে ভদ্র ভাষায় কথা বলুন। আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।"
            )
        if intent == 'human_request':
            return self._handoff_to_human(
                user_id, message, start_time,
                intent='explicit_human_request',
                response_text="স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।"
            )
        if intent == 'complaint':
            return self._handoff_to_human(
                user_id, message, start_time,
                intent='complaint_handoff',
                response_text="স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি এখনই আপনার সাথে যোগাযোগ করবেন।"
            )
        if intent == 'greeting':
            return self._create_response(
                user_id=user_id, message=message,
                response="আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?",
                mode=ChatMode.AI, intent='greeting', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )
        if intent == 'goodbye':
            prev = self._normalize_intent_content_payload(self._load_previous_intent(user_id))
            prev['exit'] = 1
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
        if intent == 'exit':
            return self.handle_exit(user_id, message, start_time)
        if intent == 'buy':
            return self.handle_buy(user_id, message, start_time)
        if intent == 'technical_advice':
            return self.handle_technical_advice(user_id, message, merged, start_time)
        if intent == 'comparison':
            return self.handle_comparison(user_id, message, merged, start_time)
        if intent == 'delivery':
            return self.handle_delivery(user_id, message, merged, start_time)
        if intent == 'faq':
            return self.handle_faq(user_id, message, merged, start_time)
        if intent == 'price_query':
            return self.handle_price_query(user_id, message, merged, start_time)
        if intent == 'product_search':
            return self.handle_product_search(user_id, message, merged, start_time)

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
        price_min = merged.get('price_min')

        keywords = self._build_search_keywords_from_merged(merged)
        result = self._cached_search(keywords, price_max, price_min)

        if result['products_found'] == 0:
            broader = self._build_broader_search_keywords(merged)
            if broader and broader != keywords:
                retry = self._cached_search(broader, price_max, price_min)
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

        # Only use context prices if they match the current category
        # e.g. "ram price koto" after laptop search → search RAM, not show laptop prices
        ctx_reply = None
        prev_products = self.user_product_context.get(user_id, [])
        if prev_products:
            first_title = (prev_products[0].get('title') or '').lower()
            current_cat = merged.get('category', '').lower()
            if current_cat and current_cat in first_title:
                ctx_reply = self._reply_price_from_context(user_id)

        if ctx_reply:
            ctx_text, ctx_buttons = ctx_reply
            self._reset_clarification_counter(user_id)
            return self._create_response(
                user_id=user_id, message=message, response=ctx_text,
                mode=ChatMode.AI, intent='price_from_context', products=None,
                link_buttons=ctx_buttons if ctx_buttons else None,
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
                self._load_previous_intent(user_id)
            ),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_exit(self, user_id: str, message: str,
                    start_time: datetime) -> Dict[str, Any]:
        self._reset_clarification_counter(user_id)
        prev = self._normalize_intent_content_payload(
            self._load_previous_intent(user_id)
        )
        prev['exit'] = 1
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

    def handle_technical_advice(self, user_id: str, message: str, merged: Dict,
                                start_time: datetime) -> Dict[str, Any]:
        """
        Purpose: Answer technical suitability/compatibility questions using Groq 70b.
        Trigger: intent=technical_advice
        Boundary: only answers if question relates to a known category in cat_list.
        Disclaimer always appended. Follow-up invitation always appended.
        """
        DISCLAIMER = "\n\nতবে স্যার, কেনার আগে অবশ্যই আরেকবার যাচাই করে নিন।"
        FOLLOWUP = "\n\nকোন প্রোডাক্ট দেখতে চান বললে আমি এখনই দেখিয়ে দিতে পারি।"

        # Only answer if question relates to a known category
        # Check full message first, then individual words as fallback
        resolved = self.category_validator.resolve_from_message(message)
        if not resolved:
            for word in message.split():
                resolved = self.category_validator.resolve(word.strip())
                if resolved:
                    break
        if not resolved:
            return self._create_response(
                user_id=user_id, message=message,
                response="স্যার, এই বিষয়ে আমি সাহায্য করতে পারব না। আপনি কি কোনো প্রোডাক্ট খুঁজছেন?",
                mode=ChatMode.AI, intent='technical_advice_out_of_scope', products=None,
                intent_content=self._intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        answer = None
        if self.groq_client and self.groq_answer_model:
            try:
                system_prompt = """You are a helpful technical assistant for BDStall.com, a Bangladeshi e-commerce platform.
Answer the user's technical question about product suitability or compatibility in 2-3 sentences maximum.
The user may write in English, Bangla, or Banglish. Always reply in the SAME language the user used.
If the question seems incomplete (e.g. "laptop valo hobe naki" = "is laptop good or not?"), 
interpret it as asking whether that product is generally good and answer accordingly.
Be direct and helpful. Do NOT say you are unsure unless truly necessary.
Do NOT add any disclaimer or suggestion to visit other websites.
Do NOT recommend specific models or prices."""

                response = self.groq_client.chat.completions.create(
                    model=self.groq_answer_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.2,
                    max_tokens=200,
                )
                answer = response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning("technical_advice Groq call failed: %s", e)

        if not answer:
            answer = "স্যার, এই বিষয়ে আমি নিশ্চিত নই।"

        return self._create_response(
            user_id=user_id, message=message,
            response=answer + DISCLAIMER + FOLLOWUP,
            mode=ChatMode.AI, intent='technical_advice', products=None,
            intent_content=self._intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_fallback(self, user_id: str, message: str, merged: Dict,
                        start_time: datetime) -> Dict[str, Any]:
        # Category presence alone does NOT mean product_search
        # Only go to product_search if last intent was search-related
        last_intent = self.user_last_intent.get(user_id, '')
        search_intents = {'product_search', 'price_query', 'no_products_found', 'need_category'}

        if merged.get('category') and last_intent in search_intents:
            return self.handle_product_search(user_id, message, merged, start_time)

        # Try to resolve single-word category reply
        # (e.g. user replied "laptop" to the category question)
        if not merged.get('category'):
            resolved = self.category_validator.resolve(message.strip())
            if resolved:
                merged['category'] = resolved['category_name']
                self._reset_clarification_counter(user_id)
                return self.handle_product_search(user_id, message, merged, start_time)

        # If category is known but last intent was not search-related,
        # treat as technical question about that category
        if merged.get('category') or self.category_validator.resolve_from_message(message):
            return self.handle_technical_advice(user_id, message, merged, start_time)

        return self._ask_for_category(user_id, message, merged, start_time)

    # ─────────────────────────────────────────────────────────────
    # Ask for category / clarification counter (no-op)
    # ─────────────────────────────────────────────────────────────
    def _ask_for_category(self, user_id: str, message: str, merged: Dict,
                          start_time: datetime) -> Dict[str, Any]:
        # Preserve any brand/title already extracted — don't wipe them
        # e.g. "hp 840 g3" → ask category but keep brand=hp, title=840 g3
        intent_content = self._intent_to_normalized(merged, message)
        return self._create_response(
            user_id=user_id, message=message, response=CATEGORY_PROMPT,
            mode=ChatMode.AI, intent='need_category', products=None,
            intent_content=intent_content,
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
product_search | price_query | comparison | buy | exit | delivery | greeting | goodbye | thanks | complaint | faq | human_request | technical_advice | hate_speech | unknown

INTENT DEFINITIONS:
- product_search    : user wants to see, find, or browse products. User is ready to buy or look at options.
- price_query       : user is asking about price or cost of a product/category
- comparison        : user wants to compare two specific products side by side
- buy               : user wants to know HOW to buy or place an order (process question). Includes "kivabe kinbo", "kivabe order korbo", "kinte chai kivabe"
- exit              : user is leaving, says later / not now / will come back
- delivery          : user asks about delivery time, charge, or process
- greeting          : hello / hi / salam with no product intent
- goodbye           : farewell with no product intent
- thanks            : thank you messages
- complaint         : refund, scam, broken product, bad experience
- faq               : general questions about the site or policies
- human_request     : user wants to speak to a human agent
- technical_advice  : user asks WHICH product is better for a use case, or whether a product is suitable/compatible. Key signal: "valo hobe", "valo ki", "suitable", "compatible", "konta nibo", "recommend koro", "upgrade kora jay", "fit hobe ki"
- hate_speech       : abusive language, insults, threats, racial slurs, sexual harassment, or any offensive content
- unknown           : truly cannot determine

TECHNICAL_ADVICE DETECTION RULE — read carefully:
Ask yourself two questions about the message:
Q1: "Is the user asking what a product CAN DO, whether it is GOOD for something,
     whether it is COMPATIBLE, or whether it can be UPGRADED/CHANGED?" → technical_advice
Q2: "Is the user asking to SEE, FIND, or BUY a product?" → product_search

IMPORTANT: Even if a category word (laptop, RAM, SSD) is present in the message,
DO NOT classify as product_search if the user is asking about capability, upgrade,
compatibility, or quality. Category presence alone does NOT mean product_search.

Examples of technical_advice (capability/suitability questions):
- "laptop er ram ki upgrade kora jay?" → asking CAN IT be upgraded → technical_advice
- "laptop valo hobe naki desktop?" → asking WHICH IS BETTER → technical_advice
- "4GB RAM ki enough gaming er jonno?" → asking IS IT SUFFICIENT → technical_advice
- "ei graphics card ki VR support kore?" → asking CAN IT do something → technical_advice
- "ssd lagano jabe ki?" → asking CAN IT be done → technical_advice
- "laptop valo ki?" → asking IS IT GOOD → technical_advice

Examples of product_search (browsing/buying intent):
- "laptop dekhao" → wants to SEE products → product_search
- "gaming laptop ache?" → asking if products exist → product_search
- "HP laptop khujchi" → wants to FIND a product → product_search

The difference: technical_advice = question about product CAPABILITY or QUALITY.
               product_search  = request to SEE or FIND products.

CATEGORY EXTRACTION — most important rule:
A "category" is a generic product type. Known examples (not exhaustive): {sample_str}
RULES:
- If the message contains a recognisable product type word → ALWAYS set category to that word.
- A single word that is a product type (e.g. "laptop", "mobile", "AC", "fridge") → category = that word, intent = product_search.
- "laptop price" / "laptop dam koto" / "laptop er dam" → category="laptop", intent=price_query.
- "hp laptop" → brand="hp", category="laptop".
- "hp 840 g3" → brand="hp", title="840 g3", category="Laptop" (HP 840 G3 is a known laptop model — infer category from model knowledge).
- If the model/title is a well-known product (e.g. iPhone=mobile, Galaxy=mobile, HP 840=laptop, RTX 4060=graphics card), infer the category even if not explicitly stated.
- Only leave category="" if truly cannot determine from model name or context.
- "X ache", "X ki ache", "X paoa jabe" → category=X, intent=product_search ("ache" means "available/do you have").

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
- "under 20k", "50k er vitor", "hp er ta" → is_followup=true (price/brand only, no category).

MISSING ARRAY:
- Add "category" to missing[] when intent is product_search, price_query, or comparison AND category="".
- All other intents: missing=[].

BUDGET PARSING: "50k"=50000, "30 hazar"=30000, "under 20k"→price_max=20000,
"50k er vitor"→price_max=50000, "50 hazar er moddhe"→price_max=50000. null if absent.
"X er vitor ache", "X budget ache", "X te ache" → price_max=X, intent=product_search, is_followup=true.

BANGLISH / BANGLA QUICK REFERENCE:
- "hi", "hello", "hey", "salam", "assalamu alaikum", "হাই", "হ্যালো", "সালাম"      → greeting
- "bye", "goodbye", "allah hafez", "আল্লাহ হাফেজ", "বিদায়"                         → goodbye
- "thanks", "thank you", "ধন্যবাদ", "অনেক ধন্যবাদ"                                 → thanks
- "pore kinbo", "pore janabo", "ekhon na", "পরে জানাবো", "এখন লাগবে না"              → exit
- "order korbo kivabe", "kivabe order korbo", "how to buy", "how can i buy",
  "how can i buy it", "how do i buy", "how to order", "order process",
  "kivabe kinbo", "kinte chai kivabe", "kinbo kivabe"                              → buy (no category needed)
- "konti valo", "konta valo", "konta bhalo", "which is better", "কোনটা ভালো",
  "laptop valo naki desktop", "pc valo naki laptop", "konta nibo", "recommend koro",
  "konta kinbo", "ei product ki valo"                                              → technical_advice
- "delivery koto din", "delivery charge", "koto din lagbe", "কত দিন লাগবে"       → delivery
- "refund chai", "baje", "faltu", "kharap"                                         → complaint
- "human chai", "agent er sathe kotha"                                             → human_request
- "X ache", "X ki ache" where X is a product type                                 → product_search
- "50k er vitor ache", "20k te ache", "30 hazar er moddhe ache"                   → product_search, price_max=X, is_followup=true
- "will this work for gaming", "gaming er jonno valo ki", "ei laptop ki editing er jonno valo",
  "is this RAM enough", "4GB RAM ki sufficient", "compatible hobe ki",
  "laptop valo hobe naki desktop gaming er jonno",
  "laptop er ram ki upgrade kora jay", "ram upgrade possible ki",
  "ei processor ki change kora jay", "ssd lagano jabe ki"                          → technical_advice

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
        """Emergency fallback — only when Groq is unavailable. Returns unknown for everything."""
        budget = self._extract_budget_range(message)
        return {
            'intent': 'unknown',
            'entities': {
                'category': '', 'brand': '', 'title': '',
                'price_max': budget.get('max_price'),
                'price_min': budget.get('min_price'),
            },
            'missing': [],
            'is_followup': False,
            'confidence': 0.0,
        }

    # ─────────────────────────────────────────────────────────────
    # Context merge (Rules 6, 7, 10)
    # ─────────────────────────────────────────────────────────────
    def _merge_intent_context(self, user_id: str, groq_result: Dict,
                              previous: Dict, intent: str = '') -> Dict:
        new_entities = groq_result['entities']
        new_category = new_entities.get('category', '')
        is_followup = groq_result.get('is_followup', False)

        # Always use DB as source of truth for previous category (Rule 14)
        # previous dict already comes from _load_previous_intent which reads from DB
        prev_category = previous.get('category', '') or previous.get('cat', '')
        prev_brand = previous.get('brand', '')
        prev_title = previous.get('title', '')
        prev_price_max = previous.get('price_max')
        prev_price_min = previous.get('price_min')

        # Rule 6: category switch → FULL reset of all entities
        # Compare new category against DB-sourced previous category
        if new_category and prev_category and new_category.lower() != prev_category.lower():
            logger.info("🔄 Category switch %s → %s. Full reset.", prev_category, new_category)
            self._clear_product_search_cache(user_id, clear_pending=True)
            return {
                'category': new_category,
                'brand': '',
                'title': '',
                'price_max': new_entities.get('price_max'),
                'price_min': new_entities.get('price_min'),
                'updated_at': datetime.now().isoformat(),
            }

        # Treat as follow-up if message has price/brand/title but no category
        has_only_refinement = (
            not new_category
            and (
                new_entities.get('price_max') is not None
                or new_entities.get('price_min') is not None
                or new_entities.get('brand')
                or new_entities.get('title')
            )
        )
        if has_only_refinement:
            is_followup = True

        # Determine effective category
        if new_category:
            effective_category = new_category
        elif is_followup:
            effective_category = prev_category
        else:
            effective_category = ''

        if prev_category and not effective_category:
            self._clear_product_search_cache(user_id, clear_pending=False)

        return {
            'category': effective_category,
            'brand': new_entities.get('brand') or prev_brand,
            'title': new_entities.get('title') or prev_title,
            'price_max': (new_entities.get('price_max')
                          if new_entities.get('price_max') is not None
                          else prev_price_max),
            'price_min': (new_entities.get('price_min')
                          if new_entities.get('price_min') is not None
                          else prev_price_min),
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
            parts.append(merged['brand'].lower())
        if merged.get('title'):
            parts.append(merged['title'].lower())
        elif merged.get('category'):
            parts.append(merged['category'].lower())
        return ' '.join(parts).strip()

    def _build_broader_search_keywords(self, merged: Dict) -> Optional[str]:
        parts = []
        if merged.get('brand'):
            parts.append(merged['brand'].lower())
        if merged.get('category'):
            parts.append(merged['category'].lower())
        elif merged.get('title'):
            parts.append(merged['title'].lower())
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
            r'(?:under|within|modde|modhhe|budget|er modde|er vitor|vitor|এর মধ্যে|মধ্যে|below|less than)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?',
            text)
        if um:
            mx = _to_taka(um.group(1), um.group(2) or '')
            return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

        gm = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)\b', text)
        if gm:
            mx = _to_taka(gm.group(1), gm.group(2) or '')
            return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

        return {'min_price': None, 'max_price': None, 'price_text': ''}

    def _cached_search(self, keywords: str, max_price: Optional[int] = None,
                       min_price: Optional[int] = None) -> Dict[str, Any]:
        cache_key = f"{keywords}|{min_price or ''}|{max_price or ''}"
        now = time.time()
        cached = self._search_cache.get(cache_key)
        if cached and (now - cached[0]) < self._search_cache_ttl:
            return cached[1]
        result = self._do_search(keywords, max_price, min_price)
        self._search_cache[cache_key] = (now, result)
        if len(self._search_cache) > self._search_cache_max:
            oldest = min(self._search_cache.keys(), key=lambda k: self._search_cache[k][0])
            self._search_cache.pop(oldest, None)
        return result

    def _do_search(self, keywords: str, explicit_max_price: Optional[int] = None,
                   explicit_min_price: Optional[int] = None) -> Dict[str, Any]:
        try:
            params = {
                'term': keywords.strip(),
                'key': self.api_key,
                'minPrice': explicit_min_price or '',
                'maxPrice': explicit_max_price or '',
            }
            started = datetime.now()
            response = requests.get(self.api_url, params=params, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call('ai_search', 'GET', self.api_url, params,
                          response.status_code, duration_ms,
                          "PASS" if response.status_code == 200 else "FAIL",
                          response.text[:400])
            if response.status_code != 200:
                return {'products_found': 0, 'products': []}

            data = response.json()
            if not data.get('getListingItem') or len(data['getListingItem']) < 2:
                return {'products_found': 0, 'products': []}

            total_count = data['getListingItem'][0]
            products_array = data['getListingItem'][1] or []
            if not products_array:
                return {'products_found': 0, 'products': []}

            # API handles price filtering — just take top 5
            top = products_array[:5]
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

    def _reply_price_from_context(self, user_id: str) -> Optional[Tuple[str, List[Dict]]]:
        """Returns (text, link_buttons) or None."""
        selected = self.user_selected_product.get(user_id) or {}
        if selected:
            title = selected.get('title') or 'এই প্রোডাক্টটির'
            price = selected.get('price') or ''
            url = selected.get('url', '')
            if price and str(price).strip().upper() != 'N/A':
                text = f"জি স্যার, {title} এর দাম {price}।"
                buttons = [{'text': 'View', 'url': url, 'title': title, 'price': price}] if url else []
                return text, buttons
            return "স্যার, এই প্রোডাক্টটির দাম এখন দেখাতে পারছি না।", []

        products = self.user_product_context.get(user_id) or []
        if not products:
            return None

        if len(products) == 1:
            p = products[0]
            title = p.get('title') or 'এই প্রোডাক্টটির'
            price = p.get('price') or ''
            url = p.get('url', '')
            if price and str(price).strip().upper() != 'N/A':
                text = f"জি স্যার, {title} এর দাম {price}।"
                buttons = [{'text': 'View', 'url': url, 'title': title, 'price': price}] if url else []
                return text, buttons

        lines = ["স্যার, আপনার দেখা প্রোডাক্টগুলোর দাম:"]
        buttons = []
        for i, p in enumerate(products[:5], 1):
            t = str(p.get('title') or f'প্রোডাক্ট {i}').strip()
            pr = str(p.get('price') or 'N/A').strip()
            url = p.get('url', '')
            if not pr or pr.upper() == 'N/A':
                pr = 'দাম পাওয়া যায়নি'
            lines.append(f"{i}. {t} - {pr}")
            if url:
                buttons.append({'text': f"{i}. View", 'url': url, 'title': t, 'price': pr})
        lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।")
        return "\n".join(lines), buttons

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
            self._load_previous_intent(user_id)
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
    # intent_content is returned in result dict for the API layer to save
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
                self._load_previous_intent(user_id)
            )
        else:
            intent_content = self._normalize_intent_content_payload(intent_content)

        # Only last intent stored locally — no mode, no intent_content (Rules 13, 14)
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