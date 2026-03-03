"""
Test the database search functionality
"""
from database_handler import DatabaseHandler

def test_database():
    """Test database search with sample messages"""
    print("=" * 80)
    print("DATABASE SEARCH TEST")
    print("=" * 80)
    
    # Initialize database
    db = DatabaseHandler("database.csv")
    
    print(f"\n✓ Loaded {len(db.database)} Q&A pairs\n")
    print("=" * 80)
    
    # Test messages
    test_messages = [
        "অর্ডার করবো কিভাবে ?",
        "মিরপুরে ডেলিভারি চার্জ কতো",
        "Customer Support Number ?",
        "গ্যারান্টি আছে",
        "Hi",
        "This is a random message that won't match"
    ]
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\n[Test {i}/{len(test_messages)}]")
        print(f"Question: {msg}")
        print("-" * 80)
        
        result = db.search_database(msg, threshold=0.7)
        
        if result:
            print(f"✓ MATCH FOUND!")
            print(f"Answer: {result}")
        else:
            print(f"✗ No match found (will use AI)")
        
        print("-" * 80)
    
    print("\n✓ Database test completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_database()
