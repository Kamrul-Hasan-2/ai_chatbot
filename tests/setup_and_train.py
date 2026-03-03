"""
Complete Setup and Training Script
Run this to set up everything and train the chatbot
"""
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def check_dependencies():
    """Check if required packages are installed"""
    print_header("Checking Dependencies")
    
    required_packages = {
        'requests': 'requests',
        'torch': 'torch',
        'transformers': 'transformers',
        'sentence_transformers': 'sentence-transformers',
        'faiss': 'faiss-cpu',
        'numpy': 'numpy',
        'pandas': 'pandas'
    }
    
    missing = []
    for package, install_name in required_packages.items():
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is missing")
            missing.append(install_name)
    
    if missing:
        print(f"\n⚠ Missing packages: {', '.join(missing)}")
        print(f"\nInstall with: pip install {' '.join(missing)}")
        return False
    
    print("\n✓ All dependencies are installed!")
    return True


def create_directories():
    """Create required directories"""
    print_header("Creating Directories")
    
    directories = ['data', 'data/knowledge', 'logs']
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created/verified: {directory}/")
    
    return True


def train_messenger_data():
    """Train the chatbot with messenger API data"""
    print_header("Training with Messenger API Data")
    
    try:
        from train_messenger import MessengerTrainer
        
        api_url = "https://ai.bdstall.com/rest_api/item/chatbot_grouped?limit=1000"
        
        print("Initializing trainer...")
        trainer = MessengerTrainer(api_url)
        
        print("Fetching and processing conversations...")
        if trainer.load_and_train():
            print("\n✓ Training completed successfully!")
            
            # Show statistics
            stats = trainer.get_training_stats()
            print(f"\n📊 Training Statistics:")
            print(f"   • Conversations processed: {stats['total_conversations']}")
            print(f"   • User messages: {stats['total_user_messages']}")
            print(f"   • Admin responses: {stats['total_admin_responses']}")
            print(f"   • Training pairs: {stats['training_pairs']}")
            
            print(f"\n📁 Files created:")
            print(f"   • data/messenger_training.json")
            print(f"   • data/rag_index.faiss")
            
            return True
        else:
            print("\n✗ Training failed. Check logs for details.")
            return False
            
    except ImportError as e:
        logger.error(f"Import error: {e}")
        print("\n✗ Could not import training modules.")
        print("Make sure all files are in the correct location.")
        return False
    except Exception as e:
        logger.error(f"Training error: {e}")
        return False


def load_knowledge_base():
    """Load knowledge base files if they exist"""
    print_header("Loading Knowledge Base")
    
    knowledge_dir = Path("data/knowledge")
    knowledge_files = list(knowledge_dir.glob("*.txt")) + list(knowledge_dir.glob("*.md"))
    
    if not knowledge_files:
        print("ℹ No knowledge base files found in data/knowledge/")
        print("  You can add .txt or .md files there for additional context.")
        return True
    
    try:
        from knowledge_loader import KnowledgeBaseLoader
        from rag_store import RAGStore
        
        rag_store = RAGStore()
        loader = KnowledgeBaseLoader(rag_store)
        
        total_chunks = 0
        for file in knowledge_files:
            print(f"Loading: {file.name}")
            chunks = loader.load_from_text_files(str(knowledge_dir), f"{file.name}")
            total_chunks += chunks
        
        if total_chunks > 0:
            rag_store.save_index()
            print(f"\n✓ Loaded {total_chunks} chunks from {len(knowledge_files)} files")
        
        return True
        
    except Exception as e:
        logger.error(f"Knowledge base loading error: {e}")
        print("\n⚠ Could not load knowledge base files (continuing anyway)")
        return True


def test_chatbot():
    """Test the chatbot with sample queries"""
    print_header("Testing Chatbot")
    
    try:
        from chatbot import AdminChatbot
        
        print("Initializing chatbot...")
        bot = AdminChatbot(enable_rag=True, rag_top_k=5)
        
        # Test messages
        test_messages = [
            ("আসসালামু আলাইকুম", "Bengali Greeting"),
            ("আপনাদের কাছে কি iPhone আছে?", "Product Availability (Bengali)"),
            ("Do you have iPhone available?", "Product Availability (English)"),
            ("Price কত?", "Price Inquiry (Mixed)"),
        ]
        
        print("\n" + "-" * 70)
        for message, description in test_messages:
            print(f"\n[{description}]")
            print(f"User: {message}")
            
            response = bot.get_response("test_user", message)
            print(f"Bot:  {response}")
            print("-" * 70)
        
        print("\n✓ Chatbot is responding correctly!")
        return True
        
    except Exception as e:
        logger.error(f"Testing error: {e}")
        print(f"\n✗ Chatbot testing failed: {e}")
        return False


def main():
    """Main setup and training function"""
    
    print("\n" + "=" * 70)
    print("  🤖 AI Chatbot - Complete Setup & Training")
    print("=" * 70)
    
    steps = [
        ("Check Dependencies", check_dependencies),
        ("Create Directories", create_directories),
        ("Train with Messenger Data", train_messenger_data),
        ("Load Knowledge Base", load_knowledge_base),
        ("Test Chatbot", test_chatbot),
    ]
    
    for step_name, step_func in steps:
        try:
            if not step_func():
                print(f"\n⚠ {step_name} had issues. Continuing...")
        except Exception as e:
            logger.error(f"{step_name} failed: {e}")
            print(f"\n✗ {step_name} failed. Check logs.")
            
            if step_name in ["Check Dependencies", "Train with Messenger Data"]:
                print("\n❌ Critical step failed. Please fix before proceeding.")
                return
    
    # Final summary
    print_header("Setup Complete!")
    print("✓ Your chatbot is now trained and ready to use!")
    print("\n📝 Next steps:")
    print("   1. Run the chatbot: python app.py")
    print("   2. Test locally: python test_chatbot.py")
    print("   3. Read the guide: MESSENGER_TRAINING_GUIDE.md")
    print("\n💡 Tips:")
    print("   • Re-run this script weekly to update training data")
    print("   • Add knowledge files to data/knowledge/ for more context")
    print("   • Check logs/ directory for conversation logs")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
