#!/usr/bin/env python3
"""Test script for brand & category extraction feature"""

import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.core.simple_chatbot_flow import SimpleChatbot

def test_brand_category_extraction():
    """Test the new brand & category extraction feature"""
    
    print("[INFO] Starting Brand & Category Extraction Tests\n")
    
    # Initialize chatbot
    chatbot = SimpleChatbot()
    
    test_messages = [
        "iphone ase",
        "iPhone SE",
        "dell laptop",
        "samsung phone",
        "hp laptop under 50k",
        "macbook pro",
        "xiaomi smartphone",
        "asus rog laptop",
        "apple tablet",
        "realme phone"
    ]
    
    print("=" * 80)
    print("Testing Brand & Category Extraction with Groq")
    print("=" * 80)
    
    for idx, message in enumerate(test_messages, 1):
        print(f"\n{idx}. Message: '{message}'")
        print("-" * 80)
        
        try:
            # Test direct extraction
            result = chatbot._extract_brand_category_groq(message)
            
            print(f"   Brand:    {result.get('brand') or 'N/A'}")
            print(f"   Category: {result.get('category') or 'N/A'}")
            print(f"   Title:    {result.get('title') or 'N/A'}")
            
            # Verify both are present
            brand = result.get('brand')
            category = result.get('category')
            title = result.get('title')
            
            if brand and category:
                print(f"   [OK] SUCCESS: Both brand and category extracted")
            elif brand or category:
                print(f"   [WARNING] Only partial extraction (brand={bool(brand)}, category={bool(category)})")
            else:
                print(f"   [FAILED] No extraction")
                
        except Exception as e:
            print(f"   [ERROR] {str(e)}")
    
    print("\n" + "=" * 80)
    print("Testing Full Process (process_message)")
    print("=" * 80)
    
    user_id = "test_user_123"
    test_message = "iphone ase"
    
    print(f"\nUser: {user_id}")
    print(f"Message: '{test_message}'")
    print("-" * 80)
    
    try:
        response = chatbot.process_message(user_id, test_message)
        
        print(f"Intent: {response.get('intent')}")
        print(f"Mode: {response.get('mode')}")
        print(f"Response: {response.get('response')[:100] if response.get('response') else 'N/A'}")
        
        intent_content = response.get('intent_content', {})
        if intent_content:
            print(f"\nIntent Content:")
            print(f"  Title:    {intent_content.get('title')}")
            print(f"  Category: {intent_content.get('category')}")
            print(f"  Brand:    {intent_content.get('brand')}")
            print(f"  Price:    {intent_content.get('price')}")
            
            if intent_content.get('title') and intent_content.get('category'):
                print(f"\n[OK] SUCCESS: Both title and category are present!")
            else:
                print(f"\n[WARNING] Missing title or category")
        
        if response.get('products_found', 0) > 0:
            print(f"\nProducts Found: {response.get('products_found')}")
            print("Sample Products:")
            for idx, prod in enumerate(response.get('products', [])[:3], 1):
                print(f"  {idx}. {prod.get('title')} - {prod.get('price')}")
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Tests Complete!")
    print("=" * 80)

if __name__ == '__main__':
    test_brand_category_extraction()
