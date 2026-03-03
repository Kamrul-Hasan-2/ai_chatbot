#!/usr/bin/env python3
"""
Test Gemini API Configuration and Functionality
"""
import os
import logging
from gemini_model import GeminiAIModel

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_gemini_api():
    """Test the Gemini API directly"""
    print("🔍 Testing Gemini API Configuration...")
    print("=" * 50)
    
    try:
        # Check environment variable
        api_key = os.getenv('GEMINI_API_KEY')
        print(f"API Key from env: {'✅ Set' if api_key else '❌ Not set'}")
        
        if not api_key:
            print("⚠️  GEMINI_API_KEY environment variable is not set!")
            print("You need to set it with: $env:GEMINI_API_KEY='your-api-key'")
            return False
            
        # Initialize Gemini model
        print("\n🚀 Initializing Gemini model...")
        gemini = GeminiAIModel(api_key=api_key)
        print("✅ Gemini model initialized successfully")
        
        # Test simple query
        print("\n💬 Testing simple query...")
        test_messages = [
            "hello",
            "stun gun", 
            "hp laptop ase"
        ]
        
        for message in test_messages:
            print(f"\n📤 Testing: '{message}'")
            try:
                response = gemini.generate_response(
                    user_message=message,
                    context="Test context",
                    temperature=0.7
                )
                print(f"✅ Response: {response}")
            except Exception as e:
                print(f"❌ Error: {type(e).__name__}: {e}")
                
        return True
            
    except Exception as e:
        print(f"❌ Failed to initialize Gemini: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_gemini_api()
    if not success:
        print("\n🔧 Troubleshooting steps:")
        print("1. Get a Gemini API key from: https://makersuite.google.com/app/apikey")
        print("2. Set it as environment variable:")
        print("   PowerShell: $env:GEMINI_API_KEY='your-api-key'")
        print("   CMD: set GEMINI_API_KEY=your-api-key")
        print("3. Restart your terminal and try again")