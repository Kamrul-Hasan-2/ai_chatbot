"""
GROQ 3-Step Product Search Pipeline
Complete workflow: Message → Groq Intent → API Search → Groq Response Formatting

This ensures every product-related message goes through:
1. Groq AI for intent/keyword detection
2. BDStall API for product search (top 3 results)
3. Groq AI for beautiful Bengali response formatting
"""
import requests
import logging
from typing import List, Dict, Optional
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from groq_model import GroqAIModel
except ImportError:
    logger.warning("Groq model not available")
    GroqAIModel = None


class Groq3StepSearch:
    """3-step product search using Groq AI at steps 1 and 3"""
    
    def __init__(self, groq_api_key: str = None, bdstall_api_key: str = "mkh677ddd2sxxkkdjff"):
        """Initialize Groq 3-step search"""
        self.bdstall_api_key = bdstall_api_key
        self.base_url = "https://www.bdstall.com/api/item/search/"
        
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
    
    def search(self, user_message: str) -> Dict:
        """
        Complete 3-step search workflow
        
        Args:
            user_message: Raw message from user
            
        Returns:
            Dictionary with final Bengali response and metadata
        """
        logger.info(f"🚀 Starting 3-step Groq search for: {user_message}")
        
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
        
        logger.info(f"✅ Step 1 Complete - Intent: {intent}, Search Terms: {search_terms}")
        
        # STEP 2: BDStall API Search (get top 3 products)
        step2_result = self._step2_api_search(search_terms)
        
        logger.info(f"✅ Step 2 Complete - Found {step2_result['product_count']} products")
        
        if step2_result['product_count'] == 0:
            return {
                'success': True,
                'response': f"দুঃখিত, '{search_terms}' এর জন্য কোনো পণ্য পাওয়া যায়নি। অন্য কিছু খুঁজে দেখুন।",
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
            # Fallback: simple keyword extraction
            logger.info("📍 Step 1 (Fallback) - Simple keyword extraction")
            return {
                'success': True,
                'intent': 'product_search',
                'search_terms': user_message.strip(),
                'confidence': 0.5,
                'method': 'fallback'
            }
        
        try:
            # Crafted prompt for Groq to extract intent and keywords
            prompt = f"""Analyze this customer message and extract the search intent and product keywords.

Customer Message: "{user_message}"

INSTRUCTIONS:
1. Determine the intent (product_search, availability_check, price_inquiry, specifications, etc.)
2. Extract the main product keywords the customer is looking for
3. Clean and optimize the keywords for an e-commerce search API

RESPOND IN THIS FORMAT ONLY (no extra text):
INTENT: [single word intent]
KEYWORDS: [clean search terms separated by spaces]

Example:
Customer: "hp laptop cheap price diye ache?"
INTENT: product_search
KEYWORDS: hp laptop cheap price

Now analyze the customer message:"""
            
            logger.info("🧠 Step 1 - Groq Intent Detection (AI-powered)")
            
            response = self.groq.generate_response(
                user_message=prompt,
                temperature=0.3,  # Low temperature for consistent extraction
                max_length=100
            )
            
            # Parse the response
            lines = response.strip().split('\n')
            intent = 'product_search'
            keywords = user_message.strip()
            
            for line in lines:
                if line.startswith('INTENT:'):
                    intent = line.replace('INTENT:', '').strip().lower()
                elif line.startswith('KEYWORDS:'):
                    keywords = line.replace('KEYWORDS:', '').strip()
            
            logger.info(f"📊 Extracted - Intent: {intent}, Keywords: {keywords}")
            
            return {
                'success': True,
                'intent': intent,
                'search_terms': keywords if keywords else user_message.strip(),
                'confidence': 0.85,
                'groq_response': response,
                'method': 'groq_ai'
            }
            
        except Exception as e:
            logger.error(f"❌ Step 1 Groq failed: {e}")
            # Fallback to simple extraction
            return {
                'success': True,
                'intent': 'product_search',
                'search_terms': user_message.strip(),
                'confidence': 0.4,
                'method': 'fallback_due_to_error'
            }
    
    def _step2_api_search(self, search_terms: str) -> Dict:
        """
        STEP 2: Search BDStall API for products
        
        Args:
            search_terms: Optimized search keywords
            
        Returns:
            Dictionary with top 3 products
        """
        try:
            logger.info(f"🔍 Step 2 - API Search for: {search_terms}")
            
            params = {
                'term': search_terms,
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
            
            logger.info(f"✅ Found {len(products)} products from API")
            
            return {
                'success': True,
                'product_count': len(products),
                'products': products,
                'search_terms': search_terms
            }
            
        except Exception as e:
            logger.error(f"❌ Step 2 API Search failed: {e}")
            return {
                'success': False,
                'product_count': 0,
                'products': [],
                'error': str(e)
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
            
            # Crafted prompt for beautiful Bengali response
            prompt = f"""আপনি BDStall.com এর কাস্টমার সাপোর্ট এজেন্ট। গ্রাহক এই অনুরোধ করেছে:

গ্রাহকের বার্তা: "{user_message}"
সার্চ কী-ওয়ার্ড: {search_terms}

আমরা এই পণ্যগুলি পেয়েছি:
{products_text}

আপনার কাজ:
1. গ্রাহক-বান্ধব, সংক্ষিপ্ত এবং প্রাসঙ্গিক উত্তর দিন (বাংলায়)
2. পণ্যগুলি সুন্দরভাবে উপস্থাপন করুন (2-3টি পণ্য উল্লেখ করুন)
3. দাম এবং বৈশিষ্ট্য হাইলাইট করুন
4. কেন এই পণ্যগুলি ভালো তা বলুন
5. শেষে "আরো দেখতে আমাদের সাথে যোগাযোগ করুন" বলুন
6. Polite, helpful, এবং professional থাকুন

উত্তরটি 3-4 লাইনের মধ্যে রাখুন। শুধুমাত্র উত্তর দিন, কোনো অতিরিক্ত টেক্সট নয়।"""
            
            logger.info("✨ Step 3 - Groq Response Formatting (AI-powered)")
            
            formatted_response = self.groq.generate_response(
                user_message=prompt,
                temperature=0.7,  # Balanced creativity
                max_length=250
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
