"""
Bot & Human Mode Manager
Admin interface to control conversation modes

BOT MODE: AI automatically responds
HUMAN MODE: AI stops, human agent responds
"""
import os
import sys
from typing import Dict, List
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from human_handoff_manager import HumanHandoffManager, HandoffReason, ConversationMode
from bdstall_chatbot_system import BDStallChatbotSystem


class ModeManager:
    """Manage Bot and Human modes for conversations"""
    
    def __init__(self):
        """Initialize with chatbot system"""
        try:
            self.chatbot = BDStallChatbotSystem()
            self.handoff_manager = self.chatbot.handoff_manager
            print(" Mode Manager initialized")
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize full chatbot system")
            print(f" ✅  Using standalone handoff manager")
            self.chatbot = None
            self.handoff_manager = HumanHandoffManager()
    
    def show_status(self):
        """Show current status of all conversations"""
        print("\n" + "=" * 70)
        print("  📊 CONVERSATION MODE STATUS")
        print("=" * 70)
        
        if not self.handoff_manager.sessions:
            print("\n  No active conversations")
            return
        
        bot_mode = []
        human_mode = []
        pending = []
        
        for user_id, session in self.handoff_manager.sessions.items():
            if session.mode == ConversationMode.AI_MODE:
                bot_mode.append(session)
            elif session.mode == ConversationMode.HUMAN_MODE:
                human_mode.append(session)
            else:
                pending.append(session)
        
        # Show Bot Mode users
        print(f"\n🤖 BOT MODE ({len(bot_mode)} users)")
        print("-" * 70)
        if bot_mode:
            for session in bot_mode:
                print(f"  👤 User: {session.user_id}")
                print(f"     Last activity: {session.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     Failed attempts: {session.failed_attempts}")
        else:
            print("  (None)")
        
        # Show Pending Handoff
        print(f"\n⏳ PENDING HANDOFF ({len(pending)} users)")
        print("-" * 70)
        if pending:
            for session in pending:
                print(f"  👤 User: {session.user_id}")
                print(f"     Reason: {session.handoff_reason.value if session.handoff_reason else 'N/A'}")
                print(f"     Triggered: {session.handoff_triggered_at.strftime('%Y-%m-%d %H:%M:%S') if session.handoff_triggered_at else 'N/A'}")
                print(f"     Pending messages: {len(session.pending_messages)}")
        else:
            print("  (None)")
        
        # Show Human Mode users
        print(f"\n👤 HUMAN MODE ({len(human_mode)} users)")
        print("-" * 70)
        if human_mode:
            for session in human_mode:
                print(f"  👤 User: {session.user_id}")
                print(f"     Activated: {session.handoff_triggered_at.strftime('%Y-%m-%d %H:%M:%S') if session.handoff_triggered_at else 'N/A'}")
                print(f"     Last activity: {session.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("  (None)")
        
        print("\n" + "=" * 70)
    
    def switch_to_bot_mode(self, user_id: str):
        """Switch user to BOT MODE"""
        print(f"\n🔄 Switching user {user_id} to BOT MODE...")
        self.handoff_manager.return_to_ai(user_id)
        print(f"✅ User {user_id} is now in BOT MODE")
        print(f"   AI will automatically respond to their messages")
    
    def switch_to_human_mode(self, user_id: str, reason: str = "manual"):
        """Switch user to HUMAN MODE"""
        print(f"\n🔄 Switching user {user_id} to HUMAN MODE...")
        
        # Trigger handoff
        if reason == "manual":
            handoff_reason = HandoffReason.USER_REQUEST
        else:
            handoff_reason = HandoffReason.EXPLICIT_HANDOFF
        
        result = self.handoff_manager.trigger_handoff(
            user_id=user_id,
            message=f"Manual switch to human mode: {reason}",
            reason=handoff_reason
        )
        
        # Activate human mode
        self.handoff_manager.activate_human_mode(user_id)
        
        print(f"✅ User {user_id} is now in HUMAN MODE")
        print(f"   AI will NOT respond - human agent must reply")
    
    def view_pending_messages(self, user_id: str = None):
        """View pending messages for a user or all users"""
        if user_id:
            session = self.handoff_manager.get_or_create_session(user_id)
            print(f"\n📨 Pending Messages for {user_id}")
            print("-" * 70)
            
            if not session.pending_messages:
                print("  No pending messages")
            else:
                for i, msg in enumerate(session.pending_messages, 1):
                    print(f"\n  {i}. {msg['message']}")
                    print(f"     Time: {msg['timestamp']}")
                    print(f"     Reason: {msg['reason']}")
        else:
            # Show all pending
            pending = self.handoff_manager.get_pending_conversations()
            print(f"\n📨 All Pending Messages ({len(pending)} conversations)")
            print("=" * 70)
            
            for conv in pending:
                print(f"\n👤 User: {conv['user_id']}")
                print(f"   Reason: {conv['handoff_reason']}")
                print(f"   Messages:")
                for msg in conv['pending_messages']:
                    print(f"   - {msg['message']} ({msg['timestamp']})")
    
    def cleanup_inactive(self):
        """Clean up inactive sessions"""
        print("\n🧹 Cleaning up inactive sessions...")
        count = self.handoff_manager.cleanup_expired_sessions()
        print(f"✅ Cleaned up {count} expired sessions")
    
    def interactive_menu(self):
        """Interactive menu for managing modes"""
        while True:
            print("\n" + "=" * 70)
            print("  🎛️  BOT & HUMAN MODE MANAGER")
            print("=" * 70)
            print("\n  Commands:")
            print("  1. status          - View all conversation modes")
            print("  2. bot <user_id>   - Switch user to BOT MODE")
            print("  3. human <user_id> - Switch user to HUMAN MODE")
            print("  4. messages        - View all pending messages")
            print("  5. messages <id>   - View messages for specific user")
            print("  6. cleanup         - Remove inactive sessions")
            print("  7. help            - Show detailed help")
            print("  8. quit            - Exit manager")
            print("\n" + "=" * 70)
            
            command = input("\nEnter command: ").strip().lower()
            
            if not command:
                continue
            
            parts = command.split()
            cmd = parts[0]
            
            try:
                if cmd == "status" or cmd == "1":
                    self.show_status()
                
                elif cmd == "bot" or cmd == "2":
                    if len(parts) < 2:
                        print("❌ Usage: bot <user_id>")
                    else:
                        user_id = parts[1]
                        self.switch_to_bot_mode(user_id)
                
                elif cmd == "human" or cmd == "3":
                    if len(parts) < 2:
                        print("❌ Usage: human <user_id>")
                    else:
                        user_id = parts[1]
                        reason = " ".join(parts[2:]) if len(parts) > 2 else "manual"
                        self.switch_to_human_mode(user_id, reason)
                
                elif cmd == "messages" or cmd == "4":
                    if len(parts) > 1:
                        user_id = parts[1]
                        self.view_pending_messages(user_id)
                    else:
                        self.view_pending_messages()
                
                elif cmd == "5":
                    if len(parts) < 2:
                        print("❌ Usage: messages <user_id>")
                    else:
                        user_id = parts[1]
                        self.view_pending_messages(user_id)
                
                elif cmd == "cleanup" or cmd == "6":
                    self.cleanup_inactive()
                
                elif cmd == "help" or cmd == "7":
                    self.show_help()
                
                elif cmd == "quit" or cmd == "exit" or cmd == "8":
                    print("\n👋 Goodbye!")
                    break
                
                else:
                    print(f"❌ Unknown command: {cmd}")
                    print("   Type 'help' for available commands")
            
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def show_help(self):
        """Show detailed help"""
        print("\n" + "=" * 70)
        print("  📖 MODE MANAGER HELP")
        print("=" * 70)
        print("""
🤖 BOT MODE:
   - AI automatically responds to messages
   - Fast, 24/7 automated support
   - Uses Bengali database + product search
   - Use when: Normal customer queries

👤 HUMAN MODE:
   - AI stops responding completely
   - Human agent must reply manually
   - All messages are queued
   - Use when: Complex issues, complaints, special requests

⏳ PENDING HANDOFF:
   - Triggered automatically when AI doesn't understand
   - After 3 failed attempts or low confidence
   - Waiting for human agent to activate human mode

EXAMPLES:

  View status:
    > status

  Switch user to bot mode:
    > bot 1234567890

  Switch user to human mode:
    > human 1234567890

  View pending messages:
    > messages
    > messages 1234567890

  Clean up:
    > cleanup

WORKFLOW:

  1. User sends unclear message → Auto switches to PENDING
  2. Admin checks status → Sees user in PENDING
  3. Admin activates HUMAN MODE:
     > human 1234567890
  4. Human agent handles conversation via Facebook
  5. After resolved, switch back to BOT:
     > bot 1234567890

""")
        print("=" * 70)


def main():
    """Main function"""
    print("=" * 70)
    print("  🎛️  BOT & HUMAN MODE MANAGER")
    print("=" * 70)
    print("\n  Manage conversation modes for Facebook chatbot")
    print("  - BOT MODE: AI responds automatically")
    print("  - HUMAN MODE: Human agent responds")
    print("\n" + "=" * 70)
    
    try:
        manager = ModeManager()
        print("\n✅ Ready to manage conversation modes!")
        print("   Type 'help' for available commands")
        
        # Show initial status
        manager.show_status()
        
        # Start interactive menu
        manager.interactive_menu()
    
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
