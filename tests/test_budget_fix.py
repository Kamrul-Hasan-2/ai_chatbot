"""
Test script to verify the budget inquiry fix
"""
from bengali_database_handler import BengaliDatabaseHandler
from intent_entity_detector import IntentEntityDetector

def test_budget_inquiry():
    """Test that budget inquiries are properly categorized"""
    
    # Initialize handlers
    db_handler = BengaliDatabaseHandler()
    intent_detector = IntentEntityDetector()
    
    print("=" * 60)
    print("Testing Budget Inquiry Fix")
    print("=" * 60)
    
    # Test cases
    test_queries = [
        "kom budget er modde dekhan",  # Main user query - SHOULD BE PRICING
        "budget friendly products",    # SHOULD BE PRICING
        "koto takar modde product",    # SHOULD BE PRICING
        "affordable price",             # SHOULD BE PRICING  
        "কম বাজেটের মধ্যে দেখান", # SHOULD BE PRICING
        "delivery time koto",           # SHOULD BE DELIVERY (has both delivery + koto din context)
        "কত দিনে ডেলিভারি হবে",    # SHOULD BE DELIVERY
        "কত টাকা",                     # SHOULD BE PRICING
    ]
    
    print("\n1. Testing Category Detection:")
    print("-" * 60)
    for query in test_queries:
        category = db_handler.categorize_question(query, "")
        expected = "PRICING" if "budget" in query.lower() or "takar" in query.lower() or "affordable" in query.lower() else ("DELIVERY" if "delivery" in query.lower() or "দিন" in query else "?")
        status = "✓" if (category.upper() in expected.upper() or expected == "?") else "✗"
        print(f"{status} Query: '{query}'")
        print(f"  → Category: {category}")
        print()
    
    print("\n2. Testing Database Answer Lookup:")
    print("-" * 60)
    budget_related_queries = [
        "kom budget er modde dekhan",
        "koto takar modde product",
        "affordable price",
    ]
    
    for query in budget_related_queries:
        result = db_handler.search_database(query, threshold=0.5)
        print(f"Query: '{query}'")
        if result and result.get('response'):
            response_text = result['response']
            print(f"  → Found Answer: {response_text[:100]}...")
            print(f"     (Similarity: {result.get('similarity', 0):.2f})")
            print(f"     (Success: {result.get('success', False)})")
        else:
            print(f"  → No answer found")
        print()

if __name__ == "__main__":
    test_budget_inquiry()

