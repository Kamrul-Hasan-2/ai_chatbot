"""
Enhanced Product Search with Groq AI Integration
3-Step Workflow: Intent Detection -> API Search -> AI-Formatted Response
"""
import requests
import logging
from typing import List, Dict, Optional
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from groq_model import GroqAIModel
except ImportError:
    logger.warning("Groq model not available")
    GroqAIModel = None


class EnhancedProductSearch:
    def __init__(self, groq_api_key: str = None, bdstall_api_key: str = "mkh677ddd2sxxkkdjff"):
        """Initialize Enhanced Product Search with Groq AI integration"""
        self.bdstall_api_key = bdstall_api_key
        self.base_url = "https://www.bdstall.com/api/item/search/"
        
        # Try to initialize Groq AI
        try:
            if GroqAIModel and (groq_api_key or os.getenv('GROQ_API_KEY')):
                self.groq = GroqAIModel(api_key=groq_api_key)
                logger.info("✅ Groq AI initialized for product search")
            else:
                self.groq = None
                logger.info("⚠️ Groq AI not available - using fallback mode")
        except Exception as e:
            logger.warning(f"⚠️ Groq AI not available: {e}")
            self.groq = None
    
    def detect_search_intent(self, user_query: str) -> Dict:
        """Step 1: Detect search intent and extract optimized search terms"""
        if not self.groq:
            # Simple fallback
            return {
                'intent': 'product_search',
                'search_terms': user_query.strip(),
                'category': 'general',
                'confidence': 0.5
            }
        
        try:
            # Simple prompt for intent detection
            prompt = f"Extract product search keywords from: '{user_query}'. Return only the main product keywords, separated by spaces."
            
            logger.info("🧠 Detecting search intent with Groq...")
            response = self.groq.generate_response(
                user_message=prompt,
                temperature=0.3,
                max_length=100
            )
            
            search_terms = response.strip() if response else user_query
            logger.info(f"✅ Search terms optimized: {search_terms}")
            
            return {
                'intent': 'product_search',
                'search_terms': search_terms,
                'category': 'general', 
                'confidence': 0.8
            }
                
        except Exception as e:
            logger.error(f"❌ Intent detection failed: {e}")
            return {
                'intent': 'product_search',
                'search_terms': user_query.strip(),
                'category': 'general',
                'confidence': 0.3
            }
    
    def search_bdstall_api(self, search_terms: str) -> Dict:
        """Step 2: Search BDStall API"""
        try:
            logger.info(f"🔍 Searching BDStall API for: {search_terms}")
            
            params = {
                'term': search_terms,
                'key': self.bdstall_api_key
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=15,
                headers={'User-Agent': 'BDStall Chatbot/1.0'}
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Handle BDStall API response format: {'getListingItem': [count, [products]]}
            if 'getListingItem' in data and len(data['getListingItem']) > 1:
                products = data['getListingItem'][1]  # Products are in the second element
                results = []
                
                # Convert to standardized format
                for product in products:
                    standardized_product = {
                        'title': product.get('ListingTitle', 'No title'),
                        'price': product.get('Price', 'Price not available'),
                        'url': f"https://www.bdstall.com/details/{product.get('ListingID', '')}/",
                        'description': product.get('Description', ''),
                        'brand': product.get('BrandName', ''),
                        'model': product.get('ModelNo', ''),
                        'listing_id': product.get('ListingID', '')
                    }
                    results.append(standardized_product)
                
                logger.info(f"✅ API returned {len(results)} products")
                
                return {
                    'success': True,
                    'results': results,
                    'total_found': len(results),
                    'search_terms': search_terms
                }
            else:
                logger.info("❌ No products found in API response")
                return {
                    'success': True,  # API worked, just no results
                    'results': [],
                    'total_found': 0,
                    'search_terms': search_terms
                }
            
        except Exception as e:
            logger.error(f"❌ API search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'total_found': 0
            }
    
    def format_ai_response(self, user_query: str, intent_data: Dict, search_results: Dict) -> str:
        """Step 3: Format AI response with top 3 products"""
        
        if not search_results.get('success'):
            return "দুঃখিত, এই মুহূর্তে সার্চ করতে সমস্যা হচ্ছে। একটু পরে চেষ্টা করুন।"
        
        products = search_results.get('results', [])[:3]
        if not products:
            return f"দুঃখিত, '{user_query}' এর জন্য কোনো পণ্য পাওয়া যায়নি। অন্য কিছু খুঁজে দেখুন।"
        
        if not self.groq:
            return self._simple_product_response(products, user_query)
        
        try:
            # Build simple product list
            product_list = []
            for i, product in enumerate(products, 1):
                title = product.get('title', 'নাম নেই')[:60]
                price = product.get('price', 'দাম নিশ্চিত নয়')
                product_list.append(f"{i}. {title} - {price} টাকা")
            
            product_text = " | ".join(product_list)
            
            # Simple prompt for response formatting
            prompt = (
                f"Customer searched for: {user_query}. "
                f"We found these products: {product_text}. "
                "Write a friendly Bengali response (2-3 sentences only) that: "
                "1) Acknowledges their search 2) Mentions 2-3 products with prices 3) Asks if they want details. "
                "Use natural Bengali conversation style."
            )
            
            logger.info("✍️ Formatting response with Groq AI...")
            ai_response = self.groq.generate_response(
                user_message=prompt,
                temperature=0.7,
                max_length=400
            )
            
            response = ai_response.strip() if ai_response else self._simple_product_response(products, user_query)
            logger.info(f"✅ AI response generated: {response[:50]}...")
            return response
            
        except Exception as e:
            logger.error(f"❌ AI response formatting failed: {e}")
            return self._simple_product_response(products, user_query)
    
    def _simple_product_response(self, products: List[Dict], user_query: str) -> str:
        """Simple fallback product response"""
        if not products:
            return f"দুঃখিত, '{user_query}' এর জন্য কোনো পণ্য পাওয়া যায়নি।"
        
        response = f"আমরা {len(products)}টি পণ্য পেয়েছি:\\n\\n"
        for i, product in enumerate(products[:3], 1):
            title = product.get('title', 'নাম নেই')[:50]
            price = product.get('price', 'দাম নিশ্চিত নয়')
            response += f"{i}. {title} - {price} টাকা\\n"
        
        response += "\\nকোনটি নিয়ে জানতে চান?"
        return response
    
    def enhanced_product_search(self, user_query: str) -> Dict:
        """Complete 3-step enhanced product search workflow"""
        logger.info(f"🚀 Starting enhanced product search for: {user_query}")
        
        # Step 1: Intent Detection
        intent_data = self.detect_search_intent(user_query)
        
        # Step 2: API Search  
        search_results = self.search_bdstall_api(intent_data['search_terms'])
        
        # Step 3: AI Response Formatting
        ai_response = self.format_ai_response(user_query, intent_data, search_results)
        
        # Compile result
        result = {
            'success': search_results.get('success', False),
            'response': ai_response,
            'products_found': search_results.get('total_found', 0),
            'top_products': search_results.get('results', [])[:3],
            'intent_detected': intent_data,
            'search_method': 'enhanced_ai_workflow'
        }
        
        logger.info(f"✅ Enhanced search completed - {result['products_found']} products found")
        return result


# Test if run directly
if __name__ == "__main__":
    searcher = EnhancedProductSearch()
    
    test_queries = [
        "web cam lagbe",
        "hp laptop price?", 
        "mobile phone ache?"
    ]
    
    for query in test_queries:
        print(f"\\n🧪 Testing: {query}")
        print("=" * 40)
        result = searcher.enhanced_product_search(query)
        print(f"Response: {result['response']}")
        print(f"Products: {result['products_found']}")