"""
GROQ 3-Step Product Search Pipeline
Complete workflow: Message → Groq Intent → API Search → Groq Response Formatting

This ensures every product-related message goes through:
1. Groq AI for intent/keyword detection
2. BDStall API for product search (top 3 results)
3. Groq AI for beautiful Bengali response formatting

✨ ENHANCED: Now includes dynamic typo correction (works with ANY product!)
"""
import requests
import logging
from typing import List, Dict, Optional, Any
import os
import re
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from groq_model import GroqAIModel
except ImportError:
    logger.warning("Groq model not available")
    GroqAIModel = None

try:
    from dynamic_typo_corrector import DynamicTypoCorrector
except ImportError:
    logger.warning("Dynamic typo corrector not available (optional)")
    DynamicTypoCorrector = None


class Groq3StepSearch:
    """3-step product search using Groq AI at steps 1 and 3"""
    
    def __init__(self, groq_api_key: str = None, bdstall_api_key: str = "mkh677ddd2sxxkkdjff"):
        """Initialize Groq 3-step search with dynamic typo correction"""
        self.bdstall_api_key = bdstall_api_key
        self.base_url = "https://www.bdstall.com/api/item/search/"
        
        # Initialize dynamic typo corrector (optional enhancement)
        try:
            if DynamicTypoCorrector:
                self.typo_corrector = DynamicTypoCorrector(bdstall_api_key)
                logger.info("✅ Dynamic Typo Corrector initialized (works with ANY product!)")
            else:
                self.typo_corrector = None
        except Exception as e:
            logger.warning(f"⚠️ Typo corrector not available: {e}")
            self.typo_corrector = None
        
        # Initialize Groq AI for intent detection and response formatting
        try:
            if GroqAIModel and (groq_api_key or os.getenv('GROQ_API_KEY')):
                self.groq = GroqAIModel(api_key=groq_api_key)
                logger.info("✅ Groq AI initialized for 3-step search")
            else:
                self.groq = None
                logger.warning("⚠️ Groq AI not available - using fallback mode")
        except Exception as e:
            logger.warning(f"⚠️ Groq AI initialization failed: {e}")
            self.groq = None
    
    def _detect_order_info(self, user_message: str) -> Optional[Dict]:
        """
        Detect if message contains order information (Name, Address, Phone)
        
        Args:
            user_message: User's message
            
        Returns:
            Dictionary with order info if detected, None otherwise
        """
        import re
        
        # Improved pattern matching for order information (supports Bengali and English)
        # More flexible patterns that handle various formats and line breaks
        name_pattern = r'(?:name|নাম)\s*:?\s*([A-Za-z\u0980-\u09FF\s]+?)(?:\s*[,|\n]|(?=\s*(?:address|ঠিকানা|phone|ফোন)|$))'
        address_pattern = r'(?:address|ঠিকানা)\s*:?\s*([A-Za-z\u0980-\u09FF\s,.-]+?)(?:\s*[,|\n]|(?=\s*(?:phone|ফোন|নাম্বার)|$))'
        phone_pattern = r'(?:phone|ফোন|নাম্বার|number)\s*:?\s*([0-9]{10,15})'
        
        # Use DOTALL and IGNORECASE flags to handle multiline and case variations
        name_match = re.search(name_pattern, user_message, re.IGNORECASE | re.DOTALL)
        address_match = re.search(address_pattern, user_message, re.IGNORECASE | re.DOTALL)
        phone_match = re.search(phone_pattern, user_message, re.IGNORECASE | re.DOTALL)
        
        # If all three are present, it's an order
        if name_match and address_match and phone_match:
            return {
                'name': name_match.group(1).strip(),
                'address': address_match.group(1).strip(),
                'phone': phone_match.group(1).strip()
            }
        
        return None
    
    def _detect_partial_order_info(self, user_message: str) -> Optional[Dict]:
        """
        Detect partial order information and return what's missing
        
        Args:
            user_message: User's message
            
        Returns:
            Dictionary with present fields and missing fields, or None
        """
        import re
        
        # Same patterns as _detect_order_info
        name_pattern = r'(?:name|নাম)\s*:?\s*([A-Za-z\u0980-\u09FF\s]+?)(?:\s*[,|\n]|(?=\s*(?:address|ঠিকানা|phone|ফোন)|$))'
        address_pattern = r'(?:address|ঠিকানা)\s*:?\s*([A-Za-z\u0980-\u09FF\s,.-]+?)(?:\s*[,|\n]|(?=\s*(?:phone|ফোন|নাম্বার)|$))'
        phone_pattern = r'(?:phone|ফোন|নাম্বার|number)\s*:?\s*([0-9]{10,15})'
        
        name_match = re.search(name_pattern, user_message, re.IGNORECASE | re.DOTALL)
        address_match = re.search(address_pattern, user_message, re.IGNORECASE | re.DOTALL)
        phone_match = re.search(phone_pattern, user_message, re.IGNORECASE | re.DOTALL)
        
        # Check if at least one field is present but not all three
        has_name = name_match is not None
        has_address = address_match is not None
        has_phone = phone_match is not None
        
        fields_count = sum([has_name, has_address, has_phone])
        
        # If some fields present but not all (partial order)
        if fields_count > 0 and fields_count < 3:
            present = {}
            missing = []
            
            if has_name:
                present['name'] = name_match.group(1).strip()
            else:
                missing.append('name')
            
            if has_address:
                present['address'] = address_match.group(1).strip()
            else:
                missing.append('address')
            
            if has_phone:
                present['phone'] = phone_match.group(1).strip()
            else:
                missing.append('phone')
            
            return {
                'is_partial': True,
                'present': present,
                'missing': missing
            }
        
        return None
    
    def _generate_missing_info_request(self, partial_info: Dict) -> str:
        """
        Generate a message asking for missing order information
        
        Args:
            partial_info: Dictionary with present and missing fields
            
        Returns:
            Bengali message asking for missing info
        """
        missing = partial_info.get('missing', [])
        present = partial_info.get('present', {})
        
        # Build the message
        message = "ধন্যবাদ! আপনার তথ্য পেয়েছি:\n\n"
        
        # Show what we received
        if 'name' in present:
            message += f"✅ নাম: {present['name']}\n"
        if 'address' in present:
            message += f"✅ ঠিকানা: {present['address']}\n"
        if 'phone' in present:
            message += f"✅ ফোন: {present['phone']}\n"
        
        message += "\nঅর্ডার সম্পূর্ণ করতে অনুগ্রহ করে নিচের তথ্যগুলো দিন:\n\n"
        
        # Ask for missing fields
        if 'name' in missing:
            message += "❌ আপনার নাম\n"
        if 'address' in missing:
            message += "❌ আপনার ঠিকানা\n"
        if 'phone' in missing:
            message += "❌ আপনার ফোন নাম্বার\n"
        
        message += "\nসম্পূর্ণ তথ্য দিলে আমরা আপনার অর্ডার কনফার্ম করতে পারবো। ধন্যবাদ!"
        
        return message
    
    def _generate_order_confirmation(self, order_info: Dict) -> str:
        """
        Generate professional order confirmation message in Bengali
        
        Args:
            order_info: Dictionary with name, address, phone
            
        Returns:
            Bengali confirmation message
        """
        name = order_info.get('name', 'গ্রাহক')
        address = order_info.get('address', 'N/A')
        phone = order_info.get('phone', 'N/A')
        
        # Convert English digits to Bengali if needed
        phone_formatted = phone
        
        confirmation = f"""ধন্যবাদ জনাব {name}! 🎉

আপনার অর্ডারটি সফলভাবে গ্রহণ করা হয়েছে। আপনার তথ্য নিশ্চিত করা হলো:

📋 অর্ডার বিবরণ:
   • নাম: {name}
   • ঠিকানা: {address}
   • ফোন: {phone_formatted}

আমাদের টিম খুব শীঘ্রই আপনার সাথে যোগাযোগ করবে অর্ডার কনফার্ম করতে। আপনার পণ্যটি ২-৩ কর্মদিবসের মধ্যে ডেলিভারি করা হবে। পেমেন্ট ক্যাশ অন ডেলিভারি অথবা অনলাইন দুইভাবেই করতে পারবেন।

BDStall.com Ltd এর সাথে কেনাকাটা করার জন্য আপনাকে আন্তরিক ধন্যবাদ। কোন প্রশ্ন থাকলে আমাদের সাথে যোগাযোগ করতে দ্বিধা করবেন না।

শুভকামনা রইলো! 🛍️
- BDStall.com Ltd টিম"""
        
        return confirmation
    
    def search(self, user_message: str) -> Dict:
        """
        Complete 3-step search workflow
        
        Args:
            user_message: Raw message from user
            
        Returns:
            Dictionary with final Bengali response and metadata
        """
        logger.info(f"🚀 Starting 3-step Groq search for: {user_message}")
        
        # CHECK FOR COMPLETE ORDER CONFIRMATION FIRST
        order_info = self._detect_order_info(user_message)
        if order_info:
            logger.info(f"📦 Complete order detected for: {order_info.get('name', 'N/A')}")
            confirmation = self._generate_order_confirmation(order_info)
            return {
                'success': True,
                'response': confirmation,
                'order_info': order_info,
                'workflow': 'order_confirmation'
            }
        
        # CHECK FOR PARTIAL ORDER INFORMATION
        partial_order = self._detect_partial_order_info(user_message)
        if partial_order:
            logger.info(f"📝 Partial order detected - Missing: {', '.join(partial_order.get('missing', []))}")
            missing_info_msg = self._generate_missing_info_request(partial_order)
            return {
                'success': True,
                'response': missing_info_msg,
                'partial_order': partial_order,
                'workflow': 'partial_order'
            }
        
        # STEP 1: Groq Intent Detection & Keyword Extraction
        step1_result = self._step1_groq_intent_detection(user_message)
        
        if not step1_result.get('success'):
            logger.warning("Step 1 failed - using fallback")
            return {
                'success': False,
                'response': 'দুঃখিত, আপনার বার্তা বুঝতে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।',
                'step1': {'success': False},
                'workflow': 'groq_3step'
            }
        
        search_terms = step1_result['search_terms']
        intent = step1_result.get('intent', 'product_search')
        search_context = step1_result.get('search_context', {})
        
        logger.info(f"✅ Step 1 Complete - Intent: {intent}, Search Terms: {search_terms}")
        
        # STEP 2: BDStall API Search (get top 3 products)
        step2_result = self._step2_api_search(search_terms, search_context=search_context)
        
        logger.info(f"✅ Step 2 Complete - Found {step2_result['product_count']} products")
        
        # If no products found, return NO response (AI is off for this user)
        if step2_result['product_count'] == 0:
            logger.warning(f"⚠️ No products found for '{search_terms}' - Returning empty response")
            return {
                'success': False,
                'response': '',  # No response when no products found
                'no_products_found': True,
                'step1': step1_result,
                'step2': step2_result,
                'workflow': 'groq_3step'
            }
        
        # STEP 3: Groq Response Formatting (beautiful Bengali message)
        step3_result = self._step3_groq_format_response(
            user_message=user_message,
            intent=intent,
            search_terms=search_terms,
            products=step2_result['products']
        )
        
        logger.info(f"✅ Step 3 Complete - Response formatted")
        
        return {
            'success': True,
            'response': step3_result['formatted_response'],
            'products_found': step2_result['product_count'],
            'top_products': step2_result['products'],
            'step1': step1_result,
            'step2': step2_result,
            'step3': step3_result,
            'search_context': search_context,
            'workflow': 'groq_3step'
        }
    
    def _step1_groq_intent_detection(self, user_message: str) -> Dict:
        """
        STEP 1: Use Groq to detect intent and extract search keywords
        
        Args:
            user_message: User's raw message
            
        Returns:
            Dictionary with intent and search terms
        """
        if not self.groq:
            # Fallback: regex-based intent metadata extraction
            logger.info("📍 Step 1 (Fallback) - Regex intent extraction")
            fallback = self._fallback_intent_metadata(user_message)
            return {
                'success': True,
                'intent': fallback.get('intent', 'product_search'),
                'search_terms': fallback.get('search_terms', user_message.strip()),
                'confidence': 0.55,
                'method': 'fallback',
                'search_context': fallback
            }
        
        try:
            # Enhanced prompt for dynamic intent + filter extraction
            prompt = f"""You are an AI assistant for BDStall.com Ltd.
Extract structured product-search intent from customer message.

CUSTOMER MESSAGE:
"{user_message}"

Return ONLY valid JSON (no markdown, no explanation):
{{
    "intent": "product_search | price_range | max_price | min_price | condition_used | condition_new | sort_cheapest | sort_expensive | sort_popular | sort_latest | context_search | brand_item_search | availability_check | specification_request",
    "search_terms": "clean core keywords for API term",
    "brand": "brand name or empty",
    "context_terms": ["extra context words if relevant"],
    "price_min": number_or_null,
    "price_max": number_or_null,
    "condition": "used | new | any",
    "sort": "relevance | price_asc | price_desc | popular | latest"
}}

Rules:
1) Keep output language-independent (works for Bangla/English mixed text).
2) Convert Bangla digits to normal numbers.
3) For ranges (10000-20000 / between), set both price_min and price_max.
4) For under/below/within, set price_max.
5) For above/over/more than, set price_min.
6) For used/second hand, set condition=used.
7) For new/brand new/new arrival, set condition=new.
8) Preserve product type + brand in search_terms.
9) If unknown, use intent=product_search and sort=relevance.
"""
            
            logger.info("🧠 Step 1 - Groq Intent Detection (AI-powered)")
            
            response = self.groq.generate_response(
                user_message=prompt,
                temperature=0.3,  # Low temperature for consistent extraction
                max_length=100
            )
            
            parsed = self._parse_step1_json(response)
            if not parsed:
                parsed = self._fallback_intent_metadata(user_message)

            intent = (parsed.get('intent') or 'product_search').strip().lower()
            keywords = (parsed.get('search_terms') or user_message.strip()).strip()

            search_context = {
                'intent': intent,
                'brand': (parsed.get('brand') or '').strip(),
                'context_terms': parsed.get('context_terms') or [],
                'price_min': self._safe_number(parsed.get('price_min')),
                'price_max': self._safe_number(parsed.get('price_max')),
                'condition': (parsed.get('condition') or 'any').strip().lower(),
                'sort': (parsed.get('sort') or 'relevance').strip().lower()
            }
            
            logger.info(f"📊 Extracted - Intent: {intent}, Keywords: {keywords}")
            
            return {
                'success': True,
                'intent': intent,
                'search_terms': keywords if keywords else user_message.strip(),
                'confidence': 0.85,
                'groq_response': response,
                'method': 'groq_ai',
                'search_context': search_context
            }
            
        except Exception as e:
            logger.error(f"❌ Step 1 Groq failed: {e}")
            # Fallback to simple extraction
            fallback = self._fallback_intent_metadata(user_message)
            return {
                'success': True,
                'intent': fallback.get('intent', 'product_search'),
                'search_terms': fallback.get('search_terms', user_message.strip()),
                'confidence': 0.4,
                'method': 'fallback_due_to_error',
                'search_context': fallback
            }
    
    def _normalize_digits(self, text: str) -> str:
        digit_map = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
        return (text or "").translate(digit_map)

    def _safe_number(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _parse_step1_json(self, raw_response: str) -> Optional[Dict]:
        text = (raw_response or "").strip()
        if not text:
            return None

        candidates = [text]
        matches = re.findall(r"\{.*\}", text, flags=re.DOTALL)
        candidates.extend(matches)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        return None

    def _fallback_intent_metadata(self, user_message: str) -> Dict:
        text = self._normalize_digits(user_message.lower())

        price_min = None
        price_max = None
        sort_type = 'relevance'
        condition = 'any'
        intent = 'product_search'

        range_match = re.search(r'(\d{3,7})\s*(?:-|to|থেকে|between)\s*(\d{3,7})', text)
        if range_match:
            price_min = float(range_match.group(1))
            price_max = float(range_match.group(2))
            intent = 'price_range'

        if re.search(r'(\bunder\b|\bbelow\b|\bwithin\b|এর\s*নিচে|নিচে|মধ্যে)', text):
            nums = re.findall(r'\d{3,7}', text)
            if nums:
                price_max = float(nums[-1])
                intent = 'max_price'

        if re.search(r'(\babove\b|\bover\b|\bmore\s+than\b|এর\s*উপরে|উপরে|এর\s*বেশি|বেশি)', text):
            nums = re.findall(r'\d{3,7}', text)
            if nums:
                price_min = float(nums[-1])
                intent = 'min_price'

        if re.search(r'(\bused\b|\bsecond\s+hand\b|\b2nd\s+hand\b|পুরাতন|সেকেন্ড\s*হ্যান্ড|ব্যবহৃত)', text):
            condition = 'used'
            intent = 'condition_used'
        elif re.search(r'(\bbrand\s+new\b|\bnew\s+arrival\b|\bnew\b|নতুন|ব্র্যান্ড\s*নিউ)', text):
            condition = 'new'
            intent = 'condition_new'

        if re.search(r'(\bcheap\b|\blowest\b|\bbudget\b|সস্তা|কম\s*দামে|বাজেট)', text):
            sort_type = 'price_asc'
            intent = 'sort_cheapest'
        elif re.search(r'(\bpremium\b|\bhighest\b|\bexpensive\b|দামি|বেশি\s*দামের)', text):
            sort_type = 'price_desc'
            intent = 'sort_expensive'
        elif re.search(r'(\bpopular\b|\bbest\b|\btop\b|জনপ্রিয়|সেরা|(?<!\S)টপ(?!\S))', text):
            sort_type = 'popular'
            intent = 'sort_popular'
        elif re.search(r'(\blatest\b|\bnewest\b|\brecent\b|সাম্প্রতিক|লেটেস্ট|নতুন\s*আগমন)', text):
            sort_type = 'latest'
            intent = 'sort_latest'

        brands = [
            'hp', 'dell', 'lenovo', 'asus', 'acer', 'apple', 'samsung',
            'xiaomi', 'huawei', 'oppo', 'vivo', 'sony', 'lg', 'canon', 'nikon'
        ]
        brand = ''
        for b in brands:
            if re.search(rf'\b{re.escape(b)}\b', text):
                brand = b
                intent = 'brand_item_search'
                break

        context_terms = []
        context_match = re.search(r'(.+?)\s+(?:for|with|জন্য|সাথে)\s+(.+)', text)
        if context_match:
            intent = 'context_search'
            context_terms = [context_match.group(2).strip()]

        stopwords_pattern = (
            r'(\bunder\b|\bbelow\b|\bwithin\b|\babove\b|\bover\b|\bmore\s+than\b|\bbetween\b|\bto\b|'
            r'থেকে|নিচে|উপরে|মধ্যে|বেশি|\bused\b|\bsecond\s+hand\b|\b2nd\s+hand\b|\bnew\b|'
            r'\bbrand\s+new\b|\bnew\s+arrival\b|\bcheap\b|\blowest\b|\bbudget\b|\bpremium\b|'
            r'\bhighest\b|\bexpensive\b|\bpopular\b|\bbest\b|\btop\b|\blatest\b|\bnewest\b|\brecent\b|'
            r'\bfor\b|\bwith\b|জন্য|সাথে|এর|(?<!\S)টপ(?!\S))'
        )
        cleaned = re.sub(stopwords_pattern, ' ', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'[-_,;:]+', ' ', cleaned)
        cleaned = re.sub(r'\d{3,7}', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return {
            'intent': intent,
            'search_terms': cleaned or user_message.strip(),
            'brand': brand,
            'context_terms': context_terms,
            'price_min': price_min,
            'price_max': price_max,
            'condition': condition,
            'sort': sort_type
        }

    def _extract_price_value(self, price_text: str) -> Optional[float]:
        if not price_text:
            return None
        text = self._normalize_digits(str(price_text).lower())
        nums = re.findall(r'\d+(?:\.\d+)?', text.replace(',', ''))
        if not nums:
            return None
        value = float(nums[0])
        if 'k' in text or 'হাজার' in text:
            value *= 1000
        return value

    def _apply_filters_and_sort(self, products: List[Dict], search_context: Optional[Dict]) -> List[Dict]:
        if not products:
            return products

        context = search_context or {}
        price_min = self._safe_number(context.get('price_min'))
        price_max = self._safe_number(context.get('price_max'))
        condition = (context.get('condition') or 'any').lower()
        sort_type = (context.get('sort') or 'relevance').lower()

        for product in products:
            product['_price_numeric'] = self._extract_price_value(product.get('price', ''))

        filtered = []
        for product in products:
            p = product.get('_price_numeric')

            if price_min is not None and p is not None and p < price_min:
                continue
            if price_max is not None and p is not None and p > price_max:
                continue

            if condition in {'used', 'new'}:
                haystack = f"{product.get('title', '')} {product.get('description', '')}".lower()
                used_hit = bool(re.search(r'(used|second hand|2nd hand|পুরাতন|ব্যবহৃত|সেকেন্ড\s*হ্যান্ড)', haystack))
                new_hit = bool(re.search(r'(new|brand new|নতুন|ব্র্যান্ড\s*নিউ)', haystack))

                if condition == 'used' and not used_hit:
                    continue
                if condition == 'new' and not new_hit:
                    continue

            filtered.append(product)

        if sort_type == 'price_asc':
            filtered.sort(key=lambda x: (x.get('_price_numeric') is None, x.get('_price_numeric') or 10**12))
        elif sort_type == 'price_desc':
            filtered.sort(key=lambda x: (x.get('_price_numeric') is None, -(x.get('_price_numeric') or 0)))
        elif sort_type == 'latest':
            filtered.sort(key=lambda x: int(str(x.get('listing_id') or '0')) if str(x.get('listing_id') or '').isdigit() else 0, reverse=True)
        elif sort_type == 'popular':
            # API does not provide stable popularity signals here; keep API relevance order.
            pass

        for product in filtered:
            product.pop('_price_numeric', None)

        return filtered

    def _step2_api_search(self, search_terms: str, search_context: Optional[Dict] = None) -> Dict:
        """
        STEP 2: Search BDStall API for products with dynamic typo correction
        
        Args:
            search_terms: Optimized search keywords (may contain typos)
            
        Returns:
            Dictionary with top 3 products
        """
        # Initialize typo_info outside try block for error handling
        typo_info = None
        corrected_terms = search_terms
        
        try:
            logger.info(f"🔍 Step 2 - API Search for: {search_terms}")
            
            # NEW: Try typo correction if available
            if self.typo_corrector:
                logger.info("💡 Checking for typos with dynamic corrector...")
                correction_result = self.typo_corrector.intelligent_search_correction(search_terms)
                
                if correction_result.get('has_corrections'):
                    corrected_terms = correction_result['output']
                    typo_info = correction_result
                    logger.info(f"✓ Typo corrected: '{search_terms}' → '{corrected_terms}'")
                else:
                    logger.info("✓ No typos detected or direct match found")
            
            context_terms = []
            if search_context and isinstance(search_context.get('context_terms'), list):
                context_terms = [str(t).strip() for t in search_context.get('context_terms', []) if str(t).strip()]

            brand = ''
            if search_context:
                brand = str(search_context.get('brand') or '').strip()

            query_parts = [corrected_terms]
            if brand and brand.lower() not in corrected_terms.lower():
                query_parts.insert(0, brand)
            query_parts.extend(context_terms)
            query_term = " ".join(part for part in query_parts if part).strip()

            # Use enriched query term for API search
            params = {
                'term': query_term or corrected_terms,
                'key': self.bdstall_api_key
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=15,
                headers={'User-Agent': 'BDStall Groq Chatbot/1.0'}
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse BDStall API response
            products = []
            
            if 'getListingItem' in data and len(data['getListingItem']) > 1:
                api_products = data['getListingItem'][1]  # Products in second element
                
                # Take top 3 products
                for product in api_products[:3]:
                    standardized = {
                        'title': product.get('ListingTitle', 'No title'),
                        'price': product.get('Price', 'Price not available'),
                        'url': f"https://www.bdstall.com/details/{product.get('ListingID', '')}/",
                        'brand': product.get('BrandName', ''),
                        'description': product.get('Description', ''),
                        'listing_id': product.get('ListingID', '')
                    }
                    products.append(standardized)
            
            filtered_products = self._apply_filters_and_sort(products, search_context)
            top_products = filtered_products[:3]

            logger.info(f"✅ Found {len(products)} raw products from API, {len(filtered_products)} after filters")
            
            return {
                'success': True,
                'product_count': len(top_products),
                'products': top_products,
                'search_terms': query_term or corrected_terms,
                'original_search_terms': search_terms,
                'typo_correction': typo_info,
                'search_context': search_context or {},
                'raw_product_count': len(products),
                'filtered_product_count': len(filtered_products)
            }
            
        except Exception as e:
            logger.error(f"❌ Step 2 API Search failed: {e}")
            return {
                'success': False,
                'product_count': 0,
                'products': [],
                'error': str(e),
                'typo_correction': typo_info if typo_info else None
            }
    
    def _step3_groq_format_response(
        self,
        user_message: str,
        intent: str,
        search_terms: str,
        products: List[Dict]
    ) -> Dict:
        """
        STEP 3: Format response using Groq for beautiful Bengali message
        
        Args:
            user_message: Original user message
            intent: Detected intent
            search_terms: Search terms used
            products: Top 3 products from API
            
        Returns:
            Dictionary with formatted Bengali response
        """
        if not self.groq:
            # Fallback: simple formatting
            logger.info("📍 Step 3 (Fallback) - Simple response formatting")
            return {
                'formatted_response': self._simple_format(user_message, products),
                'method': 'fallback'
            }
        
        try:
            # Build product information for Groq
            product_list = []
            for i, product in enumerate(products, 1):
                product_info = f"{i}. {product['title']} - {product['price']} টাকা"
                if product.get('brand'):
                    product_info += f" ({product['brand']})"
                product_list.append(product_info)
            
            products_text = "\n".join(product_list)
            
            # Enhanced prompt for professional Bengali response
            prompt = f"""আপনি BDStall.com Ltd এর অভিজ্ঞ কাস্টমার সাপোর্ট প্রতিনিধি। আপনার কাজ হলো গ্রাহকদের সঠিক পণ্য খুঁজে দিতে সাহায্য করা।

=== গ্রাহকের অনুরোধ ===
"{user_message}"

=== খোঁজার কী-ওয়ার্ড ===
{search_terms}

=== আমাদের পাওয়া পণ্য (BDStall.com Ltd থেকে) ===
{products_text}

=== আপনার দায়িত্ব ===
১. পেশাদার এবং বন্ধুত্বপূর্ণ বাংলায় সরাসরি উত্তর দিন
২. সবচেয়ে প্রাসঙ্গিক ২-৩টি পণ্য তুলে ধরুন
৩. দাম স্পষ্টভাবে উল্লেখ করুন ("টাকা" শব্দ ব্যবহার করুন)
৪. পণ্যের মূল বৈশিষ্ট্য সংক্ষেপে বলুন
৫. কেন এই পণ্যগুলো গ্রাহকের জন্য উপযুক্ত তা উল্লেখ করুন
৬. শেষে সহায়ক মনোভাব প্রকাশ করুন (যেমন: "আরো জানতে যোগাযোগ করুন" বা "অর্ডার করতে চাইলে জানান")

=== নিষিদ্ধ ===
❌ কোনো URL বা লিংক যোগ করবেন না
❌ "BDStall.com" বারবার উল্লেখ করবেন না (একবার শুরুতেই যথেষ্ট)
❌ অপ্রাসঙ্গিক পণ্যের তথ্য দেবেন না
❌ ইংরেজিতে উত্তর দেবেন না

=== উত্তরের দৈর্ঘ্য ===
৩-৫ লাইনের মধ্যে রাখুন (সংক্ষিপ্ত কিন্তু তথ্যবহুল)

=== উদাহরণ ভালো উত্তর ===
আসসালামু আলাইকুম! আপনার জন্য BDStall.com Ltd থেকে কিছু চমৎকার HP ল্যাপটপ পেয়েছি। HP 1000 Core i3 (৮GB RAM, ৫০০GB HDD) মাত্র ৯০০০ টাকায় পাবেন, যা দৈনন্দিন কাজের জন্য পারফেক্ট। আরো ভালো পারফরম্যান্স চাইলে HP EliteBook 840 (Core i5, 128GB SSD) আছে ১৫৫০০ টাকায়। সব পণ্যই অরিজিনাল এবং ওয়ারেন্টি সহ। অর্ডার করতে চাইলে জানান!

এখন আপনার পেশাদার বাংলা উত্তর দিন (শুধু উত্তর, অতিরিক্ত কিছু নয়):"""
            
            logger.info("✨ Step 3 - Groq Response Formatting (AI-powered)")
            
            formatted_response = self.groq.generate_response(
                user_message=prompt,
                temperature=0.7,  # Balanced creativity
                max_length=400
            )
            
            logger.info(f"📝 Formatted: {formatted_response[:80]}...")
            
            return {
                'formatted_response': formatted_response.strip(),
                'method': 'groq_ai',
                'groq_response': formatted_response
            }
            
        except Exception as e:
            logger.error(f"❌ Step 3 Groq formatting failed: {e}")
            # Fallback to simple formatting
            return {
                'formatted_response': self._simple_format(user_message, products),
                'method': 'fallback_due_to_error'
            }
    
    def _simple_format(self, user_message: str, products: List[Dict]) -> str:
        """Simple fallback response formatting"""
        if not products:
            return f"দুঃখিত, '{user_message}' এর জন্য পণ্য পাওয়া যায়নি।"
        
        response = f"আপনার খোঁজের জন্য আমরা কিছু ভালো পণ্য পেয়েছি:\n\n"
        
        for i, product in enumerate(products[:3], 1):
            response += f"{i}. {product['title']}\n"
            response += f"   দাম: {product['price']} টাকা\n"
        
        response += "\nআরো বিস্তারিত জানতে আমাদের সাথে যোগাযোগ করুন।"
        
        return response


def test_3step_search():
    """Test the 3-step Groq search"""
    print("\n" + "=" * 70)
    print("🚀 GROQ 3-STEP PRODUCT SEARCH TEST")
    print("=" * 70)
    print("Workflow: Message → Groq Intent → API Search → Groq Response\n")
    
    # Initialize
    searcher = Groq3StepSearch()
    
    # Test queries
    test_queries = [
        "web cam lagbe",
        "hp laptop দাম কত",
        "wireless headphone ache?",
        "gaming mouse কিনতে চাই",
        "good quality printer dekhaio"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📋 Test Query {i}: '{query}'")
        print("-" * 70)
        
        result = searcher.search(query)
        
        # Display results
        print(f"✅ Success: {result['success']}")
        
        if result['step1'].get('method') == 'groq_ai':
            print(f"🧠 Step 1 (Groq): Intent={result['step1'].get('intent')}, "
                  f"Keywords={result['step1'].get('search_terms')}")
        else:
            print(f"🧠 Step 1 (Fallback): Keywords={result['step1'].get('search_terms')}")
        
        if result['step2']['success']:
            print(f"🔍 Step 2 (API): Found {result['step2']['product_count']} products")
        
        if result['step3'].get('method') == 'groq_ai':
            print(f"✨ Step 3 (Groq): AI-formatted response")
        else:
            print(f"✨ Step 3 (Fallback): Simple formatting")
        
        print(f"\n📝 Final Response:")
        print(f"   {result['response'][:150]}...")
        
        if result.get('top_products'):
            print(f"\n🛍️ Products Found:")
            for j, prod in enumerate(result['top_products'][:2], 1):
                print(f"   {j}. {prod['title'][:50]} - {prod['price']}")
        
        print()


if __name__ == "__main__":
    test_3step_search()
