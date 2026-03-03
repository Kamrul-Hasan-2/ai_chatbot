"""
INTENT DETECTION & PRODUCT SEARCH - Quick Reference Guide
===========================================================

This guide shows how to detect intent from Bengali/English queries
and search the BDStall API for products.

WORKFLOW:
---------
User Input: "bhalo laptop ase" (Do you have good laptops?)
    ↓
Step 1: Extract Intent → "laptop"
    ↓
Step 2: Search API → BDStall API with keyword "laptop"
    ↓
Step 3: Return Results → Top products with prices

CODE IMPLEMENTATION:
--------------------
"""

from enhanced_product_search import EnhancedProductSearch
import re


class ProductIntentHandler:
    """
    Handles intent detection and product search
    """
    
    def __init__(self):
        self.product_search = EnhancedProductSearch()
    
    def detect_product_intent(self, user_message: str) -> str:
        """
        Extract product keyword from user message
        
        Args:
            user_message: User's input (Bengali/English)
            
        Returns:
            Product keyword to search for
            
        Examples:
            >>> detect_product_intent("bhalo laptop ase")
            'laptop'
            
            >>> detect_product_intent("laptop আছে কি")
            'laptop'
            
            >>> detect_product_intent("hp laptop price")
            'laptop'
        """
        text = user_message.lower()
        
        # Product keyword mapping (Bengali -> English)
        product_map = {
            'laptop': ['laptop', 'ল্যাপটপ'],
            'phone': ['phone', 'mobile', 'ফোন', 'মোবাইল'],
            'computer': ['computer', 'কম্পিউটার'],
            'webcam': ['webcam', 'web cam', 'ওয়েবক্যাম'],
            'printer': ['printer', 'প্রিন্টার'],
            'headphone': ['headphone', 'headset', 'হেডফোন'],
        }
        
        # Find product keyword
        for english_keyword, keywords in product_map.items():
            for keyword in keywords:
                if keyword in text:
                    return english_keyword
        
        # Fallback: clean and return
        cleaned = re.sub(r'\b(bhalo|valo|ase|ache|আছে|কি|ভালো|দেখান|lagbe|লাগবে)\b', 
                        '', text, flags=re.IGNORECASE)
        return cleaned.strip() or user_message
    
    def search_and_respond(self, user_message: str) -> dict:
        """
        Complete workflow: Detect intent → Search → Format response
        
        Args:
            user_message: User's query
            
        Returns:
            dict with:
                - intent: Detected product keyword  
                - products_found: Number of products
                - top_products: List of top 3 products
                - response: Bengali chatbot response
        """
        # Step 1: Detect intent
        intent = self.detect_product_intent(user_message)
        
        # Step 2: Search API
        result = self.product_search.enhanced_product_search(intent)
        
        # Step 3: Return formatted result
        return {
            'user_message': user_message,
            'intent': intent,
            'products_found': result['products_found'],
            'top_products': result['top_products'],
            'response': result['response']
        }


# ============================================================
# USAGE EXAMPLES
# ============================================================

def example_basic_usage():
    """Example 1: Basic usage"""
    handler = ProductIntentHandler()
    
    # User asks in Bengali
    user_input = "bhalo laptop ase"
    
    result = handler.search_and_respond(user_input)
    
    print(f"User: {user_input}")
    print(f"Intent Detected: {result['intent']}")
    print(f"Products Found: {result['products_found']}")
    print(f"Bot Response: {result['response']}")


def example_flask_integration():
    """Example 2: Flask app integration"""
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    handler = ProductIntentHandler()
    
    @app.route('/chat', methods=['POST'])
    def chat():
        data = request.json
        user_message = data.get('message', '')
        
        # Process message
        result = handler.search_and_respond(user_message)
        
        return jsonify({
            'intent': result['intent'],
            'response': result['response'],
            'products': result['top_products'][:3]  # Top 3 products
        })


def example_messenger_integration():
    """Example 3: Facebook Messenger integration"""
    handler = ProductIntentHandler()
    
    def handle_messenger_message(sender_id: str, message_text: str):
        # Detect intent and search
        result = handler.search_and_respond(message_text)
        
        # Send response to user
        send_message(sender_id, result['response'])
        
        # Optionally send product cards
        if result['products_found'] > 0:
            for product in result['top_products'][:3]:
                send_product_card(sender_id, product)


def example_batch_processing():
    """Example 4: Process multiple queries"""
    handler = ProductIntentHandler()
    
    queries = [
        "bhalo laptop ase",
        "laptop আছে কি",  
        "hp laptop price",
        "web cam lagbe",
        "phone দেখান"
    ]
    
    for query in queries:
        result = handler.search_and_respond(query)
        print(f"\nQuery: {query}")
        print(f"Intent: {result['intent']}")
        print(f"Found: {result['products_found']} products")
        print(f"Response: {result['response'][:80]}...")


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("INTENT DETECTION & PRODUCT SEARCH - Examples")
    print("=" * 60)
    
    # Run basic example
    print("\n1. BASIC USAGE:")
    print("-" * 60)
    example_basic_usage()
    
    # Run batch example
    print("\n\n2. BATCH PROCESSING:")
    print("-" * 60)
    example_batch_processing()
    
    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("\nYou can now integrate this into:")
    print("  - Flask web app (see example_flask_integration)")
    print("  - Facebook Messenger (see example_messenger_integration)")
    print("  - Any other platform")
    print("=" * 60)
