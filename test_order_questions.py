"""
Test Order-Related Question Handling
Verifies that the AI chatbot properly finds and answers order-related questions from the database
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.handlers.bengali_database_handler import BengaliDatabaseHandler

def test_order_questions():
    """Test various order-related question formats"""
    
    # Initialize database handler
    db_path = os.path.join("data", "database.csv")
    handler = BengaliDatabaseHandler(csv_file=db_path)
    
    # Test different order question variations
    test_questions = [
        "order kivabe dibo",           # Selected by user (line 155)
        "kibabe order korbo",           # Romanized variation 1
        "kivabe order korbo",           # Romanized variation 2
        "kemne order korbo",            # Romanized variation 3
        "অর্ডার করবো কিভাবে?",        # Bengali version 1
        "অর্ডার করবো কি ভাবে?",       # Bengali version 2
        "আমি কিভাবে অর্ডার করব?",     # Natural Bengali
        "order korar system ki?",       # Mixed language
    ]
    
    print("=" * 80)
    print("🔍 TESTING ORDER-RELATED QUESTION HANDLING")
    print("=" * 80)
    print()
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"Test #{i}: {question}")
        print('-' * 80)
        
        # Search database
        result = handler.search_database(question, threshold=0.5)
        
        if result['success']:
            print(f"✅ FOUND MATCH (Similarity: {result['similarity']:.2%})")
            print(f"\n📌 Matched Question: {result.get('question_matched', 'N/A')}")
            print(f"📝 Category: {result['category']}")
            print(f"\n💬 AI Response:")
            print(f"{result['response']}")
        else:
            print(f"❌ NO MATCH FOUND (using fallback)")
            print(f"\n📝 Category: {result['category']}")
            print(f"\n💬 Fallback Response:")
            print(f"{result['response']}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    
    # Summary statistics
    print(f"\n📊 STATISTICS:")
    print(f"Total Q&A pairs: {len(handler.qa_pairs)}")
    
    # Count ordering category
    ordering_category = handler.categories.get('ordering', [])
    print(f"Order-related Q&A pairs: {len(ordering_category)}")
    
    print("\n📋 Order-related questions in database:")
    for qa in ordering_category[:10]:  # Show first 10
        print(f"  - {qa['question'][:60]}...")

if __name__ == "__main__":
    test_order_questions()
