"""
Test Facebook Messenger Connection
Quick script to verify webhook and messaging is working
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN')

print("=" * 60)
print("  Facebook Messenger Connection Test")
print("=" * 60)

# Test 1: Check if tokens are set
print("\n1. Checking Environment Variables...")
if PAGE_ACCESS_TOKEN:
    print(f"   ✅ PAGE_ACCESS_TOKEN: {PAGE_ACCESS_TOKEN[:20]}...")
else:
    print("   ❌ PAGE_ACCESS_TOKEN not found!")

if VERIFY_TOKEN:
    print(f"   ✅ VERIFY_TOKEN: {VERIFY_TOKEN}")
else:
    print("   ❌ VERIFY_TOKEN not found!")

# Test 2: Verify Facebook token
print("\n2. Testing Facebook Token...")
if PAGE_ACCESS_TOKEN:
    try:
        url = f"https://graph.facebook.com/v18.0/me?access_token={PAGE_ACCESS_TOKEN}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Token is VALID!")
            print(f"   Page ID: {data.get('id')}")
            print(f"   Page Name: {data.get('name', 'N/A')}")
        else:
            print(f"   ❌ Token INVALID: {response.text}")
    except Exception as e:
        print(f"   ❌ Error testing token: {e}")

# Test 3: Check local server
print("\n3. Testing Local Server...")
try:
    port = os.getenv('PORT', 5000)
    response = requests.get(f"http://localhost:{port}/health", timeout=2)
    if response.status_code == 200:
        print(f"   ✅ Server is running on port {port}")
    else:
        print(f"   ⚠️  Server responded with status {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"   ❌ Server is NOT running on port {port}")
    print(f"   → Start server: python app_integrated.py")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Test webhook verification
print("\n4. Testing Webhook Verification...")
try:
    port = os.getenv('PORT', 5000)
    url = f"http://localhost:{port}/webhook"
    params = {
        'hub.mode': 'subscribe',
        'hub.verify_token': VERIFY_TOKEN,
        'hub.challenge': 'test_challenge_123'
    }
    response = requests.get(url, params=params, timeout=2)
    
    if response.status_code == 200 and response.text == 'test_challenge_123':
        print("   ✅ Webhook verification works!")
    else:
        print(f"   ❌ Webhook verification failed: {response.text}")
except requests.exceptions.ConnectionError:
    print(f"   ❌ Server is not running")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Instructions
print("\n" + "=" * 60)
print("  TROUBLESHOOTING GUIDE")
print("=" * 60)

if not PAGE_ACCESS_TOKEN:
    print("\n⚠️  PAGE_ACCESS_TOKEN is missing!")
    print("   1. Go to Facebook Developers: https://developers.facebook.com")
    print("   2. Your App → Messenger → Settings")
    print("   3. Generate Page Access Token")
    print("   4. Add to .env file")

print("\n📋 Next Steps:")
print("   1. Start server: python app_integrated.py")
print("   2. Start ngrok: ngrok http 5000")
print("   3. Copy ngrok URL: https://abc123.ngrok.io")
print("   4. Setup Facebook webhook:")
print("      - Callback URL: https://abc123.ngrok.io/webhook")
print("      - Verify Token: my_verify_token_12345")
print("   5. Subscribe your page")
print("   6. Test by messaging your page!")

print("\n" + "=" * 60)
