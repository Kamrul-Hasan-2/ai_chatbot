"""
Conversation Context Manager
Handles retrieving and managing the last 5 messages for context-aware responses
"""
import os
import sys
import logging
import requests
import json
from typing import List, Dict, Optional, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationContextManager:
    """Manages conversation history and context for the chatbot"""
    
    def __init__(self):
        """Initialize the conversation context manager"""
        self.api_url = os.getenv(
            'CHATBOT_HISTORY_API_URL',
            'https://www.bdstall.com/api/item/chatbot_history/'
        )
        self.api_key = os.getenv('SAVE_MESSAGE_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.default_limit = 5
        self.timeout = 8
        
        logger.info(f"✅ ConversationContextManager initialized")
        logger.info(f"   API URL: {self.api_url}")
        logger.info(f"   Default Limit: {self.default_limit}")
    
    def get_last_n_messages(self, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """
        Fetch the last N messages for a user from the history API
        
        Args:
            user_id: User identifier
            limit: Number of messages to retrieve (default: 5, max: 20)
            
        Returns:
            Dictionary with:
            - success: bool
            - messages: list of messages with sender_type, message, created_at
            - count: number of messages retrieved
            - user_info: user details from API
            - error: error message if failed
            - context_text: formatted text context
        """
        try:
            safe_limit = max(1, min(int(limit or 5), 20))
            
            # Build API request - matches BDStall API format
            request_url = (
                f"{self.api_url}"
                f"?user_id={user_id}&limit={safe_limit}&key={self.api_key}"
            )
            
            logger.info(f"📋 Fetching last {safe_limit} messages for user_id={user_id}")
            
            # Call API
            response = requests.get(request_url, timeout=self.timeout)
            
            if not (200 <= response.status_code < 300):
                logger.warning(f"❌ API returned status {response.status_code}")
                return {
                    "success": False,
                    "messages": [],
                    "count": 0,
                    "user_info": None,
                    "error": f"API returned status {response.status_code}",
                    "context_text": ""
                }
            
            data = response.json() if response.text else {}
            
            # Check API success flag
            if not data.get('success'):
                logger.warning(f"❌ API returned success=false")
                return {
                    "success": False,
                    "messages": [],
                    "count": 0,
                    "user_info": data.get('user_info'),
                    "error": "API returned success=false",
                    "context_text": ""
                }
            
            # Extract messages from API response
            messages = data.get('messages', [])
            user_info = data.get('user_info')
            
            if not isinstance(messages, list):
                messages = []
            
            # Format context
            context_lines = self._format_messages_as_context(messages)
            context_text = '\n'.join(context_lines)
            
            logger.info(f"✅ Retrieved {len(messages)} messages for user_id={user_id}")
            if user_info:
                logger.info(f"   User: {user_info.get('user_name', 'Unknown')}")
            
            return {
                "success": True,
                "messages": messages,
                "count": len(messages),
                "user_info": user_info,
                "error": None,
                "context_text": context_text,
                "formatted_lines": context_lines
            }
            
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ API timeout for user_id={user_id}")
            return {
                "success": False,
                "messages": [],
                "count": 0,
                "user_info": None,
                "error": "API timeout",
                "context_text": ""
            }
        except Exception as e:
            logger.error(f"❌ Error fetching messages for user_id={user_id}: {e}")
            return {
                "success": False,
                "messages": [],
                "count": 0,
                "user_info": None,
                "error": str(e),
                "context_text": ""
            }
    
    def _format_messages_as_context(self, messages: List[Dict]) -> List[str]:
        """
        Format raw messages into readable conversation context
        Handles BDStall API response format
        
        Args:
            messages: List of message dictionaries from API
            
        Returns:
            List of formatted message lines
        """
        lines = []
        
        for msg in messages:
            try:
                # Determine sender type
                sender_type = msg.get('sender_type')
                # API uses 'message' field, not 'text'
                text = msg.get('message', '')
                
                if not text:
                    continue
                
                # Truncate very long messages (product lists, etc)
                if len(text) > 200:
                    text = text[:200] + "..."
                
                # Format based on sender type
                # 1 = Admin/Agent, 2 = Bot, 3 = User/Visitor
                sender_type_str = str(sender_type)
                
                if sender_type_str == '1':
                    lines.append(f"Agent: {text}")
                elif sender_type_str == '2':
                    lines.append(f"Bot: {text}")
                elif sender_type_str == '3':
                    lines.append(f"User: {text}")
                else:
                    # Fallback if sender type is unknown
                    lines.append(f"Unknown: {text}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error formatting message: {e}")
                continue
        
        return lines[-10:]  # Keep last 10 formatted lines
    
    def build_conversation_prompt(self, user_id: str, current_message: str, limit: int = 5) -> str:
        """
        Build a conversation context string for use in AI prompts
        
        Args:
            user_id: User identifier
            current_message: The current user message
            limit: Number of historical messages to include
            
        Returns:
            Formatted prompt string with conversation context
        """
        context_data = self.get_last_n_messages(user_id, limit)
        
        if not context_data['success']:
            logger.warning(f"⚠️ Could not build context for user_id={user_id}")
            return f"Current Message: {current_message}"
        
        context_text = context_data['context_text']
        
        prompt = f"""Recent conversation context (oldest to newest):
{context_text or 'No previous messages'}

Current User Message: {current_message}"""
        
        return prompt
    
    def get_last_user_message(self, user_id: str) -> Optional[str]:
        """
        Get the last user message for context
        
        Args:
            user_id: User identifier
            
        Returns:
            Last user message text or None
        """
        context_data = self.get_last_n_messages(user_id, limit=5)
        
        if not context_data['success']:
            return None
        
        messages = context_data['messages']
        
        # Find last message from user (sender_type = 3)
        for msg in reversed(messages):
            sender_type = str(msg.get('sender_type'))
            if sender_type == '3':
                return msg.get('message')
        
        return None
    
    def get_conversation_summary(self, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """
        Get a summary of the conversation
        
        Args:
            user_id: User identifier
            limit: Number of messages to analyze
            
        Returns:
            Dictionary with conversation summary data
        """
        context_data = self.get_last_n_messages(user_id, limit)
        
        if not context_data['success']:
            return {
                "success": False,
                "user_id": user_id,
                "total_messages": 0,
                "user_messages": 0,
                "bot_messages": 0,
                "agent_messages": 0,
                "user_name": None,
                "summary": "No conversation history"
            }
        
        messages = context_data['messages']
        user_info = context_data.get('user_info')
        
        # Count messages by sender type
        user_count = sum(1 for m in messages if str(m.get('sender_type')) == '3')
        bot_count = sum(1 for m in messages if str(m.get('sender_type')) == '2')
        agent_count = sum(1 for m in messages if str(m.get('sender_type')) == '1')
        
        user_name = None
        if user_info:
            user_name = user_info.get('user_name')
        
        return {
            "success": True,
            "user_id": user_id,
            "user_name": user_name,
            "total_messages": len(messages),
            "user_messages": user_count,
            "bot_messages": bot_count,
            "agent_messages": agent_count,
            "context_text": context_data['context_text'],
            "summary": f"Last {len(messages)} messages: {user_count} from user, {bot_count} from bot, {agent_count} from agent"
        }


# Singleton instance
_context_manager = None


def get_context_manager() -> ConversationContextManager:
    """Get or create the conversation context manager singleton"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ConversationContextManager()
    return _context_manager
