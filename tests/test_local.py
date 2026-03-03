"""
Interactive Local Chatbot Tester
Test your chatbot with RAG in an interactive console
"""
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatbot import AdminChatbot
from knowledge_loader import initialize_rag_with_data

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def print_header():
    """Print welcome header"""
    print("\n" + "=" * 70)
    print("   AI CHATBOT LOCAL TESTER (with RAG)")
    print("=" * 70)
    print("\nCommands:")
    print("  - Type your message and press Enter")
    print("  - Type 'quit' or 'exit' to stop")
    print("  - Type 'clear' to clear conversation history")
    print("  - Type 'stats' to see RAG statistics")
    print("=" * 70 + "\n")


def main():
    """Run interactive chatbot test"""
    print_header()
    
    print("Initializing chatbot with RAG...")
    print("(First run may take a few minutes to download models)\n")
    
    try:
        # Initialize chatbot with RAG
        bot = AdminChatbot(
            enable_rag=True,
            rag_top_k=3
        )
        
        # Load knowledge base
        print("Loading knowledge base...")
        results = initialize_rag_with_data(bot, knowledge_dirs=["data/knowledge", "docs"])
        print(f"✓ Loaded {results.get('total', 0)} document chunks\n")
        
        print("✓ Chatbot ready!\n")
        print("=" * 70)
        
        user_id = "local_test_user"
        
        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = input("\nYou: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!\n")
                    break
                
                elif user_input.lower() == 'clear':
                    bot.clear_history(user_id)
                    print("✓ Conversation history cleared")
                    continue
                
                elif user_input.lower() == 'stats':
                    stats = bot.get_rag_stats()
                    print("\n📊 RAG Statistics:")
                    for key, value in stats.items():
                        print(f"   {key}: {value}")
                    continue
                
                # Get chatbot response
                print("\nBot: ", end="", flush=True)
                response = bot.get_response(user_id, user_input)
                print(response)
                print("-" * 70)
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"Error in chat loop: {e}", exc_info=True)
    
    except Exception as e:
        print(f"\n❌ Failed to initialize chatbot: {e}")
        logger.error(f"Initialization error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
