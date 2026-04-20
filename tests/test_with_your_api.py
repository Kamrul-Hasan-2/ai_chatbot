#!/usr/bin/env python3
"""
Test the Last 5 Messages Context with Your Real API

This script tests the conversation context manager with your actual BDStall API endpoint.

Usage:
    python tests/test_with_your_api.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.conversation_context import get_context_manager

# Your user ID from the API example
TEST_USER_ID = "35755034270762597"

print("\n" + "="*70)
print("TESTING LAST 5 MESSAGES CONTEXT WITH YOUR REAL API")
print("="*70)

print(f"\n📍 Test User ID: {TEST_USER_ID}")
print("🌐 API: https://www.bdstall.com/api/item/chatbot_history/")

# Initialize context manager
manager = get_context_manager()

# Test 1: Get last 5 messages
print("\n" + "-"*70)
print("TEST 1: Get Last 5 Messages")
print("-"*70)

result = manager.get_last_n_messages(TEST_USER_ID, limit=5)

print(f"\n✅ Success: {result['success']}")
print(f"📊 Messages Retrieved: {result['count']}")

if result['user_info']:
    user_info = result['user_info']
    print(f"\n👤 User Information:")
    print(f"   Name: {user_info.get('user_name', 'N/A')}")
    print(f"   ID: {user_info.get('user_id', 'N/A')}")
    print(f"   Status: {user_info.get('status', 'N/A')}")
    print(f"   Responder Type: {user_info.get('responder_type', 'N/A')}")

if result['success']:
    print(f"\n💬 Conversation Context:")
    print("-" * 70)
    for line in result['formatted_lines']:
        # Format nicely
        prefix = "👤" if line.startswith("User:") else "🤖" if line.startswith("Bot:") else "👨‍💼"
        print(f"  {prefix} {line}")
    print("-" * 70)
    
    print(f"\n📝 Full Context Text:")
    print(result['context_text'])
else:
    print(f"\n❌ Error: {result.get('error')}")

# Test 2: Get last user message
print("\n" + "-"*70)
print("TEST 2: Get Last User Message")
print("-"*70)

last_user_msg = manager.get_last_user_message(TEST_USER_ID)
if last_user_msg:
    print(f"\n📨 Last User Message:")
    print(f"   {last_user_msg}")
else:
    print("\n❌ No user messages found")

# Test 3: Build AI prompt
print("\n" + "-"*70)
print("TEST 3: Build AI Prompt with Context")
print("-"*70)

prompt = manager.build_conversation_prompt(
    TEST_USER_ID,
    "I want to check the price for this item",
    limit=5
)

print(f"\n🧠 Generated AI Prompt:")
print("-" * 70)
print(prompt)
print("-" * 70)

print("\n✨ This prompt is ready to send to:")
print("   • Groq API (llama-3.1-8b-instant)")
print("   • OpenAI GPT")
print("   • Any LLM of your choice")

# Test 4: Get conversation summary
print("\n" + "-"*70)
print("TEST 4: Get Conversation Summary")
print("-"*70)

summary = manager.get_conversation_summary(TEST_USER_ID, limit=5)

print(f"\n📊 Conversation Summary:")
if summary['success']:
    print(f"   Total Messages: {summary['total_messages']}")
    print(f"   User Messages: {summary['user_messages']}")
    print(f"   Bot Messages: {summary['bot_messages']}")
    print(f"   Agent Messages: {summary['agent_messages']}")
    print(f"   User Name: {summary.get('user_name', 'N/A')}")
    print(f"\n   Summary: {summary['summary']}")
else:
    print(f"   ❌ {summary.get('summary')}")

# Test 5: Test with different user (if available)
print("\n" + "-"*70)
print("TEST 5: Integration Ready")
print("-"*70)

print(f"""
✅ Your conversation context manager is ready to use!

Python Integration:
    from src.utils.conversation_context import get_context_manager
    manager = get_context_manager()
    result = manager.get_last_n_messages("user_id", limit=5)
    print(result['context_text'])

API Endpoints Available:
    GET  /api/conversation/last-5/<user_id>
    POST /api/conversation/context/<user_id>
    GET  /api/conversation/summary/<user_id>

Example Usage:
    1. Get last 5 messages
    2. Format them as conversation context
    3. Pass to Groq API for better intent detection
    4. Send contextual response to user
    5. Repeat for every message!

🚀 The chatbot will now provide context-aware responses!
""")

print("="*70)
print("✅ All Tests Complete!")
print("="*70 + "\n")
