"""
Human Handoff Manager
Manages switching between AI and human agent responses

When AI confidence is low or doesn't understand:
- Triggers handoff to human agent
- Tracks conversation sessions in 'human mode'
- Stores pending messages for human agents
- Provides interface for human agents to respond
"""
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import json
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationMode(Enum):
    """Conversation mode status"""
    AI_MODE = "ai_mode"
    HUMAN_MODE = "human_mode"
    PENDING_HANDOFF = "pending_handoff"


class HandoffReason(Enum):
    """Reasons for triggering human handoff"""
    LOW_CONFIDENCE = "low_confidence"
    NO_MATCH_FOUND = "no_match_found"
    COMPLEX_QUERY = "complex_query"
    USER_REQUEST = "user_requested"
    REPEATED_FAILURE = "repeated_failure"
    EXPLICIT_HANDOFF = "explicit_handoff"


class ConversationSession:
    """Tracks a conversation session with handoff status"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.mode = ConversationMode.AI_MODE
        self.handoff_triggered_at: Optional[datetime] = None
        self.handoff_reason: Optional[HandoffReason] = None
        self.pending_messages: List[Dict] = []
        self.failed_attempts = 0
        self.last_activity = datetime.now()
        self.metadata: Dict[str, Any] = {}
    
    def trigger_handoff(self, reason: HandoffReason, message: str):
        """Trigger handoff to human agent"""
        self.mode = ConversationMode.PENDING_HANDOFF
        self.handoff_triggered_at = datetime.now()
        self.handoff_reason = reason
        self.last_activity = datetime.now()
        
        logger.info(f"🔔 Handoff triggered for user {self.user_id}: {reason.value}")
        
        # Add message to pending queue
        self.pending_messages.append({
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'reason': reason.value
        })
    
    def activate_human_mode(self):
        """Activate human mode (human agent is now handling)"""
        self.mode = ConversationMode.HUMAN_MODE
        self.last_activity = datetime.now()
        logger.info(f"👤 Human mode activated for user {self.user_id}")
    
    def return_to_ai_mode(self):
        """Return conversation to AI mode"""
        self.mode = ConversationMode.AI_MODE
        self.handoff_triggered_at = None
        self.handoff_reason = None
        self.failed_attempts = 0
        self.pending_messages.clear()
        self.last_activity = datetime.now()
        logger.info(f"🤖 AI mode restored for user {self.user_id}")
    
    def add_failed_attempt(self):
        """Increment failed attempt counter"""
        self.failed_attempts += 1
        self.last_activity = datetime.now()
    
    def is_active(self, timeout_minutes: int = 30) -> bool:
        """Check if session is still active"""
        time_diff = datetime.now() - self.last_activity
        return time_diff < timedelta(minutes=timeout_minutes)
    
    def to_dict(self) -> Dict:
        """Convert session to dictionary"""
        return {
            'user_id': self.user_id,
            'mode': self.mode.value,
            'handoff_triggered_at': self.handoff_triggered_at.isoformat() if self.handoff_triggered_at else None,
            'handoff_reason': self.handoff_reason.value if self.handoff_reason else None,
            'pending_messages': self.pending_messages,
            'failed_attempts': self.failed_attempts,
            'last_activity': self.last_activity.isoformat(),
            'metadata': self.metadata
        }


class HumanHandoffManager:
    """
    Manages human handoff system
    - Detects when AI should hand over to human
    - Tracks conversation modes
    - Manages pending messages for human agents
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.5,
        max_failed_attempts: int = 3,
        session_timeout_minutes: int = 30
    ):
        self.confidence_threshold = confidence_threshold
        self.max_failed_attempts = max_failed_attempts
        self.session_timeout_minutes = session_timeout_minutes
        self.assign_agent_api_url = os.getenv(
            'ASSIGN_AGENT_API_URL',
            'https://www.bdstall.com/api/item/chatbot_assign_agent/'
        )
        self.assign_agent_api_key = os.getenv('ASSIGN_AGENT_API_KEY', 'mkh677ddd2sxxkkdjff')
        
        # Track active sessions
        self.sessions: Dict[str, ConversationSession] = {}
        
        # Handoff messages in Bengali
        self.handoff_messages = {
            HandoffReason.LOW_CONFIDENCE: (
                "দুঃখিত, আমি সঠিকভাবে বুঝতে পারছি না। একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবে। "
                "(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)\n"
                "জরুরী প্রয়োজনে কল করুন: 01612378255"
            ),
            HandoffReason.NO_MATCH_FOUND: (
                "BDStall.com-এ আপনাকে স্বাগতম। আপনার মেসেজ এর জন্য ধন্যবাদ। "
                "খুব শীঘ্রই BDStall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে। "
                "(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)\n"
                "জরুরী প্রয়োজনে কল করুন: 01612378255"
            ),
            HandoffReason.COMPLEX_QUERY: (
                "আপনার প্রশ্নটি একটু জটিল। আমাদের বিশেষজ্ঞ প্রতিনিধি শীঘ্রই সাহায্য করবে। "
                "(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)\n"
                "জরুরী প্রয়োজনে কল করুন: 01612378255"
            ),
            HandoffReason.USER_REQUEST: (
                "অবশ্যই! একজন প্রতিনিধি শীঘ্রই আপনার সাথে কথা বলবে। "
                "(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)\n"
                "জরুরী প্রয়োজনে কল করুন: 01612378255"
            ),
            HandoffReason.REPEATED_FAILURE: (
                "আমি বারবার বুঝতে পারছি না। একজন মানব প্রতিনিধি এখন আপনাকে সাহায্য করবে। "
                "(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)\n"
                "জরুরী প্রয়োজনে কল করুন: 01612378255"
            ),
            HandoffReason.EXPLICIT_HANDOFF: (
                "BDStall.com-এ আপনাকে স্বাগতম। পণ্যের দাম জানতে আমাদের ওয়েবসাইট দেখুন অথবা "
                "কাস্টমার সার্ভিসে যোগাযোগ করুন। (যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)\n"
                "জরুরী প্রয়োজনে কল করুন: 01612378255"
            )
        }
        
        logger.info("✅ Human Handoff Manager initialized")
    
    def get_or_create_session(self, user_id: str) -> ConversationSession:
        """Get existing session or create new one"""
        if user_id not in self.sessions:
            self.sessions[user_id] = ConversationSession(user_id)
        
        session = self.sessions[user_id]
        
        # Check if session expired, reset if needed
        if not session.is_active(self.session_timeout_minutes):
            logger.info(f"🔄 Session expired for {user_id}, resetting to AI mode")
            session.return_to_ai_mode()
        
        return session
    
    def should_trigger_handoff(
        self,
        user_id: str,
        confidence: float = 0.0,
        match_found: bool = True,
        message: str = ""
    ) -> tuple[bool, Optional[HandoffReason]]:
        """
        Determine if conversation should be handed off to human
        
        Returns: (should_handoff, reason)
        """
        session = self.get_or_create_session(user_id)
        
        # Already in human mode, no need to check
        if session.mode == ConversationMode.HUMAN_MODE:
            return False, None
        
        # Check for user requesting human agent
        if self._user_requests_human(message):
            return True, HandoffReason.USER_REQUEST
        
        # Check for repeated failures
        if session.failed_attempts >= self.max_failed_attempts:
            return True, HandoffReason.REPEATED_FAILURE
        
        # Check for no match found
        if not match_found:
            session.add_failed_attempt()
            return True, HandoffReason.NO_MATCH_FOUND
        
        # Check for low confidence
        if confidence < self.confidence_threshold:
            session.add_failed_attempt()
            return True, HandoffReason.LOW_CONFIDENCE
        
        # Reset failed attempts on successful interaction
        session.failed_attempts = 0
        
        return False, None
    
    def trigger_handoff(
        self,
        user_id: str,
        message: str,
        reason: HandoffReason
    ) -> Dict[str, Any]:
        """
        Trigger handoff to human agent
        
        Returns: Response dictionary with handoff message
        """
        session = self.get_or_create_session(user_id)
        session.trigger_handoff(reason, message)
        
        handoff_message = self.handoff_messages.get(
            reason,
            self.handoff_messages[HandoffReason.NO_MATCH_FOUND]
        )
        
        logger.info(f"🔔 Handoff triggered for {user_id}: {reason.value}")
        
        return {
            'success': True,
            'response': handoff_message,
            'handoff_triggered': True,
            'handoff_info': {
                'reason': reason.value,
                'mode': session.mode.value,
                'triggered_at': session.handoff_triggered_at.isoformat(),
                'user_id': user_id,
                'message': message
            }
        }
    
    def is_in_human_mode(self, user_id: str) -> bool:
        """Check if conversation is currently in human mode"""
        session = self.get_or_create_session(user_id)
        return session.mode in [ConversationMode.HUMAN_MODE, ConversationMode.PENDING_HANDOFF]
    
    def activate_human_mode(self, user_id: str):
        """Activate human mode for a conversation"""
        session = self.get_or_create_session(user_id)
        session.activate_human_mode()
        self._notify_assign_agent(user_id)

    def _notify_assign_agent(self, user_id: str) -> bool:
        """Notify BDStall that this user is assigned to a human agent."""
        payload = {
            "key": self.assign_agent_api_key,
            "user_id": str(user_id)
        }

        try:
            response = requests.post(self.assign_agent_api_url, json=payload, timeout=10)

            if 200 <= response.status_code < 300:
                logger.info("✅ assign-agent API called for user %s", user_id)
                return True

            logger.warning(
                "⚠️ assign-agent API failed (status=%s, user_id=%s): %s",
                response.status_code,
                user_id,
                response.text
            )
            return False
        except Exception as e:
            logger.warning("⚠️ assign-agent API call error for user %s: %s", user_id, e)
            return False
    
    def return_to_ai(self, user_id: str):
        """Return conversation to AI mode"""
        session = self.get_or_create_session(user_id)
        session.return_to_ai_mode()
    
    def get_pending_conversations(self) -> List[Dict]:
        """Get all conversations pending human response"""
        pending = []
        
        for user_id, session in self.sessions.items():
            if session.mode == ConversationMode.PENDING_HANDOFF:
                pending.append(session.to_dict())
        
        return pending
    
    def _user_requests_human(self, message: str) -> bool:
        """Detect if user explicitly requests to talk to human agent"""
        if not message:
            return False
        
        message_lower = message.lower()
        
        # Bengali keywords
        human_keywords = [
            'মানুষ', 'প্রতিনিধি', 'এজেন্ট', 'human', 'agent', 'representative',
            'talk to human', 'speak to human', 'মানুষের সাথে',
            'কাউকে', 'someone', 'কারো সাথে'
        ]
        
        return any(keyword in message_lower for keyword in human_keywords)
    
    def get_session_info(self, user_id: str) -> Dict:
        """Get session information for a user"""
        session = self.get_or_create_session(user_id)
        return session.to_dict()
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        expired_users = []
        
        for user_id, session in self.sessions.items():
            if not session.is_active(self.session_timeout_minutes):
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.sessions[user_id]
            logger.info(f"🧹 Cleaned up expired session for {user_id}")
        
        return len(expired_users)


def test_handoff_manager():
    """Test the human handoff manager"""
    print("🧪 Testing Human Handoff Manager")
    print("=" * 60)
    
    manager = HumanHandoffManager(
        confidence_threshold=0.6,
        max_failed_attempts=3
    )
    
    test_user = "test_user_123"
    
    # Test 1: Normal interaction (high confidence)
    print("\n✅ Test 1: Normal interaction (high confidence)")
    should_handoff, reason = manager.should_trigger_handoff(
        test_user, confidence=0.8, match_found=True, message="অর্ডার করবো কিভাবে?"
    )
    print(f"   Should handoff: {should_handoff}")
    
    # Test 2: Low confidence
    print("\n⚠️ Test 2: Low confidence interaction")
    should_handoff, reason = manager.should_trigger_handoff(
        test_user, confidence=0.3, match_found=True, message="something unclear"
    )
    print(f"   Should handoff: {should_handoff}, Reason: {reason}")
    
    if should_handoff:
        result = manager.trigger_handoff(test_user, "something unclear", reason)
        print(f"   Response: {result['response'][:100]}...")
    
    # Test 3: User requests human
    print("\n👤 Test 3: User explicitly requests human agent")
    test_user_2 = "test_user_456"
    should_handoff, reason = manager.should_trigger_handoff(
        test_user_2, confidence=0.9, match_found=True, 
        message="I want to talk to a human agent"
    )
    print(f"   Should handoff: {should_handoff}, Reason: {reason}")
    
    # Test 4: Check mode
    print(f"\n📊 Test 4: Check conversation modes")
    print(f"   User 1 in human mode: {manager.is_in_human_mode(test_user)}")
    print(f"   User 2 in human mode: {manager.is_in_human_mode(test_user_2)}")
    
    # Test 5: Get pending conversations
    print(f"\n📋 Test 5: Pending conversations")
    pending = manager.get_pending_conversations()
    print(f"   Pending count: {len(pending)}")
    for conv in pending:
        print(f"   - User: {conv['user_id']}, Reason: {conv['handoff_reason']}")
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    test_handoff_manager()
