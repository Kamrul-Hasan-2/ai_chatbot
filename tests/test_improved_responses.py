#!/usr/bin/env python3
"""
Test Improved Groq Responses 
Verify better, more professional responses without inappropriate content
"""
import os
from dotenv import load_dotenv
from groq_model import GroqAIModel

# Load environment variables
load_dotenv()

def test_improved_responses():
    """Test the improved response quality"""
    print("🧪 Testing Improved Response Quality")
    print("=" * 60)
    
    try:
        # Initialize Groq model
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            print("❌ GROQ_API_KEY not found")
            return
            
        groq = GroqAIModel(api_key=api_key)
        print("✅ Groq model initialized")
        
        # Test cases for better responses
        test_cases = [
            {
                "query": "stun gun",
                "context": "Customer inquiry about security products",
                "expected_elements": ["সিকিউরিটি", "পণ্য", "প্রয়োজন", "কাস্টমার সার্ভিস"]
            },
            {
                "query": "hp laptop ase", 
                "context": "Customer asking about HP laptop availability",
                "expected_elements": ["HP", "ল্যাপটপ", "কোন", "কাজ", "গেমিং", "অফিস"]
            },
            {
                "query": "ki ase",
                "context": "General product inquiry", 
                "expected_elements": ["ইলেকট্রনিক্স", "ফ্যাশন", "হোম", "পণ্য", "প্রয়োজন"]
            },
            {
                "query": "price koto",
                "context": "Price inquiry",
                "expected_elements": ["দাম", "পণ্য", "কোনটা", "বুঝান"]
            }
        ]
        
        print("\n📝 Response Quality Check:")
        print("-" * 60)
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n{i}. Query: '{test['query']}'")
            
            try:
                response = groq.generate_response(
                    user_message=test['query'],
                    context=test['context'],
                    temperature=0.6,  # Focused responses
                    max_length=150    # Concise
                )
                
                print(f"   Response: {response}")
                
                # Check response quality
                checks = {
                    "Bengali": any(char in response for char in ['আ', 'ই', 'উ', 'এ', 'ও']),
                    "Professional": "ভাই" not in response and "দাদা" not in response,
                    "Relevant": any(element in response for element in test['expected_elements']),
                    "No Names": not any(name in response.lower() for name in ['john', 'smith', 'ahmed', 'রহিম', 'করিম']),
                    "Appropriate Length": 20 <= len(response) <= 200
                }
                
                print(f"   Quality Checks:")
                for check, passed in checks.items():
                    status = "✅" if passed else "❌"
                    print(f"     {status} {check}")
                
                overall_score = sum(checks.values()) / len(checks) * 100
                print(f"   Overall Score: {overall_score:.0f}%")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                
        print("\n" + "=" * 60)
        print("🎯 IMPROVEMENTS MADE:")
        print("✅ Removed casual terms like 'ভাই', 'দাদা'")  
        print("✅ Added professional tone")
        print("✅ Focused responses (150 tokens max)")
        print("✅ No personal name mentions")
        print("✅ Better product-specific guidance")
        print("✅ Reduced temperature for consistency")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_improved_responses()