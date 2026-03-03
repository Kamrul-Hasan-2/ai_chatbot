"""
Quick test script to verify RAG functionality
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_imports():
    """Test if all required packages are installed"""
    print("Testing imports...")
    
    try:
        import sentence_transformers
        print("✓ sentence-transformers installed")
    except ImportError:
        print("✗ sentence-transformers NOT installed")
        print("  Install with: pip install sentence-transformers")
        return False
    
    try:
        import faiss
        print("✓ faiss installed")
    except ImportError:
        print("✗ faiss NOT installed")
        print("  Install with: pip install faiss-cpu")
        return False
    
    try:
        import numpy
        print("✓ numpy installed")
    except ImportError:
        print("✗ numpy NOT installed")
        print("  Install with: pip install numpy")
        return False
    
    return True


def test_rag_store():
    """Test RAG store functionality"""
    print("\nTesting RAG store...")
    
    try:
        from rag_store import RAGStore
        
        # Initialize RAG store
        rag = RAGStore()
        print("✓ RAG store initialized")
        
        # Add test documents
        test_docs = [
            "Python is a high-level programming language.",
            "Machine learning is a subset of artificial intelligence.",
            "RAG stands for Retrieval-Augmented Generation."
        ]
        
        count = rag.add_documents(test_docs)
        print(f"✓ Added {count} test documents")
        
        # Test search
        results = rag.search("What is Python?", top_k=1)
        if results:
            print(f"✓ Search working - Found: {results[0][0][:50]}...")
        else:
            print("✗ Search returned no results")
            return False
        
        # Clean up test data
        rag.clear_index()
        print("✓ Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"✗ RAG store test failed: {e}")
        return False


def test_knowledge_loader():
    """Test knowledge loader"""
    print("\nTesting knowledge loader...")
    
    try:
        from knowledge_loader import KnowledgeBaseLoader
        from rag_store import RAGStore
        
        rag = RAGStore()
        loader = KnowledgeBaseLoader(rag)
        print("✓ Knowledge loader initialized")
        
        # Clean up
        rag.clear_index()
        
        return True
        
    except Exception as e:
        print(f"✗ Knowledge loader test failed: {e}")
        return False


def test_chatbot_integration():
    """Test chatbot with RAG"""
    print("\nTesting chatbot integration...")
    
    try:
        from chatbot import AdminChatbot
        
        # Note: This will try to load the AI model which may take time
        # We'll just check if the import and initialization works
        print("✓ Chatbot can be imported with RAG support")
        print("  (Not running full initialization to save time)")
        
        return True
        
    except Exception as e:
        print(f"✗ Chatbot integration test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("RAG System Verification")
    print("=" * 60)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
        print("\n⚠ Please install missing dependencies:")
        print("  pip install sentence-transformers faiss-cpu numpy")
        print("\nOr install all requirements:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    
    # Test RAG store
    if not test_rag_store():
        all_passed = False
    
    # Test knowledge loader
    if not test_knowledge_loader():
        all_passed = False
    
    # Test chatbot integration
    if not test_chatbot_integration():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! RAG system is ready to use.")
        print("\nNext steps:")
        print("1. Add documents to data/knowledge/ directory")
        print("2. Run: python rag_example.py")
        print("3. Or integrate RAG into your app using chatbot.py")
    else:
        print("✗ Some tests failed. Please check the errors above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
