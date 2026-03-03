#!/usr/bin/env python3
"""
Test the enhanced product search system
"""
from enhanced_product_search import EnhancedProductSearch

def test_search():
    print("🧪 Testing Enhanced Product Search System")
    print("=" * 50)
    
    # Initialize the searcher
    searcher = EnhancedProductSearch()
    
    # Test with web cam search
    query = "web cam"
    print(f"\\n🔍 Searching for: {query}")
    
    result = searcher.enhanced_product_search(query)
    
    print(f"✅ Search completed!")
    print(f"📦 Products found: {result['products_found']}")
    print(f"📝 Response: {result['response']}")
    print(f"🔍 Search method: {result['search_method']}")
    
    if result.get('top_products'):
        print("\\n🛍️ Top Products:")
        for i, product in enumerate(result['top_products'][:3], 1):
            title = product.get('title', 'N/A')[:50]
            price = product.get('price', 'N/A')
            print(f"   {i}. {title} - {price}")

if __name__ == "__main__":
    test_search()