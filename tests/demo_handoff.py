#!/usr/bin/env python3
"""
Simple Human Handoff Demo
Shows how the handoff system works without full chatbot dependencies
"""
from human_handoff_manager import HumanHandoffManager, HandoffReason


def print_separator():
    print("\n" + "=" * 70)


def demo_handoff_system():
    """Demonstrate the human handoff system"""
    print("=" * 70)
    print("  🤖 HUMAN HANDOFF SYSTEM - DEMO")
    print("=" * 70)
    print("\nThis system switches from AI to Human agent when:")
    print("  • AI confidence is low")
    print("  • No matching answer found")
    print("  • User explicitly requests human agent")
    print("  • Multiple failed attempts (default: 3)")
    
    # Initialize manager
    print_separator()
    print("🚀 Initializing Human Handoff Manager...")
    manager = HumanHandoffManager(
        confidence_threshold=0.6,  # Below 60% confidence triggers handoff
        max_failed_attempts=3,      # After 3 failures, trigger handoff
        session_timeout_minutes=30
    )
    print("✅ Manager initialized!")
    
    # Scenario 1: Normal interactions (AI handles)
    print_separator()
    print("📋 SCENARIO 1: Normal User Interactions")
    print("-" * 70)
    
    test_user = "customer_001"
    
    queries = [
        ("অর্ডার করবো কিভাবে?", 0.95, True),
        ("ডেলিভারি চার্জ কত?", 0.88, True),
        ("পণ্যের দাম কত?", 0.92, True),
    ]
    
    for i, (query, confidence, found) in enumerate(queries, 1):
        should_handoff, reason = manager.should_trigger_handoff(
            user_id=test_user,
            confidence=confidence,
            match_found=found,
            message=query
        )
        
        print(f"{i}. Query: '{query}'")
        print(f"   Confidence: {confidence:.0%} | Match Found: {found}")
        print(f"   → AI handles: {'YES ✅' if not should_handoff else 'NO ❌'}")
    
    # Scenario 2: Unclear queries leading to handoff
    print_separator()
    print("📋 SCENARIO 2: Unclear Queries (Progressive Failures)")
    print("-" * 70)
    
    test_user_2 = "customer_002"
    unclear_queries = [
        ("blah blah xyz", 0.2, False, "Attempt 1"),
        ("random gibberish text", 0.15, False, "Attempt 2"),
        ("asdfghjkl qwerty", 0.1, False, "Attempt 3 - Should trigger handoff!"),
    ]
    
    for i, (query, confidence, found, note) in enumerate(unclear_queries, 1):
        print(f"\n{i}. Query: '{query}' ({note})")
        print(f"   Confidence: {confidence:.0%} | Match Found: {found}")
        
        should_handoff, reason = manager.should_trigger_handoff(
            user_id=test_user_2,
            confidence=confidence,
            match_found=found,
            message=query
        )
        
        if should_handoff:
            print(f"   → 🔔 HANDOFF TRIGGERED!")
            print(f"   → Reason: {reason.value}")
            
            # Trigger the actual handoff
            result = manager.trigger_handoff(test_user_2, query, reason)
            print(f"\n   📝 Handoff Message:")
            print(f"   {result['response'][:200]}...")
        else:
            print(f"   → AI tries again (Failed attempts: {manager.get_session_info(test_user_2)['failed_attempts']})")
    
    # Check if in human mode now
    print(f"\n   📊 User {test_user_2} Status:")
    print(f"   → In Human Mode: {manager.is_in_human_mode(test_user_2)}")
    
    # Scenario 3: User explicitly requests human
    print_separator()
    print("📋 SCENARIO 3: User Explicitly Requests Human Agent")
    print("-" * 70)
    
    test_user_3 = "customer_003"
    explicit_request = "I want to talk to a human agent"
    
    print(f"Query: '{explicit_request}'")
    print(f"Confidence: 90% | Match Found: True (but user wants human)")
    
    should_handoff, reason = manager.should_trigger_handoff(
        user_id=test_user_3,
        confidence=0.9,
        match_found=True,
        message=explicit_request
    )
    
    if should_handoff:
        print(f"→ 🔔 HANDOFF TRIGGERED!")
        print(f"→ Reason: {reason.value}")
        result = manager.trigger_handoff(test_user_3, explicit_request, reason)
        print(f"\n📝 Handoff Message:")
        print(f"{result['response'][:200]}...")
    
    # Scenario 4: Show pending conversations
    print_separator()
    print("📋 SCENARIO 4: Pending Conversations (For Human Agents)")
    print("-" * 70)
    
    pending = manager.get_pending_conversations()
    print(f"Total conversations pending human response: {len(pending)}")
    
    for conv in pending:
        print(f"\n   User: {conv['user_id']}")
        print(f"   Mode: {conv['mode']}")
        print(f"   Reason: {conv['handoff_reason']}")
        print(f"   Pending messages: {len(conv['pending_messages'])}")
        print(f"   Last activity: {conv['last_activity']}")
    
    # Scenario 5: Return to AI mode
    print_separator()
    print("📋 SCENARIO 5: Admin Returns User to AI Mode")
    print("-" * 70)
    
    print(f"Before: User {test_user_2} in human mode: {manager.is_in_human_mode(test_user_2)}")
    
    print(f"\n🔄 Admin action: Return user {test_user_2} to AI mode...")
    manager.return_to_ai(test_user_2)
    
    print(f"After: User {test_user_2} in human mode: {manager.is_in_human_mode(test_user_2)}")
    print(f"→ User can now interact with AI again! ✅")
    
    # Summary
    print_separator()
    print("✅ DEMO COMPLETED!")
    print("-" * 70)
    print("\n🎯 Key Features Demonstrated:")
    print("   ✓ AI handles high-confidence queries automatically")
    print("   ✓ System detects repeated failures (3 attempts)")
    print("   ✓ Automatic handoff when confidence is too low")
    print("   ✓ User can explicitly request human agent")
    print("   ✓ Once in human mode, AI stops responding")
    print("   ✓ Human agents can see pending conversations")
    print("   ✓ Admin can return conversations to AI mode")
    
    print("\n📞 Contact Info in Handoff Messages:")
    print("   • Phone: 01612378255")
    print("   • Hours: 10 AM - 6 PM")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    demo_handoff_system()
