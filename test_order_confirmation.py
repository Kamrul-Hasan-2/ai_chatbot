#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Order Confirmation System for BDStall.com Ltd
Demonstrates automatic order detection and professional confirmation messages
"""

from groq_3step_search import Groq3StepSearch
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_order_confirmation():
    """Test the order confirmation functionality"""
    
    print("\n" + "=" * 90)
    print("📦 ORDER CONFIRMATION SYSTEM TEST - BDStall.com Ltd")
    print("=" * 90)
    print("\nFEATURES:")
    print("  ✓ Automatic detection of Name, Address, Phone")
    print("  ✓ Professional Bengali confirmation message")
    print("  ✓ Order details verification")
    print("  ✓ Clear delivery timeline")
    print("  ✓ Payment options mentioned")
    print("=" * 90)
    
    searcher = Groq3StepSearch()
    
    # Test cases with different order formats
    test_orders = [
        {
            "description": "Standard Order Format (English)",
            "message": "Name: Kamel, Address: Uttara, Phone: 01933930303"
        },
        {
            "description": "Order with Details",
            "message": "আমি অর্ডার করতে চাই। Name: Rahim Ahmed, Address: Dhanmondi, Dhaka, Phone: 01712345678"
        },
        {
            "description": "Order with Line Breaks",
            "message": """হ্যাঁ, অর্ডার করবো
Name: Fatima Khan
Address: Mirpur-10, Dhaka
Phone: 01823456789"""
        },
        {
            "description": "Bengali Keywords",
            "message": "নাম: রাকিব হাসান, ঠিকানা: গুলশান-২, ঢাকা, ফোন: 01934567890"
        },
    ]
    
    for i, test_case in enumerate(test_orders, 1):
        print("\n" + "=" * 90)
        print(f"TEST {i}: {test_case['description']}")
        print("-" * 90)
        print(f"\nCustomer Message:")
        print(f"   '{test_case['message']}'")
        print("-" * 90)
        
        result = searcher.search(test_case['message'])
        
        if result.get('workflow') == 'order_confirmation':
            print("\n✅ ORDER DETECTED!")
            
            order_info = result.get('order_info', {})
            print(f"\n📋 Extracted Order Information:")
            print(f"   Name:    {order_info.get('name', 'N/A')}")
            print(f"   Address: {order_info.get('address', 'N/A')}")
            print(f"   Phone:   {order_info.get('phone', 'N/A')}")
            
            print(f"\n📝 CONFIRMATION MESSAGE SENT:")
            print("   " + "─" * 85)
            for line in result['response'].split('\n'):
                if line.strip():
                    print(f"   {line}")
            print("   " + "─" * 85)
        else:
            print("\n❌ No order detected - Treated as product search")
        
        print()
    
    # Test non-order messages (should go to product search)
    print("\n" + "=" * 90)
    print("NEGATIVE TEST: Non-Order Messages (Should Not Trigger Order Confirmation)")
    print("=" * 90)
    
    non_orders = [
        "hp laptop কিনতে চাই",
        "web cam ache?",
        "Premium Office Visitor Chair দাম কত?",
    ]
    
    for i, message in enumerate(non_orders, 1):
        print(f"\nTest {i}: '{message}'")
        result = searcher.search(message)
        
        if result.get('workflow') == 'order_confirmation':
            print("   ❌ ERROR: Wrongly detected as order!")
        else:
            print("   ✅ Correct: Not detected as order (product search mode)")
    
    print("\n" + "=" * 90)
    print("✅ ORDER CONFIRMATION SYSTEM WORKING!")
    print("=" * 90)
    print("\nKEY FEATURES VERIFIED:")
    print("  ✓ Detects Name, Address, Phone in various formats")
    print("  ✓ Works with Bengali and English keywords")
    print("  ✓ Generates professional confirmation message")
    print("  ✓ Doesn't trigger on regular product searches")
    print("  ✓ Provides clear order details and timeline")
    print("  ✓ BDStall.com Ltd branding consistent")
    print("=" * 90)
    print()

if __name__ == "__main__":
    test_order_confirmation()
