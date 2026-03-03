#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROQ 3-STEP PRODUCT SEARCH - LIVE DEMO
See the complete 3-step workflow in action:
1. Message -> Groq Intent Detection
2. Keywords -> BDStall API Search (top 3 products)
3. Products -> Groq Beautiful Bengali Response
"""

from groq_3step_search import Groq3StepSearch
import os
import sys

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def print_separator(char="=", length=80):
    print(char * length)

def demo_3step_search():
    """Interactive demo of Groq 3-step search"""
    
    print("\n")
    print_separator("=")
    print("GROQ 3-STEP PRODUCT SEARCH - LIVE DEMO")
    print_separator("=")
    print()
    print("WORKFLOW:")
    print("   Step 1: Message -> Groq AI (Intent & Keywords)")
    print("   Step 2: Keywords -> BDStall API (Top 3 Products)")
    print("   Step 3: Products -> Groq AI (Bengali Response)")
    print()
    
    # Initialize searcher
    print("Initializing...")
    searcher = Groq3StepSearch()
    
    # Check if Groq is available
    has_groq = searcher.groq is not None
    
    if has_groq:
        print("✅ Groq AI is ENABLED (Full Power!)")
    else:
        print("⚠️  Groq AI is DISABLED (Using Fallback)")
        print("   To enable: Set GROQ_API_KEY environment variable")
    
    print()
    print_separator()
    
    # Demo queries
    demo_queries = [
        ("web cam lagbe", "Web cam search"),
        ("hp laptop dAm koto", "HP laptop price inquiry"),
        ("wireless headphone ache", "Availability check"),
        ("gaming mouse kinte chai", "Gaming mouse inquiry"),
        ("printer dekhaio", "Printer search"),
    ]
    
    for i, (query, description) in enumerate(demo_queries, 1):
        print(f"\nDEMO {i}: {description}")
        print(f"   Input: \"{query}\"")
        print("-" * 80)
        
        result = searcher.search(query)
        
        # Step 1 Info
        step1 = result.get('step1', {})
        print(f"\nStep 1 - Intent Detection ({step1.get('method', 'unknown')})")
        print(f"   Intent:      {step1.get('intent', 'unknown')}")
        print(f"   Keywords:    {step1.get('search_terms', '')}")
        print(f"   Confidence:  {step1.get('confidence', 0):.0%}")
        
        # Step 2 Info
        step2 = result.get('step2', {})
        print(f"\nStep 2 - API Search")
        print(f"   Products:    {step2.get('product_count', 0)} found")
        
        if step2.get('product_count', 0) > 0:
            print(f"   List:")
            for j, product in enumerate(step2.get('products', [])[:3], 1):
                price = product.get('price', 'N/A')
                title = product.get('title', 'No title')[:45]
                print(f"     {j}. {title}")
                print(f"        Price: {price}")
        
        # Step 3 Info
        step3 = result.get('step3', {})
        print(f"\nStep 3 - Response Formatting ({step3.get('method', 'unknown')})")
        print(f"   Response:")
        response_lines = result.get('response', '').split('\n')
        for line in response_lines[:4]:  # First 4 lines
            if line.strip():
                print(f"   {line}")
        
        if len(response_lines) > 4:
            print(f"   ... [Response continues]")
        
        print()
    
    print_separator()
    print("\nDEMO COMPLETE!")
    print("\nKEY FEATURES:")
    print("   [OK] Groq AI detects intent and cleans keywords")
    print("   [OK] BDStall API returns top 3 relevant products")
    print("   [OK] Groq AI formats beautiful Bengali response")
    print("   [OK] Automatic fallback if any step fails")
    print("   [OK] All links automatically removed")
    print()
    print("INTEGRATION:")
    print("   Import in your chatbot:")
    print("   ")
    print("   from groq_3step_search import Groq3StepSearch")
    print("   searcher = Groq3StepSearch()")
    print("   result = searcher.search(user_message)")
    print("   print(result['response'])")
    print()
    print_separator()

if __name__ == "__main__":
    demo_3step_search()
