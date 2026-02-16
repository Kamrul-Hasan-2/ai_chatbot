"""
Interactive Chatbot Demo
Test the trained chatbot with real-time conversation
"""
import logging
from chatbot import AdminChatbot
from colorama import init, Fore, Style
import sys

# Initialize colorama for colored terminal output
try:
    init(autoreset=True)
    COLORS_AVAILABLE = True
except:
    COLORS_AVAILABLE = False

logging.basicConfig(level=logging.WARNING)


def print_colored(text, color="white", end="\n"):
    """Print colored text"""
    if not COLORS_AVAILABLE:
        print(text, end=end)
        return
    
    colors = {
        "blue": Fore.BLUE,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "red": Fore.RED,
        "cyan": Fore.CYAN,
        "magenta": Fore.MAGENTA,
        "white": Fore.WHITE,
    }
    
    print(f"{colors.get(color, Fore.WHITE)}{text}{Style.RESET_ALL}", end=end)


def print_banner():
    """Print welcome banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         🤖 AI Chatbot - Interactive Demo                    ║
║         Trained with Real Messenger Conversations           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print_colored(banner, "cyan")
    print_colored("Type your message and press Enter to chat.", "yellow")
    print_colored("Commands: 'quit' or 'exit' to stop, 'clear' to reset", "yellow")
    print_colored("          'stats' to see RAG statistics\n", "yellow")


def print_stats(bot):
    """Print chatbot statistics"""
    print_colored("\n" + "=" * 60, "cyan")
    print_colored("📊 Chatbot Statistics", "cyan")
    print_colored("=" * 60, "cyan")
    
    stats = bot.get_rag_stats()
    
    if stats.get('enabled'):
        print_colored(f"RAG Status: ✓ Enabled", "green")
        print_colored(f"Total Knowledge Chunks: {stats.get('total_chunks', 0)}", "white")
        print_colored(f"RAG Top-K: {bot.rag_top_k}", "white")
        print_colored(f"Response Style: {bot.response_style}", "white")
    else:
        print_colored("RAG Status: ✗ Disabled", "red")
    
    print_colored("=" * 60 + "\n", "cyan")


def main():
    """Main interactive chat loop"""
    
    print_banner()
    
    # Initialize chatbot
    print_colored("Initializing chatbot...", "yellow")
    try:
        bot = AdminChatbot(
            enable_rag=True,
            rag_top_k=5,
            response_style="friendly"
        )
        print_colored("✓ Chatbot ready!\n", "green")
    except Exception as e:
        print_colored(f"✗ Error initializing chatbot: {e}", "red")
        print_colored("\nMake sure you've run: python setup_and_train.py", "yellow")
        return
    
    user_id = "demo_user"
    conversation_count = 0
    
    print_colored("="* 60 + "\n", "cyan")
    
    while True:
        try:
            # Get user input
            print_colored("You: ", "blue", end="")
            user_input = input().strip()
            
            # Handle commands
            if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                print_colored("\n👋 Thank you for chatting! Goodbye!", "cyan")
                print_colored(f"Total messages exchanged: {conversation_count}", "yellow")
                break
            
            elif user_input.lower() == 'clear':
                bot.clear_history(user_id)
                print_colored("✓ Conversation history cleared!\n", "green")
                conversation_count = 0
                continue
            
            elif user_input.lower() == 'stats':
                print_stats(bot)
                continue
            
            elif not user_input:
                continue
            
            # Get bot response
            print_colored("Bot: ", "green", end="")
            response = bot.get_response(user_id, user_input)
            print_colored(response, "white")
            print()
            
            conversation_count += 1
            
        except KeyboardInterrupt:
            print_colored("\n\n👋 Chat interrupted. Goodbye!", "cyan")
            break
        except Exception as e:
            print_colored(f"\n✗ Error: {e}", "red")
            print_colored("Continuing...\n", "yellow")


def demo_conversations():
    """Run demo conversations automatically"""
    print_banner()
    print_colored("Running automated demo conversations...\n", "yellow")
    
    # Initialize chatbot
    try:
        bot = AdminChatbot(enable_rag=True, rag_top_k=5, response_style="friendly")
    except Exception as e:
        print_colored(f"✗ Error: {e}", "red")
        return
    
    # Demo conversations
    demos = [
        # Bengali conversations
        ("আসসালামু আলাইকুম", "Greeting in Bengali"),
        ("আপনাদের কাছে iPhone কি আছে?", "Product availability query"),
        ("দাম কত?", "Price inquiry"),
        ("ডেলিভারি কত দিন লাগবে?", "Delivery time question"),
        
        # English conversations
        ("Hi, do you have iPhone available?", "English product inquiry"),
        ("What is the price?", "English price question"),
        ("Can you deliver to Dhaka?", "Delivery location question"),
        
        # Mixed language
        ("iPhone 13 এর price কত?", "Mixed language query"),
    ]
    
    user_id = "demo_user"
    
    for message, description in demos:
        print_colored("=" * 60, "cyan")
        print_colored(f"[{description}]", "yellow")
        print_colored(f"You: {message}", "blue")
        
        response = bot.get_response(user_id, message)
        print_colored(f"Bot: {response}", "green")
        print()
        
        import time
        time.sleep(1)  # Pause between messages
    
    print_colored("=" * 60, "cyan")
    print_colored("\n✓ Demo completed!", "green")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        # Run automated demo
        demo_conversations()
    else:
        # Run interactive chat
        main()
