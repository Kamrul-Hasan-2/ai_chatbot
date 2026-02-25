#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo: User's Exact Scenario - Partial Order Handling
Shows how the system now asks for missing phone number
"""

from groq_3step_search import Groq3StepSearch
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    """Demo the exact user scenario"""
    
    print("\n" + "=" * 90)
    print(" " * 20 + "📱 IMPROVED ORDER HANDLING - BDStall.com Ltd")
    print("=" * 90)
    print("\n🎯 SCENARIO: Customer provides Name and Address but forgets Phone")
    print("=" * 90)
    
    searcher = Groq3StepSearch()
    
    # The conversation
    print("\n💬 CONVERSATION:\n")
    
    print("🤖 Bot:")
    print("   অর্ডারের জন্য আপনার নাম, ঠিকানা এবং ফোন নাম্বার দিবেন।")
    print("   ডেলিভারির সময় চেক করে নিতে পারবেন।")
    print("   হোম ডেলিভারি পাবেন, ঢাকা সিটির ভিতরে ফুল ক্যাশ অন ডেলিভারি এবং")
    print("   ঢাকার বাহিরে শুধুমাত্র ডেলিভারি চার্জটা অগ্রিম দিয়ে প্রোডাক্ট নিতে পারবেন,")
    print("   ধন্যবাদ।")
    
    print("\n👤 Customer:")
    customer_message = "আমি অর্ডার করতে চাই। Name: Rahim, Address: Dhanmondi"
    print(f"   {customer_message}")
    
    print("\n" + "─" * 90)
    print("🔄 PROCESSING...")
    print("─" * 90)
    
    # Process the message
    result = searcher.search(customer_message)
    
    workflow = result.get('workflow')
    
    if workflow == 'partial_order':
        partial = result.get('partial_order', {})
        present = partial.get('present', {})
        missing = partial.get('missing', [])
        
        print("\n✅ SYSTEM DETECTED: Partial Order Information")
        print(f"\n📋 Received:")
        for key, value in present.items():
            print(f"   ✅ {key.title()}: {value}")
        
        print(f"\n⚠️  Missing:")
        for field in missing:
            print(f"   ❌ {field.title()}")
        
        print("\n" + "=" * 90)
        print("🤖 BOT'S SMART RESPONSE (Instead of generic greeting):")
        print("=" * 90)
        print()
        
        response = result.get('response', '')
        for line in response.split('\n'):
            print(f"   {line}")
        
        print()
        print("=" * 90)
        
    print("\n✨ WHAT CHANGED:")
    print("   ❌ BEFORE: 'আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছিলেন?'")
    print("              (Generic greeting - not helpful!)")
    print()
    print("   ✅ NOW:    Shows what was received ✓")
    print("              Asks specifically for missing phone number ✓")
    print("              Professional and helpful ✓")
    
    print("\n🎯 BENEFITS:")
    print("   • Better customer experience")
    print("   • Clear communication")
    print("   • Faster order completion")
    print("   • Less confusion")
    print("   • Professional BDStall.com Ltd service")
    
    print("\n" + "=" * 90)
    print("✅ ORDER HANDLING IMPROVED!")
    print("=" * 90)
    print()

if __name__ == "__main__":
    main()
