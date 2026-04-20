"""
Dynamic Product Link Handler
Handles messages with product links dynamically
Extracts, parses, formats, and manages product links in conversations
"""
import os
import sys
import logging
import re
import json
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductLinkHandler:
    """
    Dynamically handles product links in messages
    - Extracts links from messages
    - Parses product information
    - Formats as interactive buttons
    - Manages product context
    """
    
    def __init__(self):
        """Initialize product link handler"""
        self.url_pattern = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
        self.bdstall_pattern = re.compile(r'https?://(?:www\.)?bdstall\.com/details/([^\s/?]+)', re.IGNORECASE)
        self.product_cache: Dict[str, Dict[str, Any]] = {}
        logger.info("✅ ProductLinkHandler initialized")
    
    def extract_links_from_message(self, message: str) -> List[str]:
        """
        Extract all URLs from a message
        
        Args:
            message: Message text
            
        Returns:
            List of URLs found
        """
        if not message:
            return []
        
        links = self.url_pattern.findall(message)
        logger.info(f"🔗 Extracted {len(links)} links from message")
        return links
    
    def is_product_link(self, link: str) -> bool:
        """
        Check if a link is a product link (from BDStall)
        
        Args:
            link: URL to check
            
        Returns:
            True if it's a BDStall product link
        """
        return bool(self.bdstall_pattern.match(link))
    
    def parse_product_link(self, link: str) -> Dict[str, Any]:
        """
        Parse product information from a link
        
        Args:
            link: Product URL
            
        Returns:
            Dictionary with product information
        """
        try:
            parsed = urlparse(link)
            
            # Extract product ID from URL
            match = self.bdstall_pattern.match(link)
            if match:
                product_id = match.group(1)
                
                return {
                    "success": True,
                    "url": link,
                    "product_id": product_id,
                    "domain": "bdstall.com",
                    "type": "product",
                    "parsed_at": datetime.now().isoformat()
                }
            
            # Generic URL parsing
            return {
                "success": True,
                "url": link,
                "product_id": None,
                "domain": parsed.netloc,
                "type": "external_link",
                "parsed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing link: {e}")
            return {
                "success": False,
                "url": link,
                "error": str(e)
            }
    
    def extract_product_info_from_message(self, message: str) -> Dict[str, Any]:
        """
        Extract all product information from a message
        Handles messages with product links and descriptions
        
        Args:
            message: Message text
            
        Returns:
            Dictionary with extracted products
        """
        links = self.extract_links_from_message(message)
        products = []
        
        for link in links:
            if self.is_product_link(link):
                product_info = self.parse_product_link(link)
                if product_info['success']:
                    products.append(product_info)
        
        # Extract text around links
        text_without_links = self.url_pattern.sub('', message).strip()
        
        return {
            "has_links": len(links) > 0,
            "has_products": len(products) > 0,
            "total_links": len(links),
            "total_products": len(products),
            "products": products,
            "all_links": links,
            "description": text_without_links,
            "raw_message": message
        }
    
    def format_message_with_links(self, message: str, max_length: int = 200) -> Dict[str, Any]:
        """
        Format a message with links, splitting description and links
        
        Args:
            message: Original message
            max_length: Max length for description
            
        Returns:
            Formatted message structure
        """
        extraction = self.extract_product_info_from_message(message)
        
        # Truncate description if too long
        description = extraction['description']
        if len(description) > max_length:
            description = description[:max_length] + "..."
        
        return {
            "formatted": True,
            "description": description,
            "products": extraction['products'],
            "links": extraction['all_links'],
            "message_type": "product_link" if extraction['has_products'] else "link",
            "extraction": extraction
        }
    
    def create_messenger_button(self, product_info: Dict[str, Any], title: str = "View Product", 
                               button_text: str = "View this link") -> Dict[str, Any]:
        """
        Create a Messenger button for a product link
        
        Args:
            product_info: Product information from parse_product_link()
            title: Button title
            button_text: Button label
            
        Returns:
            Messenger button payload
        """
        return {
            "type": "web_url",
            "url": product_info.get('url', ''),
            "title": button_text[:20],  # Messenger limit
            "webview_height_ratio": "tall"
        }
    
    def create_messenger_template(self, message: str, description: str = "") -> Dict[str, Any]:
        """
        Create a complete Messenger template with product links as buttons
        
        Args:
            message: Original message
            description: Optional additional description
            
        Returns:
            Messenger API payload
        """
        formatted = self.format_message_with_links(message)
        
        if not formatted['products']:
            # No products, return simple text
            return {
                "messaging_type": "RESPONSE",
                "message": {
                    "text": message
                }
            }
        
        # Create buttons for each product
        buttons = []
        for idx, product in enumerate(formatted['products'], 1):
            buttons.append(self.create_messenger_button(
                product,
                title=f"Product {idx}",
                button_text="View this link"
            ))
        
        if len(buttons) == 1:
            # Single button template
            return {
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "button",
                            "text": formatted['description'][:640],
                            "buttons": buttons
                        }
                    }
                }
            }
        else:
            # Generic template for multiple products
            elements = []
            for idx, (product, button) in enumerate(zip(formatted['products'], buttons), 1):
                elements.append({
                    "title": f"Product {idx}",
                    "buttons": [button]
                })
            
            return {
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": elements
                        }
                    }
                }
            }
    
    def process_incoming_link_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        Process an incoming message with links
        Store in cache and prepare for context
        
        Args:
            user_id: User identifier
            message: Message text
            
        Returns:
            Processing result
        """
        try:
            extracted = self.extract_product_info_from_message(message)
            formatted = self.format_message_with_links(message)
            
            # Store in cache for quick retrieval
            cache_key = f"{user_id}_{datetime.now().timestamp()}"
            self.product_cache[cache_key] = {
                "user_id": user_id,
                "message": message,
                "extracted": extracted,
                "formatted": formatted,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Processed link message for user_id={user_id}")
            logger.info(f"   Products found: {extracted['total_products']}")
            logger.info(f"   Links found: {extracted['total_links']}")
            
            return {
                "success": True,
                "user_id": user_id,
                "has_links": extracted['has_links'],
                "has_products": extracted['has_products'],
                "products_count": extracted['total_products'],
                "links_count": extracted['total_links'],
                "extracted": extracted,
                "formatted": formatted,
                "messenger_template": self.create_messenger_template(message)
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing link message: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }
    
    def get_user_product_context(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get product links sent/discussed in user's recent conversation
        
        Args:
            user_id: User identifier
            limit: Number of recent products to return
            
        Returns:
            List of product links from conversation
        """
        user_products = [
            item for item in self.product_cache.values()
            if item['user_id'] == user_id
        ]
        
        # Sort by timestamp, most recent first
        user_products.sort(
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        return user_products[:limit]
    
    def clean_cache(self, hours: int = 24) -> int:
        """
        Clean old entries from product cache
        
        Args:
            hours: Remove entries older than this
            
        Returns:
            Number of entries removed
        """
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        initial_size = len(self.product_cache)
        
        to_remove = []
        for key, item in self.product_cache.items():
            item_time = datetime.fromisoformat(item['timestamp'])
            if item_time < cutoff_time:
                to_remove.append(key)
        
        for key in to_remove:
            del self.product_cache[key]
        
        removed_count = len(to_remove)
        logger.info(f"🧹 Cleaned cache: removed {removed_count} old entries")
        
        return removed_count


# Singleton instance
_link_handler = None


def get_link_handler() -> ProductLinkHandler:
    """Get or create the product link handler singleton"""
    global _link_handler
    if _link_handler is None:
        _link_handler = ProductLinkHandler()
    return _link_handler
