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
from enum import Enum

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import required components
try:
    from groq import Groq
except ImportError:
    Groq = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatMode(Enum):
    """Chat mode: AI or HUMAN"""
    AI = "ai"
    HUMAN = "human"


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
        
        # BDStall API Configuration
        self.api_url = "https://www.bdstall.com/api/item/ai_search/"
        self.api_key = "mkh677ddd2sxxkkdjff"
        
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
            
            logger.info(f"📨 Processing message from {user_id} (Mode: {current_mode.value})")
            logger.info(f"💬 Message: {message}")
            
            # STEP 1: Message → Groq API (Intent Detection)
            logger.info("🚀 STEP 1: Sending to Groq API for intent detection...")
            intent_result = self._step1_groq_intent(message)
            
            if not intent_result['success']:
                # If Groq fails, switch to HUMAN mode
                self.user_modes[user_id] = ChatMode.HUMAN
                return self._create_response(
                    user_id=user_id,
                    message=message,
                    response="স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
                    mode=ChatMode.HUMAN,
                    intent=None,
                    products=None,
                    processing_time=(datetime.now() - start_time).total_seconds()
                )
            
            intent = intent_result['intent']
            search_keywords = intent_result['search_keywords']
            
            logger.info(f"✅ Intent: {intent}")
            logger.info(f"🔍 Search Keywords: {search_keywords}")
            
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
                    self.user_modes[user_id] = ChatMode.HUMAN
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
                        mode=ChatMode.HUMAN,
                        intent=intent,
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )
            
            # STEP 2 & 3: Search API → Database Format
            if intent in ['product_search', 'price_search', 'laptop_search']:
                logger.info("🚀 STEP 2-3: Searching database with keywords...")
                search_result = self._step2_search_database(search_keywords)
                
                if search_result['products_found'] == 0:
                    # No products found, switch to HUMAN mode
                    self.user_modes[user_id] = ChatMode.HUMAN
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
                        mode=ChatMode.HUMAN,
                        intent=intent,
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
                    )
                
                database_message = search_result['database_message']
                products = search_result['products']
                
                logger.info(f"✅ Found {len(products)} products")
                
                # STEP 4: Database Message → AI (Final Formatting)
                logger.info("🚀 STEP 4: Sending to AI for final response...")
                final_response = self._step4_ai_format(message, database_message, products)
                
                if not final_response['success']:
                    # AI formatting failed, switch to HUMAN
                    self.user_modes[user_id] = ChatMode.HUMAN
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
                        mode=ChatMode.HUMAN,
                        intent=intent,
                        products=products,
                        processing_time=(datetime.now() - start_time).total_seconds()
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
                    self.user_modes[user_id] = ChatMode.HUMAN
                    return self._create_response(
                        user_id=user_id,
                        message=message,
                        response="স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
                        mode=ChatMode.HUMAN,
                        intent=intent,
                        products=None,
                        processing_time=(datetime.now() - start_time).total_seconds()
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
            self.user_modes[user_id] = ChatMode.HUMAN
            
            return self._create_response(
                user_id=user_id,
                message=message,
                response="স্যার, এই বিষয়ে আমাদের আরেকজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন",
                mode=ChatMode.HUMAN,
                intent=None,
                products=None,
                processing_time=0,
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
            response = requests.get(
                self.api_url,
                params={
                    'term': search_term,
                    'key': self.api_key
                },
                timeout=10
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
            logger.error(f"❌ BDStall API search failed: {e}")
            return {
                'products_found': 0,
                'products': [],
                'database_message': ''
            }
    
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
        error: Optional[str] = None
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
            "products": products[:3] if products else None,  # Return top 3
            "processing_time_seconds": round(processing_time, 2),
            "timestamp": datetime.now().isoformat(),
            "error": error
        }
    
    def switch_to_human(self, user_id: str):
        """Manually switch user to HUMAN mode"""
        self.user_modes[user_id] = ChatMode.HUMAN
        logger.info(f"👤 User {user_id} switched to HUMAN mode")
    
    def switch_to_ai(self, user_id: str):
        """Manually switch user back to AI mode"""
        self.user_modes[user_id] = ChatMode.AI
        logger.info(f"🤖 User {user_id} switched to AI mode")
    
    def get_user_mode(self, user_id: str) -> str:
        """Get current mode for user"""
        return self.user_modes.get(user_id, ChatMode.AI).value
