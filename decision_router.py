"""
Decision Router: Routes to different response strategies
Part of BDStall Chatbot System Architecture

This module handles routing decisions for:
- Template responses
- RAG (Retrieval Augmented Generation)
- Multimedia queries
- FAQ handling  
- Human escalation
- Response strategy selection based on context
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import json
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResponseStrategy(Enum):
    """Available response strategies"""
    TEMPLATE_RESPONSE = "template_response"
    RAG_RESPONSE = "rag_response"
    FAQ_RESPONSE = "faq_response"
    MULTIMEDIA_RESPONSE = "multimedia_response"
    HUMAN_ESCALATION = "human_escalation"
    FALLBACK_RESPONSE = "fallback_response"
    PRODUCT_SEARCH = "product_search"
    BUSINESS_HOURS = "business_hours"
    GREETING = "greeting"
    GOODBYE = "goodbye"


class RoutingConfidence(Enum):
    """Confidence levels for routing decisions"""
    VERY_HIGH = "very_high"    # 0.9+
    HIGH = "high"              # 0.7-0.9
    MEDIUM = "medium"          # 0.5-0.7
    LOW = "low"                # 0.3-0.5
    VERY_LOW = "very_low"      # 0.0-0.3


class RoutingDecision:
    """Represents a routing decision"""
    
    def __init__(
        self,
        strategy: ResponseStrategy,
        confidence: float,
        reasoning: str,
        parameters: Optional[Dict] = None,
        fallback_strategies: Optional[List[ResponseStrategy]] = None
    ):
        self.strategy = strategy
        self.confidence = confidence
        self.reasoning = reasoning
        self.parameters = parameters or {}
        self.fallback_strategies = fallback_strategies or []
        self.timestamp = datetime.now()
        
        # Determine confidence level
        if confidence >= 0.9:
            self.confidence_level = RoutingConfidence.VERY_HIGH
        elif confidence >= 0.7:
            self.confidence_level = RoutingConfidence.HIGH
        elif confidence >= 0.5:
            self.confidence_level = RoutingConfidence.MEDIUM
        elif confidence >= 0.3:
            self.confidence_level = RoutingConfidence.LOW
        else:
            self.confidence_level = RoutingConfidence.VERY_LOW
    
    def to_dict(self) -> Dict:
        return {
            "strategy": self.strategy.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "reasoning": self.reasoning,
            "parameters": self.parameters,
            "fallback_strategies": [fs.value for fs in self.fallback_strategies],
            "timestamp": self.timestamp.isoformat()
        }


class DecisionRouter:
    """
    Central decision router for selecting response strategies
    Routes requests to appropriate response handlers based on context
    """
    
    def __init__(
        self,
        enable_rag: bool = True,
        enable_multimedia: bool = True,
        escalation_threshold: float = 0.3,
        template_confidence_threshold: float = 0.8
    ):
        self.enable_rag = enable_rag
        self.enable_multimedia = enable_multimedia
        self.escalation_threshold = escalation_threshold
        self.template_confidence_threshold = template_confidence_threshold
        
        # Decision history for analytics
        self.decision_history: List[RoutingDecision] = []
        
        # Load routing rules
        self._load_routing_rules()
        
        logger.info("Decision Router initialized")
    
    def _load_routing_rules(self):
        """Load routing rules and patterns"""
        
        # Intent to strategy mapping with confidence scores
        self.intent_strategy_map = {
            "greeting": {
                "primary": ResponseStrategy.TEMPLATE_RESPONSE,
                "confidence": 0.9,
                "fallbacks": [ResponseStrategy.GREETING]
            },
            "goodbye": {
                "primary": ResponseStrategy.TEMPLATE_RESPONSE,
                "confidence": 0.9,
                "fallbacks": [ResponseStrategy.GOODBYE]
            },
            "product_inquiry": {
                "primary": ResponseStrategy.PRODUCT_SEARCH,
                "confidence": 0.8,
                "fallbacks": [ResponseStrategy.RAG_RESPONSE, ResponseStrategy.FAQ_RESPONSE]
            },
            "price_inquiry": {
                "primary": ResponseStrategy.PRODUCT_SEARCH,
                "confidence": 0.85,
                "fallbacks": [ResponseStrategy.RAG_RESPONSE]
            },
            "order_inquiry": {
                "primary": ResponseStrategy.FAQ_RESPONSE,
                "confidence": 0.7,
                "fallbacks": [ResponseStrategy.RAG_RESPONSE, ResponseStrategy.TEMPLATE_RESPONSE]
            },
            "delivery_inquiry": {
                "primary": ResponseStrategy.FAQ_RESPONSE,
                "confidence": 0.75,
                "fallbacks": [ResponseStrategy.RAG_RESPONSE]
            },
            "support_request": {
                "primary": ResponseStrategy.HUMAN_ESCALATION,
                "confidence": 0.6,
                "fallbacks": [ResponseStrategy.FAQ_RESPONSE, ResponseStrategy.RAG_RESPONSE]
            },
            "complaint": {
                "primary": ResponseStrategy.HUMAN_ESCALATION,
                "confidence": 0.8,
                "fallbacks": [ResponseStrategy.FAQ_RESPONSE]
            },
            "faq": {
                "primary": ResponseStrategy.FAQ_RESPONSE,
                "confidence": 0.9,
                "fallbacks": [ResponseStrategy.RAG_RESPONSE]
            },
            "business_hours": {
                "primary": ResponseStrategy.BUSINESS_HOURS,
                "confidence": 0.9,
                "fallbacks": [ResponseStrategy.TEMPLATE_RESPONSE]
            }
        }
        
        # Patterns for multimedia queries
        self.multimedia_patterns = [
            r'(show|দেখান|প্রদর্শন|display|image|photo|picture|ছবি)',
            r'(video|ভিডিও|demonstration|demo)',
            r'(how to|কিভাবে|tutorial|guide|instructions)'
        ]
        
        # Patterns for human escalation triggers
        self.escalation_patterns = [
            r'(speak to|talk to|human|agent|representative|প্রতিনিধি)',
            r'(complaint|অভিযোগ|problem|সমস্যা|issue|help me|সাহায্য করুন)',
            r'(not working|কাজ করছে না|broken|খারাপ|defective)',
            r'(urgent|emergency|জরুরি|immediate|তাৎক্ষণিক)'
        ]
        
        # FAQ keywords
        self.faq_keywords = [
            "warranty", "ওয়ারেন্টি", "return", "exchange", "refund", "ফেরত",
            "policy", "নীতি", "guidelines", "rules", "delivery", "ডেলিভারি",
            "payment", "পেমেন্ট", "shipping", "charge", "খরচ"
        ]
    
    def route_request(
        self,
        context: Dict[str, Any]
    ) -> RoutingDecision:
        """
        Route request to appropriate response strategy
        
        Args:
            context: Complete request context including intent, entities, etc.
        
        Returns:
            RoutingDecision with selected strategy and parameters
        """
        try:
            # Extract key information from context
            intent = context.get("intent_context", {}).get("intent", "unknown")
            intent_confidence = context.get("intent_context", {}).get("confidence", 0.0)
            message = context.get("message_context", {}).get("message", "")
            entities = context.get("intent_context", {}).get("entities", [])
            business_validation = context.get("business_validation", {})
            conversation_history = context.get("conversation_context", {})
            
            # Check for escalation requirements from business rules
            if context.get("_escalate"):
                decision = RoutingDecision(
                    strategy=ResponseStrategy.HUMAN_ESCALATION,
                    confidence=1.0,
                    reasoning="Business rule triggered escalation",
                    parameters={"escalation_info": context["_escalate"]}
                )
                self.decision_history.append(decision)
                return decision
            
            # Check for business hours handling
            if not business_validation.get("business_hours_status", True):
                decision = RoutingDecision(
                    strategy=ResponseStrategy.BUSINESS_HOURS,
                    confidence=0.95,
                    reasoning="Request outside business hours",
                    parameters={"after_hours_message": True}
                )
                self.decision_history.append(decision)
                return decision
            
            # Route based on intent confidence and type
            if intent_confidence < self.escalation_threshold:
                decision = self._route_low_confidence_request(context)
            elif intent in self.intent_strategy_map:
                decision = self._route_by_intent(intent, intent_confidence, context)
            else:
                decision = self._route_unknown_intent(context)
            
            # Apply additional routing logic
            decision = self._apply_contextual_routing(decision, context)
            
            self.decision_history.append(decision)
            logger.info(f"Routed to {decision.strategy.value} with confidence {decision.confidence}")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error in routing decision: {e}")
            # Fallback decision
            fallback_decision = RoutingDecision(
                strategy=ResponseStrategy.FALLBACK_RESPONSE,
                confidence=0.5,
                reasoning=f"Error in routing: {str(e)}",
                parameters={"error": str(e)}
            )
            self.decision_history.append(fallback_decision)
            return fallback_decision
    
    def _route_by_intent(
        self,
        intent: str,
        intent_confidence: float,
        context: Dict[str, Any]
    ) -> RoutingDecision:
        """Route based on detected intent"""
        try:
            intent_mapping = self.intent_strategy_map[intent]
            primary_strategy = intent_mapping["primary"]
            base_confidence = intent_mapping["confidence"]
            fallbacks = intent_mapping.get("fallbacks", [])
            
            # Adjust confidence based on intent confidence
            adjusted_confidence = base_confidence * intent_confidence
            
            # Check for special conditions
            message = context.get("message_context", {}).get("message", "").lower()
            
            # Check for multimedia request
            if self.enable_multimedia and any(
                re.search(pattern, message, re.IGNORECASE) for pattern in self.multimedia_patterns
            ):
                return RoutingDecision(
                    strategy=ResponseStrategy.MULTIMEDIA_RESPONSE,
                    confidence=0.8,
                    reasoning="Multimedia request detected in intent-based routing",
                    parameters={"requested_media_type": "image"},
                    fallback_strategies=[primary_strategy] + fallbacks
                )
            
            # Check for escalation patterns even in normal intents
            if any(re.search(pattern, message, re.IGNORECASE) for pattern in self.escalation_patterns):
                if primary_strategy != ResponseStrategy.HUMAN_ESCALATION:
                    adjusted_confidence *= 0.7  # Reduce confidence for potential escalation
                    fallbacks = [ResponseStrategy.HUMAN_ESCALATION] + fallbacks
            
            return RoutingDecision(
                strategy=primary_strategy,
                confidence=adjusted_confidence,
                reasoning=f"Intent-based routing for '{intent}' with confidence {intent_confidence}",
                parameters={"intent": intent, "original_confidence": intent_confidence},
                fallback_strategies=fallbacks
            )
            
        except Exception as e:
            logger.error(f"Error routing by intent {intent}: {e}")
            return RoutingDecision(
                strategy=ResponseStrategy.FALLBACK_RESPONSE,
                confidence=0.3,
                reasoning=f"Error in intent routing: {str(e)}"
            )
    
    def _route_low_confidence_request(
        self,
        context: Dict[str, Any]
    ) -> RoutingDecision:
        """Route requests with low intent confidence"""
        try:
            message = context.get("message_context", {}).get("message", "").lower()
            intent_confidence = context.get("intent_context", {}).get("confidence", 0.0)
            
            # Check for escalation patterns
            escalation_score = sum(
                1 for pattern in self.escalation_patterns
                if re.search(pattern, message, re.IGNORECASE)
            ) / len(self.escalation_patterns)
            
            if escalation_score > 0.3:
                return RoutingDecision(
                    strategy=ResponseStrategy.HUMAN_ESCALATION,
                    confidence=0.7 + escalation_score * 0.3,
                    reasoning="Low intent confidence with escalation indicators",
                    parameters={"escalation_score": escalation_score}
                )
            
            # Check for FAQ keywords
            faq_score = sum(
                1 for keyword in self.faq_keywords
                if keyword in message
            ) / len(self.faq_keywords)
            
            if faq_score > 0.1:
                return RoutingDecision(
                    strategy=ResponseStrategy.FAQ_RESPONSE,
                    confidence=0.6 + faq_score * 0.3,
                    reasoning="FAQ keywords detected in low confidence request",
                    parameters={"faq_score": faq_score},
                    fallback_strategies=[ResponseStrategy.RAG_RESPONSE, ResponseStrategy.HUMAN_ESCALATION]
                )
            
            # Use RAG if available for low confidence requests
            if self.enable_rag:
                return RoutingDecision(
                    strategy=ResponseStrategy.RAG_RESPONSE,
                    confidence=0.6,
                    reasoning="Low intent confidence - using RAG for knowledge retrieval",
                    fallback_strategies=[ResponseStrategy.FAQ_RESPONSE, ResponseStrategy.HUMAN_ESCALATION]
                )
            
            # Final fallback
            return RoutingDecision(
                strategy=ResponseStrategy.HUMAN_ESCALATION,
                confidence=0.4,
                reasoning="Low intent confidence - escalating to human",
                parameters={"low_confidence": True}
            )
            
        except Exception as e:
            logger.error(f"Error routing low confidence request: {e}")
            return RoutingDecision(
                strategy=ResponseStrategy.FALLBACK_RESPONSE,
                confidence=0.2,
                reasoning="Error handling low confidence request"
            )
    
    def _route_unknown_intent(
        self,
        context: Dict[str, Any]
    ) -> RoutingDecision:
        """Route requests with unknown intent"""
        try:
            message = context.get("message_context", {}).get("message", "").lower()
            
            # Try to determine strategy based on message content
            
            # Check for product mentions
            product_keywords = [
                "iphone", "samsung", "laptop", "phone", "mobile", "computer",
                "আইফোন", "ল্যাপটপ", "ফোন", "মোবাইল", "কম্পিউটার"
            ]
            
            if any(keyword in message for keyword in product_keywords):
                return RoutingDecision(
                    strategy=ResponseStrategy.PRODUCT_SEARCH,
                    confidence=0.7,
                    reasoning="Product keywords detected in unknown intent",
                    fallback_strategies=[ResponseStrategy.RAG_RESPONSE, ResponseStrategy.FAQ_RESPONSE]
                )
            
            # Check for price-related keywords
            price_keywords = ["price", "cost", "rate", "দাম", "টাকা", "কত"]
            if any(keyword in message for keyword in price_keywords):
                return RoutingDecision(
                    strategy=ResponseStrategy.PRODUCT_SEARCH,
                    confidence=0.65,
                    reasoning="Price keywords detected in unknown intent",
                    fallback_strategies=[ResponseStrategy.RAG_RESPONSE]
                )
            
            # Use RAG for general unknown queries
            if self.enable_rag:
                return RoutingDecision(
                    strategy=ResponseStrategy.RAG_RESPONSE,
                    confidence=0.6,
                    reasoning="Unknown intent - attempting knowledge retrieval",
                    fallback_strategies=[ResponseStrategy.FAQ_RESPONSE, ResponseStrategy.HUMAN_ESCALATION]
                )
            
            # Fallback to template or escalation
            return RoutingDecision(
                strategy=ResponseStrategy.HUMAN_ESCALATION,
                confidence=0.5,
                reasoning="Unknown intent - escalating for human assistance"
            )
            
        except Exception as e:
            logger.error(f"Error routing unknown intent: {e}")
            return RoutingDecision(
                strategy=ResponseStrategy.FALLBACK_RESPONSE,
                confidence=0.3,
                reasoning="Error handling unknown intent"
            )
    
    def _apply_contextual_routing(
        self,
        decision: RoutingDecision,
        context: Dict[str, Any]
    ) -> RoutingDecision:
        """Apply additional contextual routing logic"""
        try:
            # Check conversation history for context
            conversation_context = context.get("conversation_context", {})
            turn_count = conversation_context.get("turn_count", 0)
            
            # If it's a long conversation, consider escalation
            if turn_count > 5 and decision.confidence < 0.7:
                decision.confidence *= 0.8  # Reduce confidence
                if ResponseStrategy.HUMAN_ESCALATION not in decision.fallback_strategies:
                    decision.fallback_strategies.insert(0, ResponseStrategy.HUMAN_ESCALATION)
                decision.reasoning += " | Long conversation detected"
            
            # Check for VIP customer status
            business_validation = context.get("business_validation", {})
            if business_validation.get("customer_status") == "vip":
                decision.confidence *= 1.1  # Boost confidence for VIP
                decision.parameters["vip_customer"] = True
                decision.reasoning += " | VIP customer"
            
            # Check for repeated failed attempts
            if conversation_context.get("failed_attempts", 0) > 2:
                if decision.strategy != ResponseStrategy.HUMAN_ESCALATION:
                    decision.strategy = ResponseStrategy.HUMAN_ESCALATION
                    decision.confidence = 0.9
                    decision.reasoning = "Multiple failed attempts - escalating"
            
            return decision
            
        except Exception as e:
            logger.error(f"Error applying contextual routing: {e}")
            return decision
    
    def get_strategy_parameters(
        self,
        strategy: ResponseStrategy,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get strategy-specific parameters"""
        try:
            parameters = {}
            
            if strategy == ResponseStrategy.PRODUCT_SEARCH:
                # Extract product search parameters
                entities = context.get("intent_context", {}).get("entities", [])
                product_entities = [
                    entity for entity in entities
                    if entity.get("entity_type") in ["product_name", "brand", "model"]
                ]
                parameters["search_entities"] = product_entities
                parameters["search_query"] = context.get("message_context", {}).get("message", "")
            
            elif strategy == ResponseStrategy.RAG_RESPONSE:
                # RAG parameters
                parameters["rag_enabled"] = self.enable_rag
                parameters["query"] = context.get("message_context", {}).get("message", "")
                parameters["context_limit"] = 3
            
            elif strategy == ResponseStrategy.FAQ_RESPONSE:
                # FAQ parameters
                parameters["query"] = context.get("message_context", {}).get("message", "")
                parameters["faq_categories"] = ["general", "products", "orders", "delivery"]
            
            elif strategy == ResponseStrategy.HUMAN_ESCALATION:
                # Escalation parameters
                escalation_info = context.get("_escalate", {})
                parameters["escalation_reason"] = escalation_info.get("reason", "General inquiry")
                parameters["priority"] = escalation_info.get("priority", "normal")
                parameters["department"] = escalation_info.get("department", "customer_service")
                parameters["estimated_wait"] = "5-10 minutes"
            
            elif strategy == ResponseStrategy.MULTIMEDIA_RESPONSE:
                # Multimedia parameters
                parameters["media_type"] = "image"
                parameters["search_query"] = context.get("message_context", {}).get("message", "")
            
            return parameters
            
        except Exception as e:
            logger.error(f"Error getting strategy parameters: {e}")
            return {}
    
    def should_fallback(
        self,
        decision: RoutingDecision,
        execution_result: Optional[Dict] = None
    ) -> Tuple[bool, Optional[ResponseStrategy]]:
        """Determine if fallback strategy should be used"""
        try:
            # Check if primary strategy failed
            if execution_result:
                if execution_result.get("success", True) is False:
                    if decision.fallback_strategies:
                        return True, decision.fallback_strategies[0]
                    else:
                        return True, ResponseStrategy.FALLBACK_RESPONSE
            
            # Check confidence threshold
            if decision.confidence < 0.4:
                if decision.fallback_strategies:
                    return True, decision.fallback_strategies[0]
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error determining fallback: {e}")
            return True, ResponseStrategy.FALLBACK_RESPONSE
    
    def get_routing_analytics(self) -> Dict[str, Any]:
        """Get routing analytics and statistics"""
        try:
            if not self.decision_history:
                return {"message": "No routing decisions recorded"}
            
            total_decisions = len(self.decision_history)
            
            # Strategy distribution
            strategy_counts = {}
            for decision in self.decision_history:
                strategy = decision.strategy.value
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
            # Confidence distribution
            confidence_levels = {}
            confidence_sum = 0
            for decision in self.decision_history:
                level = decision.confidence_level.value
                confidence_levels[level] = confidence_levels.get(level, 0) + 1
                confidence_sum += decision.confidence
            
            # Recent decisions (last 10)
            recent_decisions = [
                decision.to_dict() for decision in self.decision_history[-10:]
            ]
            
            analytics = {
                "total_decisions": total_decisions,
                "average_confidence": confidence_sum / total_decisions if total_decisions > 0 else 0,
                "strategy_distribution": strategy_counts,
                "confidence_distribution": confidence_levels,
                "recent_decisions": recent_decisions,
                "most_common_strategy": max(strategy_counts, key=strategy_counts.get) if strategy_counts else None,
                "routing_settings": {
                    "rag_enabled": self.enable_rag,
                    "multimedia_enabled": self.enable_multimedia,
                    "escalation_threshold": self.escalation_threshold
                }
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting routing analytics: {e}")
            return {"error": str(e)}
    
    def clear_decision_history(self, keep_last: int = 100):
        """Clear old decision history, keeping only recent decisions"""
        try:
            if len(self.decision_history) > keep_last:
                self.decision_history = self.decision_history[-keep_last:]
                logger.info(f"Cleared decision history, keeping last {keep_last} decisions")
        except Exception as e:
            logger.error(f"Error clearing decision history: {e}")


if __name__ == "__main__":
    # Test the Decision Router
    router = DecisionRouter()
    
    # Test contexts
    test_contexts = [
        {
            "intent_context": {"intent": "greeting", "confidence": 0.9},
            "message_context": {"message": "আসসালামু আলাইকুম"},
            "business_validation": {"business_hours_status": True}
        },
        {
            "intent_context": {"intent": "product_inquiry", "confidence": 0.8},
            "message_context": {"message": "Do you have iPhone 13?"},
            "business_validation": {"business_hours_status": True}
        },
        {
            "intent_context": {"intent": "unknown", "confidence": 0.2},
            "message_context": {"message": "I have a serious problem with my order"},
            "business_validation": {"business_hours_status": True},
            "conversation_context": {"turn_count": 1}
        },
        {
            "intent_context": {"intent": "support_request", "confidence": 0.7},
            "message_context": {"message": "I need help urgently"},
            "business_validation": {"business_hours_status": False}
        }
    ]
    
    print("Testing Decision Router:")
    print("=" * 60)
    
    for i, context in enumerate(test_contexts, 1):
        print(f"\nTest Case {i}:")
        print(f"Message: {context['message_context']['message']}")
        
        decision = router.route_request(context)
        print(f"Decision: {decision.to_dict()}")
        
        # Get strategy parameters
        params = router.get_strategy_parameters(decision.strategy, context)
        print(f"Parameters: {params}")
    
    print("\nRouting Analytics:")
    analytics = router.get_routing_analytics()
    print(json.dumps(analytics, indent=2, ensure_ascii=False, default=str))