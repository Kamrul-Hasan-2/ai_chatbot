#!/usr/bin/env python3
"""
Test the full chatbot system with the improved Bengali handling
"""
from bdstall_chatbot_system import BDStallChatbotSystem

def test_full_system():
    """Test the complete chatbot system with user's queries"""
    
    print("🤖 Testing Full BDStall Chatbot System")
    print("=" * 50)
    
    try:
        # Initialize the system
        chatbot = BDStallChatbotSystem()
        print("✅ Chatbot system initialized successfully")
        print()
        
        # Test user's specific queries
        test_queries = [
            "kibabe order korbo",
            "order ?", 
            "অর্ডার করবো কিভাবে ?",
            "koy din er modde delivery hoy",
            "delivery time koto",
            "assah"  # This should get a fallback response
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"🧪 Test {i}: '{query}'")
            print("-" * 40)
            
            result = chatbot.process_message(
                user_id="test_user_123",
                message=query,
                channel="web"
            )
            
            print(f"✅ Success: {result['success']}")
            print(f"📝 Response: {result['response'][:100]}...")
            
            if 'processing_info' in result:
                info = result['processing_info']
                print(f"📊 Source: {info.get('source', 'unknown')}")
                print(f"📂 Category: {info.get('category', 'unknown')}")
                if 'similarity_score' in info:
                    print(f"🎯 Similarity: {info['similarity_score']:.2f}")
                print(f"⏱️ Time: {info.get('processing_time_seconds', 'unknown')} seconds")
            
            print()
        
        print("🎉 All tests completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_system()