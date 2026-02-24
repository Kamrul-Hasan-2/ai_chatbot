"""
Intent & Entity Detection: NLP processing layer
Part of BDStall Chatbot System Architecture

This module handles:
- Intent classification (what the user wants)
- Entity extraction (specific information from messages)
- Language detection
- Sentiment analysis
- Context understanding
"""
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Intent(Enum):
    """Supported intents for the chatbot"""
    GREETING = "greeting"
    PRODUCT_INQUIRY = "product_inquiry"
    PRICE_INQUIRY = "price_inquiry"
    ORDER_INQUIRY = "order_inquiry"
    DELIVERY_INQUIRY = "delivery_inquiry"
    SUPPORT_REQUEST = "support_request"
    COMPLAINT = "complaint"
    FAQ = "faq"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"
    CUSTOMER_SERVICE = "customer_service"
    PRODUCT_AVAILABILITY = "product_availability"
    REFUND_POLICY = "refund_policy"
    PAYMENT_INQUIRY = "payment_inquiry"
    BUSINESS_HOURS = "business_hours"
    LOCATION_INQUIRY = "location_inquiry"


class EntityType(Enum):
    """Types of entities that can be extracted"""
    PRODUCT_NAME = "product_name"
    BRAND = "brand"
    PRICE_RANGE = "price_range"
    MODEL = "model"
    QUANTITY = "quantity"
    COLOR = "color"
    SIZE = "size"
    PERSON_NAME = "person_name"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    ADDRESS = "address"
    DATE = "date"
    TIME = "time"


class Language(Enum):
    """Supported languages"""
    BENGALI = "bengali"
    ENGLISH = "english"
    MIXED = "mixed"


class Sentiment(Enum):
    """Sentiment classifications"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class DetectedEntity:
    """Represents an extracted entity"""
    
    def __init__(
        self,
        entity_type: EntityType,
        value: str,
        confidence: float,
        start_pos: int,
        end_pos: int,
        context: Optional[str] = None
    ):
        self.entity_type = entity_type
        self.value = value
        self.confidence = confidence
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.context = context
    
    def to_dict(self) -> Dict:
        return {
            "entity_type": self.entity_type.value,
            "value": self.value,
            "confidence": self.confidence,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "context": self.context
        }


class NLPProcessingResult:
    """Result of NLP processing"""
    
    def __init__(
        self,
        original_message: str,
        intent: Intent,
        intent_confidence: float,
        entities: List[DetectedEntity],
        language: Language,
        sentiment: Sentiment,
        cleaned_message: str,
        processing_metadata: Optional[Dict] = None
    ):
        self.original_message = original_message
        self.intent = intent
        self.intent_confidence = intent_confidence
        self.entities = entities
        self.language = language
        self.sentiment = sentiment
        self.cleaned_message = cleaned_message
        self.processing_metadata = processing_metadata or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "original_message": self.original_message,
            "intent": self.intent.value,
            "intent_confidence": self.intent_confidence,
            "entities": [entity.to_dict() for entity in self.entities],
            "language": self.language.value,
            "sentiment": self.sentiment.value,
            "cleaned_message": self.cleaned_message,
            "processing_metadata": self.processing_metadata,
            "timestamp": self.timestamp.isoformat()
        }


class IntentEntityDetector:
    """
    NLP processing engine for intent classification and entity extraction
    """
    
    def __init__(self):
        self.intent_patterns = self._load_intent_patterns()
        self.entity_patterns = self._load_entity_patterns()
        self.language_patterns = self._load_language_patterns()
        self.sentiment_patterns = self._load_sentiment_patterns()
        logger.info("Intent & Entity Detector initialized")
    
    def _load_intent_patterns(self) -> Dict[Intent, List[str]]:
        """Load intent classification patterns"""
        return {
            Intent.GREETING: [
                r'(আসসালামু আলাইকুম|hello|hi|hey|good morning|good afternoon|good evening)',
                r'(হ্যালো|হাই|সালাম|নমস্কার)'
            ],
            Intent.PRODUCT_INQUIRY: [
                r'(আছে কি|available|have|stock|পাওয়া যায়|কিনতে|buy|purchase)',
                r'(product|প্রোডাক্ট|জিনিস|item|laptop|phone|mobile)',
                r'(show me|দেখান|দেখাও|প্রদর্শন)'
            ],
            Intent.PRICE_INQUIRY: [
                r'(price|দাম|কত টাকা|cost|rate|মূল্য|প্রাইস)',
                r'(কত|how much|টাকা|taka|৳)'
            ],
            Intent.ORDER_INQUIRY: [
                r'(order|অর্ডার|অডার|booking|বুকিং)',
                r'(কিভাবে|how to|process|প্রক্রিয়া)'
            ],
            Intent.DELIVERY_INQUIRY: [
                r'(delivery|ডেলিভারি|পৌঁছানো|shipping|courier)',
                r'(charge|খরচ|ফি|fee|cost)'
            ],
            Intent.SUPPORT_REQUEST: [
                r'(help|সাহায্য|support|customer care|problem|সমস্যা)',
                r'(contact|যোগাযোগ|number|নাম্বার)'
            ],
            Intent.COMPLAINT: [
                r'(complaint|অভিযোগ|problem|সমস্যা|issue|wrong|ভুল)',
                r'(not working|কাজ করছে না|defective|খারাপ)'
            ],
            Intent.FAQ: [
                r'(warranty|ওয়ারেন্টি|guarantee|return policy|ফেরত)',
                r'(exchange|বিনিময়|replace|replacement)'
            ],
            Intent.GOODBYE: [
                r'(bye|goodbye|ধন্যবাদ|thank you|thanks|আল্লাহ হাফেজ)',
                r'(see you|বিদায়|khoda hafez)'
            ],
            Intent.PAYMENT_INQUIRY: [
                r'(payment|পেমেন্ট|pay|টাকা দেওয়া|method|পদ্ধতি)',
                r'(bkash|নগদ|rocket|bank|card|ক্যাশ)'
            ],
            Intent.BUSINESS_HOURS: [
                r'(open|খোলা|close|বন্ধ|hours|সময়|time)',
                r'(when|কখন|office|দোকান|shop)'
            ]
        }
    
    def _load_entity_patterns(self) -> Dict[EntityType, List[str]]:
        """Load entity extraction patterns"""
        return {
            EntityType.PRODUCT_NAME: [
                r'(iphone|samsung|huawei|xiaomi|laptop|computer|printer|headphone)',
                r'(আইফোন|স্যামসাং|ল্যাপটপ|কম্পিউটার|প্রিন্টার|হেডফোন)'
            ],
            EntityType.BRAND: [
                r'(apple|samsung|huawei|xiaomi|hp|dell|asus|lenovo)',
                r'(এপল|স্যামসাং|হুয়াওয়ে|শাওমি)'
            ],
            EntityType.MODEL: [
                r'(iphone \d+|galaxy s\d+|note \d+|pro \d+)',
                r'(\d+gb|\d+tb|pro|max|plus|mini)'
            ],
            EntityType.PRICE_RANGE: [
                r'(\d+\s*হাজার|\d+\s*thousand|\d+k)',
                r'(\d+\s*টাকা|\d+\s*taka|৳\s*\d+)',
                r'(under \d+|below \d+|কম)'
            ],
            EntityType.QUANTITY: [
                r'(\d+\s*(টি|টা|piece|pcs))',
                r'(একটি|দুইটি|তিনটি|one|two|three|few|some)'
            ],
            EntityType.COLOR: [
                r'(black|white|red|blue|green|gold|silver)',
                r'(কালো|সাদা|লাল|নীল|সবুজ|সোনালী)'
            ],
            EntityType.PHONE_NUMBER: [
                r'(\+?880\d{8,10}|\d{11}|01\d{9})'
            ],
            EntityType.EMAIL: [
                r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
        }
    
    def _load_language_patterns(self) -> Dict[Language, List[str]]:
        """Load language detection patterns"""
        return {
            Language.BENGALI: [
                r'[\u0980-\u09FF]',  # Bengali Unicode range
                r'(আছে|কি|কত|কিভাবে|দাম|টাকা|প্রোডাক্ট|অর্ডার|ডেলিভারি)'
            ],
            Language.ENGLISH: [
                r'^[a-zA-Z0-9\s\.,!\?]+$',  # Only English characters
                r'(price|order|delivery|product|available|help)'
            ]
        }
    
    def _load_sentiment_patterns(self) -> Dict[Sentiment, List[str]]:
        """Load sentiment analysis patterns"""
        return {
            Sentiment.POSITIVE: [
                r'(good|great|excellent|awesome|love|like|ভালো|চমৎকার|পছন্দ)',
                r'(thanks|ধন্যবাদ|wonderful|amazing|perfect)'
            ],
            Sentiment.NEGATIVE: [
                r'(bad|terrible|awful|hate|dislike|খারাপ|ভয়ানক|পছন্দ না)',
                r'(problem|সমস্যা|complaint|অভিযোগ|wrong|ভুল|not working)'
            ],
            Sentiment.NEUTRAL: [
                r'(okay|ok|ঠিক আছে|fine|normal|usual|সাধারণ)'
            ]
        }
    
    def process_message(self, message: str) -> NLPProcessingResult:
        """
        Process a message through NLP pipeline
        
        Args:
            message: Input message to process
            
        Returns:
            NLP processing result with intent, entities, and metadata
        """
        try:
            # Clean the message
            cleaned_message = self._clean_message(message)
            
            # Detect language
            language = self._detect_language(cleaned_message)
            
            # Detect intent
            intent, intent_confidence = self._classify_intent(cleaned_message)
            
            # Extract entities
            entities = self._extract_entities(cleaned_message)
            
            # Analyze sentiment
            sentiment = self._analyze_sentiment(cleaned_message)
            
            # Create processing metadata
            processing_metadata = {
                "message_length": len(message),
                "cleaned_length": len(cleaned_message),
                "entity_count": len(entities),
                "contains_bengali": any(ord(char) >= 0x0980 and ord(char) <= 0x09FF for char in message),
                "contains_english": re.search(r'[a-zA-Z]', message) is not None
            }
            
            result = NLPProcessingResult(
                original_message=message,
                intent=intent,
                intent_confidence=intent_confidence,
                entities=entities,
                language=language,
                sentiment=sentiment,
                cleaned_message=cleaned_message,
                processing_metadata=processing_metadata
            )
            
            logger.info(f"Processed message: Intent={intent.value}, Entities={len(entities)}, Language={language.value}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # Return fallback result
            return NLPProcessingResult(
                original_message=message,
                intent=Intent.UNKNOWN,
                intent_confidence=0.0,
                entities=[],
                language=Language.MIXED,
                sentiment=Sentiment.NEUTRAL,
                cleaned_message=message,
                processing_metadata={"error": str(e)}
            )
    
    def _clean_message(self, message: str) -> str:
        """Clean and normalize the message"""
        try:
            # Remove extra whitespace
            cleaned = re.sub(r'\s+', ' ', message.strip())
            
            # Remove special characters but keep Bengali and English
            cleaned = re.sub(r'[^\u0980-\u09FFa-zA-Z0-9\s\.,!\?]', '', cleaned)
            
            return cleaned
        except Exception:
            return message
    
    def _detect_language(self, message: str) -> Language:
        """Detect the language of the message"""
        try:
            bengali_chars = len(re.findall(r'[\u0980-\u09FF]', message))
            english_chars = len(re.findall(r'[a-zA-Z]', message))
            
            if bengali_chars > 0 and english_chars > 0:
                return Language.MIXED
            elif bengali_chars > english_chars:
                return Language.BENGALI
            elif english_chars > bengali_chars:
                return Language.ENGLISH
            else:
                return Language.MIXED
        except Exception:
            return Language.MIXED
    
    def _classify_intent(self, message: str) -> Tuple[Intent, float]:
        """Classify the intent of the message"""
        try:
            message_lower = message.lower()
            best_intent = Intent.UNKNOWN
            best_score = 0.0
            
            for intent, patterns in self.intent_patterns.items():
                score = 0.0
                matches = 0
                
                for pattern in patterns:
                    if re.search(pattern, message_lower, re.IGNORECASE):
                        matches += 1
                        score += 1.0 / len(patterns)  # Normalize by number of patterns
                
                # Boost score based on multiple pattern matches
                if matches > 1:
                    score *= 1.5
                
                if score > best_score:
                    best_score = score
                    best_intent = intent
            
            # Ensure confidence is between 0 and 1
            confidence = min(best_score, 1.0)
            
            return best_intent, confidence
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return Intent.UNKNOWN, 0.0
    
    def _extract_entities(self, message: str) -> List[DetectedEntity]:
        """Extract entities from the message"""
        entities = []
        
        try:
            for entity_type, patterns in self.entity_patterns.items():
                for pattern in patterns:
                    for match in re.finditer(pattern, message, re.IGNORECASE):
                        entity = DetectedEntity(
                            entity_type=entity_type,
                            value=match.group().strip(),
                            confidence=0.8,  # Static confidence for pattern matching
                            start_pos=match.start(),
                            end_pos=match.end(),
                            context=message[max(0, match.start()-10):match.end()+10]
                        )
                        entities.append(entity)
            
            # Remove duplicate entities
            unique_entities = []
            seen = set()
            
            for entity in entities:
                key = (entity.entity_type, entity.value.lower())
                if key not in seen:
                    seen.add(key)
                    unique_entities.append(entity)
            
            return unique_entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def _analyze_sentiment(self, message: str) -> Sentiment:
        """Analyze the sentiment of the message"""
        try:
            message_lower = message.lower()
            sentiment_scores = {
                Sentiment.POSITIVE: 0,
                Sentiment.NEGATIVE: 0,
                Sentiment.NEUTRAL: 0
            }
            
            for sentiment, patterns in self.sentiment_patterns.items():
                for pattern in patterns:
                    matches = len(re.findall(pattern, message_lower, re.IGNORECASE))
                    sentiment_scores[sentiment] += matches
            
            # Return sentiment with highest score
            best_sentiment = max(sentiment_scores, key=sentiment_scores.get)
            
            # If all scores are 0, default to neutral
            if sentiment_scores[best_sentiment] == 0:
                return Sentiment.NEUTRAL
            
            return best_sentiment
            
        except Exception:
            return Sentiment.NEUTRAL
    
    def get_intent_confidence_threshold(self, intent: Intent) -> float:
        """Get confidence threshold for specific intents"""
        thresholds = {
            Intent.GREETING: 0.5,
            Intent.PRODUCT_INQUIRY: 0.6,
            Intent.PRICE_INQUIRY: 0.7,
            Intent.ORDER_INQUIRY: 0.6,
            Intent.SUPPORT_REQUEST: 0.5,
            Intent.COMPLAINT: 0.8,
            Intent.GOODBYE: 0.5,
            Intent.UNKNOWN: 0.0
        }
        return thresholds.get(intent, 0.6)
    
    def is_intent_confident(self, intent: Intent, confidence: float) -> bool:
        """Check if intent classification is confident enough"""
        threshold = self.get_intent_confidence_threshold(intent)
        return confidence >= threshold
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics"""
        return {
            "supported_intents": len(Intent),
            "supported_entities": len(EntityType),
            "supported_languages": len(Language),
            "intent_patterns_loaded": sum(len(patterns) for patterns in self.intent_patterns.values()),
            "entity_patterns_loaded": sum(len(patterns) for patterns in self.entity_patterns.values())
        }


if __name__ == "__main__":
    # Test the Intent & Entity Detector
    detector = IntentEntityDetector()
    
    # Test messages
    test_messages = [
        "আসসালামু আলাইকুম, আপনাদের কাছে iPhone আছে?",
        "Hello, do you have Samsung Galaxy S21?",
        "দাম কত?",
        "How much does it cost?",
        "আমার একটা সমস্যা আছে",
        "I want to place an order",
        "ধন্যবাদ, আল্লাহ হাফেজ",
        "01712345678 এই নাম্বারে কল করুন"
    ]
    
    print("Testing Intent & Entity Detection:")
    print("=" * 60)
    
    for message in test_messages:
        result = detector.process_message(message)
        print(f"\nMessage: {message}")
        print(f"Intent: {result.intent.value} (confidence: {result.intent_confidence:.2f})")
        print(f"Language: {result.language.value}")
        print(f"Sentiment: {result.sentiment.value}")
        print(f"Entities: {len(result.entities)}")
        
        for entity in result.entities:
            print(f"  - {entity.entity_type.value}: {entity.value}")
    
    print(f"\nProcessing Stats: {detector.get_processing_stats()}")