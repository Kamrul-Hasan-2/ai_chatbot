"""
Simple test script to verify the chatbot works
Run this before setting up Facebook Messenger
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatbot import AdminChatbot
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_chatbot():
    """Test the chatbot with sample messages"""
    print("=" * 80)
    print("AI CHATBOT TEST")
    print("=" * 80)
    print("\nInitializing chatbot...")
    print("(This will download the model on first run - may take a few minutes)\n")
    
    try:
        # Initialize chatbot
        bot = AdminChatbot()
        
        print("✓ Chatbot initialized successfully!\n")
        print("=" * 80)
        
        # Test messages
        test_messages = [
            "Hello! What can you help me with?",
            "What are your business hours?",
            "How can I contact you?",
            "Tell me about your products",
        ]
        
        user_id = "test_user_001"
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n[Test {i}/{len(test_messages)}]")
            print(f"User: {message}")
            print("-" * 80)
            
            # Get response
            response = bot.get_response(user_id, message)
            
            print(f"Bot: {response}")
            print("-" * 80)
        
        print("\n✓ All tests completed successfully!")
        print(f"\nConversation logs saved to: logs/conversations_{bot._log_conversation.__globals__['datetime'].now().strftime('%Y-%m-%d')}.log")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n✗ Test failed: {e}")
        print("\nMake sure you have:")
        print("1. Installed all requirements: pip install -r requirements.txt")
        print("2. Created data/admin_data.json with your business data")
        print("3. Enough RAM/GPU memory for the model")
        return False
    
    return True


if __name__ == "__main__":
    success = test_chatbot()
    sys.exit(0 if success else 1)
