"""
Demonstration: Intent Detection and Product Search
Shows how to extract intent from Bengali/English queries and search products
"""
import re
import logging
from intent_entity_detector import IntentEntityDetector, Intent
from enhanced_product_search import EnhancedProductSearch
import json

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class IntentSearchDemo:
    """Demonstrates intent detection and product search"""
    
    def __init__(self):
        self.intent_detector = IntentEntityDetector()
        self.product_search = EnhancedProductSearch()
        
        # Common product keywords in Bengali and English
        self.product_keywords = {
            'laptop': ['laptop', 'ল্যাপটপ'],
            'phone': ['phone', 'mobile', 'ফোন', 'মোবাইল'],
            'computer': ['computer', 'কম্পিউটার'],
            'webcam': ['webcam', 'web cam', 'ওয়েবক্যাম'],
            'printer': ['printer', 'প্রিন্টার'],
            'headphone': ['headphone', 'headset', 'হেডফোন'],
            'monitor': ['monitor', 'মনিটর'],
            'keyboard': ['keyboard', 'কীবোর্ড'],
            'mouse': ['mouse', 'মাউস']
        }
    
    def extract_product_intent(self, user_message: str) -> str:
        """
        Extract product intent from user message
        Handles both Bengali and English
        """
        # First try NLP extraction
        nlp_result = self.intent_detector.process_message(user_message)
        
        # Extract product entities
        product_entities = [
            entity.value for entity in nlp_result.entities 
            if entity.entity_type.value == 'product_name'
        ]
        
        if product_entities:
            return product_entities[0]
        
        # Fallback: Simple keyword matching
        message_lower = user_message.lower()
        
        for product, keywords in self.product_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return product
        
        # If nothing found, use the whole message
        # But clean it up
        cleaned = re.sub(r'(আছে|কি|ase|আছে কি|bhalo|ভালো|valo|দেখান|dekhao|lagbe|লাগবে|চাই|need|want)', '', user_message, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        
        return cleaned if cleaned else user_message
    
    def search_and_display(self, user_query: str):
        """
        Complete workflow: Intent Detection -> Search -> Display
        """
        print("\n" + "=" * 70)
        print(f"💬 User Query: '{user_query}'")
        print("=" * 70)
        
        # Step 1: Intent Detection
        print("\n🔍 STEP 1: Detecting Intent & Extracting Keywords")
        print("-" * 70)
        
        nlp_result = self.intent_detector.process_message(user_query)
        product_intent = self.extract_product_intent(user_query)
        
        print(f"   ✓ Detected Intent: {nlp_result.intent.value}")
        print(f"   ✓ Language: {nlp_result.language.value}")
        print(f"   ✓ Extracted Product Keyword: '{product_intent}'")
        
        # Step 2: API Search
        print("\n🔍 STEP 2: Searching BDStall API")
        print("-" * 70)
        
        search_result = self.product_search.enhanced_product_search(product_intent)
        
        print(f"   ✓ Products Found: {search_result['products_found']}")
        print(f"   ✓ Search Successful: {'Yes' if search_result['success'] else 'No'}")
        
        # Step 3: Display Results
        print("\n📦 STEP 3: Top Products")
        print("-" * 70)
        
        if search_result['products_found'] > 0:
            for i, product in enumerate(search_result['top_products'], 1):
                print(f"\n   {i}. {product['title'][:60]}")
                print(f"      💰 Price: {product['price']} টাকা")
                print(f"      🔗 Link: {product['url']}")
                if product.get('brand'):
                    print(f"      🏷️  Brand: {product['brand']}")
        else:
            print("   ⚠️  No products found")
        
        # Step 4: Chatbot Response
        print("\n🤖 STEP 4: Chatbot Response")
        print("-" * 70)
        print(f"   {search_result['response']}")
        print()
        
        return search_result


def main():
    """Run demonstrations"""
    demo = IntentSearchDemo()
    
    # Test queries demonstrating different patterns
    test_queries = [
        # Bengali queries
        "bhalo laptop ase",           # "good laptop is there?"
        "laptop আছে কি",              # "is laptop available?"
        "ভালো ল্যাপটপ দেখান",        # "show good laptops"
        
        # English queries
        "hp laptop price",
        "gaming laptop",
        "web cam lagbe",               # "need web cam"
        
        # Mixed queries
        "laptop খুঁজছি",              # "searching for laptop"
        "phone ase?",                  # "is phone available?"
    ]
    
    print("\n" + "=" * 70)
    print("🚀 INTENT DETECTION & PRODUCT SEARCH DEMONSTRATION")
    print("=" * 70)
    print("\nThis demonstrates:")
    print("  1. Detecting intent from Bengali/English queries")
    print("  2. Extracting product keywords")
    print("  3. Searching BDStall API")
    print("  4. Displaying results in Bengali")
    
    results = []
    
    for query in test_queries:
        result = demo.search_and_display(query)
        results.append({
            'query': query,
            'intent': result['intent_detected']['search_terms'],
            'products_found': result['products_found']
        })
        
        input("\n👉 Press Enter to continue to next query...")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    for r in results:
        print(f"   '{r['query']}' -> '{r['intent']}' -> {r['products_found']} products")
    
    print("\n✅ Demonstration Complete!")


if __name__ == "__main__":
    main()
