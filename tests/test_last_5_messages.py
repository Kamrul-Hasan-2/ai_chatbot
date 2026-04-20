"""
Test script for Last 5 Messages Context Feature

Demonstrates how to:
1. Retrieve the last 5 messages for a user
2. Get conversation context for AI prompts
3. Get conversation summary
4. Use context in a chatbot response
"""
import requests
import json
import sys

# API endpoints
API_BASE_URL = "http://localhost:5000"

# Test user ID
TEST_USER_ID = "user_123456"


def test_get_last_5_messages():
    """Test retrieving the last 5 messages"""
    print("\n" + "="*60)
    print("TEST 1: Get Last 5 Messages")
    print("="*60)
    
    url = f"{API_BASE_URL}/api/conversation/last-5/{TEST_USER_ID}"
    params = {"limit": 5}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Success: {data.get('success')}")
        print(f"Messages Retrieved: {data.get('count')}")
        
        if data.get('success'):
            print("\n📋 Conversation Context:")
            print(data.get('context_text', 'No context'))
            
            print("\n📝 Raw Messages:")
            for i, msg in enumerate(data.get('messages', []), 1):
                sender = {1: "Agent", 2: "Bot", 3: "User"}.get(msg.get('sender_type'), "Unknown")
                print(f"  {i}. [{sender}] {msg.get('text', msg.get('message', ''))}")
        else:
            print(f"❌ Error: {data.get('error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_build_context():
    """Test building conversation context for AI prompt"""
    print("\n" + "="*60)
    print("TEST 2: Build Conversation Context for AI Prompt")
    print("="*60)
    
    url = f"{API_BASE_URL}/api/conversation/context/{TEST_USER_ID}"
    payload = {
        "message": "what was the price again?",
        "limit": 5
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Success: {data.get('success')}")
        
        if data.get('success'):
            print("\n🧠 AI Prompt with Context:")
            print("-" * 60)
            print(data.get('prompt', ''))
            print("-" * 60)
        else:
            print(f"❌ Error: {data.get('error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_conversation_summary():
    """Test getting conversation summary"""
    print("\n" + "="*60)
    print("TEST 3: Get Conversation Summary")
    print("="*60)
    
    url = f"{API_BASE_URL}/api/conversation/summary/{TEST_USER_ID}"
    params = {"limit": 5}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Success: {data.get('success')}")
        
        if data.get('success'):
            print(f"\n📊 Conversation Summary:")
            print(f"  Total Messages: {data.get('total_messages', 0)}")
            print(f"  User Messages: {data.get('user_messages', 0)}")
            print(f"  Bot Messages: {data.get('bot_messages', 0)}")
            print(f"  Agent Messages: {data.get('agent_messages', 0)}")
            print(f"  Summary: {data.get('summary', '')}")
        else:
            print(f"❌ Error: {data.get('error')}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_send_message_with_context():
    """Test sending a message and getting context-aware response"""
    print("\n" + "="*60)
    print("TEST 4: Send Message with Context-Aware Response")
    print("="*60)
    
    # First get the context
    context_url = f"{API_BASE_URL}/api/conversation/last-5/{TEST_USER_ID}?limit=5"
    chat_url = f"{API_BASE_URL}/chat"
    
    try:
        # Get context
        context_response = requests.get(context_url)
        context_data = context_response.json()
        
        print("📋 Current Conversation Context:")
        print(context_data.get('context_text', 'No context'))
        
        # Send new message
        new_message = "show me available options"
        print(f"\n💬 Sending Message: {new_message}")
        
        payload = {
            "user_id": TEST_USER_ID,
            "message": new_message
        }
        
        chat_response = requests.post(chat_url, json=payload)
        chat_data = chat_response.json()
        
        print(f"\n🤖 Bot Response:")
        print(f"  Success: {chat_data.get('success')}")
        print(f"  Intent: {chat_data.get('intent')}")
        print(f"  Mode: {chat_data.get('mode')}")
        print(f"  Response: {chat_data.get('response', '')[:200]}...")
        
        if chat_data.get('products'):
            print(f"  Products Found: {len(chat_data.get('products', []))}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")


def test_python_integration():
    """Test using the conversation context manager directly in Python"""
    print("\n" + "="*60)
    print("TEST 5: Python Integration (Direct Module Usage)")
    print("="*60)
    
    try:
        from src.utils.conversation_context import get_context_manager
        
        context_manager = get_context_manager()
        
        # Get last 5 messages
        result = context_manager.get_last_n_messages(TEST_USER_ID, limit=5)
        
        print(f"✅ Direct Python Integration Working!")
        print(f"  Success: {result['success']}")
        print(f"  Messages Retrieved: {result['count']}")
        
        if result['success']:
            print(f"\n📝 Formatted Context:")
            for line in result.get('formatted_lines', []):
                print(f"  {line}")
        
        # Build prompt for AI
        print(f"\n🧠 Building AI Prompt:")
        prompt = context_manager.build_conversation_prompt(
            TEST_USER_ID,
            "do you have this in different colors?",
            limit=5
        )
        print(prompt[:200] + "...")
        
    except ImportError as e:
        print(f"⚠️ Module import issue: {e}")
        print("Run this test from the project root directory")
    except Exception as e:
        print(f"❌ Exception: {e}")


def print_usage():
    """Print usage instructions"""
    print("\n" + "="*80)
    print("LAST 5 MESSAGES CONTEXT FEATURE - API ENDPOINTS")
    print("="*80)
    
    print("\n1️⃣  GET /api/conversation/last-5/<user_id>")
    print("   Get the last N messages for a user")
    print("   Query: ?limit=5 (default: 5, max: 20)")
    print("   Returns: Array of messages with context text")
    
    print("\n2️⃣  POST /api/conversation/context/<user_id>")
    print("   Build AI prompt with conversation context")
    print("   Body: {\"message\": \"...\", \"limit\": 5}")
    print("   Returns: Formatted prompt ready for AI models")
    
    print("\n3️⃣  GET /api/conversation/summary/<user_id>")
    print("   Get conversation summary and statistics")
    print("   Query: ?limit=5 (default: 5)")
    print("   Returns: Message counts and summary")
    
    print("\n4️⃣  POST /chat")
    print("   Send message (uses context internally)")
    print("   Body: {\"user_id\": \"...\", \"message\": \"...\"}")
    print("   Returns: Context-aware response")


if __name__ == "__main__":
    print_usage()
    
    print("\n" + "="*80)
    print("Running Tests...")
    print("="*80)
    
    # Run all tests
    test_get_last_5_messages()
    test_build_context()
    test_conversation_summary()
    test_send_message_with_context()
    test_python_integration()
    
    print("\n" + "="*80)
    print("Tests Complete!")
    print("="*80)
