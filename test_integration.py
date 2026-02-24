#!/usr/bin/env python3
"""
Test enhanced product search integration with full chatbot system
"""
from bdstall_chatbot_system import BDStallChatbotSystem

def test_integration():
    print("🤖 Testing Enhanced Product Search Integration")
    print("=" * 55)
    
    try:
        # Initialize chatbot system
        chatbot = BDStallChatbotSystem()
        print("✅ Chatbot system initialized")
        
        # Test product search queries (mix of Bengali/English)
        product_queries = [
            "web cam lagbe",
            "laptop cheap price range",
            "mobile phone ache?",
            "wireless mouse kinte chai"
        ]
        
        for i, query in enumerate(product_queries, 1):
            print(f"\\n🧪 Test {i}: '{query}'")
            print("-" * 40)
            
            result = chatbot.process_message(
                user_id="test_enhanced_search",
                message=query,
                channel="web"
            )
            
            print(f"✅ Success: {result.get('success')}")
            print(f"📝 Response: {result.get('response', 'No response')[:120]}...")
            
            if 'processing_info' in result:
                info = result['processing_info']
                print(f"📊 Source: {info.get('source', 'unknown')}")
                print(f"⏱️ Time: {info.get('processing_time_seconds', 'unknown')} sec")
                
                # Check if enhanced search was used
                if 'enhanced_search' in str(info):
                    print("🚀 Enhanced AI Search Used!")
                elif 'search_method' in str(info):
                    print(f"🔍 Search Method: {info.get('search_method', 'unknown')}")
        
        print("\\n🎉 Integration testing completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_integration()