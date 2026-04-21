"""
Simple Chatbot Flow - Following Your Roadmap
============================================

Step 1: Message → Groq API (Intent Detection)
Step 2: Intent → Search API (e.g., "10k laptop")
Step 3: Search Results → Database Format
Step 4: Database Message → AI (Final Response)
Step 5: Track Mode: AI or HUMAN
Step 6: Return JSON with mode

"""
import os
import sys
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
import re
from enum import Enum
import requests
from urllib.parse import quote

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import required components
try:
    from groq import Groq
except ImportError:
    Groq = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _log_api_call(
    api_name: str,
    method: str,
    url: str,
    request_payload,
    status_code: int,
    duration_ms: int,
    status: str,
    response_preview: str = ""
) -> None:
    """Write outbound API call details to daily API log file."""
    try:
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"api_calls_{datetime.now().strftime('%Y-%m-%d')}.log")

        entry = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "api_name": api_name,
            "method": method,
            "url": url,
            "request": request_payload,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "result": status,
            "response_preview": response_preview[:400]
        }

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(
            "[API_LOG] %s %s %s status=%s result=%s duration_ms=%s",
            api_name,
            method,
            url,
            status_code,
            status,
            duration_ms
        )
    except Exception as e:
        logger.warning("API log write failed: %s", e)


class ChatMode(Enum):
    """Chat mode: AI or HUMAN"""
    AI = "ai"
    HUMAN = "human"


AI_ACTIVE_STATUS = "AI Active"
HUMAN_SUPPORT_REQUIRED_STATUS = "Human Support Required"


class SimpleChatbot:
    """
    Simple Chatbot following your exact roadmap
    """
    
    def __init__(self):
        """Initialize the simple chatbot"""
        self.project_root = os.path.join(os.path.dirname(__file__), '..', '..')
        self.state_file = os.path.join(self.project_root, 'data', 'chatbot_state.json')

        # Load Groq API
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key and Groq:
            self.groq_client = Groq(api_key=groq_api_key)
            self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
        else:
            self.groq_client = None
            logger.warning("⚠️ Groq API not available")
        
        # Track user modes (AI or HUMAN)
        self.user_modes: Dict[str, ChatMode] = {}
        self.user_conversation_status: Dict[str, str] = {}

        # Keep latest shown product list per user for follow-up selection (1-5)
        self.user_product_context: Dict[str, list] = {}

        # Track the latest selected product so short confirmations can trigger order intent API.
        self.user_selected_product: Dict[str, Dict[str, Any]] = {}

        # Track order form context and partially submitted order fields per user.
        self.user_order_context: Dict[str, bool] = {}
        self.user_order_draft: Dict[str, Dict[str, str]] = {}
        # Track pending product-search constraints when user gives only brand + budget.
        self.user_pending_product_query: Dict[str, Dict[str, Any]] = {}
        # Track last resolved intent so cache can be cleared on intent switches.
        self.user_last_intent: Dict[str, str] = {}
        # Track structured search intent context per user.
        self.user_intent_content: Dict[str, Dict[str, Any]] = {}
        
        # BDStall API Configuration
        self.api_url = "https://www.bdstall.com/api/item/ai_search/"
        self.api_key = "mkh677ddd2sxxkkdjff"
        self.delivery_intent_api_url = "https://www.bdstall.com/api/item/ai_template/"
        self.order_intent_api_url = "https://www.bdstall.com/api/item/ai_template/"
        self.assign_agent_api_url = os.getenv(
            'ASSIGN_AGENT_API_URL',
            'https://www.bdstall.com/api/item/chatbot_assign_agent/'
        )
        self.assign_agent_api_key = os.getenv('ASSIGN_AGENT_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.responder_api_url = os.getenv(
            'RESPONDER_API_URL',
            'https://www.bdstall.com/api/item/chatbot_responder/'
        )
        self.responder_api_key = os.getenv('RESPONDER_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.chatbot_history_api_url = os.getenv(
            'CHATBOT_HISTORY_API_URL',
            'https://www.bdstall.com/api/item/chatbot_history/'
        )
        try:
            self.chatbot_history_limit = int(os.getenv('CHATBOT_HISTORY_LIMIT', '5'))
        except Exception:
            self.chatbot_history_limit = 5

        self._load_state()
        
        # Load database.csv for FAQ responses
        self.database = self._load_database()
        # Load configured category/item names that should always trigger search intent.
        self.search_intent_items = self._load_search_intent_items()
        self.search_intent_items_mtime: Optional[float] = self._get_search_items_mtime()
        
        logger.info("✅ Simple Chatbot Initialized")
        logger.info(f"🌐 BDStall API: {self.api_url}")
        logger.info(f"📚 Database: {len(self.database)} FAQ responses loaded")
        logger.info("🧭 Search-intent items loaded: %s", len(self.search_intent_items))

    def _load_state(self) -> None:
        """Restore lightweight conversation state from disk."""
        try:
            if not os.path.exists(self.state_file):
                return

            with open(self.state_file, 'r', encoding='utf-8') as file_obj:
                state = json.load(file_obj)

            self.user_modes = {
                user_id: ChatMode(mode)
                for user_id, mode in (state.get('user_modes') or {}).items()
                if mode in {ChatMode.AI.value, ChatMode.HUMAN.value}
            }
            self.user_conversation_status = dict(state.get('user_conversation_status') or {})
            self.user_product_context = dict(state.get('user_product_context') or {})
            self.user_selected_product = dict(state.get('user_selected_product') or {})
            self.user_order_context = {
                user_id: bool(active)
                for user_id, active in (state.get('user_order_context') or {}).items()
            }
            self.user_order_draft = dict(state.get('user_order_draft') or {})
            self.user_pending_product_query = dict(state.get('user_pending_product_query') or {})
            self.user_last_intent = dict(state.get('user_last_intent') or {})
            self.user_intent_content = dict(state.get('user_intent_content') or {})
            logger.info("✅ Restored chatbot state for %s users", len(self.user_modes))
        except Exception as e:
            logger.warning("⚠️ Failed to restore chatbot state: %s", e)

    def _save_state(self) -> None:
        """Persist lightweight conversation state so Messenger survives restarts."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            state = {
                'user_modes': {user_id: mode.value for user_id, mode in self.user_modes.items()},
                'user_conversation_status': self.user_conversation_status,
                'user_product_context': self.user_product_context,
                'user_selected_product': self.user_selected_product,
                'user_order_context': self.user_order_context,
                'user_order_draft': self.user_order_draft,
                'user_pending_product_query': self.user_pending_product_query,
                'user_last_intent': self.user_last_intent,
                'user_intent_content': self.user_intent_content,
            }
            with open(self.state_file, 'w', encoding='utf-8') as file_obj:
                json.dump(state, file_obj, ensure_ascii=False)
        except Exception as e:
            logger.warning("⚠️ Failed to persist chatbot state: %s", e)

    def _clear_product_search_cache(self, user_id: str, clear_pending: bool = True) -> None:
        """Clear product-selection/search cache for a user when intent changes."""
        self.user_product_context.pop(user_id, None)
        self.user_selected_product.pop(user_id, None)
        if clear_pending:
            self.user_pending_product_query.pop(user_id, None)
    
    def _check_responder_type(self, user_id: str) -> Optional[str]:
        """
        Check user's responder status from BDStall responder API.
        Returns: 'bot' if bot should respond, 'agent' if agent should respond, None on error
        """
        try:
            import time
            start_time = time.time()
            url = f"{self.responder_api_url}?key={self.responder_api_key}&user_id={user_id}"
            
            response = requests.get(url, timeout=3)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    responder_label = data['data'].get('responder_label', 'bot')
                    logger.info(f"Responder check for {user_id}: {responder_label}")
                    _log_api_call(
                        'responder_type_check',
                        'GET',
                        url,
                        {'user_id': user_id},
                        response.status_code,
                        duration_ms,
                        'PASS',
                        json.dumps(data.get('data', {}), ensure_ascii=False)[:200]
                    )
                    return responder_label
            
            logger.warning(f"⚠️ Responder check failed: status={response.status_code}")
            _log_api_call(
                'responder_type_check',
                'GET',
                url,
                {'user_id': user_id},
                response.status_code,
                duration_ms,
                'FAILED',
                response.text[:200]
            )
            return None
        except Exception as e:
            logger.warning(f"⚠️ Responder check error: {e}")
            return None
    
    def _load_database(self) -> list:
        """Load database.csv for FAQ responses"""
        try:
            import csv
            database_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'database.csv')
            
            if not os.path.exists(database_path):
                logger.warning(f"⚠️ Database file not found: {database_path}")
                return []
            
            database = []
            with open(database_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle column name with or without space
                    question = row.get('প্রশ্ন') or row.get('প্রশ্ন ') or row.get('Question')  
                    answer = row.get('উত্তর') or row.get('Answer')
                    
                    if question and answer:
                        database.append({
                            'question': question.strip(),
                            'answer': answer.strip()
                        })
            
            logger.info(f"✅ Loaded {len(database)} FAQ responses")
            return database
        except Exception as e:
            logger.error(f"❌ Failed to load database: {e}")
            return []

    def _load_search_intent_items(self) -> list:
        """Load configured catalog/category names that must map to search intent."""
        items_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'search_intent_items.json')
        try:
            if not os.path.exists(items_path):
                logger.warning("⚠️ Search intent item file not found: %s", items_path)
                return []

            with open(items_path, 'r', encoding='utf-8') as file_obj:
                payload = json.load(file_obj)

            if not isinstance(payload, list):
                logger.warning("⚠️ Search intent item file format invalid")
                return []

            normalized_items = []
            for item in payload:
                text = str(item or '').strip().lower()
                if text:
                    normalized_items.append(text)

            # Keep insertion order while removing duplicates.
            return list(dict.fromkeys(normalized_items))
        except Exception as e:
            logger.warning("⚠️ Failed to load search intent items: %s", e)
            return []

    def _get_search_items_mtime(self) -> Optional[float]:
        """Return mtime of search intent item JSON, if available."""
        items_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'search_intent_items.json')
        try:
            if not os.path.exists(items_path):
                return None
            return os.path.getmtime(items_path)
        except Exception:
            return None

    def _refresh_search_intent_items_if_changed(self) -> None:
        """Reload search intent item list when JSON file changes on disk."""
        latest_mtime = self._get_search_items_mtime()
        if latest_mtime is None:
            return

        if self.search_intent_items_mtime is None or latest_mtime > self.search_intent_items_mtime:
            self.search_intent_items = self._load_search_intent_items()
            self.search_intent_items_mtime = latest_mtime
            logger.info("🔄 Reloaded search-intent items: %s", len(self.search_intent_items))
    
    def _search_database_faq(self, message: str) -> Optional[str]:
        """Search database for FAQ response (greetings, common questions, ordering, delivery)"""
        try:
            message_lower = message.lower().strip()
            
            # Define greeting mappings (English and Bengali)
            greeting_map = {
                'hi': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hello': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hey': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hlw': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'hai': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'assalamu alaikum': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম'],
                'আসসালামু আলাইকুম': ['হাই', 'হ্যালো', 'আসসালামু-আলাইকুম']
            }
            
            # Define ordering query mappings (romanized Bengali)e
            ordering_map = {
                'kibabe order korbo': 'অর্ডার করবো কিভাবে',
                'kivabe order korbo': 'অর্ডার করবো কিভাবে',
                'kemne order korbo': 'অর্ডার করবো কিভাবে',
                'order kivabe dibo': 'অর্ডার করবো কিভাবে',
                'order korbo kibabe': 'অর্ডার করবো কিভাবে',
                'order kivabe korbo': 'অর্ডার করবো কিভাবে',
                'how to order': 'অর্ডার করবো কিভাবে'
            }
            
            # Define delivery query mappings
            delivery_map = {
                'delivery koto din': 'ডেলিভারি চার্জ কত',
                'koto din lagbe': 'প্রোডাক্ট আসতে কত দিন সময় লাগবে',
                'delivery time': 'প্রোডাক্ট আসতে কত দিন সময় লাগবে',
                'koy din': 'প্রোডাক্ট আসতে কত দিন সময় লাগবে'
            }
            
            # Check if message is a greeting
            message_tokens = set(re.findall(r'[a-z0-9\u0980-\u09ff]+', message_lower))
            for eng_key, bengali_keys in greeting_map.items():
                # Avoid substring collisions like "chacchi" -> "hi".
                if eng_key in message_tokens or eng_key in message_lower.split():
                    # Search database for matching Bengali greeting
                    for item in self.database:
                        question = item['question']
                        for bengali_key in bengali_keys:
                            if bengali_key in question:
                                if self._is_blocked_automated_message(item['answer']):
                                    continue
                                logger.info(f"✅ Greeting match: '{message}' → '{item['answer']}'")
                                return item['answer']
            
            # Check if message is an ordering query
            for eng_pattern, bengali_query in ordering_map.items():
                if eng_pattern in message_lower:
                    # Search for Bengali ordering question in database
                    for item in self.database:
                        if bengali_query in item['question'] or 'অর্ডার' in item['question']:
                            logger.info(f"✅ Ordering match: '{message}' → database")
                            return item['answer']
            
            # Check if message has ordering keywords (Bengali or romanized)
            if any(word in message_lower for word in ['order', 'অর্ডার', 'korbo', 'করবো', 'kibabe', 'kivabe', 'kemne', 'কিভাবে']):
                # Search for ordering questions in database
                for item in self.database:
                    question = item['question'].lower()
                    if 'অর্ডার' in question and any(w in question for w in ['কিভাবে', 'কি ভাবে']):
                        logger.info(f"✅ Ordering keyword match: '{message}' → database")
                        return item['answer']
            
            # Check delivery queries
            for eng_pattern, bengali_query in delivery_map.items():
                if eng_pattern in message_lower:
                    for item in self.database:
                        if bengali_query in item['question'] or item['question'].lower() in bengali_query.lower():
                            logger.info(f"✅ Delivery match: '{message}' → database")
                            return item['answer']
            
            # Check for exact or partial matches
            for item in self.database:
                question = item['question'].lower()
                
                # Check if message matches question keywords
                if message_lower in question or question in message_lower:
                    if self._is_blocked_automated_message(item['answer']):
                        continue
                    return item['answer']
            
            return None
        except Exception as e:
            logger.error(f"❌ FAQ search failed: {e}")
            return None
    
    def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        Main process following your roadmap
        
        Step 1: Message → Groq API (Intent Detection)
        Step 2: Intent → Search API
        Step 3: Results → Database Format
        Step 4: Database → AI Formatting
        Step 5: Track AI/HUMAN mode
        Step 6: Return JSON with mode
        """
        try:
            start_time = datetime.now()
            self._refresh_search_intent_items_if_changed()
            
            # Get current mode for this user
            current_mode = self.user_modes.get(user_id, ChatMode.AI)
            current_status = self.user_conversation_status.get(user_id, AI_ACTIVE_STATUS)
            normalized_message = str(message or '').strip().lower()
            greeting_tokens = {
                'hi', 'hello', 'hey', 'salam', 'assalamualaikum', 'as-salamu alaikum',
                'হাই', 'হ্যালো', 'হেলো', 'সালাম', 'আসসালামু আলাইকুম', 'আসসালামুয়ালাইকুম'
            }
            
            logger.info(f"📨 Processing message from {user_id} (Mode: {current_mode.value})")
            logger.info(f"💬 Message: {message}")

            # Ignore known canned welcome templates to avoid unwanted auto-replies.
            if self._is_blocked_automated_message(message):
                logger.info("🔇 Ignoring blocked automated template message for user_id=%s", user_id)
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="",
                    mode=ChatMode.AI,
                    intent='ignored_automated_template',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=self.user_conversation_status.get(user_id, AI_ACTIVE_STATUS)
                )

            # ✅ NEW: Check user's responder status from BDStall API
            responder_type = self._check_responder_type(user_id)
            if responder_type == 'agent':
                if self._looks_like_possible_product_signal(message) or self._is_comparison_query(message):
                    logger.info(
                        "🔁 Overriding AGENT mode for AI-eligible query user_id=%s message='%s'",
                        user_id,
                        message,
                    )
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                else:
                    logger.info(f"🤝 User {user_id} is assigned to AGENT mode (responder_type={responder_type})")
                    self.user_modes[user_id] = ChatMode.HUMAN
                    self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
                    self._save_state()
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="",
                        mode=ChatMode.HUMAN,
                        intent='human_mode_active',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
                    )

            # Resume AI only when responder API explicitly returns bot mode.
            if responder_type == 'bot' and current_mode == ChatMode.HUMAN:
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                current_mode = ChatMode.AI
                current_status = AI_ACTIVE_STATUS
                logger.info("🔄 Resuming AI mode from responder API for user_id=%s", user_id)

            # In human mode, always stay silent (no automated reply/alert text).
            if current_mode == ChatMode.HUMAN and current_status == HUMAN_SUPPORT_REQUIRED_STATUS:
                if self._looks_like_possible_product_signal(message) or self._is_comparison_query(message):
                    logger.info(
                        "🔁 Escaping stored HUMAN mode for AI-eligible query user_id=%s message='%s'",
                        user_id,
                        message,
                    )
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                else:
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="",
                        mode=ChatMode.HUMAN,
                        intent='human_support_required',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
                    )

            # PRIMARY SCHEMA FLOW (temporary):
            # - greeting/goodbye allowed
            # - schema-based search intent handling
            # - other messages route to human
            schema_response = self._handle_intent_schema_flow(user_id, message, start_time)
            if schema_response is not None:
                return schema_response

            # Keep thank-you replies deterministic and free of sir/mam variants.
            thank_you_tokens = {
                'thank you', 'thanks', 'thx', 'thanku', 'thankyou',
                'ধন্যবাদ', 'অনেক ধন্যবাদ', 'thanks a lot'
            }
            if normalized_message in thank_you_tokens:
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="Most welcome",
                    mode=ChatMode.AI,
                    intent='thanks',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            if self._is_later_followup_message(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=self._build_later_followup_response(),
                    mode=ChatMode.AI,
                    intent='deferred_follow_up_ack',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            if self._is_deferred_reply_message(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="ধন্যবাদ স্যার, সাথে থাকার জন্য।",
                    mode=ChatMode.AI,
                    intent='deferred_follow_up_ack',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            if self._is_comparison_query(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=self._build_comparison_redirect_response(),
                    mode=ChatMode.AI,
                    intent='product_comparison',
                    products=None,
                    link_buttons=self._build_comparison_link_buttons(message),
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            if self._is_budget_only_query(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="স্যার, কোন প্রোডাক্টটি দেখতে চান?",
                    mode=ChatMode.AI,
                    intent='budget_product_clarification',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            if self._is_price_query(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS

                context_price_reply = self._reply_price_from_context(user_id)
                if context_price_reply:
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=context_price_reply,
                        mode=ChatMode.AI,
                        intent='price_from_context',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=AI_ACTIVE_STATUS
                    )

                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="কোন প্রোডাক্টটি চাচ্ছেন স্যার?",
                    mode=ChatMode.AI,
                    intent='price_product_clarification',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            if self._is_fixed_price_query(message):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=(
                        "জি স্যার, এগুলোর দাম ফিক্সড। বিস্তারিত জানতে ওয়েবসাইট ভিজিট করুন অথবা আমাদের কল করুন।"
                    ),
                    mode=ChatMode.AI,
                    intent='fixed_price_info',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            # Context-aware finisher: when user sends short acknowledgement like "ok",
            # reply with the standard Bangla closing line.
            ok_tokens = {
                'ok', 'okay', 'okk', 'okey', 'ঠিক আছে', 'acha', 'accha', 'আচ্ছা', 'ওকে'
            }
            if normalized_message in ok_tokens:
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="ধন্যবাদ স্যার, আর কিভাবে আমি আপনাকে সাহায্য করতে পারি?",
                    mode=ChatMode.AI,
                    intent='conversation_finished_ack',
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            # If user confirms after selecting a specific product, call order template API with listing ID.
            # Guard: do not trigger order flow for fresh product-search messages.
            selected_product = self.user_selected_product.get(user_id)
            if selected_product and (not self._looks_like_product_query(message)) and self._is_order_confirmation_message(message):
                listing_id = self._extract_listing_id_from_url(selected_product.get('url', ''))
                if listing_id:
                    order_template = self._fetch_order_intent_response(listing_id)
                    if order_template:
                        self.user_modes[user_id] = ChatMode.AI
                        return self._create_response(
                            user_id=user_id,
                            message=message,
                            response=order_template,
                            mode=ChatMode.AI,
                            intent='order',
                            products=None,
                            processing_time=(datetime.now() - start_time).total_seconds()
                        )

            # Handle order detail submission before any other reasoning.
            incoming_order_fields = self._extract_order_detail_fields(message)
            order_context_active = self.user_order_context.get(user_id, False)

            # Prevent stale order-form context from hijacking normal chat/search messages.
            if order_context_active and not incoming_order_fields:
                if normalized_message in greeting_tokens or self._looks_like_product_query(message):
                    logger.info(
                        "🧹 Clearing stale order context for user_id=%s on message='%s'",
                        user_id,
                        message,
                    )
                    self.user_order_context[user_id] = False
                    self.user_order_draft.pop(user_id, None)
                    order_context_active = False

            if incoming_order_fields or order_context_active:
                draft = dict(self.user_order_draft.get(user_id, {}))
                draft.update(incoming_order_fields)

                required_keys = ['name', 'phone_number', 'address', 'product_name', 'quantity']
                missing = [k for k in required_keys if not draft.get(k)]

                if not missing:
                    if not re.search(r'\d{10,15}', draft['phone_number']):
                        self.user_order_context[user_id] = True
                        self.user_order_draft[user_id] = draft
                        return self._create_response(
                            user_id=user_id,
                            message=message,
                            response="স্যার, Phone Number টি সঠিক ফরম্যাটে দিন (১০-১৫ ডিজিট)।",
                            mode=ChatMode.AI,
                            intent='order_details_incomplete',
                            products=None,
                            processing_time=(datetime.now() - start_time).total_seconds()
                        )

                    # Complete order details found - move to human handoff.
                    self.user_order_context[user_id] = False
                    self.user_order_draft.pop(user_id, None)
                    return self._handoff_to_human(
                        user_id=user_id,
                        message=message,
                        start_time=start_time,
                        intent='order_details_submission',
                        response_text="ধন্যবাদ স্যার, আমাদের অন্য একজন প্রতিনিধি এসে কথা বলবে।"
                    )

                # If user is filling order form, ask only for missing fields instead of re-running search.
                if incoming_order_fields or order_context_active:
                    self.user_order_context[user_id] = True
                    self.user_order_draft[user_id] = draft
                    missing_prompt = self._build_missing_order_fields_prompt(missing)
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=missing_prompt,
                        mode=ChatMode.AI,
                        intent='order_details_incomplete',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )

            # Handle quick follow-up selection like "4", "5", "product 4" before intent detection.
            selected_index = self._extract_product_selection(message)
            user_products = self.user_product_context.get(user_id, [])
            if selected_index and user_products and len(user_products) >= selected_index:
                selected_product = user_products[selected_index - 1]
                selection_response = self._format_selected_product_response(selected_product, selected_index)
                self.user_selected_product[user_id] = selected_product

                self.user_modes[user_id] = ChatMode.AI
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=selection_response,
                    mode=ChatMode.AI,
                    intent='product_selection',
                    products=user_products,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )

            # If previous turn had only brand+budget, require product type/title before searching.
            pending_search = self.user_pending_product_query.get(user_id)
            message_for_intent = message
            force_pending_search = False
            if pending_search:
                pending_merged_query = self._merge_pending_search_query(pending_search, message)
                if self._looks_like_product_query(message):
                    message_for_intent = pending_merged_query
                    self.user_pending_product_query.pop(user_id, None)
                    force_pending_search = True
                    logger.info(
                        "🔗 Using pending search context for user_id=%s merged_query='%s'",
                        user_id,
                        message_for_intent
                    )
                else:
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="জি স্যার, কোন প্রোডাক্ট চাচ্ছেন? যেমন: laptop, mobile, monitor।",
                        mode=ChatMode.AI,
                        intent='need_product_title',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )

            # Detect brand + budget without product and ask follow-up before search.
            if not pending_search:
                entities = self._extract_search_entities(message)
                if entities['brand'] and entities['has_price'] and not entities['has_product']:
                    self.user_pending_product_query[user_id] = {
                        'brand': entities['brand'],
                        'min_price': entities.get('min_price'),
                        'max_price': entities.get('max_price'),
                        'price_text': entities.get('price_text', ''),
                        'seed_message': str(message or '').strip()
                    }

                    budget_text = entities.get('price_text') or 'your budget'
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=(
                            f"ঠিক আছে স্যার, {entities['brand']} {budget_text} বুঝেছি। "
                            "আপনি কোন প্রোডাক্ট চাচ্ছেন?"
                        ),
                        mode=ChatMode.AI,
                        intent='need_product_title',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )

            # STEP 1: Message → Groq API (Intent Detection)
            conversation_context = self._fetch_recent_chat_context(
                user_id=user_id,
                limit=self.chatbot_history_limit
            )
            logger.info("🚀 STEP 1: Sending to Groq API for intent detection...")
            if force_pending_search:
                normalized_pending = str(message_for_intent or '').lower()
                intent_result = {
                    'success': True,
                    'intent': 'laptop_search' if ('laptop' in normalized_pending or 'ল্যাপটপ' in normalized_pending) else 'product_search',
                    'search_keywords': self._build_product_search_keywords(message_for_intent),
                    'raw_response': 'PENDING_SEARCH_BYPASS'
                }
                logger.info(
                    "🔁 [PENDING_SEARCH_BYPASS] user_id=%s keywords='%s'",
                    user_id,
                    intent_result['search_keywords']
                )
            else:
                rule_based_product = self._determine_rule_based_product_intent(message_for_intent)
                if rule_based_product:
                    intent_result = {
                        'success': True,
                        'intent': rule_based_product['intent'],
                        'search_keywords': rule_based_product['search_keywords'],
                        'raw_response': 'RULE_BASED_PRODUCT_INTENT'
                    }
                    logger.info(
                        "🔁 [RULE_BASED_PRODUCT_INTENT] user_id=%s intent=%s keywords='%s'",
                        user_id,
                        intent_result['intent'],
                        intent_result['search_keywords']
                    )
                else:
                    intent_result = self._step1_groq_intent(message_for_intent, conversation_context)

            if not intent_result['success']:
                logger.warning("⚠️ Intent detection failed; switching to HUMAN mode")
                return self._handoff_to_human(
                    user_id=user_id,
                    message=message,
                    start_time=start_time,
                    intent='intent_detection_failed'
                )

            intent = intent_result['intent']
            search_keywords = intent_result['search_keywords']

            # Normalize Groq custom product-search labels (e.g. watch_search, mobile_search)
            # so any product-like intent always flows into search API.
            if self._should_force_product_search_intent(intent, message_for_intent):
                normalized_text = str(message_for_intent or '').lower()
                normalized_keywords = str(search_keywords or '').lower()
                if 'laptop' in normalized_text or 'ল্যাপটপ' in normalized_text:
                    intent = 'laptop_search'
                elif any(term in normalized_text for term in ['price', 'dam', 'দাম', 'tk', 'taka', 'টাকা']) or any(
                    term in normalized_keywords for term in ['price', 'dam', 'দাম', 'tk', 'taka', 'টাকা']
                ):
                    intent = 'price_search'
                else:
                    intent = 'product_search'

                if str(search_keywords).strip().lower() in ['none', 'না', 'নেই', '']:
                    search_keywords = self._build_product_search_keywords(message_for_intent)

                logger.info(
                    "🔁 [GROQ_PRODUCT_INTENT_NORMALIZED] user_id=%s normalized_intent=%s keywords='%s'",
                    user_id,
                    intent,
                    search_keywords
                )

            if intent in ['product_search', 'price_search', 'laptop_search'] and str(search_keywords).strip().lower() in ['none', 'না', 'নেই', '']:
                search_keywords = self._build_product_search_keywords(message_for_intent)

            # Guardrail: prevent false handoff when LLM mislabels clear product queries.
            if intent in ['unknown', 'irrelevant'] and self._looks_like_product_query(message_for_intent):
                normalized = str(message_for_intent or '').lower()
                intent = 'laptop_search' if ('laptop' in normalized or 'ল্যাপটপ' in normalized) else 'product_search'
                search_keywords = self._build_product_search_keywords(message_for_intent)
                logger.info(
                    "🔁 Overriding %s intent to %s for product-like query user_id=%s",
                    intent_result.get('intent'),
                    intent,
                    user_id
                )
            
            logger.info(f"✅ Intent: {intent}")
            logger.info(f"🔍 Search Keywords: {search_keywords}")
            logger.info("📋 [INTENT_DETECTION] intent=%s keywords=%s looks_like_product=%s", 
                        intent, search_keywords, self._looks_like_product_query(message))

            previous_intent = self.user_last_intent.get(user_id)
            if previous_intent and previous_intent != intent:
                self._clear_product_search_cache(user_id, clear_pending=True)
                logger.info(
                    "🧹 Cleared search cache for user_id=%s due to intent switch %s -> %s",
                    user_id,
                    previous_intent,
                    intent
                )

            # Dynamic Groq recheck: if intent is unclear/general but query may be a search,
            # ask Groq once more to confirm and extract search keywords.
            if intent in ['unknown', 'irrelevant', 'general'] or (
                intent in ['greeting', 'faq'] and self._looks_like_possible_product_signal(message_for_intent)
            ):
                dynamic_keywords = self._step1_groq_dynamic_search_keywords(message_for_intent, conversation_context)
                if dynamic_keywords:
                    normalized_dynamic = str(message_for_intent or '').lower()
                    intent = 'laptop_search' if ('laptop' in normalized_dynamic or 'ল্যাপটপ' in normalized_dynamic) else 'product_search'
                    search_keywords = dynamic_keywords
                    logger.info(
                        "🔁 [DYNAMIC_GROQ_SEARCH] user_id=%s intent=%s keywords='%s'",
                        user_id,
                        intent,
                        search_keywords
                    )

            # Order/buy intent should call template API with dynamic intent + listing id.
            if intent == 'ordering' or self._looks_like_order_buy_message(message):
                self.user_order_context[user_id] = True
                self.user_order_draft[user_id] = {}
                self.user_modes[user_id] = ChatMode.AI
                order_template = self._get_order_info_template(
                    user_id=user_id,
                    message=message,
                    intent_hint=self._resolve_order_template_intent(message)
                )
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=order_template,
                    mode=ChatMode.AI,
                    intent=intent,
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )

            # Delivery intent should call template API first.
            if intent == 'delivery':
                delivery_response = self._fetch_delivery_intent_response()
                if delivery_response:
                    self.user_modes[user_id] = ChatMode.AI
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=delivery_response,
                        mode=ChatMode.AI,
                        intent=intent,
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )
            
            # Safe intents that should NOT trigger human handoff
            safe_intents = ['greeting', 'goodbye', 'thank_you', 'thanks', 'faq', 'general', 'question', 'ordering', 'delivery', 'support', 'warranty', 'availability']
            
            # SPECIAL HANDLING: Check database for FAQ responses first (greetings, common questions, ordering, delivery)
            if intent in safe_intents and not self._looks_like_possible_product_signal(message_for_intent):
                database_response = self._search_database_faq(message)
                if database_response:
                    logger.info("✅ Found response in database FAQ")
                    self.user_modes[user_id] = ChatMode.AI
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=database_response,
                        mode=ChatMode.AI,
                        intent=intent,
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )
            
            # If chatbot does not understand the intent, switch to HUMAN as per roadmap.
            if intent in ['unknown', 'irrelevant']:
                if self._looks_like_possible_product_signal(message_for_intent):
                    logger.info(
                        "🔁 Product-signal fallback activated for user_id=%s message='%s'",
                        user_id,
                        message_for_intent
                    )
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=(
                            "জি স্যার, আমি প্রোডাক্ট খুঁজে দিতে পারি। "
                            "একটু বিস্তারিত বলুন: brand/model/budget (যেমন: HP laptop 50k এর মধ্যে)।"
                        ),
                        mode=ChatMode.AI,
                        intent='product_search_clarification',
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=AI_ACTIVE_STATUS
                    )
                return self._handoff_to_human(
                    user_id=user_id,
                    message=message,
                    start_time=start_time,
                    intent=intent
                )
            
            # STEP 2 & 3: Search API → Database Format
            if intent in ['product_search', 'price_search', 'laptop_search']:
                category_name = self._resolve_generic_category_query(message_for_intent)
                if category_name:
                    logger.info(
                        "🚀 CATEGORY TEMPLATE: user_id=%s category=%s",
                        user_id,
                        category_name
                    )
                    category_response = self._fetch_category_intent_response(category_name)
                    if category_response:
                        self.user_modes[user_id] = ChatMode.AI
                        self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                        return self._create_response(
                            user_id=user_id,
                            message=message,
                            response=category_response,
                            mode=ChatMode.AI,
                            intent='category_search',
                            products=None,
                            search_keywords=category_name,
                            processing_time=(datetime.now() - start_time).total_seconds(),
                            conversation_status=AI_ACTIVE_STATUS
                        )
                    logger.info(
                        "⚠️ CATEGORY TEMPLATE unavailable; fallback to ai_search for category=%s",
                        category_name
                    )

                logger.info("🚀 STEP 2-3: Searching database with keywords...")
                logger.info("🔎 [SEARCH_INITIATED] user_id=%s intent=%s keywords='%s'", user_id, intent, search_keywords)
                search_result = self._step2_search_database(search_keywords)
                logger.info("🔎 [SEARCH_RESULT] found=%d products for keywords='%s'", search_result['products_found'], search_keywords)

                # Retry once with a broader query before switching to HUMAN mode.
                if search_result['products_found'] == 0:
                    logger.info("🔁 [SEARCH_RETRY] No exact match, trying broader keywords...")
                    broader_keywords = self._build_broader_search_keywords(search_keywords, message)
                    if broader_keywords:
                        logger.info(
                            "🔁 [SEARCH_RETRY_ATTEMPT] No results for '%s'; retrying with broader keywords '%s'",
                            search_keywords,
                            broader_keywords
                        )
                        retry_result = self._step2_search_database(broader_keywords)
                        if retry_result['products_found'] > 0:
                            logger.info("✅ [SEARCH_RETRY_SUCCESS] Found %d products with broader keywords", retry_result['products_found'])
                            search_keywords = broader_keywords
                            search_result = retry_result
                        else:
                            logger.info("❌ [SEARCH_RETRY_FAILED] Broader keywords also returned no results")
                
                if search_result['products_found'] == 0:
                    # Keep AI mode for product queries even when no exact result is found.
                    # This avoids premature human handoff for Messenger phrasing/keywords.
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                    logger.info("⚠️ [PRODUCT_SEARCH_NO_RESULTS] Returning fallback message for user_id=%s", user_id)
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=(
                            "স্যার, এই মুহূর্তে নির্দিষ্ট কোনো প্রোডাক্ট পেলাম না। "
                            "আপনি ব্র্যান্ড/মডেল/বাজেট একটু সহজ করে লিখে দিন, আমি আবার খুঁজে দিচ্ছি।"
                        ),
                        mode=ChatMode.AI,
                        intent='no_products_found',
                        products=None,
                        search_keywords=search_keywords,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=AI_ACTIVE_STATUS
                    )
                
                database_message = search_result['database_message']
                products = search_result['products']

                # Save latest result list so user can select 1-5 in follow-up message.
                self.user_product_context[user_id] = products[:5]
                
                logger.info(f"✅ Found {len(products)} products")
                logger.info("📦 [PRODUCT_SEARCH_SUCCESS] user_id=%s found %d products from %d total", 
                            user_id, len(products), search_result.get('total_products', 0))
                
                # STEP 4: Database Message → AI (Final Formatting)
                logger.info("🚀 STEP 4: Sending to AI for final response...")
                final_response = self._step4_ai_format(message, database_message, products, conversation_context)
                
                if not final_response['success']:
                    # AI formatting failed, switch to HUMAN
                    logger.error("❌ [STEP4_FAILED] AI formatting failed for user_id=%s", user_id)
                    return self._handoff_to_human(
                        user_id=user_id,
                        message=message,
                        start_time=start_time,
                        intent=intent,
                        products=products
                    )
                
                # Success! Keep in AI mode
                self.user_modes[user_id] = ChatMode.AI
                logger.info("✅ [PRODUCT_RESPONSE_READY] Returning formatted response with %d products", len(products))
                
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=final_response['response'],
                    mode=ChatMode.AI,
                    intent=intent,
                    products=products,
                    search_keywords=search_keywords,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )
            
            else:
                # Not a product search - check database for FAQ/Greeting responses first
                logger.info("🚀 Checking database for FAQ response...")
                faq_response = self._search_database_faq(message)
                
                if faq_response:
                    # Found in database - use that response
                    logger.info("✅ Found response in database")
                    self.user_modes[user_id] = ChatMode.AI
                    
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=faq_response,
                        mode=ChatMode.AI,
                        intent=intent,
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )
                
                # Not in database - use AI for general response
                logger.info("🚀 General query - using AI directly...")
                ai_response = self._step4_ai_format(message, None, None, conversation_context)
                
                if not ai_response['success']:
                    return self._handoff_to_human(
                        user_id=user_id,
                        message=message,
                        start_time=start_time,
                        intent=intent
                    )
                
                self.user_modes[user_id] = ChatMode.AI
                
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=ai_response['response'],
                    mode=ChatMode.AI,
                    intent=intent,
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )
        
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            # On error, switch to HUMAN mode
            return self._handoff_to_human(
                user_id=user_id,
                message=message,
                start_time=start_time if 'start_time' in locals() else datetime.now(),
                intent='system_error',
                error=str(e)
            )
    
    def _step1_groq_intent(self, message: str, conversation_context: str = '') -> Dict[str, Any]:
        """
        STEP 1: Send to Groq API for intent detection
        Extract: intent & search keywords
        """
        if not self.groq_client:
            local_intent, local_keywords = self._local_intent_fallback(message)
            return {
                'success': True,
                'intent': local_intent,
                'search_keywords': local_keywords,
                'raw_response': 'LOCAL_FALLBACK'
            }
        
        try:
            prompt = f"""Analyze this message and extract:
1. Intent (product_search, price_search, laptop_search, ordering, delivery, greeting, question, support, warranty, availability, general, unknown)
2. Search keywords (for product search)

Recent conversation context (oldest to newest):
{conversation_context or 'N/A'}

Intents:
- product_search/laptop_search: Looking for specific products
- price_search: Asking about prices
- ordering: Questions about how to order (কিভাবে অর্ডার, order korbo, kibabe, kivabe)
- delivery: Questions about delivery time, charges, location
- support: Contact numbers, customer service
- warranty: Warranty/guarantee questions
- availability: Stock availability
- greeting: Hi, hello, salam
- question: General informational questions
- unknown: Unclear, complaints, refunds

Rules:
- Always read the recent context before deciding intent.
- If current message is short/ambiguous, use context to infer likely intent.
- For product follow-up messages, combine with context mentally before returning keywords.

Message: {message}

Respond in this EXACT format:
Intent: [intent]
Keywords: [keywords]

Examples:
- "amake ekta 10k er modde laptop dekhan" → Intent: laptop_search, Keywords: laptop 10000 taka
- "order korbo kibabe" → Intent: ordering, Keywords: none
- "kivabe order korbo" → Intent: ordering, Keywords: none
- "delivery koto din lagbe" → Intent: delivery, Keywords: none
- "mouse er dam koto?" → Intent: price_search, Keywords: mouse price
- "hello" → Intent: greeting, Keywords: none
- "customer support number" → Intent: support, Keywords: none
- "ami amar product ferot dite chai" → Intent: unknown, Keywords: none
"""
            
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse result
            intent = "general"
            keywords = message

            # Parse leniently to handle LLM formatting variations.
            # Works for:
            # - "Intent: product_search\nKeywords: hp laptop"
            # - "Intent: product_search, Keywords: hp laptop"
            intent_match = re.search(r'(?is)intent\s*[:\-]\s*([^\n,;|]+)', result)
            if intent_match:
                intent = intent_match.group(1).strip().lower()

            keywords_match = re.search(r'(?is)keywords\s*[:\-]\s*([^\n]+)', result)
            if keywords_match:
                keywords = keywords_match.group(1).strip().rstrip(' .;|')

            # If Groq put both values in one line, sanitize intent tail.
            if any(sep in intent for sep in [',', ';', '|']):
                intent = re.split(r'[,;|]', intent, maxsplit=1)[0].strip()

            if keywords.strip().lower() in {'none', 'na', 'n/a', 'নেই', 'না'} and self._looks_like_product_query(message):
                keywords = self._build_product_search_keywords(message)

            valid_intents = {
                'product_search', 'price_search', 'laptop_search', 'ordering', 'delivery',
                'greeting', 'question', 'support', 'warranty', 'availability', 'general',
                'unknown', 'irrelevant', 'faq', 'goodbye', 'thank_you', 'thanks'
            }
            if intent not in valid_intents:
                local_intent, local_keywords = self._local_intent_fallback(message)
                intent = local_intent
                if (not keywords) or keywords == message:
                    keywords = local_keywords
            
            return {
                'success': True,
                'intent': intent,
                'search_keywords': keywords,
                'raw_response': result
            }
        
        except Exception as e:
            logger.error(f"❌ Groq intent detection failed: {e}")
            local_intent, local_keywords = self._local_intent_fallback(message)
            return {
                'success': True,
                'intent': local_intent,
                'search_keywords': local_keywords,
                'raw_response': f'LOCAL_FALLBACK_ON_ERROR: {str(e)}'
            }

    def _step1_groq_dynamic_search_keywords(self, message: str, conversation_context: str = '') -> Optional[str]:
        """Ask Groq if message is a product-search query and extract keywords when yes."""
        if not self.groq_client:
            return None

        try:
            prompt = f"""Decide if this is a PRODUCT SEARCH query for an ecommerce chatbot.

Recent conversation context:
{conversation_context or 'N/A'}

Current message:
{message}

Return EXACTLY in this format:
SearchQuery: [yes/no]
Keywords: [keyword string or none]

Rules:
- yes only if user is asking to find/check products, availability, brand/model, budget, or price-related shopping query.
- no for greetings, thanks, pure support, random chat.
- Keywords should be concise search terms for API search.
"""

            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=120
            )

            result = response.choices[0].message.content.strip()
            search_flag_match = re.search(r'(?is)searchquery\s*[:\-]\s*(yes|no)', result)
            keywords_match = re.search(r'(?is)keywords\s*[:\-]\s*([^\n]+)', result)

            if not search_flag_match:
                return None

            is_search = search_flag_match.group(1).strip().lower() == 'yes'
            keywords = keywords_match.group(1).strip() if keywords_match else ''

            if not is_search:
                return None

            if keywords.lower() in {'none', 'na', 'n/a', 'নেই', 'না', ''}:
                keywords = self._build_product_search_keywords(message)

            return keywords or None
        except Exception as e:
            logger.info("[DYNAMIC_GROQ_SEARCH] failed: %s", e)
            return None

    def _is_conversation_finished_with_context(self, message: str, conversation_context: str = '') -> bool:
        """Use Groq to decide whether a short ack means conversation has finished."""
        if not self.groq_client:
            return False

        try:
            prompt = f"""Determine if the user message indicates conversation completion.

Recent conversation context:
{conversation_context or 'N/A'}

Latest user message:
{message}

Return EXACTLY:
Finished: [yes/no]

Rules:
- Return yes when user is wrapping up/ending after receiving answer.
- Return no when user likely expects next step (order, search refinement, pending details).
"""

            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=40
            )

            result = response.choices[0].message.content.strip()
            match = re.search(r'(?is)finished\s*[:\-]\s*(yes|no)', result)
            if not match:
                return False
            return match.group(1).strip().lower() == 'yes'
        except Exception as e:
            logger.info("[FINISH_CHECK] failed: %s", e)
            return False

    def _normalize_history_messages(self, payload: Any) -> list[str]:
        """Normalize history API payload into compact role-prefixed lines."""
        candidates = []
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict):
            for key in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
                value = payload.get(key)
                if isinstance(value, list):
                    candidates = value
                    break

            if not candidates and isinstance(payload.get('data'), dict):
                nested = payload.get('data') or {}
                for key in ['messages', 'history', 'chat_history', 'conversation', 'items']:
                    value = nested.get(key)
                    if isinstance(value, list):
                        candidates = value
                        break

        lines: list[str] = []
        for item in candidates:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    lines.append(f"User: {text}")
                continue

            if not isinstance(item, dict):
                continue

            text = (
                str(item.get('message') or item.get('text') or item.get('content') or item.get('body') or '')
                .strip()
            )
            if not text:
                continue

            sender_type = str(item.get('sender_type') or '').strip()
            role = str(item.get('role') or '').strip().lower()
            if sender_type == '2' or role in {'assistant', 'bot', 'ai'}:
                lines.append(f"Bot: {text}")
            elif sender_type == '1' or role in {'agent', 'human'}:
                lines.append(f"Agent: {text}")
            else:
                lines.append(f"User: {text}")

        return lines[-10:]

    def _fetch_recent_chat_context(self, user_id: str, limit: int = 5) -> str:
        """Fetch recent chat history from BDStall and return compact context text."""
        if not user_id:
            return ''

        safe_limit = max(1, min(int(limit or 5), 20))

        request_urls = self._build_chat_history_urls(user_id, safe_limit)

        started = datetime.now()
        for request_url in request_urls:
            try:
                response = requests.get(request_url, timeout=8)
                duration_ms = int((datetime.now() - started).total_seconds() * 1000)

                _log_api_call(
                    api_name="chatbot_history",
                    method="GET",
                    url=request_url,
                    request_payload={
                        'user_id': str(user_id),
                        'limit': safe_limit,
                        'key': self.api_key
                    },
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    status="PASS" if 200 <= response.status_code < 300 else "FAIL",
                    response_preview=response.text
                )

                if not (200 <= response.status_code < 300):
                    continue

                payload = response.json() if response.text else {}
                lines = self._normalize_history_messages(payload)
                context = '\n'.join(lines).strip()
                if context:
                    logger.info("🧠 [HISTORY_CONTEXT] user_id=%s lines=%s", user_id, len(lines))
                return context
            except Exception as e:
                duration_ms = int((datetime.now() - started).total_seconds() * 1000)
                _log_api_call(
                    api_name="chatbot_history",
                    method="GET",
                    url=request_url,
                    request_payload={
                        'user_id': str(user_id),
                        'limit': safe_limit,
                        'key': self.api_key
                    },
                    status_code=0,
                    duration_ms=duration_ms,
                    status="FAIL",
                    response_preview=str(e)
                )

        return ''

    def _build_chat_history_urls(self, user_id: str, limit: int) -> list[str]:
        """Build compatible chatbot_history URL variants."""
        base = str(self.chatbot_history_api_url or '').strip()
        if not base:
            return []

        query_tail = f"user_id={user_id}&limit={limit}&key={self.api_key}"
        base_stripped = base.rstrip('/')

        candidates = [
            f"{base}{query_tail}",
            f"{base}?{query_tail}",
            f"{base_stripped}/user_id={user_id}&limit={limit}&key={self.api_key}",
            f"{base_stripped}?{query_tail}"
        ]

        deduped = []
        seen = set()
        for url in candidates:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def _normalize_compare_flag(self, value: Any) -> str:
        """Normalize compare flag to yes/no string."""
        text = str(value or '').strip().lower()
        if text in {'yes', 'true', '1', 'y'}:
            return 'yes'
        return 'no'

    def _to_title_case(self, text: str) -> str:
        """Convert category/title text into simple title case."""
        normalized = str(text or '').strip()
        if not normalized:
            return ''
        return ' '.join(part.capitalize() for part in normalized.split())

    def _extract_price_text_for_intent(self, message: str) -> Optional[str]:
        """Extract compact budget text for intent_content (e.g., 10k, under 20k)."""
        text = str(message or '').strip().lower()
        if not text:
            return None

        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        range_match = re.search(r'(\d+(?:\.\d+)?)\s*(k|tk|taka|টাকা|হাজার)?\s*(?:-|to|থেকে)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|টাকা|হাজার)?', text)
        if range_match:
            left_num = range_match.group(1)
            left_unit = (range_match.group(2) or '').strip().lower()
            right_num = range_match.group(3)
            right_unit = (range_match.group(4) or '').strip().lower()
            left = f"{left_num}k" if left_unit in {'k', 'হাজার'} else left_num
            right = f"{right_num}k" if right_unit in {'k', 'হাজার'} else right_num
            return f"{left}-{right}"

        under_match = re.search(r'(?:under|within|below|less than|modde|মধ্যে|এর মধ্যে)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|টাকা|হাজার)?', text)
        if under_match:
            number = under_match.group(1)
            unit = (under_match.group(2) or '').strip().lower()
            if unit in {'k', 'হাজার'}:
                return f"{number}k"
            return f"under {number}"

        plain_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|টাকা|হাজার)\b', text)
        if plain_match:
            number = plain_match.group(1)
            unit = plain_match.group(2).strip().lower()
            if unit in {'k', 'হাজার'}:
                return f"{number}k"
            return number

        return None

    def _fetch_recent_intent_content(self, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """Fetch last stored intent_content from chatbot_history API user_info block."""
        if not user_id:
            return {}

        safe_limit = max(1, min(int(limit or 5), 20))
        request_urls = self._build_chat_history_urls(user_id, safe_limit)

        started = datetime.now()
        for request_url in request_urls:
            try:
                response = requests.get(request_url, timeout=8)
                duration_ms = int((datetime.now() - started).total_seconds() * 1000)

                _log_api_call(
                    api_name="chatbot_history_intent_content",
                    method="GET",
                    url=request_url,
                    request_payload={
                        'user_id': str(user_id),
                        'limit': safe_limit,
                        'key': self.api_key
                    },
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    status="PASS" if 200 <= response.status_code < 300 else "FAIL",
                    response_preview=response.text
                )

                if not (200 <= response.status_code < 300):
                    continue

                payload = response.json() if response.text else {}
                user_info = payload.get('user_info') if isinstance(payload, dict) else {}
                raw = user_info.get('intent_content') if isinstance(user_info, dict) else {}
                if not isinstance(raw, dict):
                    continue

                title_value = str(raw.get('title') or '').strip()
                category_value = str(raw.get('category') or raw.get('cat') or '').strip()
                brand_value = str(raw.get('brand') or '').strip().lower()
                price_value = str(raw.get('price') or '').strip()

                normalized = {
                    'title': self._to_title_case(title_value) if title_value else '',
                    'category': self._to_title_case(category_value) if category_value else '',
                    'brand': brand_value,
                    'price': price_value,
                    'buy': 'ok' if str(raw.get('buy') or '').strip() else '',
                    'compare': self._normalize_compare_flag(raw.get('compare'))
                }

                return {k: v for k, v in normalized.items() if str(v).strip()}
            except Exception:
                continue

        return {}

    def _build_intent_content_from_schema(
        self,
        user_id: str,
        message: str,
        intent_obj: Dict[str, Optional[str]]
    ) -> Dict[str, Any]:
        """Build conversation-aware intent_content where only explicit fields are updated."""
        previous = dict(self.user_intent_content.get(user_id) or {})
        previous_from_api = self._fetch_recent_intent_content(user_id, self.chatbot_history_limit)
        if previous_from_api:
            previous = previous_from_api

        title_raw = str(intent_obj.get('title') or '').strip()
        price_raw = str(intent_obj.get('price') or '').strip()

        entities = self._extract_search_entities(message)
        brand_raw = str(entities.get('brand') or '').strip().lower()

        updated = {
            'title': str(previous.get('title') or '').strip(),
            'category': str(previous.get('category') or '').strip(),
            'brand': str(previous.get('brand') or '').strip().lower(),
            'price': str(previous.get('price') or '').strip(),
            'buy': str(previous.get('buy') or '').strip(),
            'compare': self._normalize_compare_flag(previous.get('compare'))
        }

        if title_raw:
            normalized_title = self._to_title_case(title_raw)
            previous_title = str(previous.get('title') or '').strip().lower()
            new_title_lower = normalized_title.lower()

            # ── Dynamic intent refresh ────────────────────────────────────────
            # When Groq detects a NEW product category (title changed), reset all
            # accumulated context fields so stale brand/price from the old
            # category don't pollute the new intent.  Brand/price are then filled
            # fresh from the current message further below.
            # Title is always mandatory — it is never cleared.
            if previous_title and new_title_lower != previous_title:
                logger.info(
                    "🔄 [INTENT_REFRESH] Title changed '%s' → '%s'. "
                    "Resetting brand/price/buy/category for new intent context.",
                    previous_title, normalized_title
                )
                updated['brand'] = ''
                updated['price'] = ''
                updated['buy'] = ''
                updated['compare'] = 'no'
                updated['category'] = ''
            # ─────────────────────────────────────────────────────────────────

            updated['title'] = normalized_title
            updated['category'] = normalized_title

        if brand_raw:
            updated['brand'] = brand_raw

        price_from_text = self._extract_price_text_for_intent(message)
        if price_from_text:
            updated['price'] = price_from_text
        elif price_raw and price_raw.lower() not in {'koto', 'কত', 'price', 'dam', 'দাম'}:
            updated['price'] = price_raw

        updated['buy'] = 'ok' if self._looks_like_order_buy_message(message) else updated['buy']
        updated['compare'] = 'yes' if self._is_comparison_query(message) else 'no'

        if not updated.get('category') and updated.get('title'):
            updated['category'] = updated['title']

        # Save intent_content if there are meaningful updates (title, price, or brand)
        if updated.get('title') or price_from_text or brand_raw:
            self.user_intent_content[user_id] = dict(updated)

        return updated

    def _build_search_keywords_from_intent_content(self, intent_content: Dict[str, Any]) -> str:
        """Build the exact search API term from structured intent content."""
        if not isinstance(intent_content, dict):
            return ''

        parts = []
        brand = str(intent_content.get('brand') or '').strip()
        title = str(intent_content.get('title') or '').strip()
        price = str(intent_content.get('price') or '').strip()

        if brand:
            parts.append(brand)
        if title:
            parts.append(title)
        if price and price.lower() not in {'koto', 'কত', 'price', 'dam', 'দাম'}:
            parts.append(price)

        return ' '.join(part for part in parts if part).strip()

    def _local_intent_fallback(self, message: str) -> tuple[str, str]:
        """Deterministic fallback when Groq is unavailable or returns unparsable output."""
        text = str(message or '').strip().lower()
        logger.info("🔄 [LOCAL_FALLBACK] Fallback intent detection for message: %s", message[:50])

        if self._looks_like_product_query(message):
            logger.info("🔄 [LOCAL_FALLBACK_PRODUCT] Detected as product query")
            # Keep laptop intent specific when laptop keyword appears.
            if 'laptop' in text or 'ল্যাপটপ' in text:
                logger.info("🔄 [LOCAL_FALLBACK_LAPTOP] Detected as laptop search")
                return 'laptop_search', self._build_product_search_keywords(message)
            if any(w in text for w in ['price', 'dam', 'দাম', 'tk', 'taka', 'টাকা']):
                return 'price_search', self._build_product_search_keywords(message)
            return 'product_search', self._build_product_search_keywords(message)

        if any(w in text for w in ['order', 'অর্ডার', 'kivabe', 'kibabe']):
            return 'ordering', 'none'
        if any(w in text for w in ['delivery', 'ডেলিভারি', 'কত দিন', 'koto din']):
            return 'delivery', 'none'
        if any(w in text for w in ['hello', 'hi', 'হাই', 'সালাম', 'আসসালামু']):
            return 'greeting', 'none'

        return 'general', message

    def _extract_budget_range(self, message: str) -> Dict[str, Optional[int]]:
        """Extract approximate price range from user text (supports k, tk, taka, হাজার)."""
        text = str(message or '').strip().lower()
        if not text:
            return {'min_price': None, 'max_price': None, 'price_text': ''}

        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        def _to_taka(raw_value: str, unit: str) -> int:
            value = int(float(raw_value))
            unit_norm = (unit or '').strip().lower()
            if unit_norm in {'k', 'হাজার', 'thousand'}:
                return value * 1000
            if unit_norm in {'tk', 'taka', 'টাকা'}:
                return value
            if value < 1000:
                return value * 1000
            return value

        range_match = re.search(
            r'(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)?\s*(?:-|to|থেকে)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)?',
            text
        )
        if range_match:
            min_price = _to_taka(range_match.group(1), range_match.group(2) or range_match.group(4) or '')
            max_price = _to_taka(range_match.group(3), range_match.group(4) or range_match.group(2) or '')
            if min_price > max_price:
                min_price, max_price = max_price, min_price
            return {
                'min_price': min_price,
                'max_price': max_price,
                'price_text': f"{min_price}-{max_price}"
            }

        under_match = re.search(
            r'(?:under|within|modde|modhhe|budget|er modde|এর মধ্যে|মধ্যে|below|less than)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)?',
            text
        )
        if under_match:
            max_price = _to_taka(under_match.group(1), under_match.group(2) or '')
            return {'min_price': None, 'max_price': max_price, 'price_text': f"under {max_price}"}

        generic_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা)\b', text)
        if generic_match:
            max_price = _to_taka(generic_match.group(1), generic_match.group(2) or '')
            return {'min_price': None, 'max_price': max_price, 'price_text': f"under {max_price}"}

        return {'min_price': None, 'max_price': None, 'price_text': ''}

    def _extract_search_entities(self, message: str) -> Dict[str, Any]:
        """Extract lightweight entities for search: brand, product hint, and budget range."""
        text = str(message or '').strip().lower()
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        brand_terms = [
            'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'iphone', 'samsung', 'xiaomi',
            'realme', 'oppo', 'vivo', 'msi', 'huawei'
        ]
        product_terms = [
            'laptop', 'phone', 'mobile', 'pc', 'computer', 'monitor', 'mouse', 'keyboard',
            'headphone', 'ssd', 'ram', 'printer', 'camera', 'router', 'charger', 'tablet',
            'elitebook', 'pavilion', 'thinkpad', 'inspiron', 'aspire', 'vivobook', 'zbook',
            'macbook', 'chromebook', 'probook', 'pixelbook', 'razer', 'alienware', 'rog',
            'ল্যাপটপ', 'মোবাইল', 'ফোন', 'কম্পিউটার', 'মাউস', 'কিবোর্ড', 'হেডফোন', 'ট্যাব'
        ]

        brand = next((b for b in brand_terms if b in text), None)
        has_product = any(term in text for term in product_terms)
        budget = self._extract_budget_range(text)
        has_price = budget.get('min_price') is not None or budget.get('max_price') is not None

        return {
            'brand': brand,
            'has_product': has_product,
            'has_price': has_price,
            'min_price': budget.get('min_price'),
            'max_price': budget.get('max_price'),
            'price_text': budget.get('price_text', '')
        }

    def _merge_pending_search_query(self, pending: Dict[str, Any], followup_message: str) -> str:
        """Combine pending brand/budget constraints with follow-up product request."""
        parts = []
        brand = str(pending.get('brand') or '').strip()
        if brand:
            parts.append(brand)

        followup = str(followup_message or '').strip()
        if followup:
            parts.append(followup)

        price_text = str(pending.get('price_text') or '').strip()
        if price_text:
            parts.append(price_text)

        return ' '.join(part for part in parts if part).strip()

    def _determine_rule_based_product_intent(self, message: str) -> Optional[Dict[str, str]]:
        """Deterministically derive product intent/keywords for shopping-like messages."""
        text = str(message or '').strip().lower()
        if not text:
            return None

        if self._contains_configured_search_item(text):
            return {
                'intent': 'product_search',
                'search_keywords': self._build_product_search_keywords(text)
            }

        entities = self._extract_search_entities(text)
        has_product = bool(entities.get('has_product'))
        has_price = bool(entities.get('has_price'))

        if self._looks_like_product_query(text):
            intent = 'laptop_search' if ('laptop' in text or 'ল্যাপটপ' in text) else ('price_search' if has_price else 'product_search')
            return {
                'intent': intent,
                'search_keywords': self._build_product_search_keywords(text)
            }

        if self._looks_like_possible_product_signal(text) and (has_product or entities.get('brand')):
            intent = 'laptop_search' if ('laptop' in text or 'ল্যাপটপ' in text) else ('price_search' if has_price else 'product_search')
            return {
                'intent': intent,
                'search_keywords': self._build_product_search_keywords(text)
            }

        return None

    def _should_force_product_search_intent(self, intent: str, message: str) -> bool:
        """Return True when Groq intent looks product-search-like and should route to search."""
        normalized_intent = str(intent or '').strip().lower()
        if not normalized_intent:
            return False

        if normalized_intent in {'product_search', 'price_search', 'laptop_search'}:
            return False

        product_intent_hints = {
            'search', 'product', 'laptop', 'mobile', 'phone', 'watch', 'smartwatch',
            'computer', 'electronics', 'gadget', 'item', 'catalog'
        }
        looks_like_product_intent = (
            normalized_intent.endswith('_search')
            or any(hint in normalized_intent for hint in product_intent_hints)
        )

        if not looks_like_product_intent:
            return False

        return self._looks_like_possible_product_signal(message) or self._looks_like_product_query(message)

    def _normalize_product_query_text(self, message: str) -> str:
        """Normalize product-search text so common transliterations map to canonical terms."""
        text = str(message or '').strip().lower()
        if not text:
            return ''

        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        phrase_normalizations = (
            (r'\bhat\s+ghori\b', 'hand watch'),
            (r'\bhaat\s+ghori\b', 'hand watch'),
            (r'\bghori\b', 'watch'),
        )
        for pattern, replacement in phrase_normalizations:
            text = re.sub(pattern, replacement, text)

        text = text.replace('ঘড়ি', 'watch')
        text = text.replace('ঘড়ি', 'watch')
        return text

    def _looks_like_product_query(self, message: str) -> bool:
        """Heuristic detector for short product requests in English/Bangla transliteration."""
        text = self._normalize_product_query_text(message)
        if not text:
            return False

        product_terms = [
            'laptop', 'phone', 'mobile', 'pc', 'computer', 'monitor', 'mouse', 'keyboard',
            'headphone', 'ssd', 'ram', 'printer', 'camera', 'router', 'charger',
            'watch', 'smartwatch', 'smart-watch', 'smart watch',
            'gun', 'stun', 'stun gun', 'taser',
            'elitebook', 'pavilion', 'thinkpad', 'inspiron', 'aspire', 'vivobook', 'zbook',
            'macbook', 'chromebook', 'probook', 'pixelbook', 'razer', 'alienware', 'rog',
            'g8', 'g7', 'g6', 'g5', 'g4', 'g3', 'g2', 'g1',
            'ল্যাপটপ', 'মোবাইল', 'ফোন', 'কম্পিউটার', 'মাউস', 'কিবোর্ড', 'হেডফোন',
            'ঘড়ি', 'ঘড়ি', 'স্মার্টওয়াচ', 'স্মার্টওয়াচ', 'স্মার্ট ঘড়ি', 'স্মার্ট ঘড়ি'
        ]
        brand_terms = [
            'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'iphone', 'samsung', 'xiaomi',
            'realme', 'oppo', 'vivo', 'msi', 'huawei'
        ]
        buying_cues = [
            'price', 'dam', 'tk', 'taka', 'budget', 'modde', 'within', 'under',
            'ase', 'ache', 'pawa', 'kase', 'kache', 'lagbe', 'chai',
            'দাম', 'টাকা', 'হাজার', 'আছে', 'কাছে', 'বাজেট'
        ]

        has_product = any(term in text for term in product_terms)
        has_brand = any(term in text for term in brand_terms)
        has_cue = any(cue in text for cue in buying_cues)
        has_number = bool(re.search(r'\b\d+\s*(k|tk|taka|টাকা|হাজার)?\b', text))

        availability_words = {'ase', 'ache', 'pawa', 'available', 'stock', 'আছে', 'পাওয়া', 'পাওয়া'}
        compact_tokens = [t for t in re.split(r'\s+', text) if t]
        has_availability_word = any(t in availability_words for t in compact_tokens)
        has_candidate_term = len([t for t in compact_tokens if t not in availability_words and len(t) > 1]) >= 1

        if has_product and (has_brand or has_cue or has_number):
            return True
        if has_product and len(text.split()) <= 4:
            return True
        if has_availability_word and has_candidate_term and len(compact_tokens) <= 5:
            return True

        return False

    def _looks_like_possible_product_signal(self, message: str) -> bool:
        """Broader detector used to avoid accidental human handoff for shopping-related text."""
        text = self._normalize_product_query_text(message)
        if not text:
            return False

        if self._contains_configured_search_item(text):
            return True

        if self._looks_like_product_query(text):
            return True

        signal_terms = {
            'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung', 'xiaomi',
            'laptop', 'mobile', 'phone', 'pc', 'computer', 'monitor', 'mouse', 'keyboard',
            'watch', 'smartwatch', 'smart',
            'elitebook', 'thinkpad', 'macbook', 'inspiron', 'pavilion',
            'price', 'dam', 'tk', 'taka', 'budget', 'modde', 'under', 'within',
            'ase', 'ache', 'pawa', 'available', 'stock',
            'দাম', 'টাকা', 'বাজেট', 'ল্যাপটপ', 'মোবাইল', 'ফোন', 'আছে', 'ঘড়ি', 'ঘড়ি', 'স্মার্টওয়াচ', 'স্মার্টওয়াচ'
        }

        tokens = set(re.findall(r'[a-z0-9\u0980-\u09ff]+', text))
        hits = sum(1 for token in tokens if token in signal_terms)
        return hits >= 2

    def _contains_configured_search_item(self, message: str) -> bool:
        """Return True when user message includes a configured catalog/category item name."""
        text = self._normalize_product_query_text(message)
        if not text or not getattr(self, 'search_intent_items', None):
            return False

        # Normalize separators so patterns like "smart-watch" and "smart watch" both match.
        normalized_message = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', text)
        normalized_message = re.sub(r'\s+', ' ', normalized_message).strip()
        padded_message = f" {normalized_message} "

        for item in self.search_intent_items:
            normalized_item = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', item)
            normalized_item = re.sub(r'\s+', ' ', normalized_item).strip()
            if not normalized_item:
                continue
            if f" {normalized_item} " in padded_message:
                return True

        return False

    def _find_best_search_item_match(self, message: str) -> Optional[str]:
        """Return the longest configured category/item phrase found in the message."""
        text = self._normalize_product_query_text(message)
        if not text or not getattr(self, 'search_intent_items', None):
            return None

        normalized_message = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', text)
        normalized_message = re.sub(r'\s+', ' ', normalized_message).strip()
        padded_message = f" {normalized_message} "

        best_match = None
        best_token_count = 0

        for item in self.search_intent_items:
            normalized_item = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', str(item or '').lower())
            normalized_item = re.sub(r'\s+', ' ', normalized_item).strip()
            if not normalized_item:
                continue

            if f" {normalized_item} " not in padded_message:
                continue

            token_count = len(normalized_item.split())
            if token_count > best_token_count:
                best_match = normalized_item
                best_token_count = token_count

        return best_match

    def _resolve_generic_category_query(self, message: str) -> Optional[str]:
        """Return category only when user asks a generic category query without details."""
        text = self._normalize_product_query_text(message)
        if not text:
            return None

        matched_item = self._find_best_search_item_match(text)
        if not matched_item:
            return None

        entities = self._extract_search_entities(text)
        if entities.get('brand') or entities.get('has_price'):
            return None

        filler_tokens = {
            'ami', 'amake', 'amar', 'amr', 'ase', 'ache', 'achi', 'available', 'stock', 'pawa', 'kache', 'kase',
            'chai', 'lagbe', 'dorkar', 'den', 'din', 'show', 'dekhan', 'dekhte',
            'please', 'plz', 'need', 'want', 'looking', 'for',
            'kinte', 'kinbo', 'kintechi', 'chacchi', 'chai', 'nite', 'nitechi',
            'আছে', 'পাওয়া', 'পাওয়া', 'চাই', 'লাগবে', 'দেখান', 'দিন', 'দেন',
            'কিনতে', 'কিনবো', 'কিনব', 'চাচ্ছি', 'নিতে', 'নিবো', 'নিব'
        }

        message_tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', text)
        message_tokens = [token for token in message_tokens if token not in filler_tokens]
        if not message_tokens:
            return matched_item

        item_tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', matched_item)
        item_token_set = set(item_tokens)
        extra_tokens = [token for token in message_tokens if token not in item_token_set]

        if not extra_tokens:
            return matched_item

        # Model/spec qualifiers should remain on ai_search flow.
        model_or_spec_cues = {
            'core', 'i3', 'i5', 'i7', 'i9', 'ryzen', 'gen', 'ddr',
            'gb', 'tb', 'ssd', 'hdd', 'inch', 'office', 'gaming', 'pro', 'max', 'ultra'
        }
        if any(token in model_or_spec_cues for token in extra_tokens):
            return None

        if any(re.search(r'\d', token) for token in extra_tokens):
            return None

        # Extra descriptive words mean this is a specific search request.
        return None

    def _is_fixed_price_query(self, message: str) -> bool:
        """Detect queries asking whether a product has a fixed price."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        fixed_price_terms = [
            'fixed dam', 'fixed price', 'fix dam', 'fix price', 'fixed rate',
            'ki fixed dam', 'ki fixed price', 'fixed', 'fix',
            'ফিক্সড দাম', 'ফিক্সড প্রাইস', 'নির্দিষ্ট দাম', 'স্থির দাম', 'ফিক্সড'
        ]

        query_markers = [
            'ki', 'কি', 'koto', 'কত', 'ase', 'ache', 'available', 'these', 'eigula', 'egula', 'egulo', 'eigula',
            'এইগুলা', 'এগুলা', 'এগুলো', 'egula'
        ]

        has_fixed = any(term in text for term in fixed_price_terms)
        has_query_marker = any(marker in text for marker in query_markers)
        return has_fixed and has_query_marker

    def _is_price_query(self, message: str) -> bool:
        """Detect generic price questions like 'price koto' that need context lookup."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        # Keep existing fixed-price flow unchanged.
        if self._is_fixed_price_query(message):
            return False

        price_patterns = [
            'price koto', 'dam koto', 'dham koto', 'koto price', 'koto dam',
            'er dam koto', 'etar dam koto', 'etar price koto',
            'দাম কত', 'প্রাইস কত', 'কত দাম', 'এটার দাম কত', 'এইটার দাম কত'
        ]
        return any(pattern in text for pattern in price_patterns)

    def _is_budget_only_query(self, message: str) -> bool:
        """Detect low-budget queries without any product mention."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        if self._is_fixed_price_query(message):
            return False

        if self._looks_like_product_query(message) or self._contains_configured_search_item(message):
            return False

        budget_terms = [
            'kom dame', 'কম দামে', 'কম দামের', 'low budget', 'budget',
            'cheap price', 'low price', 'cheap', 'সস্তা', 'কম বাজেটে', 'স্বল্প বাজেট'
        ]

        return any(term in text for term in budget_terms)

    def _is_deferred_reply_message(self, message: str) -> bool:
        """Detect messages like 'পরে জানাবো' and reply with a short thank-you."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        patterns = [
            'pore janabo', 'pore bolbo', 'poray janabo', 'later janabo',
            'পরে জানাবো', 'পরে জানাব', 'পরে বলবো', 'পরে বলব', 'পরে জানাই', 'পরে দিবো', 'পরে দিব'
        ]
        return any(pattern in text for pattern in patterns)

    def _is_later_followup_message(self, message: str) -> bool:
        """Detect user closing messages that indicate they will buy/check later."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        normalized = re.sub(r'\s+', ' ', text)
        patterns = [
            'i will buy later', 'will buy later', 'buy later',
            'see u later', 'see you later',
            'ok pore janbo', 'pore janbo', 'pore kinbo',
            'পরে জানবো', 'পরে জানব', 'পরে কিনবো', 'পরে কিনব'
        ]
        return any(pattern in normalized for pattern in patterns)

    def _build_later_followup_response(self) -> str:
        """Return standard Bangla closing line for later follow-up intent."""
        return "BDStall এর সাথে থাকার জন্য ধন্যবাদ স্যার, আর কিছু লাগলে আমাদের জানাবেন স্যার।"

    def _is_blocked_automated_message(self, message: str) -> bool:
        """Block known canned welcome templates so chatbot does not answer them."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        blocked_phrases = [
            'bdstall.com-এ আপনাকে স্বাগতম',
            'আপনার মেসেজ এর জন্য ধন্যবাদ',
            'খুব শীঘ্রই bdstall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে'
        ]

        # Require at least two matched fragments to avoid accidental blocking.
        return sum(1 for phrase in blocked_phrases if phrase in text) >= 2

    def _is_allowed_in_strict_mode(self, message: str) -> bool:
        """Temporary allow-list: search, greeting, and goodbye only."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        if self._looks_like_possible_product_signal(message):
            return True

        greeting_terms = {
            'hi', 'hello', 'hey', 'hlw', 'hai', 'salam', 'assalamu alaikum',
            'হাই', 'হ্যালো', 'হেলো', 'সালাম', 'আসসালামু আলাইকুম', 'আসসালামুয়ালাইকুম'
        }
        goodbye_terms = {
            'bye', 'goodbye', 'see you', 'take care', 'allah hafez', 'ok bye',
            'বিদায়', 'বিদায়', 'আল্লাহ হাফেজ', 'বাই', 'আবার দেখা হবে'
        }

        normalized = re.sub(r'\s+', ' ', text).strip()
        if normalized in greeting_terms or normalized in goodbye_terms:
            return True

        return False

    def _handle_intent_schema_flow(self, user_id: str, message: str, start_time: datetime) -> Optional[Dict[str, Any]]:
        """Handle request using strict title/price/compare schema as primary behavior."""
        text = str(message or '').strip()
        if not text:
            return None

        normalized = text.lower()

        if self._is_greeting_message(normalized):
            greeting_response = "আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?"
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=greeting_response,
                mode=ChatMode.AI,
                intent='greeting',
                products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if self._is_goodbye_message(normalized):
            goodbye_response = "ধন্যবাদ স্যার, ভালো থাকবেন।"
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=goodbye_response,
                mode=ChatMode.AI,
                intent='goodbye',
                products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if self._is_later_followup_message(message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=self._build_later_followup_response(),
                mode=ChatMode.AI,
                intent='deferred_follow_up_ack',
                products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        # Comparison-style short queries should stay in AI and avoid schema handoff.
        if self._is_comparison_query(message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=self._build_comparison_redirect_response(),
                mode=ChatMode.AI,
                intent='product_comparison',
                products=None,
                link_buttons=self._build_comparison_link_buttons(message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        if self._looks_like_order_buy_message(message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=self._build_order_guide_response(),
                mode=ChatMode.AI,
                intent='ordering_guide',
                products=None,
                link_buttons=[
                    {
                        'text': 'Shopping Guide',
                        'url': 'https://www.bdstall.com/blog/safe-shopping-guide/'
                    }
                ],
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        # Budget/number-only query: update price if we have previous context, else ask for title
        if self._is_price_only_query(text):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            
            # Extract new price and update intent_content if we have a stored title
            new_price = self._extract_price_text_for_intent(message)
            previous_intent = dict(self.user_intent_content.get(user_id) or {})
            
            if new_price and previous_intent.get('title'):
                # Update price and re-search with existing title
                previous_intent['price'] = new_price
                self.user_intent_content[user_id] = previous_intent
                
                # Build search keywords with updated intent_content and perform search
                search_keywords = self._build_search_keywords_from_intent_content(previous_intent)
                search_result = self._step2_search_database(search_keywords)
                products = search_result.get('products') or []
                
                if products and len(products) > 0:
                    # Format response with products
                    lines = []
                    for idx, product in enumerate(products[:3], 1):
                        product_title = str(product.get('title') or 'N/A').strip()
                        product_price = str(product.get('price') or 'N/A').strip()
                        product_url = str(product.get('url') or '').strip()
                        lines.append(f"{idx}. {product_title}")
                        lines.append(f"   মূল্য: {product_price}")
                        if product_url:
                            lines.append(f"   লিংক: {product_url}")
                    
                    self.user_product_context[user_id] = products[:3]
                    conversation_context = self._fetch_recent_chat_context(user_id, self.chatbot_history_limit) if self.groq_client else ''
                    formatted_result = self._step4_ai_format(
                        original_message=message,
                        database_message=f"Search results for {search_keywords}",
                        products=products[:3],
                        conversation_context=conversation_context
                    )
                    response_text = (formatted_result.get('response') or '').strip()
                    if not response_text:
                        response_lines = ["স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:", ""]
                        response_lines.extend(lines)
                        response_lines.extend(["", "আরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।"])
                        response_text = '\n'.join(response_lines)

                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=response_text,
                        mode=ChatMode.AI,
                        intent='schema_search',
                        products=products[:3],
                        search_keywords=search_keywords,
                        intent_content=previous_intent,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=AI_ACTIVE_STATUS
                    )
                else:
                    # No products found with new price
                    brand_label = str(previous_intent.get('brand') or '').strip()
                    title_label = str(previous_intent.get('title') or '').strip()
                    if brand_label or title_label:
                        no_result_response = (
                            f"দুঃখিত স্যার, এই মুহূর্তে {brand_label} {title_label} স্টকে নেই। "
                            "অন্য কোনো ব্র্যান্ড দেখাবো?"
                        ).strip()
                    else:
                        no_result_response = "দুঃখিত স্যার, এই মুহূর্তে কোনো প্রোডাক্ট পাওয়া যায়নি।"
                    
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=no_result_response,
                        mode=ChatMode.AI,
                        intent='schema_search_no_result',
                        products=None,
                        search_keywords=search_keywords,
                        intent_content=previous_intent,
                        processing_time=(datetime.now() - start_time).total_seconds(),
                        conversation_status=AI_ACTIVE_STATUS
                    )
            
            # No previous title, ask for product name
            return self._create_response(
                user_id=user_id,
                message=message,
                response="কোন প্রোডাক্টটি চাচ্ছেন স্যার?",
                mode=ChatMode.AI,
                intent='schema_need_title_price_only',
                products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        intent_obj = self._extract_intent_schema(message)
        intent_content = self._build_intent_content_from_schema(user_id, message, intent_obj)
        is_search_related = bool(
            intent_obj.get('title')
            or intent_obj.get('price')
            or intent_obj.get('compare')
            or intent_content.get('title')
            or intent_content.get('brand')
            or intent_content.get('price')
            or self._looks_like_possible_product_signal(message)
        )

        if not is_search_related:
            extracted = self._extract_search_entities(message)
            if extracted.get('brand'):
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="কোন প্রোডাক্টটি খুঁজছেন স্যার?",
                    mode=ChatMode.AI,
                    intent='schema_need_title',
                    products=None,
                    intent_content=intent_content,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )
            return self._handoff_to_human(
                user_id=user_id,
                message=message,
                start_time=start_time,
                intent='schema_non_search_handoff',
                response_text="স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।"
            )

        # Keep previous structured intent context for follow-ups like
        # "dell er ta dekhan to" where only brand should change.
        self._clear_product_search_cache(user_id, clear_pending=True)
        self.user_order_context[user_id] = False
        self.user_order_draft.pop(user_id, None)

        if not intent_content.get('title'):
            prompt = "কোন প্রোডাক্টটি খুঁজছেন স্যার?"

            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=prompt,
                mode=ChatMode.AI,
                intent='schema_need_title',
                products=None,
                intent_content=intent_content,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        title = str(intent_content.get('title') or '').strip()
        price = str(intent_content.get('price') or '').strip()
        brand = str(intent_content.get('brand') or '').strip()
        search_keywords = self._build_search_keywords_from_intent_content(intent_content)

        category_name = self._resolve_generic_category_query(text)
        should_use_category_template = bool(
            category_name
            and not brand
            and not price
            and (title.lower() == category_name.lower() if title else True)
        )
        if should_use_category_template:
            logger.info(
                "🚀 SCHEMA CATEGORY TEMPLATE: user_id=%s category=%s",
                user_id,
                category_name
            )
            category_response = self._fetch_category_intent_response(category_name)
            if category_response:
                self.user_modes[user_id] = ChatMode.AI
                self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=category_response,
                    mode=ChatMode.AI,
                    intent='category_search',
                    products=None,
                    search_keywords=category_name,
                    intent_content=intent_content,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )
            logger.info(
                "⚠️ SCHEMA CATEGORY TEMPLATE unavailable; fallback to ai_search for category=%s",
                category_name
            )

        if not search_keywords and title:
            search_keywords = title

        search_result = self._step2_search_database(search_keywords)
        products = search_result.get('products') or []

        if not products:
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            brand_label = str(intent_content.get('brand') or '').strip()
            title_label = str(intent_content.get('title') or '').strip()
            if brand_label or title_label:
                no_result_response = (
                    f"দুঃখিত স্যার, এই মুহূর্তে {brand_label} {title_label} স্টকে নেই। "
                    "অন্য কোনো ব্র্যান্ড দেখাবো?"
                ).strip()
            else:
                no_result_response = "দুঃখিত স্যার, এই মুহূর্তে কোনো প্রোডাক্ট পাওয়া যায়নি।"
            return self._create_response(
                user_id=user_id,
                message=message,
                response=no_result_response,
                mode=ChatMode.AI,
                intent='schema_search_no_result',
                products=None,
                search_keywords=search_keywords,
                intent_content=intent_content,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        self.user_product_context[user_id] = products[:3]

        lines = []

        for idx, product in enumerate(products[:3], 1):
            product_title = str(product.get('title') or 'N/A').strip()
            product_price = str(product.get('price') or 'N/A').strip()
            product_url = str(product.get('url') or '').strip()
            lines.append(f"{idx}. {product_title}")
            lines.append(f"   মূল্য: {product_price}")
            if product_url:
                lines.append(f"   লিংক: {product_url}")

        self.user_modes[user_id] = ChatMode.AI
        self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
        conversation_context = self._fetch_recent_chat_context(user_id, self.chatbot_history_limit) if self.groq_client else ''
        formatted_result = self._step4_ai_format(
            original_message=message,
            database_message=f"Search results for {search_keywords}",
            products=products[:3],
            conversation_context=conversation_context
        )
        response_text = (formatted_result.get('response') or '').strip()
        if not response_text:
            response_lines = ["স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:", ""]
            response_lines.extend(lines)
            response_lines.extend(["", "আরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।"])
            response_text = '\n'.join(response_lines)

        return self._create_response(
            user_id=user_id,
            message=message,
            response=response_text,
            mode=ChatMode.AI,
            intent='schema_search',
            products=products[:3],
            search_keywords=search_keywords,
            intent_content=intent_content,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def _extract_intent_schema(self, message: str) -> Dict[str, Optional[str]]:
        """Extract schema: title (mandatory), price (optional), compare (optional)."""
        text = str(message or '').strip()
        lowered = text.lower()

        title = self._resolve_title_from_search_reference(text)
        price = self._extract_schema_price(lowered)
        compare = self._extract_schema_compare(text)

        if not title:
            title = None

        return {
            'title': title or None,
            'price': price or None,
            'compare': compare or None,
        }

    def _is_price_only_query(self, message: str) -> bool:
        """Detect price-only queries like 'under 10k'/'under 20k' or multi-number budgets without product title."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        # If product title/signal exists, this is not a price-only query.
        if self._contains_configured_search_item(text) or self._looks_like_product_query(text):
            return False

        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        numbers = re.findall(r'\d+(?:\.\d+)?', text)

        # Any explicit price cue + at least one number is a price-only query.
        explicit_price_cues = [
            'under', 'budget', 'within', 'less than', 'below', 'k', 'tk', 'taka',
            'দাম', 'টাকা', 'বাজেট', 'মধ্যে', 'এর মধ্যে'
        ]
        if any(cue in text for cue in explicit_price_cues) and len(numbers) >= 1:
            return True

        # If user sends two or more numbers with no product title, treat as price intent.
        if len(numbers) >= 2:
            return True

        return False

    def _resolve_title_from_search_reference(self, message: str) -> Optional[str]:
        """Resolve title by matching known entries from search intent reference list."""
        text = self._normalize_product_query_text(message)
        normalized_message = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', text)
        normalized_message = re.sub(r'\s+', ' ', normalized_message).strip()
        padded_message = f" {normalized_message} "

        best_match = None
        best_len = 0
        for item in getattr(self, 'search_intent_items', []):
            normalized_item = re.sub(r'[^a-z0-9\u0980-\u09ff]+', ' ', str(item).lower())
            normalized_item = re.sub(r'\s+', ' ', normalized_item).strip()
            if not normalized_item:
                continue
            if f" {normalized_item} " in padded_message and len(normalized_item) > best_len:
                best_match = str(item).strip()
                best_len = len(normalized_item)

        return best_match

    def _extract_schema_price(self, lowered_message: str) -> Optional[str]:
        """Extract price intent value only when price trigger appears."""
        price_triggers = [
            'দাম', 'price', 'koto', 'কত', 'budget', 'কত টাকা', 'how much',
            'সস্তা', 'cheap', 'expensive', 'low budget', 'কম দামে'
        ]
        if not any(trigger in lowered_message for trigger in price_triggers):
            return None

        budget = self._extract_budget_range(lowered_message)
        if budget.get('min_price') is not None and budget.get('max_price') is not None:
            return f"{budget['min_price']}-{budget['max_price']}"
        if budget.get('max_price') is not None and budget.get('min_price') is None:
            return f"under {budget['max_price']}"

        return 'koto'

    def _extract_schema_compare(self, message: str) -> Optional[str]:
        """Extract compare target only when comparison trigger appears."""
        text = str(message or '').strip()
        lowered = text.lower()
        compare_triggers = ['vs', 'compare', 'difference', 'kon ta valo', 'কোনটা ভালো', 'better', 'তুলনা']
        if not any(trigger in lowered for trigger in compare_triggers):
            return None

        vs_match = re.search(r'\bvs\b\s+(.+)$', lowered)
        if vs_match:
            return vs_match.group(1).strip()

        compare_match = re.search(r'compare\s+(.+)$', lowered)
        if compare_match:
            return compare_match.group(1).strip()

        return 'target'

    def _is_greeting_message(self, lowered_message: str) -> bool:
        """Detect allowed greeting messages."""
        normalized = re.sub(r'\s+', ' ', str(lowered_message or '').strip())
        allowed = {
            'hi', 'hello', 'hey', 'hlw', 'hai', 'assalamualikum', 'assalamu alaikum',
            'হাই', 'হ্যালো', 'হেলো', 'সালাম', 'আসসালামু আলাইকুম', 'আসসালামুয়ালাইকুম'
        }
        return normalized in allowed

    def _is_goodbye_message(self, lowered_message: str) -> bool:
        """Detect allowed goodbye messages."""
        normalized = re.sub(r'\s+', ' ', str(lowered_message or '').strip())
        allowed = {
            'bye', 'goodbye', 'see you', 'take care', 'allah hafez', 'ok bye',
            'বিদায়', 'বিদায়', 'আল্লাহ হাফেজ', 'বাই', 'আবার দেখা হবে'
        }
        return normalized in allowed

    def _is_comparison_query(self, message: str) -> bool:
        """Detect compare/best-product questions like 'compare these' or 'which one is best'."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        # If user mentions alternatives with "or/অথবা" and product signal,
        # treat it as a comparison request (e.g., "hp or dell laptop").
        has_or_connector = (' or ' in f" {text} ") or (' অথবা ' in f" {text} ")
        if has_or_connector:
            has_product_signal = self._looks_like_possible_product_signal(message) or self._contains_configured_search_item(message)
            if has_product_signal:
                return True

        compare_terms = [
            'compare', 'comparison', 'compare these', 'compare this', 'which one is best',
            'best', 'better', 'good', 'best one', 'better one', 'good laptop', 'good one',
            'konta valo', 'konta bhalo', 'konta ভাল', 'konta ভালো',
            'konti valo', 'konti bhalo', 'konti ভাল', 'konti ভালো',
            'valo', 'bhalo', 'bhalo ta', 'bhalo konta',
            'tulona', 'compare koren', 'compare korba', 'tulona koren',
            'তুলনা', 'কোনটা ভালো', 'কোনটা ভাল', 'কোনটা best', 'কোনটা ভালো হবে',
            'কোনটি ভালো', 'কোনটি ভাল',
            'ভালো হবে', 'ভালো', 'ভাল', 'বেস্ট'
        ]

        has_compare_term = any(term in text for term in compare_terms)
        standalone_compare_terms = {
            'valo', 'bhalo', 'konta valo', 'konta bhalo',
            'konti valo', 'konti bhalo',
            'ভালো', 'ভাল', 'বেস্ট', 'best', 'good', 'better'
        }
        if text in standalone_compare_terms:
            return True

        has_product_signal = self._looks_like_possible_product_signal(message) or self._contains_configured_search_item(message)
        return has_compare_term and has_product_signal

    def _build_comparison_redirect_response(self) -> str:
        """Return standard comparison guidance with website URL for a single link button."""
        return "স্যার, আমাদের সকল প্রোডাক্টই ভালো। আপনি আমাদের ওয়েবসাইটের প্রোডাক্ট রেটিং এবং রিভিউ দেখে নিতে পারেন।"

    def _resolve_comparison_category(self, message: str) -> Optional[str]:
        """Resolve a best-effort category name from comparison message text."""
        text = self._normalize_product_query_text(message)
        if not text:
            return None

        category = self._resolve_generic_category_query(text)
        if category:
            return category

        category_terms = {
            'laptop': 'laptop',
            'ল্যাপটপ': 'laptop',
            'mobile': 'mobile',
            'phone': 'mobile',
            'ফোন': 'mobile',
            'মোবাইল': 'mobile',
            'watch': 'watch',
            'ঘড়ি': 'watch',
            'ঘড়ি': 'watch',
            'camera': 'camera',
            'কম্পিউটার': 'computer',
            'computer': 'computer',
            'monitor': 'monitor',
            'tablet': 'tablet',
            'printer': 'printer'
        }
        for term, normalized in category_terms.items():
            if term in text:
                return normalized

        best_match = self._find_best_search_item_match(text)
        if best_match:
            tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', best_match.lower())
            if tokens:
                return tokens[-1]

        return None

    def _fetch_category_link_from_api(self, category: str) -> Optional[str]:
        """Fetch category template from API and extract first URL for button use."""
        category_text = str(category or '').strip().lower()
        if not category_text:
            return None

        params = {
            'intent': 'category',
            'category': category_text,
            'key': self.api_key
        }
        started = datetime.now()

        try:
            response = requests.get(
                self.delivery_intent_api_url,
                params=params,
                timeout=10
            )
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)

            _log_api_call(
                api_name="ai_template_category_link_button",
                method="GET",
                url=self.delivery_intent_api_url,
                request_payload=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status="PASS" if response.status_code == 200 else "FAIL",
                response_preview=response.text
            )

            if response.status_code != 200:
                return None

            payload = response.json() if response.text else {}
            candidate_texts = []

            if isinstance(payload, str):
                candidate_texts.append(payload)
            elif isinstance(payload, dict):
                for key in ['response', 'message', 'template', 'text', 'content', 'data']:
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        candidate_texts.append(value)
                if len(payload) == 1:
                    only_value = next(iter(payload.values()))
                    if isinstance(only_value, str) and only_value.strip():
                        candidate_texts.append(only_value)

            for candidate in candidate_texts:
                match = re.search(r'https?://[^\s<>"\']+', str(candidate))
                if match:
                    return match.group(0).rstrip('.,!?)')

            return None
        except Exception:
            return None

    def _build_comparison_link_buttons(self, message: str) -> list:
        """Return single button with dynamic category URL for comparison guidance."""
        category = self._resolve_comparison_category(message)
        if category:
            api_url = self._fetch_category_link_from_api(category)
            if api_url:
                target_url = api_url
            else:
                slug = re.sub(r'\s+', '-', str(category).strip().lower())
                slug = re.sub(r'[^a-z0-9\u0980-\u09ff\-]', '', slug).strip('-')
                if slug:
                    target_url = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
                else:
                    target_url = 'https://www.bdstall.com/'
        else:
            target_url = 'https://www.bdstall.com/'

        return [
            {
                'text': 'Product Details',
                'url': target_url
            }
        ]

    def _build_order_guide_response(self) -> str:
        """Return standard order-guide text for buy/order help messages."""
        return (
            "স্যার এই লিংকে গিয়ে আপনি দেখতে পারেন কিভাবে অর্ডার অথবা বাই করা যায়"
        )

    def _reply_comparison_from_context(self, user_id: str) -> Optional[str]:
        """Create a simple comparison from the last shown products."""
        products = self.user_product_context.get(user_id, []) or []
        if len(products) < 2:
            selected = self.user_selected_product.get(user_id) or {}
            if selected:
                return self._build_comparison_redirect_response()
            return None

        comparison_items = []
        sortable_items = []
        for idx, product in enumerate(products[:3], 1):
            title = str(product.get('title') or f'প্রোডাক্ট {idx}').strip()
            price_text = str(product.get('price') or '').strip()
            numeric_price = self._parse_price_for_comparison(price_text)
            sortable_items.append((numeric_price if numeric_price is not None else 10**12, idx, title, price_text))

        sortable_items.sort(key=lambda item: item[0])
        cheapest = sortable_items[0]

        comparison_items.append("স্যার, আপনার দেখানো প্রোডাক্টগুলোর ছোট্ট তুলনা নিচে দিলাম:")
        for _, idx, title, price_text in sortable_items:
            display_price = price_text or 'দাম পাওয়া যায়নি'
            comparison_items.append(f"{idx}. {title} - {display_price}")

        comparison_items.append(f"দাম অনুযায়ী সবচেয়ে ভাল অপশন হতে পারে {cheapest[2]}।")
        comparison_items.append("আপনি চাইলে আমি বাজেট অনুযায়ীও বেছে দিতে পারি স্যার।")
        return "\n".join(comparison_items)

    def _parse_price_for_comparison(self, price_text: str) -> Optional[int]:
        """Convert a price string into an integer for comparison sorting."""
        text = str(price_text or '').strip().lower()
        if not text:
            return None

        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)', text)
        if not match:
            return None

        try:
            return int(float(match.group(1).replace(',', '')))
        except Exception:
            return None

    def _reply_price_from_context(self, user_id: str) -> Optional[str]:
        """Return product price from selected or recently suggested product context."""
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
            product = products[0]
            title = product.get('title') or 'এই প্রোডাক্টটির'
            price = product.get('price') or ''
            if price and str(price).strip().upper() != 'N/A':
                return f"জি স্যার, {title} এর দাম {price}।"
            return "স্যার, এই প্রোডাক্টটির দাম এখন দেখাতে পারছি না।"

        # Multiple products are in context. Return a compact price list so user can pick quickly.
        lines = ["স্যার, আপনি যে প্রোডাক্টগুলো দেখেছেন সেগুলোর দাম:"]
        for idx, product in enumerate(products[:5], 1):
            title = str(product.get('title') or f'প্রোডাক্ট {idx}').strip()
            price = str(product.get('price') or 'N/A').strip()
            if not price or price.upper() == 'N/A':
                price = 'দাম পাওয়া যায়নি'
            lines.append(f"{idx}. {title} - {price}")

        lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।")
        return "\n".join(lines)

        return None

    def _build_product_search_keywords(self, message: str) -> str:
        """Build cleaner search keywords from informal user queries."""
        text = self._normalize_product_query_text(message)
        if not text:
            return ''

        # Normalize frequent spaced brand/model phrases seen in Messenger typing.
        phrase_normalizations = {
            'elite book': 'elitebook',
            'think pad': 'thinkpad',
            'mac book': 'macbook'
        }
        for old_phrase, new_phrase in phrase_normalizations.items():
            text = text.replace(old_phrase, new_phrase)

        # Support Bangla digits in user input.
        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

        stop_words = [
            'ase', 'ache', 'apnar', 'amar', 'kase', 'kache', 'pls', 'please', 'need',
            'den', 'dao', 'diben', 'ase?', 'ache?', 'ki', 'dorkar', 'ekta', 'akta',
            'kindly', 'bhai', 'sir', 'স্যার', 'ভাই', 'আমার', 'আপনার', 'কাছে', 'আছে',
            'একটা', 'দেন', 'কি',
            'apnader', 'amader', 'eikhane', 'ekhane', 'ekhne', 'ekhane?', 'eikhane?',
            'apnadar', 'apnaderi', 'ekhankar', 'pawa', 'pabo',
            'cheap', 'low', 'budget', 'affordable', 'কম', 'দামে', 'বাজেটে', 'সস্তা'
        ]

        words = []
        for token in re.split(r'\s+', text):
            clean = re.sub(r'[^a-z0-9\u0980-\u09ff]', '', token)
            if not clean or clean in stop_words:
                continue
            words.append(clean)

        keywords = ' '.join(words).strip()
        return keywords or text

    def _extract_search_tokens(self, text: str) -> list[str]:
        """Extract meaningful query tokens for relevance filtering."""
        normalized = self._normalize_product_query_text(text)
        if not normalized:
            return []

        normalized = normalized.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        raw_tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', normalized)
        stop = {
            'and', 'or', 'the', 'a', 'an', 'for',
            'ase', 'ache', 'kase', 'kache', 'apnar', 'amar', 'ami', 'amake',
            'sir', 'bhai', 'please', 'need', 'ki', 'dorkar', 'ekta', 'akta',
            'taka', 'tk', 'price', 'dam',
            'আছে', 'কাছে', 'আপনার', 'আমার', 'একটা', 'দাম', 'টাকা'
        }

        tokens = [t for t in raw_tokens if len(t) > 1 and t not in stop]
        # Keep order but remove duplicates.
        deduped = list(dict.fromkeys(tokens))
        return deduped

    def _build_broader_search_keywords(self, keywords: str, original_message: str) -> Optional[str]:
        """Create a broader query when exact terms return no products."""
        base_tokens = self._extract_search_tokens(keywords)
        if not base_tokens:
            base_tokens = self._extract_search_tokens(original_message)
        if not base_tokens:
            return None

        product_terms = {
            'laptop', 'phone', 'mobile', 'iphone', 'computer', 'pc', 'monitor', 'tablet',
            'ল্যাপটপ', 'ফোন', 'মোবাইল', 'কম্পিউটার'
        }
        brand_terms = {
            'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung', 'xiaomi',
            'realme', 'oppo', 'vivo', 'msi', 'huawei'
        }

        selected: list[str] = []
        brand = next((token for token in base_tokens if token in brand_terms), None)
        product = next((token for token in base_tokens if token in product_terms), None)

        if brand:
            selected.append(brand)
        if product and product not in selected:
            selected.append(product)

        for token in base_tokens:
            if token in selected:
                continue
            if len(token) > 2:
                selected.append(token)
                break

        if not selected:
            selected = base_tokens[:2]

        broader = ' '.join(selected).strip()
        if not broader:
            return None

        if broader.lower() == str(keywords or '').strip().lower():
            return None
        return broader
    
    def _step2_search_database(self, keywords: str) -> Dict[str, Any]:
        """
        STEP 2-3: Search BDStall API with keywords and format as database message
        """
        try:
            import requests
            
            # Clean keywords for API
            search_term = self._normalize_search_keywords_for_api(keywords)
            
            logger.info(f"🔍 Searching BDStall API with term: {search_term}")
            
            # Call BDStall API
            params = {
                'term': search_term,
                'key': self.api_key
            }

            started = datetime.now()

            response = requests.get(
                self.api_url,
                params=params,
                timeout=10
            )
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)

            _log_api_call(
                api_name="ai_search",
                method="GET",
                url=self.api_url,
                request_payload=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status="PASS" if response.status_code == 200 else "FAIL",
                response_preview=response.text
            )
            
            if response.status_code != 200:
                logger.error(f"❌ API returned status {response.status_code}")
                return {
                    'products_found': 0,
                    'products': [],
                    'database_message': ''
                }
            
            data = response.json()
            
            # Parse response: {"getListingItem": [total, [products], "Item 1-5 of total"]}
            if not data.get('getListingItem') or len(data['getListingItem']) < 2:
                logger.warning("⚠️ No products found in API response")
                return {
                    'products_found': 0,
                    'products': [],
                    'database_message': ''
                }
            
            total_count = data['getListingItem'][0]
            products_array = data['getListingItem'][1]
            
            if not products_array:
                return {
                    'products_found': 0,
                    'products': [],
                    'database_message': ''
                }
            
            # Extract price limit if mentioned in keywords
            import re
            price_match = re.search(r'(\d+)k?', keywords.lower())
            max_price = None
            if price_match:
                price_value = int(price_match.group(1))
                if price_value < 1000:  # Likely in thousands (10k = 10000)
                    max_price = price_value * 1000
                else:
                    max_price = price_value
            
            query_tokens = self._extract_search_tokens(search_term)

            # Filter products by query relevance first, then price.
            scored_products = []
            for product in products_array[:20]:  # Take top 20 first
                try:
                    title = str(product.get('ListingTitle', '')).lower()
                    description = str(product.get('ListingDescription', '')).lower()
                    haystack = f"{title} {description}"

                    token_hits = 0
                    if query_tokens:
                        token_hits = sum(1 for token in query_tokens if token in haystack)
                        # If we have query tokens, require at least one match to avoid irrelevant listings.
                        if token_hits == 0:
                            continue

                    product_price = int(product.get('app_ListingPrice', 999999))
                    if max_price and product_price > max_price:
                        continue

                    # Prefer products with more token matches.
                    scored_products.append((token_hits, product))

                except Exception:
                    continue

            # If no relevant results matched query tokens, return empty to avoid wrong products.
            if query_tokens and not scored_products:
                logger.info("⚠️ No relevant product matched query tokens: %s", query_tokens)
                return {
                    'products_found': 0,
                    'products': [],
                    'database_message': ''
                }

            # Sort by relevance score desc and take top candidates.
            scored_products.sort(key=lambda item: item[0], reverse=True)
            filtered_products = [item[1] for item in scored_products]

            if not query_tokens:
                # No meaningful tokens - keep behavior close to previous logic with price filtering only.
                filtered_products = []
                for product in products_array[:20]:
                    try:
                        product_price = int(product.get('app_ListingPrice', 999999))
                        if max_price and product_price > max_price:
                            continue
                        filtered_products.append(product)
                    except Exception:
                        continue

            # Take top 5
            top_products = filtered_products[:5]

            if not top_products:
                return {
                    'products_found': 0,
                    'products': [],
                    'database_message': ''
                }

            logger.info(f"✅ Found {len(top_products)} products (Total: {total_count})")

            # Format as database message
            database_message = f"পণ্য তালিকা (মোট {total_count} পণ্য পাওয়া গেছে):\n\n"
            products_list = []

            for i, product in enumerate(top_products, 1):
                title = product.get('ListingTitle', 'N/A')
                price = product.get('ListingPrice', 'N/A')
                original_price = product.get('app_ListingOriginalPrice', '')
                discount = product.get('ListingDiscountPercentage', 0)
                url = product.get('ListingURL', '')
                description = product.get('ListingDescription', '')[:100]

                database_message += f"{i}. {title}\n"
                database_message += f"   মূল্য: {price}"

                if discount > 0:
                    database_message += f" (ছাড় {discount}%)"

                database_message += "\n"

                database_message += f"   লিংক: {url}\n\n"

                products_list.append({
                    'title': title,
                    'price': price,
                    'original_price': original_price,
                    'discount': discount,
                    'url': url,
                    'image': product.get('ListingThumbAvator', '')
                })

            return {
                'products_found': len(top_products),
                'total_products': total_count,
                'products': products_list,
                'database_message': database_message
            }
        
        except Exception as e:
            _log_api_call(
                api_name="ai_search",
                method="GET",
                url=self.api_url,
                request_payload={"term": keywords, "key": self.api_key},
                status_code=0,
                duration_ms=0,
                status="FAIL",
                response_preview=str(e)
            )
            logger.error(f"❌ BDStall API search failed: {e}")
            return {
                'products_found': 0,
                'products': [],
                'database_message': ''
            }

    def _normalize_search_keywords_for_api(self, keywords: str) -> str:
        """Normalize user search keywords so budget adjectives don't hurt API matching."""
        text = str(keywords or '').strip().lower()
        if not text:
            return ''

        text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
        tokens = re.findall(r'[a-z0-9\u0980-\u09ff]+', text)

        drop_tokens = {
            'cheap', 'low', 'budget', 'affordable', 'best', 'good',
            'কম', 'দামে', 'বাজেটে', 'সস্তা', 'ভালো', 'ভাল',
            'taka', 'tk', 'টাকা'
        }

        kept = [token for token in tokens if token not in drop_tokens]
        normalized = ' '.join(kept).strip()
        return normalized or text

    def _build_category_link_response(self, category: str) -> Optional[str]:
        """Build fixed category message with direct category URL."""
        category_text = str(category or '').strip().lower()
        if not category_text:
            return None

        slug = re.sub(r'\s+', '-', category_text)
        slug = re.sub(r'[^a-z0-9\u0980-\u09ff\-]', '', slug)
        slug = slug.strip('-')
        if not slug:
            return None

        category_url = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
        return (
            f"আপনি {category_text} ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন।\n"
            f"এই লিংকে ক্লিক করুন:\n{category_url}"
        )

    def _fetch_category_intent_response(self, category: str) -> Optional[str]:
        """Return fixed category-link text; fallback to BDStall template API when needed."""
        direct_response = self._build_category_link_response(category)
        if direct_response:
            return direct_response

        params = {
            'intent': 'category',
            'category': str(category or '').strip().lower(),
            'key': self.api_key
        }
        started = datetime.now()

        try:
            response = requests.get(
                self.delivery_intent_api_url,
                params=params,
                timeout=10
            )
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            status = "PASS" if response.status_code == 200 else "FAIL"

            _log_api_call(
                api_name="ai_template_category",
                method="GET",
                url=self.delivery_intent_api_url,
                request_payload=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status=status,
                response_preview=response.text
            )

            if status == "FAIL":
                logger.warning(
                    "⚠️ Category intent API failed with status %s for category=%s",
                    response.status_code,
                    category
                )
                return None

            data = response.json()

            if isinstance(data, str):
                return data.strip() or None

            if isinstance(data, dict):
                if data.get('success') is False:
                    return None

                for key in [
                    'response',
                    'message',
                    'template',
                    'text',
                    'content',
                    'data'
                ]:
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

                if len(data) == 1:
                    only_value = next(iter(data.values()))
                    if isinstance(only_value, str) and only_value.strip():
                        return only_value.strip()

            logger.warning("⚠️ Category intent API returned unexpected payload format")
            return None

        except Exception as e:
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                api_name="ai_template_category",
                method="GET",
                url=self.delivery_intent_api_url,
                request_payload=params,
                status_code=0,
                duration_ms=duration_ms,
                status="FAIL",
                response_preview=str(e)
            )
            logger.warning("⚠️ Category intent API call failed: %s", e)
            return None

    def _fetch_delivery_intent_response(self) -> Optional[str]:
        """Fetch delivery template text from BDStall intent API."""
        params = {
            'intent': 'delivery',
            'key': self.api_key
        }
        started = datetime.now()

        try:
            response = requests.get(
                self.delivery_intent_api_url,
                params=params,
                timeout=10
            )
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            status = "PASS" if response.status_code == 200 else "FAIL"

            _log_api_call(
                api_name="ai_template_delivery",
                method="GET",
                url=self.delivery_intent_api_url,
                request_payload=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status=status,
                response_preview=response.text
            )

            if status == "FAIL":
                logger.warning(
                    "⚠️ Delivery intent API failed with status %s",
                    response.status_code
                )
                return None

            data = response.json()

            if isinstance(data, str):
                return data.strip() or None

            if isinstance(data, dict):
                for key in [
                    'response',
                    'message',
                    'template',
                    'text',
                    'content',
                    'data'
                ]:
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

                if len(data) == 1:
                    only_value = next(iter(data.values()))
                    if isinstance(only_value, str) and only_value.strip():
                        return only_value.strip()

            logger.warning("⚠️ Delivery intent API returned unexpected payload format")
            return None

        except Exception as e:
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                api_name="ai_template_delivery",
                method="GET",
                url=self.delivery_intent_api_url,
                request_payload=params,
                status_code=0,
                duration_ms=duration_ms,
                status="FAIL",
                response_preview=str(e)
            )
            logger.warning("⚠️ Delivery intent API call failed: %s", e)
            return None

    def _fetch_order_intent_response(self, listing_id: str, template_intent: str = 'order') -> Optional[str]:
        """Fetch order/buy template text from BDStall intent API using listing ID."""
        normalized_intent = str(template_intent or 'order').strip().lower()
        if normalized_intent not in {'order', 'buy'}:
            normalized_intent = 'order'

        request_url = (
            f"{self.order_intent_api_url}"
            f"intent={normalized_intent}&id={listing_id}&key={self.api_key}"
        )
        started = datetime.now()

        try:
            response = requests.get(
                request_url,
                timeout=10
            )
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            status = "PASS" if response.status_code == 200 else "FAIL"

            _log_api_call(
                api_name="ai_template_order",
                method="GET",
                url=request_url,
                request_payload={
                    'intent': normalized_intent,
                    'id': listing_id,
                    'key': self.api_key
                },
                status_code=response.status_code,
                duration_ms=duration_ms,
                status=status,
                response_preview=response.text
            )

            if status == "FAIL":
                logger.warning(
                    "⚠️ Order intent API failed with status %s for intent=%s listing_id=%s",
                    response.status_code,
                    normalized_intent,
                    listing_id
                )
                return None

            data = response.json()

            if isinstance(data, str):
                return data.strip() or None

            if isinstance(data, dict):
                for key in [
                    'response',
                    'message',
                    'template',
                    'text',
                    'content',
                    'data'
                ]:
                    value = data.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

                if len(data) == 1:
                    only_value = next(iter(data.values()))
                    if isinstance(only_value, str) and only_value.strip():
                        return only_value.strip()

            logger.warning("⚠️ Order intent API returned unexpected payload format")
            return None

        except Exception as e:
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                api_name="ai_template_order",
                method="GET",
                url=request_url,
                request_payload={
                    'intent': normalized_intent,
                    'id': listing_id,
                    'key': self.api_key
                },
                status_code=0,
                duration_ms=duration_ms,
                status="FAIL",
                response_preview=str(e)
            )
            logger.warning("⚠️ Order intent API call failed: %s", e)
            return None
    
    def _step4_ai_format(
        self,
        original_message: str,
        database_message: Optional[str],
        products: Optional[list],
        conversation_context: str = ''
    ) -> Dict[str, Any]:
        """
        STEP 4: Send database message to AI for final formatting
        """
        try:
            if database_message and products:
                if self.groq_client:
                    compact_products = []
                    for idx, product in enumerate(products[:5], 1):
                        compact_products.append({
                            'index': idx,
                            'title': product.get('title', ''),
                            'price': product.get('price', ''),
                            'url': product.get('url', '')
                        })

                    prompt = f"""তুমি BDStall.com এর একজন সহায়ক বাংলা সেলস অ্যাসিস্ট্যান্ট।

Recent chat context:
{conversation_context or 'N/A'}

User latest message:
{original_message}

Available products (top matches):
{json.dumps(compact_products, ensure_ascii=False)}

Instructions:
- Context পড়ে user intent বুঝে উত্তর দাও।
- ৩টি প্রোডাক্ট সুন্দরভাবে 1-3 লিস্টে দাও (title, price, link)।
- একটি natural, friendly Bengali intro লেখো যা user message অনুযায়ী বদলাবে.
- একই opening line বারবার ব্যবহার কোরো না.
- শেষে একটি short helpful closing দাও, কিন্তু একদম একই sentence repeat কোরো না.
- ভদ্র, সংক্ষিপ্ত, বিক্রয় সহায়ক টোন রাখো.
- অপ্রয়োজনীয় তথ্য দিও না।
"""

                    response = self.groq_client.chat.completions.create(
                        model=self.groq_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.5,
                        max_tokens=700
                    )

                    ai_response = response.choices[0].message.content.strip()
                    if ai_response:
                        return {
                            'success': True,
                            'response': ai_response
                        }

                # Fallback deterministic product formatting if Groq unavailable.
                seed_text = f"{original_message or ''} {database_message or ''}"
                seed_value = sum(ord(char) for char in seed_text)
                intro_options = [
                    "স্যার, মিল পাওয়া কিছু প্রোডাক্ট দিলাম:",
                    "আপনার জন্য এই অপশনগুলো পেলাম:",
                    "দেখে নিতে পারেন এই প্রোডাক্টগুলো:"
                ]
                closing_options = [
                    "চাইলে আরও অপশন খুঁজে দিচ্ছি.",
                    "আরও দেখাতে পারি, বললেই হবে.",
                    "আরও কিছু লাগলে জানাবেন."
                ]
                response_text = f"{intro_options[seed_value % len(intro_options)]}\n\n"
                for idx, product in enumerate(products[:3], 1):
                    title = product.get('title', 'N/A')
                    price = product.get('price', 'N/A')
                    url = product.get('url', '')

                    response_text += f"{idx}. {title}\n"
                    response_text += f"মূল্য: {price}\n"
                    if url:
                        response_text += f"লিংক: {url}\n"
                    response_text += "\n"

                response_text += closing_options[(seed_value // 3) % len(closing_options)]
                return {
                    'success': True,
                    'response': response_text
                }

            if not self.groq_client:
                return {'success': False, 'error': 'Groq not available'}

            # General query - Use AI with recent chat context.
            prompt = f"""তুমি একজন বন্ধুত্বপূর্ণ বাংলা চ্যাটবট। BDStall.com এর হয়ে উত্তর দাও।

Recent chat context:
{conversation_context or 'N/A'}

Latest user message:
{original_message}

Rules:
- Context পড়ে উত্তর দাও।
- আগের কথার সাথে connection রাখো।
- সংক্ষিপ্ত, স্পষ্ট এবং সহায়ক বাংলা উত্তর দাও।
"""

            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )

            ai_response = response.choices[0].message.content.strip()

            return {
                'success': True,
                'response': ai_response
            }
        
        except Exception as e:
            logger.error(f"❌ AI formatting failed: {e}")

            # Never hand off to human when we already have product results.
            # Return deterministic product formatting as a safe fallback.
            if products:
                seed_text = f"{original_message or ''} {database_message or ''}"
                seed_value = sum(ord(char) for char in seed_text)
                intro_options = [
                    "স্যার, মিল পাওয়া কিছু প্রোডাক্ট দিলাম:",
                    "আপনার জন্য এই অপশনগুলো পেলাম:",
                    "দেখে নিতে পারেন এই প্রোডাক্টগুলো:"
                ]
                closing_options = [
                    "চাইলে আরও অপশন খুঁজে দিচ্ছি.",
                    "আরও দেখাতে পারি, বললেই হবে.",
                    "আরও কিছু লাগলে জানাবেন."
                ]
                response_text = f"{intro_options[seed_value % len(intro_options)]}\n\n"
                for idx, product in enumerate(products[:3], 1):
                    title = product.get('title', 'N/A')
                    price = product.get('price', 'N/A')
                    url = product.get('url', '')

                    response_text += f"{idx}. {title}\n"
                    response_text += f"মূল্য: {price}\n"
                    if url:
                        response_text += f"লিংক: {url}\n"
                    response_text += "\n"

                response_text += closing_options[(seed_value // 3) % len(closing_options)]
                return {
                    'success': True,
                    'response': response_text
                }

            return {'success': False, 'error': str(e)}

    def _get_order_info_template(self, user_id: str, message: str, intent_hint: str = 'order') -> str:
        """Fetch order/buy template from API using conversation context and dynamic listing ID."""
        listing_id = self._resolve_order_listing_id(user_id, message)
        if listing_id:
            api_template = self._fetch_order_intent_response(listing_id, intent_hint)
            if api_template:
                logger.info(
                    "✅ %s template fetched from API for listing_id=%s",
                    intent_hint,
                    listing_id
                )
                return api_template

            logger.warning(
                "⚠️ %s template API returned empty for listing_id=%s",
                intent_hint,
                listing_id
            )

        return (
            "আপনি কোন প্রোডাক্টটি অর্ডার/বাই করতে চান তার লিংক বা প্রোডাক্ট নম্বর দিন। "
            "আমি সাথে সাথে অর্ডার টেমপ্লেট এনে দিচ্ছি।"
        )

    def _resolve_order_template_intent(self, message: str) -> str:
        """Choose API template intent between 'order' and 'buy' from message text."""
        text = str(message or '').lower()
        buy_markers = [
            'buy', 'kinbo', 'kinte', 'kinte pari', 'kivabe kinte pari', 'kibabe kinte pari',
            'কিনবো', 'কিনব', 'কিনতে', 'কিনতে পারি', 'কিভাবে কিনবো', 'কিভাবে কিনতে পারি',
            'kibabe kinbo', 'kivabe kinbo'
        ]
        return 'buy' if any(marker in text for marker in buy_markers) else 'order'

    def _looks_like_order_buy_message(self, message: str) -> bool:
        """Detect order/buy intent phrases even if upstream intent classifier misses them."""
        text = str(message or '').lower()
        if not text.strip():
            return False

        markers = [
            'order', 'buy', 'order korbo', 'kibabe order korbo', 'kivabe order korbo',
            'কিভাবে অর্ডার', 'অর্ডার করবো', 'অর্ডার করব', 'অর্ডার দিব', 'অর্ডার দেব',
            'কিনবো', 'কিনব', 'কিনতে চাই', 'কিনতে পারি', 'কিভাবে কিনবো', 'কিভাবে কিনব', 'কিভাবে কিনতে পারি',
            'kinte pari', 'kivabe kinte pari', 'kibabe kinte pari', 'kibabe kinbo', 'kivabe kinbo'
        ]
        return any(marker in text for marker in markers)

    def _resolve_order_listing_id(self, user_id: str, message: str) -> Optional[str]:
        """Resolve listing ID from user message URL, selected product, or latest product context."""
        message_text = str(message or '').strip()

        # Priority 1: listing ID present in current message (usually from BDStall URL).
        direct_id = self._extract_listing_id_from_url(message_text)
        if direct_id:
            return direct_id

        # Priority 2: selected product from prior numbered selection.
        selected_product = self.user_selected_product.get(user_id) or {}
        selected_url = str(selected_product.get('url') or '').strip()
        selected_id = self._extract_listing_id_from_url(selected_url)
        if selected_id:
            return selected_id

        # Priority 3: latest shown product list in current conversation.
        user_products = self.user_product_context.get(user_id) or []
        if user_products:
            first_url = str(user_products[0].get('url') or '').strip()
            first_id = self._extract_listing_id_from_url(first_url)
            if first_id:
                return first_id

        return None

    def _get_irrelevant_handoff_message(self) -> str:
        """Bangla handoff message for irrelevant or out-of-scope customer queries."""
        return (
            "ধন্যবাদ আপনার মেসেজের জন্য। মনে হচ্ছে আপনার বিষয়টি আমাদের সাপোর্ট টিম সরাসরি দেখলে ভালো হবে। "
            "অনুগ্রহ করে কিছুক্ষণ অপেক্ষা করুন, আমাদের একজন প্রতিনিধি খুব শীঘ্রই আপনাকে সহায়তা করবেন।"
        )

    def _handoff_to_human(
        self,
        user_id: str,
        message: str,
        start_time: datetime,
        intent: Optional[str],
        products: Optional[list] = None,
        response_text: Optional[str] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Switch a conversation to human support and return standardized response."""
        # Central guard: product-like queries should never be hard-handed off.
        if self._looks_like_possible_product_signal(message):
            self.user_modes[user_id] = ChatMode.AI
            self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
            return self._create_response(
                user_id=user_id,
                message=message,
                response=(
                    "জি স্যার, আমি প্রোডাক্ট সার্চ করে দেখছি। "
                    "ব্র্যান্ড/মডেল/বাজেট দিলে আরও ভালো ফল পাবেন।"
                ),
                mode=ChatMode.AI,
                intent='product_search_clarification',
                products=products,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error=error,
                conversation_status=AI_ACTIVE_STATUS
            )

        self.user_modes[user_id] = ChatMode.HUMAN
        self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
        self.user_order_context[user_id] = False
        self.user_order_draft.pop(user_id, None)
        self.user_pending_product_query.pop(user_id, None)
        self._notify_assign_agent(user_id)

        return self._create_response(
            user_id=user_id,
            message=message,
            response=response_text or "স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
            mode=ChatMode.HUMAN,
            intent=intent,
            products=products,
            processing_time=(datetime.now() - start_time).total_seconds(),
            error=error,
            conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
        )

    def _extract_product_selection(self, message: str) -> Optional[int]:
        """Extract product selection number (1-5) from short follow-up messages."""
        normalized = str(message or "").strip()
        if not normalized:
            return None

        # Do not treat order-form style text as a product-selection message.
        if self._extract_order_detail_fields(normalized):
            return None

        # Support Bangla numerals in user input.
        bangla_to_ascii = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
        normalized = normalized.translate(bangla_to_ascii)
        normalized_lower = normalized.lower()

        # Direct single-number selection, e.g. "4" or "5".
        direct_match = re.fullmatch(r"\s*([1-5])\s*", normalized_lower)
        if direct_match:
            return int(direct_match.group(1))

        number_matches = re.findall(r"\b([1-5])\b", normalized_lower)
        if len(number_matches) != 1:
            return None

        # Require selection cues for longer messages to avoid false positives.
        selection_cues = [
            'number', 'no', 'option', 'choose', 'select', 'selected', 'pick',
            'নম্বর', 'নাম্বার', 'পছন্দ', 'নিবো', 'নেবো', 'নিচ্ছি', 'নিলাম'
        ]
        if len(normalized_lower.split()) <= 3 or any(cue in normalized_lower for cue in selection_cues):
            return int(number_matches[0])

        return None

    def _is_order_confirmation_message(self, message: str) -> bool:
        """Detect short confirmation replies after product selection."""
        text = str(message or "").strip().lower()
        if not text:
            return False

        # Fresh product-search queries should never be treated as order confirmation.
        if self._looks_like_product_query(text):
            return False

        # Confirmation replies are usually short acknowledgements.
        if len(text.split()) > 4:
            return False

        positive_tokens = {
            'yes', 'y', 'ok', 'okay', 'hea', 'hya', 'ha', 'nibo', 'nib', 'nibo.',
            'nibo!', 'nibo?', 'dekhan', 'dekhao', 'dekhun', 'lagbe', 'nei', 'nibo bhai',
            'yes please', 'please', 'ji', 'jii', 'hmm', 'hm', 'sure'
        }

        if text in positive_tokens:
            return True

        confirmation_patterns = [
            r'\b(yes|ok|okay|sure|please)\b',
            r'\b(hea|hya|ha|ji)\b',
            r'\b(nibo|nib|lagbe|dekhan|dekhao|dekhun)\b',
            r'\b(নে[বভ]|নিব|নিবো|লাগবে|দেখান|দেখাও|দেখুন)\b'
        ]

        return any(re.search(pattern, text) for pattern in confirmation_patterns)

    def _extract_listing_id_from_url(self, url: str) -> Optional[str]:
        """Extract trailing numeric listing ID from BDStall details URL.

        Example:
        https://www.bdstall.com/details/hp-15s-du1014tu-core-i3-10th-gen-156-1tb-hdd-laptop-48723/
        -> 48723
        """
        normalized_url = str(url or "").strip()
        if not normalized_url:
            return None

        match = re.search(r'-(\d+)(?:/)?$', normalized_url)
        if match:
            return match.group(1)

        fallback_match = re.search(r'(\d+)(?:/)?$', normalized_url)
        if fallback_match:
            return fallback_match.group(1)

        return None

    def _format_selected_product_response(self, product: Dict[str, Any], selected_index: int) -> str:
        """Build a conversational response after user selects a product by number."""
        title = product.get('title', 'N/A')
        price = product.get('price', 'N/A')
        description = product.get('description', '')
        url = product.get('url', '')

        response_text = f"দারুণ পছন্দ স্যার। আপনি {selected_index} নম্বর প্রোডাক্টটি নির্বাচন করেছেন।\n\n"
        response_text += f"{selected_index}. {title}\n"
        response_text += f"মূল্য: {price}\n"

        if description:
            response_text += f"বিবরণ: {description}\n"

        if url:
            response_text += f"লিংক: {url}\n"

        response_text += "\nআপনি চাইলে আমি এখন এই প্রোডাক্টটি অর্ডার করার ধাপগুলোও বলে দিতে পারি।"
        return response_text

    def _extract_order_detail_fields(self, message: str) -> Dict[str, str]:
        """Extract any order-detail fields from a message.

        Supports compact input where fields may be adjacent, e.g.
        'Phone Number: 017...Address: Uttara'.
        Supports separators: ':', ';', '=' and '-'.
        """
        text = str(message or "").strip()
        if not text:
            return {}

        # Keep longer labels first so "product name" is matched before "name".
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
            (r'name', 'name')
        ]

        labels_regex = "|".join(label for label, _ in label_to_key)
        pattern = re.compile(rf'(?i)(?P<label>{labels_regex})\s*[:;=\-]\s*', re.DOTALL)

        matches = list(pattern.finditer(text))
        if not matches:
            return {}

        extracted: Dict[str, str] = {}
        for idx, match in enumerate(matches):
            raw_label = match.group('label').strip().lower()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            value = re.sub(r'\s+', ' ', text[start:end]).strip()
            if not value:
                continue

            mapped_key = None
            for label_regex, key in label_to_key:
                if re.fullmatch(label_regex, raw_label, flags=re.IGNORECASE):
                    mapped_key = key
                    break

            if mapped_key and mapped_key not in extracted:
                extracted[mapped_key] = value

        return extracted

    def _extract_order_details(self, message: str) -> Optional[Dict[str, str]]:
        """Extract complete order details from a single message."""
        extracted = self._extract_order_detail_fields(message)

        required_keys = ['name', 'phone_number', 'address', 'product_name', 'quantity']
        if not all(k in extracted and extracted[k] for k in required_keys):
            return None

        if not re.search(r'\d{10,15}', extracted['phone_number']):
            return None

        return extracted

    def _build_missing_order_fields_prompt(self, missing_keys: list) -> str:
        """Return a clear prompt with only missing order fields."""
        labels = {
            'name': 'Name',
            'phone_number': 'Phone Number',
            'address': 'Address',
            'product_name': 'Product Name',
            'quantity': 'Quantity'
        }
        missing_lines = "\n".join(f"{labels[k]}:" for k in missing_keys if k in labels)

        return (
            "অর্ডার সম্পন্ন করতে শুধু বাকি তথ্যগুলো দিন:\n\n"
            f"{missing_lines}\n\n"
            "ধন্যবাদ।"
        )

    def _build_link_buttons(self, products: Optional[list]) -> list:
        """Build UI-friendly link button metadata from product URLs."""
        if not products:
            return []

        buttons = []
        seen_urls = set()
        for index, product in enumerate(products[:5], 1):
            product = product or {}
            url = str((product or {}).get('url') or '').strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            buttons.append({
                'index': index,
                'title': str(product.get('title') or product.get('name') or 'Product').strip(),
                'price': str(product.get('price') or '').strip(),
                'text': 'View Product',
                'url': url
            })

        return buttons
    
    def _create_response(
        self,
        user_id: str,
        message: str,
        response: str,
        mode: ChatMode,
        intent: Optional[str],
        products: Optional[list],
        search_keywords: Optional[str] = None,
        link_buttons: Optional[list] = None,
        intent_content: Optional[Dict[str, Any]] = None,
        processing_time: float = 0.0,
        error: Optional[str] = None,
        conversation_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create standardized JSON response with mode
        """
        if intent:
            self.user_last_intent[user_id] = str(intent)
        self._save_state()
        trimmed_products = products[:5] if products else None
        resolved_intent_content = dict(intent_content or self.user_intent_content.get(user_id) or {})
        return {
            "success": mode == ChatMode.AI,
            "user_id": user_id,
            "message": message,
            "response": response,
            "mode": mode.value,  # Always show: "ai" or "human"
            "intent": intent,
            "search_keywords": search_keywords,
            "products_found": len(products) if products else 0,
            "products": trimmed_products,  # Keep top 5 for follow-up selection
            "link_buttons": link_buttons if link_buttons is not None else self._build_link_buttons(trimmed_products),
            "intent_content": resolved_intent_content,
            "conversation_status": conversation_status or self.user_conversation_status.get(
                user_id,
                HUMAN_SUPPORT_REQUIRED_STATUS if mode == ChatMode.HUMAN else AI_ACTIVE_STATUS
            ),
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
    
    def switch_to_human(self, user_id: str):
        """Manually switch user to HUMAN mode"""
        self.user_modes[user_id] = ChatMode.HUMAN
        self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
        self._save_state()
        self._notify_assign_agent(user_id)
        logger.info(f"👤 User {user_id} switched to HUMAN mode")

    def _notify_assign_agent(self, user_id: str) -> bool:
        """Notify BDStall that a user has been assigned to a human agent."""
        payload = {
            "key": self.assign_agent_api_key,
            "user_id": str(user_id)
        }
        started = datetime.now()

        try:
            response = requests.post(self.assign_agent_api_url, json=payload, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            status = "PASS" if 200 <= response.status_code < 300 else "FAIL"

            _log_api_call(
                api_name="chatbot_assign_agent",
                method="POST",
                url=self.assign_agent_api_url,
                request_payload=payload,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status=status,
                response_preview=response.text
            )

            if status == "FAIL":
                logger.warning(
                    "⚠️ Failed to assign human agent (status=%s, user_id=%s): %s",
                    response.status_code,
                    user_id,
                    response.text
                )

            return status == "PASS"
        except Exception as e:
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                api_name="chatbot_assign_agent",
                method="POST",
                url=self.assign_agent_api_url,
                request_payload=payload,
                status_code=0,
                duration_ms=duration_ms,
                status="FAIL",
                response_preview=str(e)
            )
            logger.warning("⚠️ assign-agent API call failed for user %s: %s", user_id, e)
            return False
    
    def switch_to_ai(self, user_id: str):
        """Manually switch user back to AI mode"""
        self.user_modes[user_id] = ChatMode.AI
        self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
        self.user_order_context[user_id] = False
        self.user_order_draft.pop(user_id, None)
        self.user_pending_product_query.pop(user_id, None)
        self._save_state()
        logger.info(f"🤖 User {user_id} switched to AI mode")
    
    def get_user_mode(self, user_id: str) -> str:
        """Get current mode for user"""
        return self.user_modes.get(user_id, ChatMode.AI).value
