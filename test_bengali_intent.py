"""
Test Bengali Intent Detection and Product Search
Demonstrates: "bhalo laptop ase" -> Intent Detection -> Search API
"""
import logging
from intent_entity_detector import IntentEntityDetector, Intent
from enhanced_product_search import EnhancedProductSearch
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_bengali_intent_search():
    """Test intent detection and search for Bengali input"""
    
    # Initialize components
    intent_detector = IntentEntityDetector()
    product_search = EnhancedProductSearch()
    
    # User input
    user_message = "bhalo laptop ase"
    
    print("=" * 60)
    print("🧪 Bengali Intent Detection & Search Test")
    print("=" * 60)
    print(f"📝 User Input: {user_message}")
    print()
    
    # Step 1: Detect Intent
    print("🔍 Step 1: Detecting Intent...")
    print("-" * 60)
    
    nlp_result = intent_detector.process_message(user_message)
    
    print(f"✅ Intent Detected: {nlp_result.intent.value}")
    print(f"✅ Confidence: {nlp_result.intent_confidence:.2f}")
    print(f"✅ Language: {nlp_result.language.value}")
    print(f"✅ Sentiment: {nlp_result.sentiment.value}")
    print()
    
    # Step 2: Extract Product Keywords
    print("🔍 Step 2: Extracting Product Keywords...")
    print("-" * 60)
    
    # Extract "laptop" from the message
    extracted_keywords = []
    for entity in nlp_result.entities:
        print(f"   - {entity.entity_type.value}: {entity.value}")
        extracted_keywords.append(entity.value)
    
    # If no entities found, extract from message
    if not extracted_keywords:
        # Simple keyword extraction for "laptop"
        message_lower = user_message.lower()
        if 'laptop' in message_lower:
            extracted_keywords.append('laptop')
        
    search_term = ' '.join(extracted_keywords) if extracted_keywords else user_message
    print(f"✅ Search Keywords: {search_term}")
    print()
    
    # Step 3: Search BDStall API
    print("🔍 Step 3: Searching BDStall API...")
    print("-" * 60)
    
    result = product_search.enhanced_product_search(search_term)
    
    print(f"✅ Products Found: {result['products_found']}")
    print()
    
    # Step 4: Display Results
    print("📦 Top Products:")
    print("-" * 60)
    
    for i, product in enumerate(result['top_products'], 1):
        print(f"\n{i}. {product['title']}")
        print(f"   💰 Price: {product['price']} টাকা")
        print(f"   🔗 URL: {product['url']}")
        if product.get('brand'):
            print(f"   🏷️  Brand: {product['brand']}")
        if product.get('model'):
            print(f"   📱 Model: {product['model']}")
    
    print()
    print("=" * 60)
    print("🤖 Chatbot Response:")
    print("=" * 60)
    print(result['response'])
    print()
    
    # Return full result for further analysis
    return {
        'user_input': user_message,
        'detected_intent': nlp_result.intent.value,
        'confidence': nlp_result.intent_confidence,
        'search_keywords': search_term,
        'products_found': result['products_found'],
        'top_products': result['top_products'],
        'chatbot_response': result['response']
    }


def test_multiple_bengali_queries():
    """Test multiple Bengali product queries"""
    
    test_queries = [
        "bhalo laptop ase",
        "laptop আছে কি",
        "ভালো ল্যাপটপ দেখান",
        "hp laptop price",
        "gaming laptop খুঁজছি"
    ]
    
    product_search = EnhancedProductSearch()
    
    print("\n" + "=" * 60)
    print("🧪 Testing Multiple Bengali Queries")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 60)
        
        result = product_search.enhanced_product_search(query)
        
        print(f"✅ Products: {result['products_found']}")
        print(f"💬 Response: {result['response'][:100]}...")
        print()


if __name__ == "__main__":
    # Test single query with detailed output
    result = test_bengali_intent_search()
    
    # Save result to JSON for analysis
    with open('test_bengali_intent_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Test results saved to: test_bengali_intent_result.json")
    
    # Test multiple queries
    input("\n\nPress Enter to test multiple queries...")
    test_multiple_bengali_queries()
