"""
Example script demonstrating RAG usage
"""
import logging
from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data, KnowledgeBaseLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Example usage of chatbot with RAG"""
    
    print("=" * 60)
    print("AI Chatbot with RAG (Retrieval-Augmented Generation)")
    print("=" * 60)
    
    # Initialize chatbot with RAG enabled
    print("\n1. Initializing chatbot with RAG enabled...")
    chatbot = AdminChatbot(
        data_file="data/admin_data.json",
        csv_database="database.csv",
        enable_rag=True,
        rag_top_k=3  # Retrieve top 3 relevant documents
    )
    
    # Load knowledge base into RAG
    print("\n2. Loading knowledge base into RAG store...")
    print("   This will load documents from:")
    print("   - data/admin_data.json")
    print("   - Any text files in data/knowledge/ (if exists)")
    print("   - Any documents in docs/ (if exists)")
    
    results = initialize_rag_with_data(chatbot, knowledge_dirs=["data/knowledge", "docs"])
    print(f"\n   Loaded {results['total']} document chunks into RAG store")
    
    # Show RAG statistics
    print("\n3. RAG Store Statistics:")
    stats = chatbot.get_rag_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Optional: Add more documents programmatically
    print("\n4. You can add more documents programmatically:")
    print("   Example:")
    print('   chatbot.add_documents_to_rag(')
    print('       documents=["Your document text here"],')
    print('       metadata=[{"source": "manual_input"}]')
    print('   )')
    
    # Example: Add some sample documents
    sample_docs = [
        "Our company offers 24/7 customer support through email and phone. Response time is typically within 2 hours.",
        "We have a 30-day money-back guarantee on all products. No questions asked.",
        "Shipping is free for orders over $50. Standard shipping takes 5-7 business days."
    ]
    
    sample_metadata = [
        {"source": "support_policy", "type": "policy"},
        {"source": "refund_policy", "type": "policy"},
        {"source": "shipping_policy", "type": "policy"}
    ]
    
    added = chatbot.add_documents_to_rag(sample_docs, sample_metadata)
    print(f"\n   Added {added} sample policy chunks to demonstrate")
    
    # Test chatbot with some queries
    print("\n" + "=" * 60)
    print("5. Testing Chatbot Responses (RAG-Enhanced)")
    print("=" * 60)
    
    test_queries = [
        "What is your refund policy?",
        "How long does shipping take?",
        "What are your support hours?",
        "Tell me about your products"
    ]
    
    user_id = "test_user_123"
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"User: {query}")
        response = chatbot.get_response(user_id, query)
        print(f"Bot: {response}")
    
    print("\n" + "=" * 60)
    print("RAG Demo Complete!")
    print("=" * 60)
    
    # Show how to load documents from files
    print("\n6. Loading documents from files:")
    print("\n   To load documents from various sources:")
    print("   ")
    print("   loader = KnowledgeBaseLoader(chatbot.rag_store)")
    print("   ")
    print("   # From text files:")
    print("   loader.load_from_text_files('data/knowledge')")
    print("   ")
    print("   # From JSON:")
    print("   loader.load_from_json('data/my_docs.json')")
    print("   ")
    print("   # From CSV:")
    print("   loader.load_from_csv('data/products.csv', text_column='description')")
    print("   ")
    print("   # From Markdown:")
    print("   loader.load_from_markdown('docs/README.md')")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
