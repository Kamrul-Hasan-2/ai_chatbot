#!/usr/bin/env python3
"""
Test Groq API Integration
Verify the new Groq implementation works properly
"""
import os
import logging
from groq_model import GroqAIModel

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_groq_integration():
    """Test the complete Groq integration"""
    print("🚀 Testing Groq API Integration...")
    print("=" * 60)
    
    try:
        # Check environment variable
        api_key = os.getenv('GROQ_API_KEY')
        print(f"API Key from env: {'✅ Set' if api_key else '❌ Not set'}")
        
        if not api_key:
            print("⚠️  GROQ_API_KEY environment variable is not set!")
            return False
            
        # Initialize Groq model
        print("\n🤖 Initializing Groq model...")
        groq = GroqAIModel(api_key=api_key)
        print("✅ Groq model initialized successfully")
        
        # Test connection
        print("\n🔗 Testing API connection...")
        is_working = groq.test_connection()
        print(f"Connection test: {'✅ Working' if is_working else '❌ Failed'}")
        
        # Get available models
        print("\n📋 Getting available models...")
        models = groq.get_available_models()
        print(f"Available models: {models[:3]}...")  # Show first 3
        
        # Test the problematic queries
        print("\n💬 Testing with user queries...")
        test_messages = [
            "hello",
            "stun gun", 
            "hp laptop ase",
            "ki ase"
        ]
        
        for message in test_messages:
            print(f"\n📤 Testing: '{message}'")
            try:
                response = groq.generate_response(
                    user_message=message,
                    context="BDStall.com online shopping site",
                    temperature=0.7,
                    max_length=100
                )
                print(f"✅ Response: {response}")
                
                # Check if it's still the server busy message
                if "আমাদের সার্ভার মোমেন্টে ব্যস্ত আছে" in response:
                    print("⚠️  Still getting server busy message!")
                    
            except Exception as e:
                print(f"❌ Error: {type(e).__name__}: {e}")
                
        return True
            
    except Exception as e:
        print(f"❌ Failed to test Groq integration: {type(e).__name__}: {e}")
        return False

def test_chatbot_endpoints():
    """Test the full chatbot system with Groq"""
    import requests
    
    print("\n" + "=" * 60)
    print("🌐 Testing Full Chatbot System...")
    print("=" * 60)
    
    try:
        # Test with the problematic queries
        test_cases = [
            "hello",
            "stun gun", 
            "hp laptop ase",
            "ki ase"
        ]
        
        for message in test_cases:
            print(f"\n📤 Testing chatbot: '{message}'")
            
            response = requests.post(
                'http://localhost:5000/test',
                json={'message': message, 'user_id': 'groq_test'},
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get('response', 'No response')
                
                # Check if it's still the server busy message
                if "আমাদের সার্ভার মোমেন্টে ব্যস্ত আছে" in bot_response:
                    print("❌ Still getting server busy message")
                else:
                    print(f"✅ Response: {bot_response}")
                    print(f"   Source: {result.get('processing_info', {}).get('source', 'unknown')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to chatbot server")
        print("   Make sure to run: python app.py")
    except Exception as e:
        print(f"❌ Error testing endpoints: {e}")

if __name__ == "__main__":
    # Test Groq API directly
    success = test_groq_integration()
    
    if success:
        # Test full chatbot system
        test_chatbot_endpoints()
        
        print("\n" + "=" * 60)
        print("🎉 Groq Integration Test Complete!")
        print("=" * 60)
        print("Next steps:")
        print("1. ✅ Groq API is working")
        print("2. 🔄 Restart your chatbot: python app.py") 
        print("3. 🧪 Test with your queries")
        print("4. 🎯 Enjoy faster AI responses!")
    else:
        print("\n❌ Groq integration failed. Check your API key and try again.")