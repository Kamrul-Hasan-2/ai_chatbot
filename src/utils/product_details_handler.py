"""
Enhanced Product Details Handler
Fetches product information and creates rich Messenger templates with images/prices
"""

import re
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductDetailsHandler:
    """Fetches product details from BDStall API and creates rich templates"""
    
    def __init__(self, api_key: str = "mkh677ddd2sxxkkdjff"):
        """Initialize the product details handler"""
        self.api_key = api_key
        self.search_api = "https://www.bdstall.com/api/item/search/"
        self.product_cache = {}
        self.cache_timeout = 3600  # 1 hour
        logger.info("✅ ProductDetailsHandler initialized")
    
    def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch product details from BDStall API
        
        Args:
            product_id: Product identifier (e.g., "hp-laptop-123")
            
        Returns:
            Dictionary with product details or None if not found
        """
        try:
            # Check cache first
            if product_id in self.product_cache:
                cached_product, timestamp = self.product_cache[product_id]
                if (datetime.now() - timestamp).total_seconds() < self.cache_timeout:
                    logger.info(f"✅ Using cached product: {product_id}")
                    return cached_product
            
            logger.info(f"🔍 Fetching product details: {product_id}")
            
            # Search for product using BDStall API
            params = {
                'term': product_id,
                'key': self.api_key
            }
            
            response = requests.get(
                self.search_api,
                params=params,
                timeout=8,
                headers={'User-Agent': 'BDStall Chatbot/1.0'}
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️ API returned status {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse BDStall API format: {"getListingItem":["count",[{products}]]}
            if 'getListingItem' in data:
                listing_data = data['getListingItem']
                if isinstance(listing_data, list) and len(listing_data) >= 2:
                    products = listing_data[1] if isinstance(listing_data[1], list) else []
                    
                    if products:
                        product = products[0]  # Take first result
                        
                        product_details = {
                            'title': product.get('ListingTitle', 'Product'),
                            'price': product.get('Price', 'N/A'),
                            'description': product.get('Description', '')[:100],  # First 100 chars
                            'brand': product.get('BrandName', ''),
                            'model': product.get('ModelNo', ''),
                            'listing_id': product.get('ListingID', product_id),
                            'image_url': product.get('ImagePath', f"https://www.bdstall.com/details/{product_id}/"),
                            'url': f"https://www.bdstall.com/details/{product.get('ListingID', product_id)}/",
                            'availability': 'In Stock'
                        }
                        
                        # Cache the result
                        self.product_cache[product_id] = (product_details, datetime.now())
                        
                        logger.info(f"✅ Found product: {product_details['title']}")
                        return product_details
            
            logger.warning(f"⚠️ No product found for: {product_id}")
            return None
            
        except Exception as e:
            logger.warning(f"❌ Error fetching product: {e}")
            return None
    
    def create_generic_template(self, products: List[Dict[str, Any]], 
                                message_text: str = "") -> Dict[str, Any]:
        """
        Create a generic Messenger template with multiple products
        
        Args:
            products: List of product dictionaries
            message_text: Optional message text to include
            
        Returns:
            Messenger API payload
        """
        if not products:
            return self._create_text_message(message_text or "No products found")
        
        # Limit to 10 products (Messenger generic template limit)
        products = products[:10]
        
        elements = []
        for product in products:
            element = {
                "title": product.get('title', 'Product')[:80],  # 80 char limit
                "subtitle": f"Price: {product.get('price', 'N/A')}",
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
            description = product.get('description', '')
            if description:
                element['subtitle'] = f"{description}\nPrice: {product.get('price', 'N/A')}"
            
            elements.append(element)
        
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
    
    def create_button_template(self, product: Dict[str, Any], 
                              message_text: str = "") -> Dict[str, Any]:
        """
        Create a button template for a single product
        
        Args:
            product: Product dictionary
            message_text: Message text to display
            
        Returns:
            Messenger API payload
        """
        if not message_text:
            message_text = f"{product.get('title', 'Product')}\nPrice: {product.get('price', 'N/A')}"
        
        return {
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": message_text[:640],  # 640 char limit
                        "buttons": [
                            {
                                "type": "web_url",
                                "url": product.get('url', ''),
                                "title": "View this link"
                            }
                        ]
                    }
                }
            }
        }
    
    def create_image_template(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an image template with product photo
        
        Args:
            product: Product dictionary
            
        Returns:
            Messenger API payload
        """
        return {
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {
                        "url": product.get('image_url', ''),
                        "is_reusable": True
                    }
                }
            }
        }
    
    def _create_text_message(self, text: str) -> Dict[str, Any]:
        """Create a simple text message"""
        return {
            "messaging_type": "RESPONSE",
            "message": {
                "text": text
            }
        }
    
    def create_card_carousel(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a carousel of product cards
        
        Args:
            products: List of product dictionaries
            
        Returns:
            Messenger API payload
        """
        if not products:
            return self._create_text_message("No products available")
        
        # Limit to 10 items (Messenger carousel limit)
        products = products[:10]
        
        elements = []
        for product in products:
            element = {
                "title": product.get('title', 'Product')[:40],
                "subtitle": f"৳ {product.get('price', 'N/A')}",
                "image_url": product.get('image_url', ''),
                "buttons": [
                    {
                        "type": "web_url",
                        "url": product.get('url', ''),
                        "title": "Order Now"
                    }
                ]
            }
            elements.append(element)
        
        return {
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "product",
                        "elements": elements
                    }
                }
            }
        }
    
    def process_product_links(self, product_ids: List[str], 
                             message_text: str = "") -> Dict[str, Any]:
        """
        Process multiple product links and create appropriate template
        
        Args:
            product_ids: List of product IDs
            message_text: Message text context
            
        Returns:
            Dictionary with template and product details
        """
        logger.info(f"📦 Processing {len(product_ids)} products")
        
        products = []
        for product_id in product_ids:
            product = self.get_product_details(product_id)
            if product:
                products.append(product)
        
        # Choose template based on product count
        if len(products) == 0:
            template = self._create_text_message(message_text or "No products found")
        elif len(products) == 1:
            template = self.create_button_template(products[0], message_text)
        else:
            template = self.create_generic_template(products, message_text)
        
        return {
            "success": True,
            "products_found": len(products),
            "products": products,
            "template": template
        }


# Singleton instance
_handler_instance = None


def get_details_handler() -> ProductDetailsHandler:
    """Get or create singleton instance"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = ProductDetailsHandler()
    return _handler_instance
