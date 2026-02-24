#!/usr/bin/env python3
"""
Quick fix verification script
"""
import requests
import json

def test_chatbot_fix():
    """Test if the chatbot is working after the fix"""
    print("🔧 Testing chatbot after API key update...")
    print("=" * 50)
    
    try:
        # Test with the problematic queries
        test_cases = [
            "hello",
            "stun gun", 
            "hp laptop ase",
            "ki ase"
        ]
        
        for message in test_cases:
            print(f"\n📤 Testing: '{message}'")
            
            response = requests.post(
                'http://localhost:5000/test',
                json={'message': message, 'user_id': 'test_user'},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get('response', 'No response')
                
                # Check if it's still the server busy message
                if "আমাদের সার্ভার মোমেন্টে ব্যস্ত আছে" in bot_response:
                    print("❌ Still getting server busy message")
                else:
                    print(f"✅ Response: {bot_response}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to chatbot server. Make sure it's running:")
        print("   Run: python app.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_chatbot_fix()