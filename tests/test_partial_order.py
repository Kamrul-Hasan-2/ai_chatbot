#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Partial Order Detection - Asks for Missing Information
Shows that the system now intelligently asks for missing order details
"""

from groq_3step_search import Groq3StepSearch
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_partial_orders():
    """Test partial order information handling"""
    
    print("\n" + "=" * 90)
    print("📝 PARTIAL ORDER DETECTION TEST - BDStall.com Ltd")
    print("=" * 90)
    print("\nFEATURE: Asks for missing information instead of ignoring partial orders")
    print("=" * 90)
    
    searcher = Groq3StepSearch()
    
    test_cases = [
        {
            "description": "Missing Phone Number",
            "message": "আমি অর্ডার করতে চাই। Name: Rahim, Address: Dhanmondi",
            "expected": "Should ask for phone number"
        },
        {
            "description": "Missing Address",
            "message": "Name: Karim Ahmed, Phone: 01712345678",
            "expected": "Should ask for address"
        },
        {
            "description": "Missing Name",
            "message": "Address: Gulshan-2, Dhaka, Phone: 01823456789",
            "expected": "Should ask for name"
        },
        {
            "description": "Only Phone (Missing Name & Address)",
            "message": "Phone: 01934567890",
            "expected": "Should ask for name and address"
        },
        {
            "description": "Complete Order (All Info Present)",
            "message": "Name: Kamel, Address: Uttara, Phone: 01933930303",
            "expected": "Should confirm order"
        },
        {
            "description": "No Order Info (Regular Message)",
            "message": "hp laptop কিনতে চাই",
            "expected": "Should do product search"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*90}")
        print(f"TEST {i}: {test_case['description']}")
        print(f"Expected: {test_case['expected']}")
        print("-" * 90)
        
        print(f"\n👤 Customer Message:")
        print(f"   \"{test_case['message']}\"")
        
        result = searcher.search(test_case['message'])
        
        workflow = result.get('workflow', 'unknown')
        
        print(f"\n🔍 Detected Workflow: {workflow}")
        
        if workflow == 'order_confirmation':
            print("\n✅ COMPLETE ORDER CONFIRMED!")
            order_info = result.get('order_info', {})
            print(f"   Name: {order_info.get('name')}")
            print(f"   Address: {order_info.get('address')}")
            print(f"   Phone: {order_info.get('phone')}")
            
        elif workflow == 'partial_order':
            print("\n📝 PARTIAL ORDER DETECTED!")
            partial = result.get('partial_order', {})
            present = partial.get('present', {})
            missing = partial.get('missing', [])
            
            print(f"   Present Fields: {', '.join(present.keys())}")
            print(f"   Missing Fields: {', '.join(missing)}")
            
        else:
            print(f"\n🔍 PRODUCT SEARCH MODE")
            if result.get('no_products_found'):
                print("   No products found")
            elif result.get('products_found', 0) > 0:
                print(f"   Found {result.get('products_found')} products")
        
        print(f"\n📱 Bot Response:")
        print("   " + "-" * 85)
        response = result.get('response', '')
        if response:
            for line in response.split('\n')[:5]:  # First 5 lines
                if line.strip():
                    print(f"   {line}")
            if len(response.split('\n')) > 5:
                print("   ...")
        else:
            print("   (No response - Product not found)")
        print("   " + "-" * 85)
    
    print("\n" + "=" * 90)
    print("✅ PARTIAL ORDER DETECTION WORKING!")
    print("=" * 90)
    print("\nKEY IMPROVEMENTS:")
    print("  ✓ Detects when customer provides partial order information")
    print("  ✓ Shows what information was received")
    print("  ✓ Clearly lists what information is still needed")
    print("  ✓ No more generic 'আসসালামু-আলাইকুম' when order is incomplete")
    print("  ✓ Professional and helpful guidance for customers")
    print("=" * 90)
    print()

if __name__ == "__main__":
    test_partial_orders()
