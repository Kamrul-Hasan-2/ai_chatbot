#!/usr/bin/env python3
"""
Test script to debug Bengali question matching issues
"""
import sys
from bengali_database_handler import BengaliDatabaseHandler

def test_bengali_matching():
    """Test Bengali question matching with user's queries"""
    
    print("🔍 Testing Bengali Database Matching")
    print("=" * 50)
    
    try:
        # Initialize the handler
        handler = BengaliDatabaseHandler()
        
        if not handler.qa_pairs:
            print("❌ No Q&A pairs loaded!")
            return
            
        print(f"✅ Loaded {len(handler.qa_pairs)} Q&A pairs")
        print(f"📂 Categories: {list(handler.categories.keys())}")
        print()
        
        # Test user's specific queries
        test_queries = [
            "kibabe order korbo",
            "order ?", 
            "অর্ডার করবো কিভাবে ?",
            "koy din er modde delivery hoy",
            "কত দিনের মধ্যে ডেলিভারি হয়",
            "ডেলিভারির সময় কত"
        ]
        
        for query in test_queries:
            print(f"🧪 Testing: '{query}'")
            print("-" * 30)
            
            result = handler.search_database(query, threshold=0.4)
            
            print(f"✅ Success: {result['success']}")
            if result['success']:
                print(f"📝 Response: {result['response'][:100]}...")
                print(f"📊 Similarity: {result['similarity']:.2f}")
                print(f"📂 Category: {result['category']}")
                print(f"❓ Matched Q: {result['question_matched']}")
            else:
                print(f"❌ Response: {result['response']}")
                print(f"📂 Category: {result['category']}")
            print()
        
        # Show what ordering questions exist
        print("📋 Available Ordering Questions:")
        print("-" * 40)
        ordering_questions = [qa for qa in handler.qa_pairs if qa['category'] == 'ordering']
        for i, qa in enumerate(ordering_questions[:5], 1):
            print(f"{i}. Q: '{qa['question']}'")
            print(f"   A: '{qa['answer'][:80]}...'")
            print()
            
        # Show delivery questions
        print("🚚 Available Delivery Questions:")
        print("-" * 40)
        delivery_questions = [qa for qa in handler.qa_pairs if qa['category'] == 'delivery']
        for i, qa in enumerate(delivery_questions[:5], 1):
            print(f"{i}. Q: '{qa['question']}'")
            print(f"   A: '{qa['answer'][:80]}...'")
            print()
        
        # Test similarity calculation manually
        print("🔬 Manual Similarity Testing:")
        print("-" * 35)
        
        test_pairs = [
            ("kibabe order korbo", "অর্ডার করবো কিভাবে ?"),
            ("order ?", "অর্ডার করবো কিভাবে ?"),
            ("koy din delivery", "Koto din lagbe product ashte?"),
            ("delivery time", "ম্যাম সাধারণত ঢাকার ভিতরে ১-২ দিন এবং বাহিরে ৪-৫ দিন সময় লাগে")
        ]
        
        for test_q, db_q in test_pairs:
            similarity = handler.calculate_similarity_bengali(test_q, db_q)
            print(f"'{test_q}' vs '{db_q}'")
            print(f"Similarity: {similarity:.3f}")
            print()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bengali_matching()