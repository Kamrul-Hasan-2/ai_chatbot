"""
Channel Adapter: Handles different communication channels
Part of BDStall Chatbot System Architecture

This module provides a unified interface for handling messages from different channels:
- Web/App interface
- Facebook Messenger
- Customer service integrations
- Future channel extensions
"""
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Supported communication channels"""
    WEB = "web"
    FACEBOOK = "facebook"
    CUSTOMER_SERVICE = "customer_service"
    API = "api"
    WEBHOOK = "webhook"


class MessageType(Enum):
    """Types of messages that can be processed"""
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    POSTBACK = "postback"
    QUICK_REPLY = "quick_reply"
    MULTIMEDIA = "multimedia"


class ChannelMessage:
    """Standardized message format across all channels"""
    
    def __init__(
        self,
        channel: ChannelType,
        user_id: str,
        message_content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
        timestamp: Optional[datetime] = None
    ):
        self.channel = channel
        self.user_id = user_id
        self.message_content = message_content
        self.message_type = message_type
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()
        self.message_id = self._generate_message_id()
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        return f"{self.channel.value}_{self.user_id}_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict:
        """Convert message to dictionary format"""
        return {
            "message_id": self.message_id,
            "channel": self.channel.value,
            "user_id": self.user_id,
            "message_content": self.message_content,
            "message_type": self.message_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ChannelMessage':
        """Create message from dictionary"""
        return cls(
            channel=ChannelType(data["channel"]),
            user_id=data["user_id"],
            message_content=data["message_content"],
            message_type=MessageType(data["message_type"]),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class ChannelAdapter:
    """
    Central adapter for handling messages from different channels
    Normalizes input from various sources into standardized format
    """
    
    def __init__(self):
        self.supported_channels = {
            ChannelType.WEB,
            ChannelType.FACEBOOK,
            ChannelType.CUSTOMER_SERVICE,
            ChannelType.API,
            ChannelType.WEBHOOK
        }
        self.message_processors = {
            ChannelType.WEB: self._process_web_message,
            ChannelType.FACEBOOK: self._process_facebook_message,
            ChannelType.CUSTOMER_SERVICE: self._process_customer_service_message,
            ChannelType.API: self._process_api_message,
            ChannelType.WEBHOOK: self._process_webhook_message
        }
        self.message_history: List[ChannelMessage] = []
        logger.info("Channel Adapter initialized")
    
    def process_incoming_message(self, raw_message: Dict, channel: ChannelType) -> Optional[ChannelMessage]:
        """
        Process incoming message from any channel
        
        Args:
            raw_message: Raw message data from the channel
            channel: The channel type this message came from
            
        Returns:
            Standardized ChannelMessage or None if processing fails
        """
        try:
            if channel not in self.supported_channels:
                logger.error(f"Unsupported channel: {channel}")
                return None
            
            processor = self.message_processors.get(channel)
            if not processor:
                logger.error(f"No processor found for channel: {channel}")
                return None
            
            message = processor(raw_message)
            if message:
                self.message_history.append(message)
                logger.info(f"Processed message from {channel.value}: {message.message_id}")
            
            return message
            
        except Exception as e:
            logger.error(f"Error processing message from {channel.value}: {e}")
            return None
    
    def _process_web_message(self, raw_message: Dict) -> Optional[ChannelMessage]:
        """Process message from web interface"""
        try:
            return ChannelMessage(
                channel=ChannelType.WEB,
                user_id=raw_message.get("user_id", "web_user"),
                message_content=raw_message.get("message", ""),
                message_type=MessageType.TEXT,
                metadata={
                    "ip_address": raw_message.get("ip_address"),
                    "user_agent": raw_message.get("user_agent"),
                    "session_id": raw_message.get("session_id")
                }
            )
        except Exception as e:
            logger.error(f"Error processing web message: {e}")
            return None
    
    def _process_facebook_message(self, raw_message: Dict) -> Optional[ChannelMessage]:
        """Process message from Facebook Messenger"""
        try:
            # Handle Facebook Messenger webhook format
            if "messaging" in raw_message:
                for entry in raw_message.get("entry", []):
                    for messaging_event in entry.get("messaging", []):
                        sender_id = messaging_event["sender"]["id"]
                        
                        # Handle text message
                        if "message" in messaging_event:
                            message = messaging_event["message"]
                            if "text" in message:
                                return ChannelMessage(
                                    channel=ChannelType.FACEBOOK,
                                    user_id=sender_id,
                                    message_content=message["text"],
                                    message_type=MessageType.TEXT,
                                    metadata={
                                        "message_id": message.get("mid"),
                                        "timestamp": messaging_event.get("timestamp")
                                    }
                                )
                        
                        # Handle postback
                        elif "postback" in messaging_event:
                            postback = messaging_event["postback"]
                            return ChannelMessage(
                                channel=ChannelType.FACEBOOK,
                                user_id=sender_id,
                                message_content=postback.get("payload", ""),
                                message_type=MessageType.POSTBACK,
                                metadata={
                                    "title": postback.get("title"),
                                    "timestamp": messaging_event.get("timestamp")
                                }
                            )
            
            # Handle direct Facebook message format
            else:
                return ChannelMessage(
                    channel=ChannelType.FACEBOOK,
                    user_id=raw_message.get("sender_id", ""),
                    message_content=raw_message.get("text", ""),
                    message_type=MessageType.TEXT,
                    metadata=raw_message.get("metadata", {})
                )
                
        except Exception as e:
            logger.error(f"Error processing Facebook message: {e}")
            return None
    
    def _process_customer_service_message(self, raw_message: Dict) -> Optional[ChannelMessage]:
        """Process message from customer service interface"""
        try:
            return ChannelMessage(
                channel=ChannelType.CUSTOMER_SERVICE,
                user_id=raw_message.get("customer_id", "cs_user"),
                message_content=raw_message.get("message", ""),
                message_type=MessageType.TEXT,
                metadata={
                    "agent_id": raw_message.get("agent_id"),
                    "ticket_id": raw_message.get("ticket_id"),
                    "priority": raw_message.get("priority", "normal")
                }
            )
        except Exception as e:
            logger.error(f"Error processing customer service message: {e}")
            return None
    
    def _process_api_message(self, raw_message: Dict) -> Optional[ChannelMessage]:
        """Process message from API call"""
        try:
            return ChannelMessage(
                channel=ChannelType.API,
                user_id=raw_message.get("user_id", "api_user"),
                message_content=raw_message.get("message", ""),
                message_type=MessageType.TEXT,
                metadata={
                    "api_key": raw_message.get("api_key"),
                    "endpoint": raw_message.get("endpoint"),
                    "request_id": raw_message.get("request_id")
                }
            )
        except Exception as e:
            logger.error(f"Error processing API message: {e}")
            return None
    
    def _process_webhook_message(self, raw_message: Dict) -> Optional[ChannelMessage]:
        """Process message from webhook"""
        try:
            return ChannelMessage(
                channel=ChannelType.WEBHOOK,
                user_id=raw_message.get("user_id", "webhook_user"),
                message_content=raw_message.get("message", ""),
                message_type=MessageType.TEXT,
                metadata={
                    "webhook_source": raw_message.get("source"),
                    "webhook_id": raw_message.get("webhook_id")
                }
            )
        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")
            return None
    
    def format_response_for_channel(
        self, 
        response: str, 
        channel: ChannelType, 
        user_id: str,
        additional_data: Optional[Dict] = None
    ) -> Dict:
        """
        Format response for specific channel requirements
        
        Args:
            response: The text response to send
            channel: Target channel
            user_id: Recipient user ID
            additional_data: Any additional data for the response
            
        Returns:
            Formatted response dictionary for the channel
        """
        try:
            base_response = {
                "text": response,
                "channel": channel.value,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            
            if channel == ChannelType.WEB:
                return {
                    **base_response,
                    "response": response,
                    "success": True
                }
            
            elif channel == ChannelType.FACEBOOK:
                return {
                    "recipient": {"id": user_id},
                    "message": {"text": response},
                    **base_response
                }
            
            elif channel == ChannelType.CUSTOMER_SERVICE:
                return {
                    **base_response,
                    "customer_id": user_id,
                    "message_type": "agent_response",
                    "ticket_data": additional_data or {}
                }
            
            elif channel == ChannelType.API:
                return {
                    **base_response,
                    "status": "success",
                    "data": additional_data or {}
                }
            
            else:
                return base_response
                
        except Exception as e:
            logger.error(f"Error formatting response for {channel.value}: {e}")
            return {"error": str(e), "channel": channel.value}
    
    def get_channel_metrics(self) -> Dict:
        """Get usage metrics for all channels"""
        try:
            metrics = {
                "total_messages": len(self.message_history),
                "channels": {}
            }
            
            # Count messages per channel
            for message in self.message_history:
                channel = message.channel.value
                if channel not in metrics["channels"]:
                    metrics["channels"][channel] = {
                        "message_count": 0,
                        "unique_users": set()
                    }
                
                metrics["channels"][channel]["message_count"] += 1
                metrics["channels"][channel]["unique_users"].add(message.user_id)
            
            # Convert sets to counts
            for channel_data in metrics["channels"].values():
                channel_data["unique_users"] = len(channel_data["unique_users"])
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting channel metrics: {e}")
            return {"error": str(e)}
    
    def get_user_messages(self, user_id: str, channel: Optional[ChannelType] = None) -> List[ChannelMessage]:
        """Get all messages from a specific user, optionally filtered by channel"""
        try:
            messages = [
                msg for msg in self.message_history
                if msg.user_id == user_id and (channel is None or msg.channel == channel)
            ]
            return messages
        except Exception as e:
            logger.error(f"Error getting user messages: {e}")
            return []
    
    def clear_message_history(self, older_than_days: int = 30):
        """Clear old messages from history"""
        try:
            cutoff_date = datetime.now().timestamp() - (older_than_days * 24 * 60 * 60)
            
            original_count = len(self.message_history)
            self.message_history = [
                msg for msg in self.message_history
                if msg.timestamp.timestamp() > cutoff_date
            ]
            
            cleared_count = original_count - len(self.message_history)
            logger.info(f"Cleared {cleared_count} old messages from history")
            
        except Exception as e:
            logger.error(f"Error clearing message history: {e}")


if __name__ == "__main__":
    # Test the Channel Adapter
    adapter = ChannelAdapter()
    
    # Test web message
    web_msg = {
        "user_id": "web_user_123",
        "message": "Hello from web",
        "session_id": "sess_123"
    }
    
    processed = adapter.process_incoming_message(web_msg, ChannelType.WEB)
    if processed:
        print(f"Processed web message: {processed.to_dict()}")
        
        # Test response formatting
        response = adapter.format_response_for_channel(
            "Hello! How can I help you?", 
            ChannelType.WEB, 
            "web_user_123"
        )
        print(f"Formatted response: {response}")
    
    # Test Facebook message
    fb_msg = {
        "entry": [{
            "messaging": [{
                "sender": {"id": "fb_user_456"},
                "message": {"text": "Hello from Facebook"},
                "timestamp": 1234567890
            }]
        }]
    }
    
    processed_fb = adapter.process_incoming_message(fb_msg, ChannelType.FACEBOOK)
    if processed_fb:
        print(f"Processed Facebook message: {processed_fb.to_dict()}")
    
    # Show metrics
    print(f"Channel metrics: {adapter.get_channel_metrics()}")