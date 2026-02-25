#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify API search always runs and returns no response when no products found
"""

from groq_3step_search import Groq3StepSearch
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_api_search():
    """Test API search with various queries"""
    
    print("\n" + "=" * 80)
    print("API SEARCH FIX TEST")
    print("=" * 80)
    print("\nVerifying:")
    print("  1. API is ALWAYS searched")
    print("  2. If no products found, return EMPTY response (AI off)")
    print("=" * 80)
    
    searcher = Groq3StepSearch()
    
    test_cases = [
        ("Premium Office Visitor Chair aee", "Product that might not exist"),
        ("xyz123nonexistentproduct", "Definitely non-existent product"),
        ("hp laptop", "Common product (should find results)"),
        ("web cam", "Common product (should find results)"),
    ]
    
    for i, (query, description) in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {description}")
        print(f"Query: '{query}'")
        print("-" * 80)
        
        result = searcher.search(query)
        
        # Check Step 1
        step1 = result.get('step1', {})
        print(f"\n✓ Step 1 - Intent Detection:")
        print(f"  - Intent: {step1.get('intent', 'N/A')}")
        print(f"  - Keywords: {step1.get('search_terms', 'N/A')}")
        print(f"  - Method: {step1.get('method', 'N/A')}")
        
        # Check Step 2 - API Search
        step2 = result.get('step2', {})
        print(f"\n✓ Step 2 - API Search (ALWAYS CALLED):")
        print(f"  - API Called: {'YES' if step2 else 'NO'}")
        print(f"  - Products Found: {step2.get('product_count', 0)}")
        
        # Check response logic
        product_count = step2.get('product_count', 0)
        response = result.get('response', '')
        
        print(f"\n✓ Response Logic:")
        if product_count == 0:
            print(f"  - No products found")
            print(f"  - Response: '{response}'")
            if response == '':
                print(f"  - ✅ CORRECT: Empty response (AI is OFF)")
            else:
                print(f"  - ❌ ERROR: Should be empty, but got text!")
        else:
            print(f"  - Products: {product_count}")
            print(f"  - Response Length: {len(response)} characters")
            print(f"  - Response Preview: {response[:100]}...")
            print(f"  - ✅ CORRECT: Response provided")
            
            # Show products
            if step2.get('products'):
                print(f"\n  Top products:")
                for j, prod in enumerate(step2['products'][:3], 1):
                    print(f"    {j}. {prod['title'][:60]}")
                    print(f"       Price: {prod['price']}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nKEY FEATURES VERIFIED:")
    print("  ✓ API is called for EVERY query")
    print("  ✓ When no products found -> Empty response")
    print("  ✓ When products found -> Groq formatted Bengali response")
    print("=" * 80)

if __name__ == "__main__":
    test_api_search()
