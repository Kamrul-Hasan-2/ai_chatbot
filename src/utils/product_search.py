"""
Product Search API Handler
Searches products from BDStall API and formats responses
"""
import requests
import logging
from typing import List, Dict, Optional
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductSearchAPI:
    def __init__(self, api_key: str = "mkh677ddd2sxxkkdjff"):
        """
        Initialize Product Search API
        
        Args:
            api_key: API key for BDStall API
        """
        self.base_url = "https://www.bdstall.com/api/item/search/"
        self.api_key = api_key
        
    def search_products(self, query: str, max_results: int = 5) -> Dict:
        """
        Search for products using the API
        
        Args:
            query: Search term (e.g., "hp laptop", "iphone 13")
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        try:
            logger.info(f"Searching for: {query}")
            
            # Build API URL
            params = {
                'term': query,
                'key': self.api_key
            }
            
            # Make API request
            response = requests.get(
                self.base_url,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Parse results - BDStall API format: {"getListingItem":["count",[{products}]]}
            if 'getListingItem' in data:
                listing_data = data['getListingItem']
                if isinstance(listing_data, list) and len(listing_data) >= 2:
                    total_count = listing_data[0]
                    products = listing_data[1] if isinstance(listing_data[1], list) else []
                    
                    if products:
                        result_products = products[:max_results]
                        
                        result = {
                            'success': True,
                            'query': query,
                            'total_found': int(total_count) if total_count else len(products),
                            'products': self._parse_products(result_products)
                        }
                        
                        logger.info(f"Found {len(result_products)} products")
                        return result
            
            # No products found
            logger.warning("No products found")
            return {
                'success': False,
                'query': query,
                'total_found': 0,
                'products': []
            }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'total_found': 0,
                'products': []
            }
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'total_found': 0,
                'products': []
            }
    
    def _parse_products(self, products: List[Dict]) -> List[Dict]:
        """
        Parse product data from BDStall API response
        
        Args:
            products: List of product dictionaries from API
            
        Returns:
            List of parsed product information
        """
        parsed = []
        
        for product in products:
            # Parse price
            price = product.get('Price', 0) or product.get('price', 0)
            original_price = product.get('OriginalPrice') or product.get('original_price', 0)
            
            # Parse stock status
            stock_qty = int(product.get('StockQuantity', 0) or product.get('stock_quantity', 0) or 0)
            in_stock = stock_qty > 0 or product.get('in_stock', True)
            
            # Calculate discount
            discount = 0
            if original_price and price:
                try:
                    discount = int(((float(original_price) - float(price)) / float(original_price)) * 100)
                except:
                    discount = 0
            
            parsed_product = {
                'name': product.get('ListingTitle') or product.get('title', 'Unknown Product'),
                'price': self._format_price(price),
                'original_price': self._format_price(original_price) if original_price else None,
                'discount': discount,
                'available': in_stock,
                'stock_status': 'In Stock' if in_stock else 'Out of Stock',
                'url': product.get('UrlSlug') or product.get('slug', ''),
                'seller': product.get('ShopName') or product.get('shop_name', 'BDStall'),
                'image': product.get('ImageURL') or product.get('image', ''),
                'rating': float(product.get('Star', 0) or 0),
                'category': product.get('CategoryName') or product.get('category', ''),
                'listing_id': product.get('ListingID') or product.get('id', ''),
            }
            
            parsed.append(parsed_product)
        
        return parsed
    
    def _format_price(self, price) -> str:
        """Format price with Taka symbol"""
        if not price or price == 0:
            return "Price not available"
        
        try:
            return f"৳ {float(price):,.0f}"
        except:
            return str(price)
    
    def format_response(
        self, 
        search_result: Dict, 
        language: str = 'bengali'
    ) -> str:
        """
        Format search results into a natural conversational response
        
        Args:
            search_result: Search result dictionary
            language: 'bengali' or 'english'
            
        Returns:
            Natural conversational response string
        """
        if not search_result.get('success'):
            if language == 'bengali':
                return f"দুঃখিত, '{search_result['query']}' এর কোনো পণ্য খুঁজে পাইনি। অন্য কিছু খোঁজ করে দেখুন।"
            else:
                return f"Sorry, I couldn't find any products for '{search_result['query']}'. Try searching for something else."
        
        products = search_result['products']
        total = search_result['total_found']
        
        if not products:
            if language == 'bengali':
                return f"'{search_result['query']}' এর কোনো পণ্য পাওয়া যায়নি।"
            else:
                return f"No products found for '{search_result['query']}'."
        
        # Build natural conversational response
        if language == 'bengali':
            if len(products) == 1:
                response = f"হ্যাঁ, আমার কাছে {products[0]['name']} আছে। দাম {products[0]['price']} টাকা।"
            else:
                response = f"আপনার জন্য কয়েকটি ভালো অপশন আছে। "
                
                for i, product in enumerate(products[:3]):
                    if i == 0:
                        response += f"প্রথমে {product['name']} - এর দাম {product['price']} টাকা"
                    elif i == 1:
                        response += f", তারপর {product['name']} - {product['price']} টাকা"
                    else:
                        response += f", এবং {product['name']} - {product['price']} টাকা"
                
                response += "। "
                
                if total > 3:
                    response += f"আরও {total - 3}টি পণ্য আছে। "
            
            # Add stock information naturally
            available_products = [p for p in products[:3] if p['available']]
            if available_products:
                response += "সব পণ্যই স্টকে আছে। "
            else:
                response += "কিছু পণ্য স্টকে নেই, আপনি চাইলে অর্ডার করে রাখতে পারেন। "
                
            response += "আরো জানতে চাইলে বা অর্ডার করতে চাইলে www.bdstall.com দেখুন।"
            
        else:
            if len(products) == 1:
                response = f"Yes, we have {products[0]['name']} for {products[0]['price']} taka."
            else:
                response = f"I found some great options for you. "
                
                for i, product in enumerate(products[:3]):
                    if i == 0:
                        response += f"First, {product['name']} costs {product['price']} taka"
                    elif i == 1:
                        response += f", then {product['name']} for {product['price']} taka"
                    else:
                        response += f", and {product['name']} for {product['price']} taka"
                
                response += ". "
                
                if total > 3:
                    response += f"We have {total - 3} more options available. "
            
            # Add stock information naturally  
            available_products = [p for p in products[:3] if p['available']]
            if available_products:
                response += "All products are in stock. "
            else:
                response += "Some products may be out of stock, but you can pre-order. "
                
            response += "Visit www.bdstall.com for more details and to place an order."
        
        return response
    
    def detect_product_query(self, message: str) -> Optional[str]:
        """
        Detect if message is a product search query
        
        Args:
            message: User message
            
        Returns:
            Extracted search term or None
        """
        message_lower = message.lower()
        
        # Common product keywords
        product_keywords = [
            'laptop', 'phone', 'mobile', 'iphone', 'samsung', 'hp', 'dell',
            'asus', 'lenovo', 'acer', 'watch', 'headphone', 'earphone',
            'speaker', 'camera', 'printer', 'monitor', 'keyboard', 'mouse',
            'tablet', 'charger', 'cable', 'case', 'cover', 'screen protector',
            # Bengali
            'ল্যাপটপ', 'ফোন', 'মোবাইল', 'কম্পিউটার', 'প্রিন্টার',
        ]
        
        # Check if any product keyword is in the message
        has_product_keyword = any(keyword in message_lower for keyword in product_keywords)
        
        # Search trigger phrases
        search_triggers = [
            'search for', 'find', 'looking for', 'need', 'want to buy',
            'show me', 'do you have', 'available', 'আছে', 'খুজছি',
            'দেখাও', 'পাওয়া যাবে', 'কিনতে চাই', 'লাগবে'
        ]
        
        has_search_trigger = any(trigger in message_lower for trigger in search_triggers)
        
        if has_product_keyword or has_search_trigger:
            # Extract product name (remove trigger words)
            query = message
            
            # Remove common trigger phrases
            for trigger in ['search for', 'find me', 'looking for', 'show me',
                          'do you have', 'আছে কি', 'পাওয়া যাবে', 'খুজছি']:
                query = re.sub(trigger, '', query, flags=re.IGNORECASE)
            
            # Clean up
            query = query.strip().strip('?!.,')
            
            if len(query) > 2:
                return query
        
        return None


def main():
    """Test the product search API"""
    
    print("=" * 70)
    print("Product Search API Test")
    print("=" * 70)
    
    api = ProductSearchAPI()
    
    # Test queries
    test_queries = [
        "hp laptop",
        "iphone 13",
        "samsung phone",
        "printer"
    ]
    
    for query in test_queries:
        print(f"\nSearching for: {query}")
        print("-" * 70)
        
        result = api.search_products(query, max_results=3)
        
        if result['success']:
            print(f"✓ Found {result['total_found']} products\n")
            
            # Format in Bengali
            response_bn = api.format_response(result, 'bengali')
            print("Bengali Response:")
            print(response_bn)
            print()
            
            # Format in English
            response_en = api.format_response(result, 'english')
            print("English Response:")
            print(response_en)
        else:
            print(f"✗ Search failed: {result.get('error', 'Unknown error')}")
        
        print("=" * 70)


if __name__ == "__main__":
    main()
