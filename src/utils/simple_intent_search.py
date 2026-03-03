"""
Simple Intent Detection & Search Example
User Input: "bhalo laptop ase"
Intent: laptop
Action: Search API for laptops
"""
import re
from enhanced_product_search import EnhancedProductSearch


def extract_intent_keyword(user_input: str) -> str:
    """
    Extract the main product keyword (intent) from user input
    Examples:
        "bhalo laptop ase" -> "laptop"
        "laptop আছে কি" -> "laptop"
        "hp laptop price" -> "laptop"
    """
    # Convert to lowercase for easier matching
    text = user_input.lower()
    
    # Common product keywords to look for
    product_keywords = [
        'laptop', 'phone', 'mobile', 'computer', 'webcam', 
        'printer', 'headphone', 'keyboard', 'mouse', 'monitor',
        'ল্যাপটপ', 'ফোন', 'মোবাইল', 'কম্পিউটার'
    ]
    
    # Find which product keyword exists in the text
    for keyword in product_keywords:
        if keyword in text:
            # Return English version for API search
            if keyword == 'ল্যাপটপ':
                return 'laptop'
            elif keyword in ['ফোন', 'মোবাইল', 'mobile']:
                return 'phone'
            elif keyword == 'কম্পিউটার':
                return 'computer'
            else:
                return keyword
    
    # If no keyword found, return cleaned input
    # Remove common Bengali words like "আছে", "কি", "ভালো", etc.
    cleaned = re.sub(r'\b(bhalo|valo|ase|ache|আছে|কি|ভালো)\b', '', text, flags=re.IGNORECASE)
    return cleaned.strip() or user_input


def search_products(intent_keyword: str):
    """
    Search BDStall API using the extracted intent keyword
    """
    searcher = EnhancedProductSearch()
    result = searcher.enhanced_product_search(intent_keyword)
    return result


def main():
    # User input
    user_input = "bhalo laptop ase"
    
    print("=" * 60)
    print("INTENT DETECTION & SEARCH WORKFLOW")
    print("=" * 60)
    
    # Step 1: Detect Intent
    print(f"\n📝 User Input: {user_input}")
    
    intent = extract_intent_keyword(user_input)
    print(f"🎯 Detected Intent: {intent}")
    
    # Step 2: Search API
    print(f"\n🔍 Searching API for: {intent}")
    print("-" * 60)
    
    result = search_products(intent)
    
    # Step 3: Display Results
    print(f"\n✅ Found {result['products_found']} products")
    print("\nTop 3 Products:")
    print("-" * 60)
    
    for i, product in enumerate(result['top_products'], 1):
        print(f"\n{i}. {product['title']}")
        print(f"   Price: {product['price']} টাকা")
        print(f"   Link: {product['url']}")
    
    print("\n" + "=" * 60)
    print("CHATBOT RESPONSE:")
    print("=" * 60)
    print(result['response'])
    
    # Test with more examples
    print("\n\n" + "=" * 60)
    print("MORE EXAMPLES:")
    print("=" * 60)
    
    test_cases = [
        "laptop আছে কি",
        "hp laptop price",
        "web cam lagbe",
        "ভালো phone দেখান"
    ]
    
    for test in test_cases:
        intent = extract_intent_keyword(test)
        print(f"\n'{test}' → intent: '{intent}'")


if __name__ == "__main__":
    main()
