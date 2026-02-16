"""
Test Product Search Integration
"""
from product_search import ProductSearchAPI


def test_product_search():
    """Test product search API"""
    
    print("\n" + "=" * 70)
    print("🔍 Product Search API Test")
    print("=" * 70 + "\n")
    
    api = ProductSearchAPI()
    
    # Test queries
    test_cases = [
        ("hp laptop", "Bengali"),
        ("iphone 13", "English"),
        ("samsung phone", "Bengali"),
        ("printer", "English"),
        ("headphone", "Bengali"),
    ]
    
    for query, lang in test_cases:
        print(f"\n{'─' * 70}")
        print(f"🔎 Search Query: '{query}'")
        print(f"📝 Language: {lang}")
        print(f"{'─' * 70}\n")
        
        # Search
        result = api.search_products(query, max_results=3)
        
        if result['success']:
            print(f"✓ Found {result['total_found']} products\n")
            
            # Show products
            for i, product in enumerate(result['products'], 1):
                print(f"【{i}】 {product['name']}")
                print(f"    💰 Price: {product['price']}")
                print(f"    📦 Status: {product['stock_status']}")
                if product['discount'] > 0:
                    print(f"    🏷️  Discount: {product['discount']}%")
                print()
            
            # Format response
            language = 'bengali' if lang == 'Bengali' else 'english'
            response = api.format_response(result, language)
            
            print(f"🤖 Bot Response ({lang}):")
            print(f"{'-' * 70}")
            print(response)
            print(f"{'-' * 70}")
            
        else:
            error = result.get('error', 'Unknown error')
            print(f"✗ Search failed: {error}")
    
    print("\n" + "=" * 70)
    print("✓ Product Search Test Complete!")
    print("=" * 70 + "\n")


def test_query_detection():
    """Test product query detection"""
    
    print("\n" + "=" * 70)
    print("🎯 Query Detection Test")
    print("=" * 70 + "\n")
    
    api = ProductSearchAPI()
    
    test_messages = [
        "আপনাদের কাছে hp laptop আছে?",
        "Do you have iPhone 13?",
        "আমি একটা samsung phone কিনতে চাই",
        "Show me printers",
        "laptop দেখাও",
        "আসসালামু আলাইকুম",  # Should not detect
        "দাম কত?",  # Should not detect
    ]
    
    print("Testing query detection:\n")
    
    for message in test_messages:
        detected = api.detect_product_query(message)
        
        if detected:
            print(f"✓ Detected: '{message}'")
            print(f"  → Search term: '{detected}'")
        else:
            print(f"✗ Not detected: '{message}'")
        print()
    
    print("=" * 70 + "\n")


def test_chatbot_integration():
    """Test product search integrated with chatbot"""
    
    print("\n" + "=" * 70)
    print("🤖 Chatbot Integration Test")
    print("=" * 70 + "\n")
    
    try:
        from chatbot import AdminChatbot
        
        print("Initializing chatbot...\n")
        bot = AdminChatbot(enable_rag=True)
        
        test_messages = [
            "আপনাদের কাছে hp laptop আছে?",
            "Show me iPhone 13",
            "আমি samsung phone খুজছি",
        ]
        
        user_id = "test_user"
        
        for message in test_messages:
            print(f"{'─' * 70}")
            print(f"👤 User: {message}")
            print(f"{'─' * 70}")
            
            response = bot.get_response(user_id, message)
            
            print(f"🤖 Bot: {response}")
            print()
        
        print("=" * 70)
        print("✓ Integration Test Complete!")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nMake sure you've run: python setup_and_train.py\n")


def main():
    """Run all tests"""
    
    print("\n" + "=" * 70)
    print("🧪 Product Search - Complete Test Suite")
    print("=" * 70)
    
    # Test 1: Direct API
    test_product_search()
    
    # Test 2: Query detection
    test_query_detection()
    
    # Test 3: Chatbot integration
    test_chatbot_integration()
    
    print("\n✅ All tests completed!\n")


if __name__ == "__main__":
    main()
