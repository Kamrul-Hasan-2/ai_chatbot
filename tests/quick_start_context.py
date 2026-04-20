#!/usr/bin/env python3
"""
Quick Start Guide - Last 5 Messages Context Feature

This script demonstrates how to use the conversation context features
with your chatbot.

Run this after starting the server:
    python tests/quick_start_context.py
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:5000"
TEST_USER = "demo_user_" + str(int(time.time()))

print("\n" + "="*70)
print("LAST 5 MESSAGES CONTEXT - QUICK START GUIDE")
print("="*70)

print(f"\n🔍 Test User ID: {TEST_USER}")
print("📍 API Base: " + API_BASE)

# Test 1: Get last 5 messages
print("\n" + "-"*70)
print("TEST 1: Get Last 5 Messages for a User")
print("-"*70)

url = f"{API_BASE}/api/conversation/last-5/{TEST_USER}?limit=5"
print(f"\n📍 Endpoint: GET {url}")
print(f"📋 Description: Retrieve the last 5 messages")

try:
    response = requests.get(url, timeout=5)
    data = response.json()
    
    print(f"\n✅ Status: {response.status_code}")
    print(f"✅ Success: {data.get('success')}")
    print(f"✅ Messages Found: {data.get('count')}")
    
    if data.get('success'):
        print("\n📝 Context Text:")
        context = data.get('context_text', 'No messages yet')
        if context:
            for line in context.split('\n'):
                print(f"   {line}")
        else:
            print("   (User has no conversation history yet)")
    else:
        print(f"\nℹ️  Note: {data.get('error')}")
        
except Exception as e:
    print(f"\n⚠️  Error: {e}")

# Test 2: Build AI Prompt
print("\n" + "-"*70)
print("TEST 2: Build Conversation Context for AI Prompt")
print("-"*70)

url = f"{API_BASE}/api/conversation/context/{TEST_USER}"
print(f"\n📍 Endpoint: POST {url}")
print(f"📋 Description: Build an AI prompt with conversation history")

payload = {
    "message": "what options do you have?",
    "limit": 5
}

print(f"\n📨 Request Body:")
print(f"   {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, timeout=5)
    data = response.json()
    
    print(f"\n✅ Status: {response.status_code}")
    print(f"✅ Success: {data.get('success')}")
    
    if data.get('success'):
        print("\n🧠 Generated AI Prompt:")
        print("-" * 70)
        prompt = data.get('prompt', '')
        for line in prompt.split('\n'):
            print(f"   {line}")
        print("-" * 70)
        print("\nℹ️  This prompt is ready to send to:")
        print("   - Groq API")
        print("   - OpenAI GPT")
        print("   - Any LLM of your choice")
    else:
        print(f"\nℹ️  Note: {data.get('error')}")
        
except Exception as e:
    print(f"\n⚠️  Error: {e}")

# Test 3: Get Conversation Summary
print("\n" + "-"*70)
print("TEST 3: Get Conversation Summary")
print("-"*70)

url = f"{API_BASE}/api/conversation/summary/{TEST_USER}?limit=5"
print(f"\n📍 Endpoint: GET {url}")
print(f"📋 Description: Get statistics about the conversation")

try:
    response = requests.get(url, timeout=5)
    data = response.json()
    
    print(f"\n✅ Status: {response.status_code}")
    print(f"✅ Success: {data.get('success')}")
    
    if data.get('success'):
        print("\n📊 Conversation Statistics:")
        print(f"   Total Messages: {data.get('total_messages', 0)}")
        print(f"   User Messages: {data.get('user_messages', 0)}")
        print(f"   Bot Messages: {data.get('bot_messages', 0)}")
        print(f"   Agent Messages: {data.get('agent_messages', 0)}")
        print(f"\n   Summary: {data.get('summary', '')}")
    else:
        print(f"\nℹ️  Note: {data.get('error')}")
        
except Exception as e:
    print(f"\n⚠️  Error: {e}")

# Test 4: Send a message with context
print("\n" + "-"*70)
print("TEST 4: Send Message (Uses Context Internally)")
print("-"*70)

url = f"{API_BASE}/chat"
print(f"\n📍 Endpoint: POST {url}")
print(f"📋 Description: Send a message (context is used automatically)")

payload = {
    "user_id": TEST_USER,
    "message": "laptop dekhaen"
}

print(f"\n📨 Request Body:")
print(f"   {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload, timeout=10)
    data = response.json()
    
    print(f"\n✅ Status: {response.status_code}")
    print(f"✅ Success: {data.get('success')}")
    print(f"✅ Intent: {data.get('intent')}")
    print(f"✅ Mode: {data.get('mode')}")
    
    response_text = data.get('response', '')[:100]
    print(f"\n🤖 Bot Response:")
    print(f"   {response_text}...")
    
    if data.get('products'):
        print(f"\n📦 Products Found: {len(data.get('products', []))}")
        
except Exception as e:
    print(f"\n⚠️  Error: {e}")

# Summary
print("\n" + "="*70)
print("QUICK START SUMMARY")
print("="*70)

print("""
✅ Features Implemented:

1. 📋 GET /api/conversation/last-5/<user_id>
   → Fetch the last 5 messages for any user

2. 🧠 POST /api/conversation/context/<user_id>
   → Build AI-ready prompts with conversation context

3. 📊 GET /api/conversation/summary/<user_id>
   → Get conversation statistics

4. 💬 POST /chat (Already Integrated)
   → Automatically uses context for better responses

✨ Benefits:

• Better intent detection
• More contextual responses
• Understands follow-up messages
• No manual setup required
• Configurable via environment variables

🚀 Usage:

Python:
    from src.utils.conversation_context import get_context_manager
    manager = get_context_manager()
    result = manager.get_last_n_messages("user_123", limit=5)

cURL:
    curl http://localhost:5000/api/conversation/last-5/user_123?limit=5

JavaScript:
    fetch('/api/conversation/last-5/user_123?limit=5')
      .then(r => r.json())
      .then(data => console.log(data.context_text))

📚 Documentation:
   - See: IMPLEMENTATION_LAST_5_MESSAGES.md
   - See: LAST_5_MESSAGES_CONTEXT_FEATURE.md
   - Tests: tests/test_last_5_messages.py
""")

print("="*70)
print("✅ Quick Start Complete!")
print("="*70 + "\n")
