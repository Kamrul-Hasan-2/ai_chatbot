"""
Context Router: Manages conversation context
Part of BDStall Chatbot System Architecture

This module handles:
- Conversation context management
- Session tracking
- Context switching between topics
- Memory management for multi-turn conversations
- Context prioritization and relevance scoring
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timedelta
import json
from dataclasses import dataclass, asdict
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of context that can be managed"""
    USER_PROFILE = "user_profile"
    CONVERSATION_HISTORY = "conversation_history"
    CURRENT_TOPIC = "current_topic"
    BUSINESS_CONTEXT = "business_context"
    PRODUCT_CONTEXT = "product_context"
    SESSION_CONTEXT = "session_context"
    INTENT_CONTEXT = "intent_context"
    ENTITY_CONTEXT = "entity_context"


class ContextPriority(Enum):
    """Priority levels for different contexts"""
    CRITICAL = "critical"  # Always kept in memory
    HIGH = "high"         # Kept for current session
    MEDIUM = "medium"     # Kept for recent messages
    LOW = "low"          # Can be discarded when memory is full


@dataclass
class ContextItem:
    """Individual context item"""
    context_id: str
    context_type: ContextType
    content: Dict[str, Any]
    priority: ContextPriority
    created_at: datetime
    last_accessed: datetime
    expiry_time: Optional[datetime] = None
    relevance_score: float = 1.0
    user_id: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "context_id": self.context_id,
            "context_type": self.context_type.value,
            "content": self.content,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expiry_time": self.expiry_time.isoformat() if self.expiry_time else None,
            "relevance_score": self.relevance_score,
            "user_id": self.user_id
        }
    
    def is_expired(self) -> bool:
        """Check if context item has expired"""
        if self.expiry_time is None:
            return False
        return datetime.now() > self.expiry_time
    
    def update_access_time(self):
        """Update last accessed time"""
        self.last_accessed = datetime.now()


class ConversationSession:
    """Represents a conversation session for a user"""
    
    def __init__(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        max_history_length: int = 20,
        session_timeout_minutes: int = 30
    ):
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self.max_history_length = max_history_length
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.message_count = 0
        
        # Context storage
        self.contexts: Dict[str, ContextItem] = {}
        self.conversation_history: List[Dict] = []
        self.current_topics: List[str] = []
        self.active_intents: List[str] = []
        
        logger.info(f"Created session {self.session_id} for user {user_id}")
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > self.session_timeout
    
    def update_activity(self):
        """Update last activity time"""
        self.last_activity = datetime.now()
    
    def add_message(self, message: str, response: str, intent: str = "", entities: List = None):
        """Add message to conversation history"""
        self.update_activity()
        self.message_count += 1
        
        conversation_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "response": response,
            "intent": intent,
            "entities": entities or [],
            "message_number": self.message_count
        }
        
        self.conversation_history.append(conversation_entry)
        
        # Keep only recent messages
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def get_recent_context(self, context_type: ContextType, limit: int = 5) -> List[ContextItem]:
        """Get recent contexts of specific type"""
        contexts = [
            ctx for ctx in self.contexts.values()
            if ctx.context_type == context_type and not ctx.is_expired()
        ]
        
        # Sort by last accessed time (most recent first)
        contexts.sort(key=lambda x: x.last_accessed, reverse=True)
        
        return contexts[:limit]
    
    def to_dict(self) -> Dict:
        """Convert session to dictionary"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": self.message_count,
            "conversation_history": self.conversation_history[-10:],  # Last 10 messages
            "current_topics": self.current_topics,
            "active_intents": self.active_intents,
            "context_count": len(self.contexts)
        }


class ContextRouter:
    """
    Central context management system
    Handles conversation context, routing, and memory management
    """
    
    def __init__(
        self,
        max_sessions: int = 1000,
        cleanup_interval_minutes: int = 60,
        default_context_ttl_hours: int = 24
    ):
        self.max_sessions = max_sessions
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self.default_context_ttl = timedelta(hours=default_context_ttl_hours)
        
        # Session storage
        self.sessions: Dict[str, ConversationSession] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id mapping
        
        # Global contexts (shared across users)
        self.global_contexts: Dict[str, ContextItem] = {}
        
        # Last cleanup time
        self.last_cleanup = datetime.now()
        
        logger.info("Context Router initialized")
    
    def get_or_create_session(
        self,
        user_id: str,
        create_new: bool = False
    ) -> ConversationSession:
        """Get existing session or create new one for user"""
        try:
            # Check if we need to cleanup first
            self._cleanup_expired_sessions()
            
            # If create_new is True or no existing session, create new
            if create_new or user_id not in self.user_sessions:
                session = ConversationSession(user_id)
                self.sessions[session.session_id] = session
                self.user_sessions[user_id] = session.session_id
                return session
            
            # Get existing session
            session_id = self.user_sessions[user_id]
            session = self.sessions.get(session_id)
            
            # If session doesn't exist or expired, create new
            if not session or session.is_expired():
                session = ConversationSession(user_id)
                self.sessions[session.session_id] = session
                self.user_sessions[user_id] = session.session_id
            
            return session
            
        except Exception as e:
            logger.error(f"Error getting/creating session for {user_id}: {e}")
            # Fallback: create new session
            session = ConversationSession(user_id)
            self.sessions[session.session_id] = session
            self.user_sessions[user_id] = session.session_id
            return session
    
    def add_context(
        self,
        user_id: str,
        context_type: ContextType,
        content: Dict[str, Any],
        priority: ContextPriority = ContextPriority.MEDIUM,
        ttl_hours: Optional[int] = None
    ) -> str:
        """Add context to user's session"""
        try:
            session = self.get_or_create_session(user_id)
            
            # Create context item
            context_id = str(uuid.uuid4())
            ttl = ttl_hours or 24
            expiry_time = datetime.now() + timedelta(hours=ttl)
            
            context_item = ContextItem(
                context_id=context_id,
                context_type=context_type,
                content=content,
                priority=priority,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                expiry_time=expiry_time,
                user_id=user_id
            )
            
            session.contexts[context_id] = context_item
            session.update_activity()
            
            logger.info(f"Added context {context_type.value} for user {user_id}")
            return context_id
            
        except Exception as e:
            logger.error(f"Error adding context: {e}")
            return ""
    
    def get_context(
        self,
        user_id: str,
        context_types: Optional[List[ContextType]] = None,
        priority_filter: Optional[ContextPriority] = None,
        limit: int = 10
    ) -> List[ContextItem]:
        """Get contexts for user"""
        try:
            session = self.get_or_create_session(user_id)
            
            # Filter contexts
            contexts = []
            for context in session.contexts.values():
                # Skip expired contexts
                if context.is_expired():
                    continue
                
                # Filter by type if specified
                if context_types and context.context_type not in context_types:
                    continue
                
                # Filter by priority if specified
                if priority_filter and context.priority != priority_filter:
                    continue
                
                context.update_access_time()
                contexts.append(context)
            
            # Sort by relevance and recency
            contexts.sort(
                key=lambda x: (x.relevance_score, x.last_accessed.timestamp()),
                reverse=True
            )
            
            return contexts[:limit]
            
        except Exception as e:
            logger.error(f"Error getting context for {user_id}: {e}")
            return []
    
    def update_conversation_context(
        self,
        user_id: str,
        message: str,
        response: str,
        intent: str = "",
        entities: List[Dict] = None,
        topics: List[str] = None
    ):
        """Update conversation context with new message"""
        try:
            session = self.get_or_create_session(user_id)
            
            # Add to conversation history
            session.add_message(message, response, intent, entities or [])
            
            # Update current topics
            if topics:
                # Keep only recent topics (last 5)
                session.current_topics = list(set(session.current_topics + topics))[-5:]
            
            # Update active intents
            if intent:
                if intent not in session.active_intents:
                    session.active_intents.append(intent)
                # Keep only last 3 intents
                session.active_intents = session.active_intents[-3:]
            
            # Add conversation context
            self.add_context(
                user_id=user_id,
                context_type=ContextType.CONVERSATION_HISTORY,
                content={
                    "message": message,
                    "response": response,
                    "intent": intent,
                    "entities": entities or [],
                    "topics": topics or []
                },
                priority=ContextPriority.HIGH,
                ttl_hours=2
            )
            
            logger.info(f"Updated conversation context for {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating conversation context: {e}")
    
    def get_conversation_summary(self, user_id: str, summary_length: int = 3) -> str:
        """Get a summary of recent conversation"""
        try:
            session = self.get_or_create_session(user_id)
            
            if not session.conversation_history:
                return "No previous conversation."
            
            # Get recent messages
            recent_messages = session.conversation_history[-summary_length:]
            
            summary_parts = []
            for msg in recent_messages:
                user_msg = msg.get('message', '').strip()[:100]  # Limit length
                intent = msg.get('intent', '')
                
                if user_msg:
                    part = f"User asked about {intent}: '{user_msg}'"
                    summary_parts.append(part)
            
            summary = " | ".join(summary_parts)
            return summary or "Recent conversation available."
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return "Unable to retrieve conversation summary."
    
    def route_context(
        self,
        user_id: str,
        current_message: str,
        current_intent: str
    ) -> Dict[str, Any]:
        """
        Route and prioritize context based on current message and intent
        
        Returns:
            Dictionary with prioritized context information
        """
        try:
            session = self.get_or_create_session(user_id)
            
            # Get relevant contexts
            contexts = self.get_context(user_id, limit=20)
            
            # Prioritize contexts based on current intent and message
            prioritized_context = {
                "conversation_summary": self.get_conversation_summary(user_id),
                "current_topics": session.current_topics,
                "active_intents": session.active_intents,
                "relevant_contexts": [],
                "session_info": {
                    "message_count": session.message_count,
                    "session_duration": str(datetime.now() - session.created_at),
                    "last_activity": session.last_activity.isoformat()
                }
            }
            
            # Score and filter relevant contexts
            for context in contexts:
                relevance_score = self._calculate_context_relevance(
                    context, current_message, current_intent
                )
                
                if relevance_score > 0.3:  # Minimum relevance threshold
                    context.relevance_score = relevance_score
                    prioritized_context["relevant_contexts"].append({
                        "type": context.context_type.value,
                        "content": context.content,
                        "relevance_score": relevance_score,
                        "priority": context.priority.value
                    })
            
            # Sort by relevance score
            prioritized_context["relevant_contexts"].sort(
                key=lambda x: x["relevance_score"],
                reverse=True
            )
            
            return prioritized_context
            
        except Exception as e:
            logger.error(f"Error routing context: {e}")
            return {"error": str(e)}
    
    def _calculate_context_relevance(
        self,
        context: ContextItem,
        current_message: str,
        current_intent: str
    ) -> float:
        """Calculate relevance score for context item"""
        try:
            score = 0.0
            
            # Base score based on priority
            priority_scores = {
                ContextPriority.CRITICAL: 1.0,
                ContextPriority.HIGH: 0.8,
                ContextPriority.MEDIUM: 0.6,
                ContextPriority.LOW: 0.4
            }
            score += priority_scores.get(context.priority, 0.5)
            
            # Boost score for recent contexts
            hours_ago = (datetime.now() - context.last_accessed).total_seconds() / 3600
            if hours_ago < 1:
                score += 0.3
            elif hours_ago < 6:
                score += 0.2
            elif hours_ago < 24:
                score += 0.1
            
            # Boost score for matching intent
            if current_intent and 'intent' in context.content:
                if context.content['intent'] == current_intent:
                    score += 0.4
            
            # Boost score for matching keywords
            message_lower = current_message.lower()
            context_str = str(context.content).lower()
            
            # Simple keyword matching
            message_words = set(message_lower.split())
            context_words = set(context_str.split())
            
            if message_words & context_words:  # Intersection
                overlap = len(message_words & context_words) / len(message_words | context_words)
                score += overlap * 0.3
            
            return min(score, 1.0)  # Cap at 1.0
            
        except Exception:
            return 0.5  # Default relevance
    
    def clear_user_context(self, user_id: str, context_types: Optional[List[ContextType]] = None):
        """Clear context for a user"""
        try:
            if user_id in self.user_sessions:
                session_id = self.user_sessions[user_id]
                session = self.sessions.get(session_id)
                
                if session:
                    if context_types:
                        # Clear specific context types
                        contexts_to_remove = [
                            ctx_id for ctx_id, ctx in session.contexts.items()
                            if ctx.context_type in context_types
                        ]
                        for ctx_id in contexts_to_remove:
                            del session.contexts[ctx_id]
                    else:
                        # Clear all contexts
                        session.contexts.clear()
                        session.conversation_history.clear()
                        session.current_topics.clear()
                        session.active_intents.clear()
                    
                    logger.info(f"Cleared context for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error clearing context for {user_id}: {e}")
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions and contexts"""
        try:
            now = datetime.now()
            
            # Only cleanup if enough time has passed
            if now - self.last_cleanup < self.cleanup_interval:
                return
            
            # Remove expired sessions
            expired_sessions = []
            for session_id, session in self.sessions.items():
                if session.is_expired():
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                session = self.sessions[session_id]
                if session.user_id in self.user_sessions:
                    del self.user_sessions[session.user_id]
                del self.sessions[session_id]
            
            # Clean expired contexts in remaining sessions
            for session in self.sessions.values():
                expired_contexts = [
                    ctx_id for ctx_id, ctx in session.contexts.items()
                    if ctx.is_expired()
                ]
                for ctx_id in expired_contexts:
                    del session.contexts[ctx_id]
            
            # Limit number of sessions
            if len(self.sessions) > self.max_sessions:
                # Remove oldest sessions
                sessions_by_age = sorted(
                    self.sessions.values(),
                    key=lambda s: s.last_activity
                )
                
                sessions_to_remove = sessions_by_age[:len(self.sessions) - self.max_sessions]
                for session in sessions_to_remove:
                    if session.user_id in self.user_sessions:
                        del self.user_sessions[session.user_id]
                    if session.session_id in self.sessions:
                        del self.sessions[session.session_id]
            
            self.last_cleanup = now
            logger.info(f"Cleanup completed: removed {len(expired_sessions)} expired sessions")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_router_stats(self) -> Dict:
        """Get router statistics"""
        try:
            active_sessions = sum(1 for s in self.sessions.values() if not s.is_expired())
            total_contexts = sum(len(s.contexts) for s in self.sessions.values())
            
            return {
                "total_sessions": len(self.sessions),
                "active_sessions": active_sessions,
                "total_contexts": total_contexts,
                "global_contexts": len(self.global_contexts),
                "last_cleanup": self.last_cleanup.isoformat(),
                "memory_usage": {
                    "sessions": len(self.sessions),
                    "user_mappings": len(self.user_sessions)
                }
            }
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    # Test the Context Router
    router = ContextRouter()
    
    # Test user session
    user_id = "test_user_123"
    
    # Add some contexts
    router.add_context(
        user_id=user_id,
        context_type=ContextType.USER_PROFILE,
        content={"name": "John Doe", "preferences": ["electronics", "mobiles"]},
        priority=ContextPriority.HIGH
    )
    
    # Update conversation context
    router.update_conversation_context(
        user_id=user_id,
        message="Do you have iPhone 13?",
        response="Yes, we have iPhone 13 in stock.",
        intent="product_inquiry",
        entities=[{"type": "product", "value": "iPhone 13"}],
        topics=["iphone", "availability"]
    )
    
    # Route context for new message
    context = router.route_context(
        user_id=user_id,
        current_message="What's the price?",
        current_intent="price_inquiry"
    )
    
    print("Context Routing Result:")
    print(json.dumps(context, indent=2, ensure_ascii=False))
    
    # Show stats
    print(f"\nRouter Stats: {router.get_router_stats()}")