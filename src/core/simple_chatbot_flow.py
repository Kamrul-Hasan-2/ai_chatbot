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

        self._load_state()
        
        # Load database.csv for FAQ responses
        self.database = self._load_database()
        
        logger.info("✅ Simple Chatbot Initialized")
        logger.info(f"🌐 BDStall API: {self.api_url}")
        logger.info(f"📚 Database: {len(self.database)} FAQ responses loaded")

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
            }
            with open(self.state_file, 'w', encoding='utf-8') as file_obj:
                json.dump(state, file_obj, ensure_ascii=False)
        except Exception as e:
            logger.warning("⚠️ Failed to persist chatbot state: %s", e)
    
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
            
            # Define ordering query mappings (romanized Bengali)
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
            for eng_key, bengali_keys in greeting_map.items():
                if eng_key in message_lower:
                    # Search database for matching Bengali greeting
                    for item in self.database:
                        question = item['question']
                        for bengali_key in bengali_keys:
                            if bengali_key in question:
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

            # ✅ NEW: Check user's responder status from BDStall API
            responder_type = self._check_responder_type(user_id)
            if responder_type == 'agent':
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

            # STEP 1: Message → Groq API (Intent Detection)
            logger.info("🚀 STEP 1: Sending to Groq API for intent detection...")
            intent_result = self._step1_groq_intent(message)

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

            if intent in ['product_search', 'price_search', 'laptop_search'] and str(search_keywords).strip().lower() in ['none', 'না', 'নেই', '']:
                search_keywords = self._build_product_search_keywords(message)

            # Guardrail: prevent false handoff when LLM mislabels clear product queries.
            if intent in ['unknown', 'irrelevant'] and self._looks_like_product_query(message):
                normalized = str(message or '').lower()
                intent = 'laptop_search' if ('laptop' in normalized or 'ল্যাপটপ' in normalized) else 'product_search'
                search_keywords = self._build_product_search_keywords(message)
                logger.info(
                    "🔁 Overriding %s intent to %s for product-like query user_id=%s",
                    intent_result.get('intent'),
                    intent,
                    user_id
                )
            
            logger.info(f"✅ Intent: {intent}")
            logger.info(f"🔍 Search Keywords: {search_keywords}")

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
            if intent in safe_intents:
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
                return self._handoff_to_human(
                    user_id=user_id,
                    message=message,
                    start_time=start_time,
                    intent=intent
                )
            
            # STEP 2 & 3: Search API → Database Format
            if intent in ['product_search', 'price_search', 'laptop_search']:
                logger.info("🚀 STEP 2-3: Searching database with keywords...")
                search_result = self._step2_search_database(search_keywords)

                # Retry once with a broader query before switching to HUMAN mode.
                if search_result['products_found'] == 0:
                    broader_keywords = self._build_broader_search_keywords(search_keywords, message)
                    if broader_keywords:
                        logger.info(
                            "🔁 No results for '%s'; retrying with broader keywords '%s'",
                            search_keywords,
                            broader_keywords
                        )
                        retry_result = self._step2_search_database(broader_keywords)
                        if retry_result['products_found'] > 0:
                            search_keywords = broader_keywords
                            search_result = retry_result
                
                if search_result['products_found'] == 0:
                    # Keep AI mode for product queries even when no exact result is found.
                    # This avoids premature human handoff for Messenger phrasing/keywords.
                    self.user_modes[user_id] = ChatMode.AI
                    self.user_conversation_status[user_id] = AI_ACTIVE_STATUS
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response=(
                            "স্যার, আপনার কথার সাথে মিলে এই মুহূর্তে নির্দিষ্ট কোনো প্রোডাক্ট পেলাম না। "
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
                
                # STEP 4: Database Message → AI (Final Formatting)
                logger.info("🚀 STEP 4: Sending to AI for final response...")
                final_response = self._step4_ai_format(message, database_message, products)
                
                if not final_response['success']:
                    # AI formatting failed, switch to HUMAN
                    return self._handoff_to_human(
                        user_id=user_id,
                        message=message,
                        start_time=start_time,
                        intent=intent,
                        products=products
                    )
                
                # Success! Keep in AI mode
                self.user_modes[user_id] = ChatMode.AI
                
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
                ai_response = self._step4_ai_format(message, None, None)
                
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
    
    def _step1_groq_intent(self, message: str) -> Dict[str, Any]:
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

    def _local_intent_fallback(self, message: str) -> tuple[str, str]:
        """Deterministic fallback when Groq is unavailable or returns unparsable output."""
        text = str(message or '').strip().lower()

        if self._looks_like_product_query(message):
            # Keep laptop intent specific when laptop keyword appears.
            if 'laptop' in text or 'ল্যাপটপ' in text:
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

    def _looks_like_product_query(self, message: str) -> bool:
        """Heuristic detector for short product requests in English/Bangla transliteration."""
        text = str(message or '').strip().lower()
        if not text:
            return False

        product_terms = [
            'laptop', 'phone', 'mobile', 'pc', 'computer', 'monitor', 'mouse', 'keyboard',
            'headphone', 'ssd', 'ram', 'printer', 'camera', 'router', 'charger',
            'gun', 'stun', 'stun gun', 'taser',
            'ল্যাপটপ', 'মোবাইল', 'ফোন', 'কম্পিউটার', 'মাউস', 'কিবোর্ড', 'হেডফোন'
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

        # Availability style query like "stun gun ase" should trigger search.
        availability_words = {'ase', 'ache', 'pawa', 'available', 'stock', 'আছে', 'পাওয়া', 'পাওয়া'}
        compact_tokens = [t for t in re.split(r'\s+', text) if t]
        has_availability_word = any(t in availability_words for t in compact_tokens)
        has_candidate_term = len([t for t in compact_tokens if t not in availability_words and len(t) > 1]) >= 1

        if has_product and (has_brand or has_cue or has_number):
            return True

        # Short brand+product queries such as "hp laptop" should always search.
        if has_product and len(text.split()) <= 4:
            return True

        # Fallback: generic product availability ask with at least one candidate term.
        if has_availability_word and has_candidate_term and len(compact_tokens) <= 5:
            return True

        return False

    def _build_product_search_keywords(self, message: str) -> str:
        """Build cleaner search keywords from informal user queries."""
        text = str(message or '').strip().lower()
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
            'apnadar', 'apnaderi', 'ekhankar', 'pawa', 'pabo'
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
        normalized = str(text or '').strip().lower()
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
            search_term = keywords.replace('taka', '').replace('tk', '').strip()
            
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
    
    def _step4_ai_format(self, original_message: str, database_message: Optional[str], products: Optional[list]) -> Dict[str, Any]:
        """
        STEP 4: Send database message to AI for final formatting
        """
        try:
            if database_message and products:
                # Product search response - Use custom formatting with greeting
                response_text = "স্যার এই প্রোডাক্টগুলা দেখতে পারেন:\n\n"
                
                # Format each product with details
                for idx, product in enumerate(products[:5], 1):  # Show top 5 products
                    title = product.get('title', 'N/A')
                    price = product.get('price', 'N/A')
                    url = product.get('url', '')
                    description = product.get('description', '')
                    
                    # Clean up description (first 100 chars)
                    if description and len(description) > 100:
                        description = description[:100] + "..."
                    
                    response_text += f"{idx}. {title}\n"
                    response_text += f"মূল্য: {price}\n"
                    
                    if description:
                        response_text += f"বিবরণ: {description}\n"
                    
                    if url:
                        response_text += f"লিংক: {url}\n"
                    
                    response_text += "\n"
                
                response_text += "আরও তথ্যের জন্য আমাদের সাথে যোগাযোগ করুন। ধন্যবাদ!"
                
                return {
                    'success': True,
                    'response': response_text
                }
            else:
                if not self.groq_client:
                    return {'success': False, 'error': 'Groq not available'}

                # General query - Use AI
                prompt = f"""তুমি একজন বন্ধুত্বপূর্ণ বাংলা চ্যাটবট। BDStall.com এর হয়ে উত্তর দাও।

প্রশ্ন: {original_message}

একটি সুন্দর, সংক্ষিপ্ত বাংলা উত্তর দাও।
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
            'buy', 'kinbo', 'kinte', 'কিনবো', 'কিনব', 'কিনতে', 'কিভাবে কিনবো', 'kibabe kinbo'
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
            'কিনবো', 'কিনব', 'কিনতে চাই', 'কিভাবে কিনবো', 'কিভাবে কিনব',
            'kibabe kinbo', 'kivabe kinbo'
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
        self.user_modes[user_id] = ChatMode.HUMAN
        self.user_conversation_status[user_id] = HUMAN_SUPPORT_REQUIRED_STATUS
        self.user_order_context[user_id] = False
        self.user_order_draft.pop(user_id, None)
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
    
    def _create_response(
        self,
        user_id: str,
        message: str,
        response: str,
        mode: ChatMode,
        intent: Optional[str],
        products: Optional[list],
        search_keywords: Optional[str] = None,
        processing_time: float = 0.0,
        error: Optional[str] = None,
        conversation_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create standardized JSON response with mode
        """
        self._save_state()
        return {
            "success": mode == ChatMode.AI,
            "user_id": user_id,
            "message": message,
            "response": response,
            "mode": mode.value,  # Always show: "ai" or "human"
            "intent": intent,
            "search_keywords": search_keywords,
            "products_found": len(products) if products else 0,
            "products": products[:5] if products else None,  # Keep top 5 for follow-up selection
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
        self._save_state()
        logger.info(f"🤖 User {user_id} switched to AI mode")
    
    def get_user_mode(self, user_id: str) -> str:
        """Get current mode for user"""
        return self.user_modes.get(user_id, ChatMode.AI).value
