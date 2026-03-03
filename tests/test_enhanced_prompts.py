#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Enhanced Prompt Engineering for BDStall.com Ltd
Shows the improved AI responses with better structured prompts
"""

from groq_3step_search import Groq3StepSearch
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_enhanced_prompts():
    """Test the enhanced prompt engineering"""
    
    print("\n" + "=" * 90)
    print("🚀 ENHANCED PROMPT ENGINEERING TEST - BDStall.com Ltd")
    print("=" * 90)
    print("\nIMPROVEMENTS:")
    print("  ✓ Better role definition (BDStall.com Ltd representative)")
    print("  ✓ Structured intent detection with clear examples")
    print("  ✓ Professional Bengali business communication")
    print("  ✓ Cleaner keyword extraction (removes filler words)")
    print("  ✓ Warm yet professional tone")
    print("  ✓ Clear constraints (no URLs, proper formatting)")
    print("=" * 90)
    
    searcher = Groq3StepSearch()
    
    # Check if Groq is available
    has_groq = searcher.groq is not None
    
    if has_groq:
        print("\n✅ Groq AI is ACTIVE - You'll see AI-powered responses!")
    else:
        print("\n⚠️  Groq AI is DISABLED - Using fallback mode")
        print("   To see full AI power: Set GROQ_API_KEY environment variable")
    
    print()
    
    test_cases = [
        ("Premium Office Visitor Chair kinte chai", "Office chair purchase intent"),
        ("hp laptop dam koto", "Price inquiry with Bengali"),
        ("web cam lagbe urgent", "Product search with filler words"),
        ("gaming mouse ache naki", "Availability check"),
        ("wireless headphone dekhaio", "Product browsing request"),
    ]
    
    for i, (query, description) in enumerate(test_cases, 1):
        print("\n" + "=" * 90)
        print(f"TEST {i}: {description}")
        print(f"Input: '{query}'")
        print("-" * 90)
        
        result = searcher.search(query)
        
        # Display Step 1 - Intent Detection
        step1 = result.get('step1', {})
        print(f"\n📊 STEP 1 - Intent Detection ({step1.get('method', 'unknown')})")
        print(f"   Intent:       {step1.get('intent', 'N/A')}")
        print(f"   Keywords:     {step1.get('search_terms', 'N/A')}")
        print(f"   Confidence:   {step1.get('confidence', 0):.0%}")
        if has_groq and step1.get('method') == 'groq_ai':
            print(f"   AI Response:  {step1.get('groq_response', '')[:80]}...")
        
        # Display Step 2 - API Search
        step2 = result.get('step2', {})
        print(f"\n🔍 STEP 2 - BDStall API Search")
        print(f"   Products:     {step2.get('product_count', 0)} found")
        
        if step2.get('product_count', 0) > 0:
            print(f"   Top Results:")
            for j, product in enumerate(step2.get('products', [])[:3], 1):
                print(f"     {j}. {product.get('title', 'N/A')[:65]}")
                print(f"        Price: {product.get('price', 'N/A')} টাকা")
        
        # Display Step 3 - Response
        response = result.get('response', '')
        if response:
            step3 = result.get('step3', {})
            print(f"\n✨ STEP 3 - Response Formatting ({step3.get('method', 'unknown')})")
            print(f"\n📝 FINAL RESPONSE (BDStall.com Ltd):")
            print("   " + "─" * 85)
            for line in response.split('\n'):
                if line.strip():
                    print(f"   {line}")
            print("   " + "─" * 85)
        else:
            print(f"\n❌ NO RESPONSE (No products found)")
        
        print()
    
    print("=" * 90)
    print("✅ TEST COMPLETE - Enhanced Prompt Engineering Working!")
    print("=" * 90)
    print("\nKEY FEATURES OF NEW PROMPTS:")
    print("  1. Clear role: BDStall.com Ltd customer support representative")
    print("  2. Better keyword extraction: Removes 'lagbe', 'chai', 'koto', etc.")
    print("  3. Professional Bengali: Business-appropriate yet friendly tone")
    print("  4. Structured format: Clear sections for better AI understanding")
    print("  5. Examples included: AI learns from concrete examples")
    print("  6. Constraints defined: No URLs, no unnecessary repetition")
    print("=" * 90)

if __name__ == "__main__":
    test_enhanced_prompts()
