"""
Test Follow-up Conversation Flow
Tests the new conversation tracking feature where AI asks about product and user responds
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.handlers.bengali_database_handler import BengaliDatabaseHandler

def test_follow_up_conversation():
    """Test conversation flow with follow-up response"""
    
    # Initialize database handler
    db_path = os.path.join("data", "database.csv")
    handler = BengaliDatabaseHandler(csv_file=db_path)
    
    user_id = "test_user_123"
    
    print("=" * 80)
    print("🗣️  TESTING FOLLOW-UP CONVERSATION FLOW")
    print("=" * 80)
    print()
    
    # Conversation Scenario 1: Order inquiry
    print("📌 SCENARIO 1: Order Inquiry Flow")
    print("-" * 80)
    
    # User asks how to order
    print("\n👤 User: অর্ডার করবো কি ভাবে?")
    result1 = handler.search_with_context(user_id, "অর্ডার করবো কি ভাবে?")
    print(f"🤖 Bot: {result1['response']}")
    print(f"📊 Category: {result1['category']}")
    
    # User mentions a product (this should trigger follow-up response)
    print("\n👤 User: Nokia 1110")
    result2 = handler.search_with_context(user_id, "Nokia 1110")
    print(f"🤖 Bot: {result2['response']}")
    print(f"📊 Category: {result2['category']}")
    
    if result2.get('is_follow_up'):
        print("✅ Follow-up detected successfully!")
    else:
        print("❌ Follow-up NOT detected")
    
    print("\n" + "=" * 80)
    
    # Conversation Scenario 2: Different product
    print("\n📌 SCENARIO 2: Another Product Inquiry")
    print("-" * 80)
    
    user_id2 = "test_user_456"
    
    # User asks how to order
    print("\n👤 User: order kivabe dibo")
    result3 = handler.search_with_context(user_id2, "order kivabe dibo")
    print(f"🤖 Bot: {result3['response']}")
    
    # User mentions samsung phone
    print("\n👤 User: Samsung Galaxy A54")
    result4 = handler.search_with_context(user_id2, "Samsung Galaxy A54")
    print(f"🤖 Bot: {result4['response']}")
    
    if result4.get('is_follow_up'):
        print("✅ Follow-up detected successfully!")
    else:
        print("❌ Follow-up NOT detected")
    
    print("\n" + "=" * 80)
    
    # Conversation Scenario 3: No follow-up (regular question)
    print("\n📌 SCENARIO 3: Regular Question (No Follow-up)")
    print("-" * 80)
    
    user_id3 = "test_user_789"
    
    print("\n👤 User: ডেলিভারি চার্জ কত?")
    result5 = handler.search_with_context(user_id3, "ডেলিভারি চার্জ কত?")
    print(f"🤖 Bot: {result5['response']}")
    print(f"📊 Category: {result5['category']}")
    
    if result5.get('is_follow_up'):
        print("❌ Should NOT be follow-up")
    else:
        print("✅ Regular response (correct)")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    
    # Summary
    print("\n📋 SUMMARY:")
    print(f"- Scenario 1: Follow-up {'✅ PASSED' if result2.get('is_follow_up') else '❌ FAILED'}")
    print(f"- Scenario 2: Follow-up {'✅ PASSED' if result4.get('is_follow_up') else '❌ FAILED'}")
    print(f"- Scenario 3: Regular {'✅ PASSED' if not result5.get('is_follow_up') else '❌ FAILED'}")

if __name__ == "__main__":
    test_follow_up_conversation()
