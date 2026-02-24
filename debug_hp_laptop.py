#!/usr/bin/env python3
"""
Debug why 'hp laptop ase' shows server busy message instead of product search
"""
from bdstall_chatbot_system import BDStallChatbotSystem
from enhanced_product_search import EnhancedProductSearch

def debug_hp_laptop_query():
    print("🔍 Debugging 'hp laptop ase' Query Issue")
    print("=" * 50)
    
    query = "hp laptop ase"
    
    # Test 1: Direct enhanced search
    print("🧪 Test 1: Direct Enhanced Product Search")
    print("-" * 40)
    try:
        searcher = EnhancedProductSearch()
        result = searcher.enhanced_product_search(query)
        print(f"✅ Direct search works: {result['success']}")
        print(f"📦 Products found: {result['products_found']}")
        print(f"📝 Response: {result['response'][:100]}...")
    except Exception as e:
        print(f"❌ Direct search failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🧪 Test 2: Bengali Database Check")
    print("-" * 40)
    try:
        from bengali_database_handler import BengaliDatabaseHandler
        db_handler = BengaliDatabaseHandler()
        db_result = db_handler.search_database(query)
        print(f"📋 Database match: {db_result['success']}")
        if db_result['success']:
            print(f"📝 Database response: {db_result['response'][:100]}...")
            print(f"📊 Similarity: {db_result.get('similarity', 'N/A')}")
        else:
            print(f"📝 Database fallback: {db_result['response']}")
    except Exception as e:
        print(f"❌ Database check failed: {e}")
    
    print("\n🧪 Test 3: Full Chatbot System")
    print("-" * 40)
    try:
        chatbot = BDStallChatbotSystem()
        result = chatbot.process_message(
            user_id="debug_user",
            message=query,
            channel="web"
        )
        
        print(f"✅ Chatbot success: {result['success']}")
        print(f"📝 Response: {result['response']}")
        
        if 'processing_info' in result:
            info = result['processing_info']
            print(f"📊 Source: {info.get('source', 'unknown')}")
            print(f"📂 Category: {info.get('category', 'unknown')}")
            print(f"⏱️ Time: {info.get('processing_time_seconds', 'unknown')} sec")
    except Exception as e:
        print(f"❌ Chatbot failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_hp_laptop_query()