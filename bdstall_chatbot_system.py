"""
BDStall Chatbot System Integration
Main orchestrator that integrates all architectural components

This module brings together:
- Channel Adapter
- Intent & Entity Detection
- Context Router
- Business Rule Engine
- Decision Router
- Response Composer

Following the BDStall Chatbot System Architecture
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

# Import architectural components
from channel_adapter import ChannelAdapter, ChannelType, ChannelMessage
from intent_entity_detector import IntentEntityDetector, NLPProcessingResult, Intent
from context_router import ContextRouter, ContextType, ContextPriority
from business_rule_engine import BusinessRuleEngine
from decision_router import DecisionRouter, RoutingDecision
from response_composer import ResponseComposer, GeneratedResponse
from bengali_database_handler import BengaliDatabaseHandler
from groq_3step_search import Groq3StepSearch
from human_handoff_manager import HumanHandoffManager, HandoffReason

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BDStallChatbotSystem:
    """
    Main chatbot system integrating all architectural components
    """
    
    def __init__(
        self,
        enable_rag: bool = True,
        enable_multimedia: bool = True,
        enable_analytics: bool = True
    ):
        self.enable_rag = enable_rag
        self.enable_multimedia = enable_multimedia
        self.enable_analytics = enable_analytics
        
        # Initialize all components
        try:
            # Initialize Bengali database handler first
            self.database_handler = BengaliDatabaseHandler()
            logger.info("✓ Bengali Database Handler initialized")
            
            self.channel_adapter = ChannelAdapter()
            logger.info("✓ Channel Adapter initialized")
            
            self.intent_detector = IntentEntityDetector()
            logger.info("✓ Intent & Entity Detector initialized")
            
            self.context_router = ContextRouter()
            logger.info("✓ Context Router initialized")
            
            self.business_engine = BusinessRuleEngine()
            logger.info("✓ Business Rule Engine initialized")
            
            self.decision_router = DecisionRouter(
                enable_rag=enable_rag,
                enable_multimedia=enable_multimedia
            )
            logger.info("✓ Decision Router initialized")
            
            self.response_composer = ResponseComposer(
                enable_personalization=True,
                max_response_length=1200
            )
            logger.info("✓ Response Composer initialized")
            
            # Initialize Groq 3-Step Search
            self.groq_3step_search = Groq3StepSearch()
            logger.info("✓ Groq 3-Step Search initialized")
            
            # Initialize Human Handoff Manager
            self.handoff_manager = HumanHandoffManager(
                confidence_threshold=0.5,
                max_failed_attempts=3,
                session_timeout_minutes=30
            )
            logger.info("✓ Human Handoff Manager initialized")
            
            logger.info("🚀 BDStall Chatbot System fully initialized")
            
        except Exception as e:
            logger.error(f"Error initializing chatbot system: {e}")
            raise
    
    def process_message(
        self,
        user_id: str,
        message: str,
        channel: str = "web",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main message processing pipeline
        
        Args:
            user_id: Unique user identifier
            message: User message text
            channel: Communication channel (web, facebook, etc.)
            metadata: Additional metadata
            
        Returns:
            Dictionary with response and processing information
        """
        try:
            processing_start = datetime.now()
            
            # Step 0: Check if conversation is in human mode
            if self.handoff_manager.is_in_human_mode(user_id):
                logger.info(f"👤 User {user_id} is in HUMAN MODE - not processing with AI")
                return {
                    "success": True,
                    "response": "",  # No AI response
                    "in_human_mode": True,
                    "processing_info": {
                        "mode": "human_mode",
                        "message": "Conversation is being handled by human agent",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            
            # Step 1: Channel Adapter - Normalize input message
            logger.info(f"🔄 Processing message from {user_id} via {channel}")
            
            channel_type = self._get_channel_type(channel)
            raw_message = {
                "user_id": user_id,
                "message": message,
                **(metadata or {})
            }
            
            normalized_message = self.channel_adapter.process_incoming_message(
                raw_message, channel_type
            )
            
            if not normalized_message:
                raise Exception("Failed to process incoming message")
            
            # Step 2: Intent & Entity Detection - NLP Processing
            logger.info("🧠 Analyzing intent and entities")
            nlp_result = self.intent_detector.process_message(message)
            
            # Step 2.5: Check Bengali Database First (Priority Response)
            logger.info("📋 Checking Bengali database for direct matches")
            db_result = self.database_handler.search_database(message)
            
            if db_result['success']:
                # Direct database match found - return immediately
                logger.info(f"✅ Database match found! Using direct response")
                
                processing_time = (datetime.now() - processing_start).total_seconds()
                
                try:
                    # Still update context for conversation history
                    self.context_router.add_context(
                        user_id=user_id,
                        context_type=ContextType.CONVERSATION_HISTORY,
                        content={
                            "question": message,
                            "response": db_result['response'],
                            "category": db_result['category'],
                            "similarity": db_result['similarity'],
                            "source": "bengali_database"
                        },
                        priority=ContextPriority.HIGH
                    )
                except Exception as ctx_error:
                    logger.warning(f"Context update failed: {ctx_error}")
                
                if self._is_handover_response(db_result['response']):
                    logger.info("🔁 Handover triggered by database response")
                    return {
                        "success": True,
                        "response": "",
                        "handover": True,
                        "processing_info": {
                            "processing_time_seconds": processing_time,
                            "source": "bengali_database",
                            "category": db_result['category'],
                            "similarity_score": db_result['similarity'],
                            "question_matched": db_result.get('question_matched', ''),
                            "intent": nlp_result.intent.value,
                            "language": "bengali",
                            "timestamp": datetime.now().isoformat(),
                            "handover": True
                        }
                    }

                return {
                    "success": True,
                    "response": db_result['response'],  # Always Bengali from database
                    "processing_info": {
                        "processing_time_seconds": processing_time,
                        "source": "bengali_database",
                        "category": db_result['category'],
                        "similarity_score": db_result['similarity'],
                        "question_matched": db_result.get('question_matched', ''),
                        "intent": nlp_result.intent.value,
                        "language": "bengali",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            
            # Step 2.6: Check if handoff needed (database didn't find good match)
            db_similarity = db_result.get('similarity', 0.0)
            should_handoff, handoff_reason = self.handoff_manager.should_trigger_handoff(
                user_id=user_id,
                confidence=db_similarity,
                match_found=db_result['success'],
                message=message
            )
            
            if should_handoff:
                logger.info(f"🔔 Triggering handoff for {user_id}: {handoff_reason}")
                handoff_response = self.handoff_manager.trigger_handoff(
                    user_id=user_id,
                    message=message,
                    reason=handoff_reason
                )
                
                processing_time = (datetime.now() - processing_start).total_seconds()
                
                return {
                    "success": True,
                    "response": handoff_response['response'],
                    "handoff_triggered": True,
                    "processing_info": {
                        "processing_time_seconds": processing_time,
                        "handoff_reason": handoff_reason.value,
                        "mode": "handoff_triggered",
                        "similarity_score": db_similarity,
                        "intent": nlp_result.intent.value,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            
            # Step 3: Check if product search - use Groq 3-step workflow
            is_product_search = nlp_result.intent in [
                Intent.PRODUCT_INQUIRY,
                Intent.PRICE_INQUIRY,
                Intent.PRODUCT_AVAILABILITY
            ]
            
            if is_product_search and self.groq_3step_search:
                logger.info("🚀 Routing to Groq 3-Step Search (Message → Intent → API → Response)")
                
                try:
                    groq_result = self.groq_3step_search.search(message)
                    
                    if groq_result.get('success'):
                        # Update context
                        try:
                            self.context_router.add_context(
                                user_id=user_id,
                                context_type=ContextType.CONVERSATION_HISTORY,
                                content={
                                    "question": message,
                                    "response": groq_result['response'],
                                    "workflow": "groq_3step",
                                    "products_found": groq_result.get('products_found', 0),
                                    "step1_intent": groq_result.get('step1', {}).get('intent'),
                                    "source": "groq_3step_search"
                                },
                                priority=ContextPriority.HIGH
                            )
                        except Exception as ctx_error:
                            logger.warning(f"Context update failed: {ctx_error}")
                        
                        processing_time = (datetime.now() - processing_start).total_seconds()
                        
                        return {
                            "success": True,
                            "response": groq_result['response'],
                            "processing_info": {
                                "processing_time_seconds": processing_time,
                                "source": "groq_3step_search",
                                "workflow": "groq_3step",
                                "step1_method": groq_result.get('step1', {}).get('method'),
                                "step1_intent": groq_result.get('step1', {}).get('intent'),
                                "step1_search_terms": groq_result.get('step1', {}).get('search_terms'),
                                "step2_products_found": groq_result.get('products_found', 0),
                                "step3_method": groq_result.get('step3', {}).get('method'),
                                "intent": nlp_result.intent.value,
                                "language": "bengali",
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                
                except Exception as e:
                    logger.error(f"Groq 3-step search failed: {e}")
                    # Fall through to normal processing
            
            # Step 4: Context Router - Get conversation context (normal flow)
            logger.info("📋 Routing context information")
            context = self.context_router.route_context(
                user_id=user_id,
                current_message=message,
                current_intent=nlp_result.intent.value
            )
            
            # Step 5: Build comprehensive context
            logger.info("🔗 Building comprehensive context")
            comprehensive_context = self._build_comprehensive_context(
                normalized_message, nlp_result, context
            )
            
            # Step 6: Business Rule Engine - Apply business logic
            logger.info("⚡ Applying business rules")
            validated_context = self.business_engine.execute_rules(comprehensive_context)
            
            # Step 7: Decision Router - Select response strategy
            logger.info("🎯 Routing to response strategy")
            routing_decision = self.decision_router.route_request(validated_context)
            
            # Step 8: Response Composer - Generate final response
            logger.info("✍️ Composing response")
            strategy_parameters = self.decision_router.get_strategy_parameters(
                routing_decision.strategy, validated_context
            )
            
            final_response = self.response_composer.generate_response(
                strategy=routing_decision.strategy.value,
                context=validated_context,
                parameters=strategy_parameters
            )
            
            # Step 9: Update context with conversation
            self.context_router.update_conversation_context(
                user_id=user_id,
                message=message,
                response=final_response.content,
                intent=nlp_result.intent.value,
                entities=[entity.to_dict() for entity in nlp_result.entities]
            )
            
            # Step 10: Format response for channel
            formatted_response = self.channel_adapter.format_response_for_channel(
                response=final_response.content,
                channel=channel_type,
                user_id=user_id,
                additional_data={
                    "response_type": final_response.response_type.value,
                    "quality_score": final_response.quality_score
                }
            )
            
            # Calculate processing time
            processing_time = (datetime.now() - processing_start).total_seconds()
            
            # Build comprehensive result
            result = {
                "success": True,
                "response": final_response.content,
                "formatted_response": formatted_response,
                "processing_info": {
                    "processing_time_seconds": processing_time,
                    "intent": nlp_result.intent.value,
                    "intent_confidence": nlp_result.intent_confidence,
                    "entities": [entity.to_dict() for entity in nlp_result.entities],
                    "language": nlp_result.language.value,
                    "sentiment": nlp_result.sentiment.value,
                    "strategy_used": routing_decision.strategy.value,
                    "routing_confidence": routing_decision.confidence,
                    "response_quality": final_response.quality_score,
                    "business_rules_applied": bool(validated_context.get("_rule_execution")),
                    "escalated": bool(validated_context.get("_escalate")),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Add analytics if enabled
            if self.enable_analytics:
                result["analytics"] = self._get_analytics_data()
            
            logger.info(f"✅ Message processed successfully in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            
            # Generate fallback response
            fallback_response = self._generate_fallback_response(e)
            
            return {
                "success": False,
                "response": fallback_response,
                "error": str(e),
                "processing_info": {
                    "error": True,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    def _get_channel_type(self, channel: str) -> ChannelType:
        """Convert string channel to ChannelType enum"""
        channel_mapping = {
            "web": ChannelType.WEB,
            "facebook": ChannelType.FACEBOOK,
            "messenger": ChannelType.FACEBOOK,
            "api": ChannelType.API,
            "webhook": ChannelType.WEBHOOK,
            "customer_service": ChannelType.CUSTOMER_SERVICE
        }
        return channel_mapping.get(channel.lower(), ChannelType.WEB)

    def _is_handover_response(self, response_text: str) -> bool:
        """Check if a response should trigger human handover."""
        if not response_text:
            return False

        trigger_messages = [
            (
                "BDStall.com-এ আপনাকে স্বাগতম। পণ্যের দাম জানতে আমাদের ওয়েবসাইট দেখুন অথবা "
                "কাস্টমার সার্ভিসে যোগাযোগ করুন। (যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা)।"
            ),
            (
                "মিঠুন চন্দ্র বর্মন ,BDStall.com-এ আপনাকে স্বাগতম। আপনার মেসেজ এর জন্য ধন্যবাদ। "
                "খুব শীঘ্রই BDStall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে। "
                "(যোগাযোগের সময় সকাল ১০ টা থেকে সন্ধ্যা ৬ টা) ।"
            )
        ]

        def normalize(text: str) -> str:
            return " ".join(text.strip().split())

        normalized_response = normalize(response_text)
        return any(normalized_response == normalize(msg) for msg in trigger_messages)
    
    def _build_comprehensive_context(
        self,
        message: ChannelMessage,
        nlp_result: NLPProcessingResult,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build comprehensive context from all sources"""
        try:
            return {
                # Channel information
                "channel_context": {
                    "channel": message.channel.value,
                    "channel_metadata": message.metadata
                },
                
                # Message context
                "message_context": {
                    "message": message.message_content,
                    "message_type": message.message_type.value,
                    "timestamp": message.timestamp.isoformat(),
                    "user_id": message.user_id
                },
                
                # NLP results
                "intent_context": {
                    "intent": nlp_result.intent.value,
                    "confidence": nlp_result.intent_confidence,
                    "entities": [entity.to_dict() for entity in nlp_result.entities],
                    "language": nlp_result.language.value,
                    "sentiment": nlp_result.sentiment.value,
                    "cleaned_message": nlp_result.cleaned_message
                },
                
                # Context router results
                "conversation_context": context.get("session_info", {}),
                "conversation_summary": context.get("conversation_summary", ""),
                "current_topics": context.get("current_topics", []),
                "active_intents": context.get("active_intents", []),
                "relevant_contexts": context.get("relevant_contexts", []),
                
                # User context (placeholder - would be populated from user database)
                "user_context": {
                    "user_id": message.user_id,
                    "total_orders": 0,  # Would come from database
                    "total_spent": 0,   # Would come from database
                    "preferences": []   # Would come from user profile
                },
                
                # System context
                "system_context": {
                    "processing_timestamp": datetime.now().isoformat(),
                    "system_version": "1.0.0",
                    "components_loaded": {
                        "channel_adapter": True,
                        "intent_detector": True,
                        "context_router": True,
                        "business_engine": True,
                        "decision_router": True,
                        "response_composer": True
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error building comprehensive context: {e}")
            return {"error": str(e)}
    
    def _generate_fallback_response(self, error: Exception) -> str:
        """Generate fallback response when processing fails"""
        try:
            fallback_messages = [
                "দুঃখিত, আমি এই মুহূর্তে আপনার প্রশ্নের উত্তর দিতে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।",
                "Sorry, I'm having trouble processing your request right now. Please try again.",
                "আমাদের সিস্টেমে সাময়িক সমস্যা হচ্ছে। একটু পরে চেষ্টা করুন বা আমাদের সাথে যোগাযোগ করুন।"
            ]
            
            import random
            return random.choice(fallback_messages)
            
        except Exception:
            return "System temporarily unavailable. Please try again later."
    
    def _get_analytics_data(self) -> Dict[str, Any]:
        """Get analytics data from all components"""
        try:
            analytics = {
                "channel_metrics": self.channel_adapter.get_channel_metrics(),
                "intent_detector_stats": self.intent_detector.get_processing_stats(),
                "context_router_stats": self.context_router.get_router_stats(),
                "business_engine_stats": self.business_engine.get_engine_stats(),
                "decision_router_analytics": self.decision_router.get_routing_analytics(),
                "response_composer_stats": self.response_composer.get_composer_stats()
            }
            return analytics
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return {"analytics_error": str(e)}
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "channel_adapter": "operational",
                    "intent_detector": "operational",
                    "context_router": "operational",
                    "business_engine": "operational",
                    "decision_router": "operational",
                    "response_composer": "operational"
                },
                "system_info": {
                    "rag_enabled": self.enable_rag,
                    "multimedia_enabled": self.enable_multimedia,
                    "analytics_enabled": self.enable_analytics
                }
            }
            
            # Add component-specific health checks
            try:
                health_status["component_stats"] = self._get_analytics_data()
            except Exception as e:
                health_status["component_stats_error"] = str(e)
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def clear_user_data(self, user_id: str):
        """Clear all data for a specific user"""
        try:
            self.context_router.clear_user_context(user_id)
            logger.info(f"Cleared data for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing user data: {e}")
    
    def get_user_conversation_history(self, user_id: str) -> Dict[str, Any]:
        """Get conversation history for a user"""
        try:
            session = self.context_router.get_or_create_session(user_id)
            return {
                "user_id": user_id,
                "conversation_history": session.conversation_history,
                "session_info": session.to_dict(),
                "message_count": session.message_count
            }
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return {"error": str(e)}


# Integration helpers for existing app.py
class ChatbotIntegration:
    """
    Helper class to integrate BDStall system with existing app.py
    """
    
    def __init__(self):
        self.chatbot_system = BDStallChatbotSystem(
            enable_rag=True,
            enable_multimedia=True,
            enable_analytics=True
        )
        logger.info("Chatbot Integration initialized")
    
    def get_response(
        self,
        user_id: str,
        message: str,
        channel: str = "web"
    ) -> str:
        """
        Simple interface compatible with existing AdminChatbot.get_response()
        
        Args:
            user_id: User identifier
            message: User message
            channel: Communication channel
            
        Returns:
            Response text
        """
        try:
            result = self.chatbot_system.process_message(user_id, message, channel)
            return result.get("response", "দুঃখিত, কিছু সমস্যা হয়েছে।")
        except Exception as e:
            logger.error(f"Error in get_response: {e}")
            return "দুঃখিত, আমি এই মুহূর্তে আপনাকে সাহায্য করতে পারছি না।"
    
    def clear_history(self, user_id: str):
        """Clear conversation history for user"""
        try:
            self.chatbot_system.clear_user_data(user_id)
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
    
    def get_rag_stats(self) -> Dict:
        """Get RAG statistics for compatibility"""
        try:
            return self.chatbot_system.get_system_health()
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    # Test the integrated system
    print("Testing BDStall Chatbot System Integration")
    print("=" * 60)
    
    # Initialize system
    chatbot_system = BDStallChatbotSystem()
    
    # Test messages
    test_messages = [
        ("user123", "আসসালামু আলাইকুম", "web"),
        ("user123", "Do you have iPhone 13?", "web"),
        ("user456", "আমার একটা সমস্যা আছে", "facebook"),
        ("user789", "What are your business hours?", "api")
    ]
    
    for user_id, message, channel in test_messages:
        print(f"\n📱 Processing: {message}")
        print(f"👤 User: {user_id} | 📡 Channel: {channel}")
        print("-" * 40)
        
        result = chatbot_system.process_message(user_id, message, channel)
        
        print(f"🤖 Response: {result['response']}")
        print(f"📊 Processing Info:")
        processing_info = result['processing_info']
        print(f"   • Intent: {processing_info.get('intent', 'N/A')} ({processing_info.get('intent_confidence', 0):.2f})")
        print(f"   • Strategy: {processing_info.get('strategy_used', 'N/A')}")
        print(f"   • Quality: {processing_info.get('response_quality', 0):.2f}")
        print(f"   • Time: {processing_info.get('processing_time_seconds', 0):.3f}s")
    
    # Show system health
    print(f"\n🏥 System Health:")
    health = chatbot_system.get_system_health()
    print(json.dumps(health["components"], indent=2))