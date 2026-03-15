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
        
        # Load database.csv for FAQ responses
        self.database = self._load_database()
        
        logger.info("✅ Simple Chatbot Initialized")
        logger.info(f"🌐 BDStall API: {self.api_url}")
        logger.info(f"📚 Database: {len(self.database)} FAQ responses loaded")
    
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
            
            logger.info(f"📨 Processing message from {user_id} (Mode: {current_mode.value})")
            logger.info(f"💬 Message: {message}")

            # Once handed over, stop automated reasoning until a human resets the conversation.
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

            # If user confirms after selecting a specific product, call order template API with listing ID.
            selected_product = self.user_selected_product.get(user_id)
            if selected_product and self._is_order_confirmation_message(message):
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
                # If Groq fails, switch to HUMAN mode
                return self._handoff_to_human(
                    user_id=user_id,
                    message=message,
                    start_time=start_time,
                    intent='system_fallback'
                )
            
            intent = intent_result['intent']
            search_keywords = intent_result['search_keywords']
            
            logger.info(f"✅ Intent: {intent}")
            logger.info(f"🔍 Search Keywords: {search_keywords}")

            # Ordering intent should always return the standard order-info template.
            if intent == 'ordering':
                self.user_order_context[user_id] = True
                self.user_order_draft[user_id] = {}
                self.user_modes[user_id] = ChatMode.AI
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response=self._get_order_info_template(),
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
            
            # Check if intent is unknown or irrelevant - switch to HUMAN
            # BUT skip handoff for safe intents like greetings
            if intent in ['unknown', 'irrelevant'] or search_keywords.lower() in ['none', 'না', 'নেই', '']:
                # If it's a safe intent (like greeting), don't switch to human
                if intent not in safe_intents:
                    logger.warning("⚠️ Irrelevant message detected - switching to HUMAN mode")
                    return self._handoff_to_human(
                        user_id=user_id,
                        message=message,
                        start_time=start_time,
                        intent=intent,
                        response_text=self._get_irrelevant_handoff_message()
                    )
            
            # STEP 2 & 3: Search API → Database Format
            if intent in ['product_search', 'price_search', 'laptop_search']:
                logger.info("🚀 STEP 2-3: Searching database with keywords...")
                search_result = self._step2_search_database(search_keywords)
                
                if search_result['products_found'] == 0:
                    # No products found, switch to HUMAN mode
                    return self._handoff_to_human(
                        user_id=user_id,
                        message=message,
                        start_time=start_time,
                        intent=intent
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
            return {'success': False, 'error': 'Groq not available'}
        
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
            
            for line in result.split('\n'):
                if line.startswith('Intent:'):
                    intent = line.split(':', 1)[1].strip().lower()
                elif line.startswith('Keywords:'):
                    keywords = line.split(':', 1)[1].strip()
            
            return {
                'success': True,
                'intent': intent,
                'search_keywords': keywords,
                'raw_response': result
            }
        
        except Exception as e:
            logger.error(f"❌ Groq intent detection failed: {e}")
            return {'success': False, 'error': str(e)}
    
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
            
            # Filter products by price if specified
            filtered_products = []
            for product in products_array[:20]:  # Take top 20 first
                try:
                    product_price = int(product.get('app_ListingPrice', 999999))
                    
                    if max_price:
                        if product_price <= max_price:
                            filtered_products.append(product)
                    else:
                        filtered_products.append(product)
                        
                except:
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
                
                if description:
                    database_message += f"   বিবরণ: {description}...\n"
                
                database_message += f"   লিংক: {url}\n\n"
                
                products_list.append({
                    'title': title,
                    'price': price,
                    'original_price': original_price,
                    'discount': discount,
                    'url': url,
                    'image': product.get('ListingThumbAvator', ''),
                    'description': description
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

    def _fetch_order_intent_response(self, listing_id: str) -> Optional[str]:
        """Fetch order template text from BDStall intent API using selected product listing ID."""
        params = {
            'intent': 'order',
            'id': listing_id,
            'key': self.api_key
        }
        started = datetime.now()

        try:
            response = requests.get(
                self.order_intent_api_url,
                params=params,
                timeout=10
            )
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            status = "PASS" if response.status_code == 200 else "FAIL"

            _log_api_call(
                api_name="ai_template_order",
                method="GET",
                url=self.order_intent_api_url,
                request_payload=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status=status,
                response_preview=response.text
            )

            if status == "FAIL":
                logger.warning(
                    "⚠️ Order intent API failed with status %s for listing_id=%s",
                    response.status_code,
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
                url=self.order_intent_api_url,
                request_payload=params,
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
        if not self.groq_client:
            return {'success': False, 'error': 'Groq not available'}
        
        try:
            if database_message and products:
                # Product search response - Use custom formatting with greeting
                response_text = "স্যার, আপনার পছন্দের কিছু প্রোডাক্ট আমাদের কাছে এসে গেছে। প্রোডাক্টগুলোর বিস্তারিত নিচে দেওয়া হলো:\n\n"
                
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
                    response_text += f"💰 মূল্য: {price}\n"
                    
                    if description:
                        response_text += f"📝 বিবরণ: {description}\n"
                    
                    if url:
                        response_text += f"🔗 লিংক: {url}\n"
                    
                    response_text += "\n"
                
                response_text += "আরও তথ্যের জন্য আমাদের সাথে যোগাযোগ করুন। ধন্যবাদ! 🙏"
                
                return {
                    'success': True,
                    'response': response_text
                }
            else:
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

    def _get_order_info_template(self) -> str:
        """Standard template to collect order details from user."""
        return (
            "Sir, আপনি যদি প্রোডাক্টটি অর্ডার করতে চান, তাহলে দয়া করে নিচের তথ্যগুলো দিন:\n\n"
            "Name:\n"
            "Phone Number:\n"
            "Address:\n"
            "Product Name:\n"
            "Quantity:\n\n"
            "এই তথ্যগুলো দিলে আমরা আপনার অর্ডারটি কনফার্ম করে দেব।"
        )

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
        response_text += f"💰 মূল্য: {price}\n"

        if description:
            response_text += f"📝 বিবরণ: {description}\n"

        if url:
            response_text += f"🔗 লিংক: {url}\n"

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
            "স্যার, অর্ডার কনফার্ম করার জন্য নিচের বাকি তথ্যগুলো দিন:\n\n"
            f"{missing_lines}\n\n"
            "সব তথ্য দিলে আমরা আপনার অর্ডারটি কনফার্ম করে দেব।"
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
        logger.info(f"🤖 User {user_id} switched to AI mode")
    
    def get_user_mode(self, user_id: str) -> str:
        """Get current mode for user"""
        return self.user_modes.get(user_id, ChatMode.AI).value
