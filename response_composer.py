"""
Response Composer: Uses LLM for final response generation
Part of BDStall Chatbot System Architecture

This module handles:
- Final response generation using LLM
- Response personalization and formatting
- Multi-language support
- Response quality assurance
- Template-based responses
- Dynamic content integration
"""
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime
import json
import re

# Import existing components
try:
    from gemini_model import GeminiAIModel
    from robust_ai_model import RobustAIModel
    from fallback_handler import FallbackResponder
    from database_handler import DatabaseHandler
    from rag_store import RAGStore
    from product_search import ProductSearchAPI
    from enhanced_product_search import EnhancedProductSearch
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import some components: {e}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResponseType(Enum):
    """Types of responses that can be generated"""
    TEXT_RESPONSE = "text_response"
    TEMPLATE_RESPONSE = "template_response"
    RICH_RESPONSE = "rich_response"
    MULTIMEDIA_RESPONSE = "multimedia_response"
    ESCALATION_RESPONSE = "escalation_response"
    ERROR_RESPONSE = "error_response"


class PersonalizationLevel(Enum):
    """Levels of response personalization"""
    HIGH = "high"      # Full personalization with history and preferences
    MEDIUM = "medium"  # Basic personalization with name and context
    LOW = "low"        # Minimal personalization
    NONE = "none"      # Generic responses


class ResponseQuality(Enum):
    """Response quality indicators"""
    EXCELLENT = "excellent"  # 0.9+
    GOOD = "good"           # 0.7-0.9 
    ACCEPTABLE = "acceptable" # 0.5-0.7
    POOR = "poor"           # 0.3-0.5
    VERY_POOR = "very_poor" # 0.0-0.3


class GeneratedResponse:
    """Represents a generated response"""
    
    def __init__(
        self,
        content: str,
        response_type: ResponseType,
        quality_score: float,
        personalization_level: PersonalizationLevel,
        language: str = "mixed",
        metadata: Optional[Dict] = None,
        alternatives: Optional[List[str]] = None
    ):
        self.content = content
        self.response_type = response_type
        self.quality_score = quality_score
        self.personalization_level = personalization_level
        self.language = language
        self.metadata = metadata or {}
        self.alternatives = alternatives or []
        self.generated_at = datetime.now()
        
        # Determine quality level
        if quality_score >= 0.9:
            self.quality_level = ResponseQuality.EXCELLENT
        elif quality_score >= 0.7:
            self.quality_level = ResponseQuality.GOOD
        elif quality_score >= 0.5:
            self.quality_level = ResponseQuality.ACCEPTABLE
        elif quality_score >= 0.3:
            self.quality_level = ResponseQuality.POOR
        else:
            self.quality_level = ResponseQuality.VERY_POOR
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "response_type": self.response_type.value,
            "quality_score": self.quality_score,
            "quality_level": self.quality_level.value,
            "personalization_level": self.personalization_level.value,
            "language": self.language,
            "metadata": self.metadata,
            "alternatives": self.alternatives,
            "generated_at": self.generated_at.isoformat()
        }


class ResponseComposer:
    """
    Final response generation and composition system
    Integrates with LLM and various response strategies
    """
    
    def __init__(
        self,
        enable_personalization: bool = True,
        quality_threshold: float = 0.6,
        max_response_length: int = 500,
        fallback_enabled: bool = True
    ):
        self.enable_personalization = enable_personalization
        self.quality_threshold = quality_threshold
        self.max_response_length = max_response_length
        self.fallback_enabled = fallback_enabled
        
        # Initialize components
        self._initialize_components()
        
        # Load templates and patterns
        self._load_response_templates()
        self._load_personalization_patterns()
        
        # Response history for learning
        self.response_history: List[GeneratedResponse] = []
        
        logger.info("Response Composer initialized")
    
    def _initialize_components(self):
        """Initialize AI model and helper components"""
        try:
            # Initialize robust AI model with fallbacks
            self.ai_model = RobustAIModel()
            logger.info("Robust AI model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load AI model: {e}")
            self.ai_model = None
        
        try:
            # Initialize fallback responder
            self.fallback_responder = FallbackResponder()
            logger.info("Fallback responder loaded")
        except Exception as e:
            logger.warning(f"Could not load fallback responder: {e}")
            self.fallback_responder = None
        
        try:
            # Initialize enhanced product search with Gemini AI
            self.enhanced_product_search = EnhancedProductSearch()
            logger.info("Enhanced Product Search with Gemini AI loaded")
        except Exception as e:
            logger.warning(f"Could not initialize enhanced product search: {e}")
            self.enhanced_product_search = None
            
        try:
            # Initialize fallback product search
            self.product_search = ProductSearchAPI()
            logger.info("Fallback product search API loaded")
        except Exception as e:
            logger.warning(f"Could not load fallback product search: {e}")
            self.product_search = None
    
    def _load_response_templates(self):
        """Load conversational response templates for different scenarios"""
        self.templates = {
            "greeting": {
                "bengali": [
                    "হ্যালো! কি খবর? আজ কি কিনতে চান?",
                    "আরে এসেছেন! বলুন তো কি দরকার?",
                    "স্বাগতম! কিভাবে সাহায্য করবো?",
                    "আসসালামু আলাইকুম! কিছু খুঁজছেন?"
                ],
                "english": [
                    "Hey there! What can I help you find today?",
                    "Hello! Looking for anything special?",
                    "Hi! What brings you here today?",
                    "Welcome! How can I assist you?"
                ],
                "mixed": [
                    "Hi! আজ কি কিনবেন?",
                    "Hello! কি খুঁজছেন?"
                ]
            },
            "goodbye": {
                "bengali": [
                    "ধন্যবাদ! আবার আসবেন কিন্তু।",
                    "ভালো থাকবেন! আমরা তো আছিই।",
                    "আল্লাহ হাফেজ! দরকার হলে ডাকবেন।"
                ],
                "english": [
                    "Thanks for visiting! Come back anytime.",
                    "Take care! We're always here to help.",
                    "Goodbye! Feel free to ask if you need anything."
                ],
                "mixed": [
                    "ধন্যবাদ! Thanks for stopping by!"
                ]
            },
            "business_hours": {
                "bengali": [
                    "আমাদের দোকান সকাল ৯টা থেকে সন্ধ্যা ৬টা পর্যন্ত খোলা থাকে। রবিবার থেকে বৃহস্পতিবার। এখন তো আমি আছি, কি লাগবে বলুন?",
                    "অফিসের সময় হলো সকাল ৯টা থেকে সন্ধ্যা ৬টা পর্যন্ত, রবি থেকে বৃহস্পতি। তবে আমি তো এখানেই আছি!"
                ],
                "english": [
                    "Our office is open 9 AM to 6 PM, Sunday to Thursday. But I'm here anytime to help!",
                    "Office hours are 9 to 6, but you can always chat with me!"
                ],
                "mixed": [
                    "Office time সকাল ৯টা থেকে সন্ধ্যা ৬টা. But I'm always available!"
                ]
            },
            "product_not_found": {
                "bengali": [
                    "হুমম, এটা তো আমার কাছে নেই। অন্য কিছু দেখবেন?",
                    "দুঃখিত, এই জিনিসটা এখন স্টকে নেই। আর কিছু?", 
                    "এটা খুঁজে পাইনি। আরেকটু ভিন্নভাবে বলেন তো?"
                ],
                "english": [
                    "Hmm, I don't have that one. Want to try something else?",
                    "Sorry, that's not in stock right now. Anything else?",
                    "Couldn't find that. Can you describe it differently?"
                ]
            },
            "unknown": {
                "bengali": [
                    "একটু বুঝিয়ে বলবেন? আমি সাহায্য করতে চাই।",
                    "দুঃখিত, ঠিক বুঝতে পারিনি। আরেকবার বলুন তো?",
                    "কি বলতে চাইছেন একটু ক্লিয়ার করে বলবেন?"
                ],
                "english": [
                    "Can you explain that a bit more? I want to help.",
                    "Sorry, didn't quite get that. Can you try again?", 
                    "What exactly are you looking for?"
                ]
            },
            
            "escalation": {
                "bengali": [
                    "আপনার বিষয়টি আমাদের একজন প্রতিনিধির কাছে পাঠানো হচ্ছে। শীঘ্রই আপনার সাথে যোগাযোগ করা হবে।",
                    "একজন কাস্টমার সার্ভিস প্রতিনিধি আপনাকে সাহায্য করবেন। অনুগ্রহ করে অপেক্ষা করুন।"
                ],
                "english": [
                    "I'm connecting you with a human representative who will assist you shortly.",
                    "Your query has been escalated to our customer service team. Someone will contact you soon."
                ]
            },
            "error": {
                "bengali": [
                    "দুঃখিত, আমি এই মুহূর্তে আপনার প্রশ্নের উত্তর দিতে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।",
                    "কিছু সমস্যা হয়েছে। আমাদের প্রতিনিধির সাথে যোগাযোগ করুন।"
                ],
                "english": [
                    "I apologize, but I'm unable to process your request right now. Please try again.",
                    "Something went wrong. Please contact our support team."
                ]
            }
        }
    
    def _load_personalization_patterns(self):
        """Load personalization patterns and preferences"""
        self.personalization_patterns = {
            "name_mentions": [
                "{name}স্যার/ম্যাম",
                "{name}, আপনার জন্য",
                "Dear {name}",
                "{name}, here's what I found"
            ],
            "vip_customer": [
                "আপনি আমাদের মূল্যবান কাস্টমার",
                "As a valued customer",
                "আপনার জন্য বিশেষ সেবা"
            ],
            "repeat_customer": [
                "আবারও আমাদের সাথে যোগাযোগ করার জন্য ধন্যবাদ",
                "Welcome back!",
                "আপনাকে আবার দেখে খুশি হলাম"
            ]
        }
    
    def generate_response(
        self,
        strategy: str,
        context: Dict[str, Any],
        parameters: Optional[Dict] = None
    ) -> GeneratedResponse:
        """
        Generate final response based on strategy and context
        
        Args:
            strategy: Response strategy (from DecisionRouter)
            context: Complete context information
            parameters: Strategy-specific parameters
            
        Returns:
            GeneratedResponse object with composed response
        """
        try:
            parameters = parameters or {}
            
            # Route to appropriate response generator
            if strategy == "template_response":
                response = self._generate_template_response(context, parameters)
            elif strategy == "rag_response":
                response = self._generate_rag_response(context, parameters)
            elif strategy == "faq_response":
                response = self._generate_faq_response(context, parameters)
            elif strategy == "product_search":
                response = self._generate_product_response(context, parameters)
            elif strategy == "multimedia_response":
                response = self._generate_multimedia_response(context, parameters)
            elif strategy == "human_escalation":
                response = self._generate_escalation_response(context, parameters)
            elif strategy == "business_hours":
                response = self._generate_business_hours_response(context, parameters)
            elif strategy == "greeting":
                response = self._generate_greeting_response(context, parameters)
            elif strategy == "goodbye":
                response = self._generate_goodbye_response(context, parameters)
            else:
                response = self._generate_fallback_response(context, parameters)
            
            # Apply personalization if enabled
            if self.enable_personalization:
                response = self._personalize_response(response, context)
            
            # Quality assurance check
            response = self._quality_assurance(response, context)
            
            # Store in history
            self.response_history.append(response)
            
            logger.info(f"Generated {response.response_type.value} with quality {response.quality_score:.2f}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._generate_error_response(str(e))
    
    def _generate_template_response(
        self,
        context: Dict[str, Any],
        parameters: Dict
    ) -> GeneratedResponse:
        """Generate template-based response"""
        try:
            intent = parameters.get("intent", "unknown")
            language = self._detect_language(context)
            
            # Get appropriate template
            if intent in self.templates:
                templates = self.templates[intent].get(language, self.templates[intent].get("mixed", []))
                if templates:
                    import random
                    template = random.choice(templates)
                    
                    return GeneratedResponse(
                        content=template,
                        response_type=ResponseType.TEMPLATE_RESPONSE,
                        quality_score=0.8,
                        personalization_level=PersonalizationLevel.LOW,
                        language=language,
                        metadata={"template_used": True, "intent": intent}
                    )
            
            # Fallback to generic response
            return GeneratedResponse(
                content="আমি আপনার প্রশ্ন বুঝতে পারলাম। আরও সাহায্যের জন্য বলুন।",
                response_type=ResponseType.TEMPLATE_RESPONSE,
                quality_score=0.6,
                personalization_level=PersonalizationLevel.NONE,
                language="bengali"
            )
            
        except Exception as e:
            logger.error(f"Error generating template response: {e}")
            return self._generate_error_response("Template generation failed")
    
    def _generate_rag_response(
        self,
        context: Dict[str, Any],
        parameters: Dict
    ) -> GeneratedResponse:
        """Generate RAG-enhanced response using AI model"""
        try:
            if not self.ai_model:
                return self._generate_fallback_response(context, parameters)
            
            query = parameters.get("query", context.get("message_context", {}).get("message", ""))
            
            # Get context from router
            conversation_summary = context.get("conversation_summary", "")
            relevant_contexts = context.get("relevant_contexts", [])
            
            # Build context for AI model
            rag_context = ""
            if relevant_contexts:
                context_parts = []
                for ctx in relevant_contexts[:3]:  # Top 3 contexts
                    if ctx.get("content"):
                        context_parts.append(str(ctx["content"]))
                rag_context = "\n\n".join(context_parts)
            
            # Generate response using AI model (only if available)
            if self.ai_model:
                ai_response = self.ai_model.generate_response(
                    user_message=query,
                    context=rag_context,
                    conversation_history=[]
                )
            else:
                # Fallback to simple response when AI model not available
                if rag_context:
                    ai_response = f"আমি আপনার প্রশ্নের উত্তর দিতে চাই, কিন্তু এই মুহূর্তে AI সিস্টেম উপলব্ধ নেই। অনুগ্রহ করে আরও নির্দিষ্ট প্রশ্ন করুন অথবা আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন।"
                else:
                    ai_response = "দুঃখিত, এই প্রশ্নের উত্তর দিতে আমার আরও তথ্য দরকার। অনুগ্রহ করে আরও স্পষ্ট করে জানান।"
            
            # Calculate quality score based on context relevance
            quality_score = 0.8 if rag_context else 0.6
            if len(ai_response) > 10:
                quality_score += 0.1
            
            return GeneratedResponse(
                content=ai_response,
                response_type=ResponseType.TEXT_RESPONSE,
                quality_score=min(quality_score, 1.0),
                personalization_level=PersonalizationLevel.MEDIUM,
                language=self._detect_language(context),
                metadata={
                    "rag_used": True,
                    "context_provided": bool(rag_context),
                    "ai_model": "gemini"
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return self._generate_fallback_response(context, parameters)
    
    def _generate_product_response(
        self,
        context: Dict[str, Any],
        parameters: Dict
    ) -> GeneratedResponse:
        """Generate enhanced product search response using 3-step Gemini AI workflow"""
        try:
            query = parameters.get("search_query", "")
            search_entities = parameters.get("search_entities", [])
            
            # Extract product search term from context
            search_term = query or context.get('message_context', {}).get('normalized_text', '')
            if search_entities:
                for entity in search_entities:
                    if entity.get("value"):
                        search_term = entity["value"]
                        break
            
            logger.info(f"🛍️ Processing product search for: {search_term}")
            
            # Try enhanced product search first (3-step Gemini workflow)
            if self.enhanced_product_search:
                try:
                    logger.info("🚀 Using Enhanced Product Search with Gemini AI")
                    enhanced_result = self.enhanced_product_search.enhanced_product_search(search_term)
                    
                    if enhanced_result.get('success'):
                        return GeneratedResponse(
                            content=enhanced_result['response'],
                            response_type=ResponseType.RICH_RESPONSE,
                            quality_score=0.95,  # Higher quality due to AI enhancement
                            personalization_level=PersonalizationLevel.HIGH,
                            language="bengali",
                            metadata={
                                "products_found": enhanced_result.get('products_found', 0),
                                "search_term": search_term,
                                "enhanced_search": True,
                                "intent_detected": enhanced_result.get('intent_detected', {}),
                                "top_products": enhanced_result.get('top_products', []),
                                "search_method": "enhanced_ai_workflow"
                            }
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Enhanced search failed, falling back: {e}")
            
            # Fallback to basic product search
            if self.product_search:
                logger.info("📦 Using fallback product search")
                search_result = self.product_search.search_products(search_term, max_results=3)
                
                if search_result.get("success") and search_result.get("products"):
                    response_text = self.product_search.format_response(search_result, "bengali")
                    
                    return GeneratedResponse(
                        content=response_text,
                        response_type=ResponseType.RICH_RESPONSE,
                        quality_score=0.75,
                        personalization_level=PersonalizationLevel.MEDIUM,
                        language="bengali",
                        metadata={
                            "products_found": len(search_result["products"]),
                            "search_term": search_term,
                            "enhanced_search": False,
                            "search_method": "basic_api"
                        }
                    )
            
            # No products found - Bengali response
            no_products_msg = f"দুঃখিত, '{search_term}' এর জন্য কোনো পণ্য পাওয়া যায়নি। অন্য কিছু খুঁজে দেখুন।"
            
            return GeneratedResponse(
                content=no_products_msg,
                response_type=ResponseType.TEXT_RESPONSE,
                quality_score=0.7,
                personalization_level=PersonalizationLevel.LOW,
                language="bengali",
                metadata={"products_found": 0, "search_term": search_term}
            )
                
        except Exception as e:
            logger.error(f"Error generating product response: {e}")
            return self._generate_fallback_response(context, parameters)
    
    def _generate_escalation_response(
        self,
        context: Dict[str, Any],
        parameters: Dict
    ) -> GeneratedResponse:
        """Generate human escalation response"""
        try:
            escalation_reason = parameters.get("escalation_reason", "General inquiry")
            priority = parameters.get("priority", "normal")
            estimated_wait = parameters.get("estimated_wait", "5-10 minutes")
            
            language = self._detect_language(context)
            
            if language == "bengali":
                escalation_msg = (
                    f"আপনার বিষয়টি ({escalation_reason}) আমাদের একজন প্রতিনিধির কাছে পাঠানো হচ্ছে। "
                    f"প্রাথমিক অপেক্ষার সময়: {estimated_wait}। "
                    f"অনুগ্রহ করে লাইনে থাকুন।"
                )
            else:
                escalation_msg = (
                    f"Your inquiry ({escalation_reason}) is being transferred to a human representative. "
                    f"Estimated wait time: {estimated_wait}. Please stay on the line."
                )
            
            return GeneratedResponse(
                content=escalation_msg,
                response_type=ResponseType.ESCALATION_RESPONSE,
                quality_score=0.9,
                personalization_level=PersonalizationLevel.MEDIUM,
                language=language,
                metadata={
                    "escalated": True,
                    "reason": escalation_reason,
                    "priority": priority,
                    "estimated_wait": estimated_wait
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating escalation response: {e}")
            return self._generate_error_response("Escalation failed")
    
    def _generate_business_hours_response(
        self,
        context: Dict[str, Any],
        parameters: Dict
    ) -> GeneratedResponse:
        """Generate business hours response"""
        try:
            language = self._detect_language(context)
            templates = self.templates["business_hours"].get(language, self.templates["business_hours"]["bengali"])
            
            import random
            response_text = random.choice(templates)
            
            return GeneratedResponse(
                content=response_text,
                response_type=ResponseType.TEMPLATE_RESPONSE,
                quality_score=0.95,
                personalization_level=PersonalizationLevel.LOW,
                language=language,
                metadata={"business_hours_response": True}
            )
            
        except Exception as e:
            logger.error(f"Error generating business hours response: {e}")
            return self._generate_error_response("Business hours response failed")
    
    def _generate_greeting_response(self, context: Dict, parameters: Dict) -> GeneratedResponse:
        """Generate greeting response"""
        try:
            language = self._detect_language(context)
            templates = self.templates["greeting"].get(language, self.templates["greeting"]["mixed"])
            
            import random
            response_text = random.choice(templates)
            
            return GeneratedResponse(
                content=response_text,
                response_type=ResponseType.TEMPLATE_RESPONSE,
                quality_score=0.9,
                personalization_level=PersonalizationLevel.MEDIUM,
                language=language,
                metadata={"greeting": True}
            )
        except Exception as e:
            return self._generate_error_response("Greeting failed")
    
    def _generate_goodbye_response(self, context: Dict, parameters: Dict) -> GeneratedResponse:
        """Generate goodbye response"""
        try:
            language = self._detect_language(context)
            templates = self.templates["goodbye"].get(language, self.templates["goodbye"]["mixed"])
            
            import random
            response_text = random.choice(templates)
            
            return GeneratedResponse(
                content=response_text,
                response_type=ResponseType.TEMPLATE_RESPONSE,
                quality_score=0.9,
                personalization_level=PersonalizationLevel.MEDIUM,
                language=language,
                metadata={"goodbye": True}
            )
        except Exception as e:
            return self._generate_error_response("Goodbye failed")
    
    def _generate_faq_response(self, context: Dict, parameters: Dict) -> GeneratedResponse:
        """Generate FAQ response"""
        try:
            # This would integrate with FAQ database
            return GeneratedResponse(
                content="এটি একটি FAQ উত্তর। আরও তথ্যের জন্য আমাদের সাথে যোগাযোগ করুন।",
                response_type=ResponseType.TEXT_RESPONSE,
                quality_score=0.8,
                personalization_level=PersonalizationLevel.LOW,
                language=self._detect_language(context),
                metadata={"faq_response": True}
            )
        except Exception as e:
            return self._generate_error_response("FAQ failed")
    
    def _generate_multimedia_response(self, context: Dict, parameters: Dict) -> GeneratedResponse:
        """Generate multimedia response"""
        try:
            return GeneratedResponse(
                content="এখানে আপনার জন্য একটি ছবি/ভিডিও থাকবে। আরও তথ্যের জন্য বলুন।",
                response_type=ResponseType.MULTIMEDIA_RESPONSE,
                quality_score=0.7,
                personalization_level=PersonalizationLevel.LOW,
                language=self._detect_language(context),
                metadata={"multimedia": True}
            )
        except Exception as e:
            return self._generate_error_response("Multimedia failed")
    
    def _generate_fallback_response(self, context: Dict, parameters: Dict) -> GeneratedResponse:
        """Generate fallback response"""
        try:
            if self.fallback_responder:
                fallback_text = self.fallback_responder.get_fallback_response()
            else:
                fallback_text = "দুঃখিত, আমি এই মুহূর্তে আপনাকে সাহায্য করতে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।"
            
            return GeneratedResponse(
                content=fallback_text,
                response_type=ResponseType.TEXT_RESPONSE,
                quality_score=0.5,
                personalization_level=PersonalizationLevel.NONE,
                language=self._detect_language(context),
                metadata={"fallback": True}
            )
        except Exception as e:
            return self._generate_error_response("Fallback failed")
    
    def _generate_error_response(self, error_msg: str) -> GeneratedResponse:
        """Generate error response"""
        return GeneratedResponse(
            content="দুঃখিত, কিছু সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।",
            response_type=ResponseType.ERROR_RESPONSE,
            quality_score=0.3,
            personalization_level=PersonalizationLevel.NONE,
            language="bengali",
            metadata={"error": error_msg, "error_response": True}
        )
    
    def _personalize_response(
        self,
        response: GeneratedResponse,
        context: Dict[str, Any]
    ) -> GeneratedResponse:
        """Apply personalization to response"""
        try:
            # Get user context
            user_context = context.get("user_context", {})
            business_validation = context.get("business_validation", {})
            
            # Check for VIP customer
            if business_validation.get("customer_status") == "vip":
                vip_prefix = "আপনি আমাদের মূল্যবান কাস্টমার। "
                response.content = vip_prefix + response.content
                response.personalization_level = PersonalizationLevel.HIGH
                response.metadata["vip_personalization"] = True
            
            # Add name if available
            user_name = user_context.get("name")
            if user_name and len(response.content) > 20:  # Only for longer responses
                response.content = f"{user_name}, " + response.content
                response.personalization_level = PersonalizationLevel.MEDIUM
            
            return response
            
        except Exception as e:
            logger.error(f"Error personalizing response: {e}")
            return response
    
    def _quality_assurance(
        self,
        response: GeneratedResponse,
        context: Dict[str, Any]
    ) -> GeneratedResponse:
        """Apply quality assurance checks"""
        try:
            # Remove any links from responses
            sanitized_content = self._remove_links(response.content)
            if sanitized_content != response.content:
                response.content = sanitized_content
                response.metadata["links_removed"] = True

            # Length check
            if len(response.content) > self.max_response_length:
                response.content = response.content[:self.max_response_length] + "..."
                response.quality_score *= 0.9
                response.metadata["truncated"] = True
            
            # Minimum quality check
            if response.quality_score < self.quality_threshold:
                # Try to improve or use fallback
                if response.response_type != ResponseType.ERROR_RESPONSE:
                    response.metadata["low_quality_warning"] = True
            
            # Language consistency check
            detected_lang = self._detect_language(context)
            if response.language != detected_lang and response.language != "mixed":
                response.language = "mixed"
                response.metadata["language_mismatch"] = True
            
            return response
            
        except Exception as e:
            logger.error(f"Error in quality assurance: {e}")
            return response

    def _remove_links(self, text: str) -> str:
        """Strip URLs and link placeholders from response text."""
        if not text:
            return text

        # Remove explicit URLs
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"www\.\S+", "", text)
        text = re.sub(r"\b\S+\.com/\S+", "", text)
        text = re.sub(r"\b\S+\.com\b", "", text)
        text = re.sub(r"\[লিংক\]\S*", "", text)

        # Collapse whitespace introduced by removals
        text = re.sub(r"\s{2,}", " ", text).strip()

        return text
    
    def _detect_language(self, context: Dict[str, Any]) -> str:
        """Always return Bengali to force Bengali-only responses"""
        # Always return 'bengali' to ensure all responses are in Bengali
        return "bengali"
    
    def get_composer_stats(self) -> Dict[str, Any]:
        """Get composer statistics"""
        try:
            if not self.response_history:
                return {"message": "No responses generated yet"}
            
            total_responses = len(self.response_history)
            
            # Response type distribution
            type_counts = {}
            quality_sum = 0
            
            for response in self.response_history:
                response_type = response.response_type.value
                type_counts[response_type] = type_counts.get(response_type, 0) + 1
                quality_sum += response.quality_score
            
            # Quality distribution
            quality_levels = {}
            for response in self.response_history:
                level = response.quality_level.value
                quality_levels[level] = quality_levels.get(level, 0) + 1
            
            return {
                "total_responses": total_responses,
                "average_quality": quality_sum / total_responses if total_responses > 0 else 0,
                "response_type_distribution": type_counts,
                "quality_distribution": quality_levels,
                "personalization_enabled": self.enable_personalization,
                "quality_threshold": self.quality_threshold,
                "recent_responses": [r.to_dict() for r in self.response_history[-5:]]
            }
            
        except Exception as e:
            logger.error(f"Error getting composer stats: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    # Test the Response Composer
    composer = ResponseComposer()
    
    # Test contexts
    test_contexts = [
        {
            "strategy": "greeting",
            "context": {
                "message_context": {"message": "আসসালামু আলাইকুম"},
                "user_context": {"name": "John"}
            }
        },
        {
            "strategy": "product_search",
            "context": {
                "message_context": {"message": "Do you have iPhone 13?"}
            },
            "parameters": {"search_query": "iPhone 13"}
        },
        {
            "strategy": "human_escalation",
            "context": {
                "message_context": {"message": "I need urgent help"},
                "business_validation": {"customer_status": "vip"}
            },
            "parameters": {"escalation_reason": "Urgent support request"}
        }
    ]
    
    print("Testing Response Composer:")
    print("=" * 60)
    
    for i, test_case in enumerate(test_contexts, 1):
        print(f"\nTest Case {i}:")
        print(f"Strategy: {test_case['strategy']}")
        
        response = composer.generate_response(
            strategy=test_case["strategy"],
            context=test_case["context"],
            parameters=test_case.get("parameters", {})
        )
        
        print(f"Response: {response.to_dict()}")
    
    print("\nComposer Stats:")
    stats = composer.get_composer_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))