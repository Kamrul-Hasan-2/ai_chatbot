"""
Test irrelevant message handling - should switch to HUMAN mode
"""
import requests
import json

API_URL = "http://localhost:5000/chat"

test_cases = [
    {
        "name": "Normal Product Search (should stay AI)",
        "message": "amake ekta 10k er modde laptop dekhan",
        "expected_mode": "ai"
    },
    {
        "name": "Greeting (should stay AI)",
        "message": "hello",
        "expected_mode": "ai"
    },
    {
        "name": "Irrelevant nonsense (should switch HUMAN)",
        "message": "asdasd xyz 123 random text",
        "expected_mode": "human"
    },
    {
        "name": "Complaint/Refund (should switch HUMAN)",
        "message": "ami amar product ferot dite chai",
        "expected_mode": "human"
    },
    {
        "name": "Off-topic question (should switch HUMAN)",
        "message": "aj brishti hobe?",
        "expected_mode": "human"  # Weather question - irrelevant to shopping
    }
]

print("=" * 60)
print("🧪 Testing Irrelevant Message Detection")
print("=" * 60)

for i, test in enumerate(test_cases, 1):
    print(f"\n{i}. {test['name']}")
    print(f"   Message: {test['message']}")
    
    try:
        response = requests.post(
            API_URL,
            json={
                "user_id": f"test_user_{i}",
                "message": test['message']
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            mode = data.get('mode', 'unknown')
            intent = data.get('intent', 'unknown')
            response_text = data.get('response', '')[:100]
            
            status = "✅ PASS" if mode == test['expected_mode'] else "❌ FAIL"
            
            print(f"   Expected: {test['expected_mode']}")
            print(f"   Got: {mode}")
            print(f"   Intent: {intent}")
            print(f"   Response: {response_text}...")
            print(f"   {status}")
        else:
            print(f"   ❌ ERROR: Status {response.status_code}")
    
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
