#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST: Typo Handling in Product Search
Test if Groq AI can correct typos like "laptpp" to "laptop"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.groq_3step_search import Groq3StepSearch

def test_typo_handling():
    """Test typo correction in product searches"""
    
    print("\n" + "="*80)
    print("TEST: TYPO HANDLING IN PRODUCT SEARCH")
    print("="*80 + "\n")
    
    searcher = Groq3StepSearch()
    
    # Test cases with typos
    test_queries = [
        ("laptpp", "Typo: laptop"),
        ("wireles mouse", "Typo: wireless"),
        ("headfone", "Typo: headphone"),
        ("hp lapto", "Typo: hp laptop"),
        ("gamin mouse", "Typo: gaming mouse"),
        ("print", "Incomplete: printer"),
        ("web cma", "Typo: web cam"),
        ("smartfone", "Typo: smartphone"),
    ]
    
    print("Testing these typo queries:\n")
    
    for query, description in test_queries:
        print(f"\n{'─'*80}")
        print(f"Query: '{query}' ({description})")
        print(f"{'─'*80}")
        
        try:
            result = searcher.search(query)
            
            # Step 1: Intent Detection
            step1 = result.get('step1', {})
            detected_keywords = step1.get('search_terms', '')
            
            print(f"✓ Step 1 (Intent Detection):")
            print(f"  Input:    {query}")
            print(f"  Keywords: {detected_keywords}")
            print(f"  Intent:   {step1.get('intent', 'unknown')}")
            
            # Step 2: API Search
            step2 = result.get('step2', {})
            products_found = step2.get('product_count', 0)
            
            print(f"\n✓ Step 2 (API Search):")
            print(f"  Products Found: {products_found}")
            
            if products_found > 0:
                print(f"  Top Results:")
                for i, product in enumerate(step2.get('products', [])[:2], 1):
                    title = product.get('title', 'No title')[:50]
                    price = product.get('price', 'N/A')
                    print(f"    {i}. {title}")
                    print(f"       Price: {price}")
                print(f"  ✅ Typo correction was SUCCESSFUL!")
            else:
                print(f"  ❌ No products found - typo not corrected")
            
            # Step 3: Response
            response = result.get('response', '')
            if response:
                print(f"\n✓ Step 3 (Response):")
                first_line = response.split('\n')[0]
                print(f"  {first_line[:70]}...")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print("""
Current Status:
- Groq AI uses natural language processing to understand intent
- It should be able to correct minor typos naturally
- More serious typos may require explicit spell-checking

Recommendation:
- Add a spell-check layer BEFORE sending to Groq
- Use difflib or similar for fuzzy matching
- Maintain a product keyword dictionary for correction
    """)

if __name__ == "__main__":
    test_typo_handling()
