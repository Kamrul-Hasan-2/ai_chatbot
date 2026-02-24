"""
Test Script for BDStall Chatbot System
This script tests the new integrated architectural components
"""
import sys
import os
import logging
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_individual_components():
    """Test each architectural component individually"""
    print("🧪 Testing Individual Components")
    print("=" * 50)
    
    try:
        # Test Channel Adapter
        from channel_adapter import ChannelAdapter, ChannelMessage
        adapter = ChannelAdapter()
        
        test_message = ChannelMessage(
            content="Hello test",
            user_id="test_user",
            channel="web",
            timestamp=datetime.now(),
            metadata={}
        )
        
        normalized = adapter.normalize_message(test_message)
        print("✓ Channel Adapter - WORKING")
        
    except Exception as e:
        print(f"❌ Channel Adapter - ERROR: {e}")
    
    try:
        # Test Intent & Entity Detection
        from intent_entity_detector import IntentEntityDetector
        detector = IntentEntityDetector()
        
        result = detector.detect_intent_and_entities("I want to buy a phone")
        print("✓ Intent & Entity Detector - WORKING")
        print(f"  Detected intent: {result.intent}")
        
    except Exception as e:
        print(f"❌ Intent & Entity Detector - ERROR: {e}")
    
    try:
        # Test Context Router
        from context_router import ContextRouter
        router = ContextRouter()
        
        router.add_context("test_user", "greeting", {"name": "test"})
        context = router.get_context("test_user")
        print("✓ Context Router - WORKING")
        print(f"  Context items: {len(context.context_items)}")
        
    except Exception as e:
        print(f"❌ Context Router - ERROR: {e}")
    
    try:
        # Test Business Rule Engine
        from business_rule_engine import BusinessRuleEngine, BusinessRule, RuleCondition, RuleAction
        engine = BusinessRuleEngine()
        
        # Add a test rule
        condition = RuleCondition(
            field="product_category",
            operator="equals",
            value="electronics"
        )
        action = RuleAction(
            action_type="set_response",
            parameters={"message": "Electronics products available!"}
        )
        rule = BusinessRule(
            rule_id="test_rule",
            name="Test Rule",
            conditions=[condition],
            actions=[action],
            priority=1
        )
        
        engine.add_rule(rule)
        result = engine.evaluate_rules({"product_category": "electronics"})
        print("✓ Business Rule Engine - WORKING")
        print(f"  Rules executed: {len(result.executed_actions)}")
        
    except Exception as e:
        print(f"❌ Business Rule Engine - ERROR: {e}")
    
    try:
        # Test Decision Router
        from decision_router import DecisionRouter
        router = DecisionRouter()
        
        # Mock components for testing
        context = {"user_id": "test", "intent": "product_query"}
        decision = router.route_request(context)
        print("✓ Decision Router - WORKING")
        print(f"  Selected strategy: {decision.selected_strategy}")
        
    except Exception as e:
        print(f"❌ Decision Router - ERROR: {e}")
    
    try:
        # Test Response Composer
        from response_composer import ResponseComposer
        composer = ResponseComposer()
        
        # Mock context for testing
        context = {
            "user_id": "test",
            "intent": "greeting",
            "entities": [],
            "conversation_history": []
        }
        
        response = composer.compose_response(context, "rag")
        print("✓ Response Composer - WORKING")
        print(f"  Response generated: {len(response.content) > 0}")
        
    except Exception as e:
        print(f"❌ Response Composer - ERROR: {e}")


def test_integrated_system():
    """Test the complete integrated system"""
    print("\n🚀 Testing Integrated System")
    print("=" * 50)
    
    try:
        from bdstall_chatbot_system import BDStallChatbotSystem
        
        # Initialize system
        system = BDStallChatbotSystem(
            enable_rag=True,
            enable_multimedia=False,  # Disable for testing
            enable_analytics=True
        )
        
        print("✓ System initialization - SUCCESS")
        
        # Test message processing
        test_messages = [
            "Hello, how are you?",
            "What products do you sell?",  
            "I want to buy a smartphone",
            "What is your return policy?",
            "Thank you"
        ]
        
        for i, message in enumerate(test_messages, 1):
            try:
                result = system.process_message(
                    user_id=f"test_user_{i}",
                    message=message,
                    channel="test"
                )
                
                if result["success"]:
                    print(f"✓ Message {i}: '{message}' - PROCESSED")
                    print(f"  Response: {result['response'][:50]}...")
                else:
                    print(f"❌ Message {i}: '{message}' - FAILED")
                    print(f"  Error: {result.get('error', 'Unknown')}")
                
            except Exception as e:
                print(f"❌ Message {i}: '{message}' - ERROR: {e}")
        
        # Test system health
        health = system.get_system_health()
        print(f"\n📊 System Health: {health['status']}")
        
        print("\nComponent Status:")
        for component, status in health['components'].items():
            print(f"  {'✓' if status == 'healthy' else '❌'} {component}: {status}")
        
    except Exception as e:
        print(f"❌ Integrated System - ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_compatibility_layer():
    """Test the ChatbotIntegration compatibility layer"""
    print("\n🔄 Testing Compatibility Layer")
    print("=" * 50)
    
    try:
        from bdstall_chatbot_system import ChatbotIntegration
        
        integration = ChatbotIntegration()
        
        # Test legacy-style processing
        response = integration.process_message("Hello from compatibility layer")
        print("✓ Compatibility layer - WORKING")
        print(f"  Response: {response[:50]}...")
        
    except Exception as e:
        print(f"❌ Compatibility Layer - ERROR: {e}")


def run_performance_test():
    """Run a simple performance test"""
    print("\n⚡ Performance Test")
    print("=" * 50)
    
    try:
        import time
        from bdstall_chatbot_system import BDStallChatbotSystem
        
        system = BDStallChatbotSystem()
        
        # Test processing speed
        start_time = time.time()
        
        for i in range(5):
            system.process_message(
                user_id=f"perf_test_{i}",
                message="Quick performance test message",
                channel="test"
            )
        
        end_time = time.time()
        avg_time = (end_time - start_time) / 5
        
        print(f"✓ Average processing time: {avg_time:.3f} seconds per message")
        
        if avg_time < 1.0:
            print("✓ Performance: GOOD (< 1 second)")
        elif avg_time < 3.0:
            print("⚠️ Performance: MODERATE (1-3 seconds)")
        else:
            print("❌ Performance: SLOW (> 3 seconds)")
        
    except Exception as e:
        print(f"❌ Performance Test - ERROR: {e}")


def main():
    """Run all tests"""
    print("🤖 BDStall Chatbot System - Complete Test Suite")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Run all tests
    test_individual_components()
    test_integrated_system()
    test_compatibility_layer()
    run_performance_test()
    
    print("\n" + "=" * 60)
    print("🎉 Test Suite Completed!")
    print("=" * 60)
    print("If all tests passed, your BDStall Chatbot System is ready!")
    print("You can now:")
    print("1. Start the server: python app.py")
    print("2. Run migration: python migrate_to_integrated.py")
    print("3. Test the API endpoints with the migrated system")


if __name__ == "__main__":
    main()