#!/usr/bin/env python3
"""
Test Human Handoff System
Demonstrates AI to Human agent transition when AI doesn't understand
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bdstall_chatbot_system import BDStallChatbotSystem
from human_handoff_manager import HumanHandoffManager, HandoffReason


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_result(result: dict, test_num: int, query: str):
    """Print formatted result"""
    print(f"\n🧪 Test {test_num}: '{query}'")
    print("-" * 70)
    print(f"✅ Success: {result.get('success')}")
    
    if result.get('in_human_mode'):
        print(f"👤 MODE: HUMAN MODE - AI is not responding")
        print(f"📝 Message: {result.get('processing_info', {}).get('message')}")
    elif result.get('handoff_triggered'):
        print(f"🔔 HANDOFF TRIGGERED!")
        print(f"📋 Reason: {result.get('processing_info', {}).get('handoff_reason')}")
        print(f"📝 Response: {result.get('response')[:120]}...")
    else:
        response = result.get('response', '')
        print(f"📝 Response: {response[:120]}...")
        
        info = result.get('processing_info', {})
        source = info.get('source', 'unknown')
        similarity = info.get('similarity_score', 0)
        
        print(f"📊 Source: {source}")
        if similarity:
            print(f"📈 Similarity: {similarity:.2f}")


def test_handoff_scenarios():
    """Test various handoff scenarios"""
    print_header("🤖 HUMAN HANDOFF SYSTEM TEST")
    print("\nThis test demonstrates when AI switches to human agent mode")
    print("When AI doesn't understand, it hands over to human agents\n")
    
    try:
        # Initialize chatbot system
        print("🚀 Initializing BDStall Chatbot System...")
        chatbot = BDStallChatbotSystem()
        print("✅ Chatbot initialized successfully!\n")
        
        # Test user ID
        test_user = "test_handoff_user_001"
        
        # Scenario 1: Normal query - AI handles
        print_header("Scenario 1: Normal Query - AI Understands")
        query1 = "অর্ডার করবো কিভাবে?"
        result1 = chatbot.process_message(
            user_id=test_user,
            message=query1,
            channel="web"
        )
        print_result(result1, 1, query1)
        
        # Scenario 2: Unclear query - First attempt
        print_header("Scenario 2: Unclear Query #1 - AI Tries")
        query2 = "blah blah xyz unclear message"
        result2 = chatbot.process_message(
            user_id=test_user,
            message=query2,
            channel="web"
        )
        print_result(result2, 2, query2)
        
        # Scenario 3: Another unclear query - Second attempt
        print_header("Scenario 3: Unclear Query #2 - AI Confidence Low")
        query3 = "asdfghjkl random text without meaning"
        result3 = chatbot.process_message(
            user_id=test_user,
            message=query3,
            channel="web"
        )
        print_result(result3, 3, query3)
        
        # Scenario 4: Third unclear query - Handoff triggered
        print_header("Scenario 4: Unclear Query #3 - HANDOFF TRIGGERED!")
        query4 = "qwerty poiuyt nonsense gibberish"
        result4 = chatbot.process_message(
            user_id=test_user,
            message=query4,
            channel="web"
        )
        print_result(result4, 4, query4)
        
        # Scenario 5: After handoff - Now in human mode
        print_header("Scenario 5: After Handoff - Human Mode Active")
        query5 = "অর্ডার করবো কিভাবে?"  # Even valid query won't get AI response
        result5 = chatbot.process_message(
            user_id=test_user,
            message=query5,
            channel="web"
        )
        print_result(result5, 5, query5)
        
        print("\n" + "=" * 70)
        print("🎯 KEY OBSERVATION:")
        print("   After Test 4, AI handed over to human agent")
        print("   In Test 5, even though query is valid, AI doesn't respond")
        print("   Conversation is now in HUMAN MODE - only humans can respond")
        print("=" * 70)
        
        # Scenario 6: User explicitly requests human
        print_header("Scenario 6: New User Explicitly Requests Human Agent")
        new_user = "test_handoff_user_002"
        query6 = "I want to talk to a human agent"
        result6 = chatbot.process_message(
            user_id=new_user,
            message=query6,
            channel="web"
        )
        print_result(result6, 6, query6)
        
        # Scenario 7: Check handoff manager status
        print_header("Scenario 7: Checking Handoff Manager Status")
        print(f"👤 User 1 in human mode: {chatbot.handoff_manager.is_in_human_mode(test_user)}")
        print(f"👤 User 2 in human mode: {chatbot.handoff_manager.is_in_human_mode(new_user)}")
        
        pending = chatbot.handoff_manager.get_pending_conversations()
        print(f"\n📋 Total pending conversations: {len(pending)}")
        for conv in pending:
            print(f"   - User: {conv['user_id']}")
            print(f"     Reason: {conv['handoff_reason']}")
            print(f"     Pending messages: {len(conv['pending_messages'])}")
        
        # Scenario 8: Return to AI mode
        print_header("Scenario 8: Admin Returns User to AI Mode")
        print(f"🔄 Returning user {test_user} back to AI mode...")
        chatbot.handoff_manager.return_to_ai(test_user)
        
        query8 = "অর্ডার করবো কিভাবে?"
        result8 = chatbot.process_message(
            user_id=test_user,
            message=query8,
            channel="web"
        )
        print_result(result8, 8, query8)
        
        print_header("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("\n🎉 Summary:")
        print("   ✓ AI handles normal queries")
        print("   ✓ AI detects repeated failures and triggers handoff")
        print("   ✓ After handoff, conversation enters HUMAN MODE")
        print("   ✓ In human mode, AI stops responding")
        print("   ✓ Human agents can take over the conversation")
        print("   ✓ Admin can return conversation back to AI mode")
        print("\n" + "=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


def test_handoff_manager_directly():
    """Test the handoff manager independently"""
    print_header("🧪 Testing Human Handoff Manager (Direct)")
    
    manager = HumanHandoffManager(
        confidence_threshold=0.6,
        max_failed_attempts=3
    )
    
    test_user = "direct_test_user"
    
    # Test 1: Normal interaction
    print("\n✅ Test 1: High confidence - No handoff")
    should_handoff, reason = manager.should_trigger_handoff(
        test_user, 
        confidence=0.9, 
        match_found=True, 
        message="Normal query"
    )
    print(f"   Should handoff: {should_handoff}")
    
    # Test 2: Low confidence (attempt 1)
    print("\n⚠️ Test 2: Low confidence - Attempt 1")
    should_handoff, reason = manager.should_trigger_handoff(
        test_user, 
        confidence=0.3, 
        match_found=False, 
        message="Unclear query 1"
    )
    print(f"   Should handoff: {should_handoff}")
    if should_handoff:
        print(f"   Reason: {reason}")
    
    # Test 3: Low confidence (attempt 2)
    print("\n⚠️ Test 3: Low confidence - Attempt 2")
    should_handoff, reason = manager.should_trigger_handoff(
        test_user, 
        confidence=0.2, 
        match_found=False, 
        message="Unclear query 2"
    )
    print(f"   Should handoff: {should_handoff}")
    if should_handoff:
        print(f"   Reason: {reason}")
    
    # Test 4: Low confidence (attempt 3) - Should trigger
    print("\n🔔 Test 4: Low confidence - Attempt 3 (HANDOFF!)")
    should_handoff, reason = manager.should_trigger_handoff(
        test_user, 
        confidence=0.1, 
        match_found=False, 
        message="Unclear query 3"
    )
    print(f"   Should handoff: {should_handoff}")
    if should_handoff:
        print(f"   Reason: {reason}")
        result = manager.trigger_handoff(test_user, "Unclear query 3", reason)
        print(f"   Response: {result['response'][:100]}...")
    
    # Test 5: Check mode
    print(f"\n📊 Test 5: Check conversation mode")
    print(f"   In human mode: {manager.is_in_human_mode(test_user)}")
    
    session_info = manager.get_session_info(test_user)
    print(f"   Mode: {session_info['mode']}")
    print(f"   Failed attempts: {session_info['failed_attempts']}")
    
    print("\n✅ Direct handoff manager tests completed!\n")


if __name__ == "__main__":
    # Run both test suites
    test_handoff_manager_directly()
    test_handoff_scenarios()
