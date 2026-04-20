"""
Category Product Handler
Fetches and displays products from a specific BDStall category
Converts category links to rich product templates
"""

import re
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CategoryProductHandler:
    """Handles BDStall category searches and product display"""
    
    def __init__(self, api_key: str = "mkh677ddd2sxxkkdjff"):
        """Initialize category product handler"""
        self.api_key = api_key
        self.search_api = "https://www.bdstall.com/api/item/search/"
        self.category_cache = {}
        self.cache_timeout = 3600  # 1 hour
        logger.info("✅ CategoryProductHandler initialized")
    
    def extract_category_from_message(self, message: str) -> Optional[str]:
        """
        Extract category name from message
        
        Examples:
        - "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন"
        - "You can see products in laptop category"
        - Category link: https://www.bdstall.com/laptop/
        
        Args:
            message: Message text
            
        Returns:
            Category name or None
        """
        if not message:
            return None
        
        # Pattern 1: Extract from Bengali message
        bengali_pattern = r'(?:আপনি\s+)?([^\s]+)\s+(?:ক্যাটাগরিতে|category)'
        match = re.search(bengali_pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern 2: Extract from English message
        english_pattern = r'(?:in\s+the\s+)?([^\s/]+)\s+(?:category|ক্যাটাগরি)'
        match = re.search(english_pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern 3: Extract from URL
        url_pattern = r'bdstall\.com/([^\s/?]+)/?'
        match = re.search(url_pattern, message, re.IGNORECASE)
        if match:
            category = match.group(1)
            if category not in ['details', 'api', 'item']:
                return category
        
        return None
    
    def fetch_category_products(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch products from a specific category
        
        Args:
            category: Category name (e.g., "laptop", "phone", "camera")
            limit: Number of products to fetch (max 10)
            
        Returns:
            List of product dictionaries
        """
        try:
            # Check cache first
            cache_key = f"{category.lower()}_{limit}"
            if cache_key in self.category_cache:
                cached_products, timestamp = self.category_cache[cache_key]
                if (datetime.now() - timestamp).total_seconds() < self.cache_timeout:
                    logger.info(f"✅ Using cached category: {category}")
                    return cached_products
            
            logger.info(f"🔍 Fetching products for category: {category}")
            
            # Search using BDStall API
            params = {
                'term': category,
                'key': self.api_key
            }
            
            response = requests.get(
                self.search_api,
                params=params,
                timeout=10,
                headers={'User-Agent': 'BDStall Chatbot/1.0'}
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ API returned status {response.status_code}")
                return []
            
            data = response.json()
            
            # Parse BDStall API format: {"getListingItem":["count",[{products}]]}
            if 'getListingItem' in data:
                listing_data = data['getListingItem']
                if isinstance(listing_data, list) and len(listing_data) >= 2:
                    products_raw = listing_data[1] if isinstance(listing_data[1], list) else []
                    
                    # Parse and limit results
                    products = []
                    for product_data in products_raw[:limit]:
                        product = {
                            'title': product_data.get('ListingTitle', 'Product'),
                            'price': product_data.get('Price', 'N/A'),
                            'description': product_data.get('Description', '')[:100],
                            'brand': product_data.get('BrandName', ''),
                            'model': product_data.get('ModelNo', ''),
                            'listing_id': product_data.get('ListingID', ''),
                            'image_url': product_data.get('ImagePath', ''),
                            'url': f"https://www.bdstall.com/details/{product_data.get('ListingID', '')}/",
                            'availability': 'In Stock'
                        }
                        products.append(product)
                    
                    # Cache the results
                    self.category_cache[cache_key] = (products, datetime.now())
                    
                    logger.info(f"✅ Found {len(products)} products in {category}")
                    return products
            
            logger.warning(f"⚠️ No products found for category: {category}")
            return []
            
        except Exception as e:
            logger.warning(f"❌ Error fetching category products: {e}")
            return []
    
    def create_category_generic_template(self, category: str, products: List[Dict[str, Any]],
                                         message_text: str = "") -> Dict[str, Any]:
        """
        Create generic template for category products
        
        Args:
            category: Category name
            products: List of product dictionaries
            message_text: Optional message prefix
            
        Returns:
            Messenger template
        """
        if not products:
            category_link = f"https://www.bdstall.com/{category}/"
            return {
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "button",
                            "text": message_text or f"Check out {category} products",
                            "buttons": [
                                {
                                    "type": "web_url",
                                    "url": category_link,
                                    "title": "View All"
                                }
                            ]
                        }
                    }
                }
            }
        
        # Build elements for generic template
        elements = []
        for product in products[:10]:  # Limit to 10 products
            element = {
                "title": product.get('title', 'Product')[:80],
                "subtitle": f"৳ {product.get('price', 'N/A')}",
                "image_url": product.get('image_url', ''),
                "default_action": {
                    "type": "web_url",
                    "url": product.get('url', ''),
                    "webview_height_ratio": "tall"
                },
                "buttons": [
                    {
                        "type": "web_url",
                        "url": product.get('url', ''),
                        "title": "View Details"
                    },
                    {
                        "type": "postback",
                        "title": "Add to Cart",
                        "payload": f"ADD_TO_CART_{product.get('listing_id', '')}"
                    }
                ]
            }
            
            # Add description if available
            if product.get('description'):
                element['subtitle'] = f"{product['description']}\n৳ {product.get('price', 'N/A')}"
            
            elements.append(element)
        
        if not message_text:
            message_text = f"Popular {category} products"
        
        return {
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "image_aspect_ratio": "square",
                        "elements": elements
                    }
                }
            }
        }
    
    def convert_category_message_to_template(self, message: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Convert a category message to an enhanced template
        
        Args:
            message: Message text potentially containing category reference
            
        Returns:
            Tuple of (is_category, template_dict)
        """
        try:
            # Extract category
            category = self.extract_category_from_message(message)
            
            if not category:
                return False, {}
            
            logger.info(f"🎯 Detected category: {category}")
            
            # Fetch products
            products = self.fetch_category_products(category, limit=5)
            
            if not products:
                logger.info(f"   ⚠️  No products found, returning basic message")
                return False, {}
            
            # Create template
            template = self.create_category_generic_template(
                category,
                products,
                message_text=f"আপনি {category} ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন"
            )
            
            logger.info(f"   ✅ Created category template with {len(products)} products")
            
            return True, {
                "success": True,
                "is_category": True,
                "category": category,
                "products_found": len(products),
                "products": products,
                "template": template
            }
            
        except Exception as e:
            logger.warning(f"❌ Error converting category message: {e}")
            return False, {}
    
    def process_category_link(self, category_link: str, limit: int = 5) -> Dict[str, Any]:
        """
        Process a category link and create template
        
        Args:
            category_link: Category URL (e.g., "https://www.bdstall.com/laptop/")
            limit: Number of products to show
            
        Returns:
            Processing result with template
        """
        try:
            # Extract category from URL
            match = re.search(r'bdstall\.com/([^\s/?]+)/?', category_link)
            if not match:
                return {"success": False, "error": "Invalid category link"}
            
            category = match.group(1)
            
            # Fetch products
            products = self.fetch_category_products(category, limit)
            
            # Create template
            template = self.create_category_generic_template(category, products)
            
            return {
                "success": True,
                "category": category,
                "products_found": len(products),
                "products": products,
                "template": template
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing category link: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
_handler_instance = None


def get_category_handler() -> CategoryProductHandler:
    """Get or create singleton instance"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = CategoryProductHandler()
    return _handler_instance
