"""
API Test: Follow-up Conversation Flow
Tests the complete system with API calls
"""
import requests
import json
import time

def test_api_follow_up():
    """Test follow-up conversation via API"""
    
    base_url = "http://localhost:5000"
    
    print("=" * 80)
    print("🌐 API FOLLOW-UP CONVERSATION TEST")
    print("=" * 80)
    print()
    
    # Test user
    user_id = "api_test_user_001"
    
    # Conversation 1: Order inquiry -> Product name
    print("📌 TEST 1: Order Inquiry Flow")
    print("-" * 80)
    
    # Step 1: Ask how to order
    print("\n👤 User: order kivabe dibo")
    response1 = requests.post(f"{base_url}/test", json={
        "user_id": user_id,
        "message": "order kivabe dibo"
    })
    
    if response1.status_code == 200:
        data1 = response1.json()
        print(f"🤖 Bot: {data1['response']}")
        print(f"📊 Source: {data1.get('processing_info', {}).get('source', 'N/A')}")
        print(f"📊 Category: {data1.get('processing_info', {}).get('category', 'N/A')}")
    else:
        print(f"❌ Error: {response1.status_code}")
        return
    
    time.sleep(1)
    
    # Step 2: Mention product
    print("\n👤 User: iPhone 15 Pro")
    response2 = requests.post(f"{base_url}/test", json={
        "user_id": user_id,
        "message": "iPhone 15 Pro"
    })
    
    if response2.status_code == 200:
        data2 = response2.json()
        print(f"🤖 Bot: {data2['response']}")
        print(f"📊 Source: {data2.get('processing_info', {}).get('source', 'N/A')}")
        print(f"📊 Category: {data2.get('processing_info', {}).get('category', 'N/A')}")
        
        # Check if follow-up was detected
        if "প্রতিনিধি কিছুক্ষণের মধ্যেই যোগাযোগ করবে" in data2['response']:
            print("✅ Follow-up detected! Correct response given.")
        else:
            print("❌ Follow-up NOT detected")
    else:
        print(f"❌ Error: {response2.status_code}")
    
    print("\n" + "=" * 80)
    
    # Test with different user and Bengali text
    print("\n📌 TEST 2: Bengali Order Flow")
    print("-" * 80)
    
    user_id2 = "api_test_user_002"
    
    # Step 1
    print("\n👤 User: অর্ডার করবো কি ভাবে?")
    response3 = requests.post(f"{base_url}/test", json={
        "user_id": user_id2,
        "message": "অর্ডার করবো কি ভাবে?"
    })
    
    if response3.status_code == 200:
        data3 = response3.json()
        print(f"🤖 Bot: {data3['response']}")
    
    time.sleep(1)
    
    # Step 2
    print("\n👤 User: Samsung Galaxy S24 Ultra")
    response4 = requests.post(f"{base_url}/test", json={
        "user_id": user_id2,
        "message": "Samsung Galaxy S24 Ultra"
    })
    
    if response4.status_code == 200:
        data4 = response4.json()
        print(f"🤖 Bot: {data4['response']}")
        
        if "প্রতিনিধি কিছুক্ষণের মধ্যেই যোগাযোগ করবে" in data4['response']:
            print("✅ Follow-up detected! Correct response given.")
        else:
            print("❌ Follow-up NOT detected")
    
    print("\n" + "=" * 80)
    print("✅ API TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    print("\n⚠️  Note: Make sure the server is running on http://localhost:5000")
    print("Press Enter to start test...")
    input()
    
    try:
        test_api_follow_up()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to server.")
        print("Please start the server with: python run.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
