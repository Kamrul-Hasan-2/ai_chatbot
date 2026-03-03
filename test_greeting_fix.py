"""
Test: Greetings should NOT trigger human handoff
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_greeting(message, user_id="test_user"):
    """Test a greeting message"""
    print(f"\n{'='*60}")
    print(f"Testing: {message}")
    print('='*60)
    
    # First reset to AI mode
    reset_response = requests.post(f"{BASE_URL}/mode/{user_id}/ai")
    print(f"✅ Reset to AI mode: {reset_response.json()}")
    
    # Send message
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": message
        }
    )
    
    data = response.json()
    
    print(f"\n📨 Message: {data.get('message')}")
    print(f"🤖 Response: {data.get('response')}")
    print(f"🎯 Intent: {data.get('intent')}")
    print(f"📍 Mode: {data.get('mode')}")
    
    if data.get('mode') == 'ai':
        print("✅ SUCCESS: Stayed in AI mode (not sent to human)")
    else:
        print("❌ FAILED: Was sent to HUMAN mode")
    
    return data


def test_product_search(message, user_id="test_user"):
    """Test a product search"""
    print(f"\n{'='*60}")
    print(f"Testing: {message}")
    print('='*60)
    
    # First reset to AI mode
    reset_response = requests.post(f"{BASE_URL}/mode/{user_id}/ai")
    print(f"✅ Reset to AI mode: {reset_response.json()}")
    
    # Send message
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": message
        }
    )
    
    data = response.json()
    
    print(f"\n📨 Message: {data.get('message')}")
    print(f"🎯 Intent: {data.get('intent')}")
    print(f"📦 Products Found: {data.get('products_found', 0)}")
    print(f"📍 Mode: {data.get('mode')}")
    print(f"🤖 Response: {data.get('response')[:100]}...")
    
    if data.get('mode') == 'ai' and data.get('products_found', 0) > 0:
        print("✅ SUCCESS: Found products and stayed in AI mode")
    elif data.get('mode') == 'ai':
        print("⚠️ WARNING: No products found")
    else:
        print("❌ FAILED: Was sent to HUMAN mode")
    
    return data


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 Testing Greeting Fix - Should NOT go to HUMAN mode")
    print("="*60)
    
    # Test 1: Simple greetings should stay in AI mode
    test_greeting("hi")
    test_greeting("hello")
    test_greeting("hey")
    test_greeting("assalamu alaikum")
    test_greeting("আসসালামু আলাইকুম")
    
    # Test 2: Goodbye should stay in AI mode  
    test_greeting("bye")
    test_greeting("goodbye")
    test_greeting("ধন্যবাদ")
    
    # Test 3: Product search should work and stay in AI
    test_product_search("laptop dekhan")
    test_product_search("10k er modde laptop")
    test_product_search("hp laptop")
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
