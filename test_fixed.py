#!/usr/bin/env python3
"""
Test the fixed system with 'hp laptop ase' query
"""
from bdstall_chatbot_system import BDStallChatbotSystem

def test_fixed_system():
    print("🧪 Testing Fixed System with 'hp laptop ase'")
    print("=" * 50)
    
    try:
        # Initialize chatbot system
        print("🚀 Initializing chatbot system...")
        chatbot = BDStallChatbotSystem()
        print("✅ Chatbot system initialized")
        
        # Test the problematic query
        query = "hp laptop ase"
        print(f"\n🔍 Testing query: '{query}'")
        
        result = chatbot.process_message(
            user_id="test_fixed_user",
            message=query,
            channel="web"
        )
        
        print(f"\n📋 Results:")
        print(f"✅ Success: {result['success']}")
        print(f"📝 Response: {result['response']}")
        
        if 'processing_info' in result:
            info = result['processing_info']
            print(f"\n📊 Processing Info:")
            print(f"   Source: {info.get('source', 'unknown')}")
            print(f"   Category: {info.get('category', 'unknown')}")
            print(f"   Time: {info.get('processing_time_seconds', 'unknown')} seconds")
            
            # Check what search method was used
            if 'enhanced_search' in str(info):
                print("   🚀 Enhanced Product Search Used!")
            elif 'search_method' in str(info):
                print(f"   🔍 Search Method: {info.get('search_method')}")
        
        # Check if it contains the server busy message
        if "আমাদের সার্ভার মোমেন্টে ব্যস্ত" in result['response']:
            print("\n❌ Still getting server busy message!")
        else:
            print("\n✅ No more server busy message!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fixed_system()