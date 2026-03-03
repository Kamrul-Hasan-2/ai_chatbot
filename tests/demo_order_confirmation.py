#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Demo: Order Confirmation for BDStall.com Ltd
Shows the exact use case requested by the user
"""

from groq_3step_search import Groq3StepSearch
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    """Demo the exact order confirmation use case"""
    
    print("\n" + "=" * 90)
    print(" " * 25 + "📦 BDStall.com Ltd - Order Confirmation Demo")
    print("=" * 90)
    
    # Initialize the search system
    searcher = Groq3StepSearch()
    
    # Simulate the exact scenario from the user
    print("\n📱 CUSTOMER CONVERSATION:")
    print("-" * 90)
    
    print("\n🤖 Bot:")
    print("   আপনি কি এ অর্ডার করতে চান? আপনার নাম, ঠিকানা এবং ফোন নাম্বার দিলে")
    print("   আমরা আপনার অর্ডার করতে সাহায্য করতে পারি। আমরা আপনার ডেলিভারির")
    print("   সময়ও চেক করে দেব।")
    
    print("\n👤 Customer:")
    customer_message = "Name: Kamel, Address: Uttara, Phone: 01933930303"
    print(f"   {customer_message}")
    
    print("\n" + "-" * 90)
    print("🔄 PROCESSING ORDER...")
    print("-" * 90)
    
    # Process the order
    result = searcher.search(customer_message)
    
    if result.get('workflow') == 'order_confirmation':
        print("\n✅ ORDER SUCCESSFULLY DETECTED!")
        
        order_info = result.get('order_info', {})
        print(f"\n📋 Order Information Captured:")
        print(f"   • Customer Name: {order_info.get('name')}")
        print(f"   • Delivery Address: {order_info.get('address')}")
        print(f"   • Contact Number: {order_info.get('phone')}")
        
        print("\n" + "=" * 90)
        print("🤖 BOT RESPONSE TO CUSTOMER:")
        print("=" * 90)
        print()
        
        # Display the confirmation message
        response = result.get('response', '')
        for line in response.split('\n'):
            print(f"   {line}")
        
        print()
        print("=" * 90)
        print("✅ ORDER CONFIRMATION SENT SUCCESSFULLY!")
        print("=" * 90)
        
    else:
        print("\n❌ Order not detected")
    
    print("\n💡 HOW IT WORKS:")
    print("   1. Customer provides: Name, Address, Phone")
    print("   2. System automatically detects order information")
    print("   3. Professional Bengali confirmation message generated")
    print("   4. Customer receives clear order details and timeline")
    print("   5. BDStall.com Ltd brand maintained throughout")
    
    print("\n🎯 INTEGRATION:")
    print("   Just call: searcher.search(user_message)")
    print("   The system handles:")
    print("      • Order detection")
    print("      • Product search")
    print("      • Appropriate response generation")
    
    print("\n" + "=" * 90)
    print()

if __name__ == "__main__":
    main()
