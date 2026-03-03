"""
Test initialization components individually to identify issues
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gemini_api():
    """Test if Gemini API key works"""
    try:
        from gemini_model import GeminiAIModel
        api_key = os.getenv('GEMINI_API_KEY')
        logger.info(f"Testing Gemini API with key: {api_key[:20]}...")
        
        model = GeminiAIModel()
        logger.info("✓ Gemini model initialized successfully")
        
        # Test a simple response
        response = model.generate_response("Hello, this is a test")
        logger.info(f"✓ Gemini response: {response[:100]}...")
        return True
        
    except Exception as e:
        logger.error(f"✗ Gemini initialization failed: {e}")
        return False

def test_components():
    """Test each component individually"""
    results = {}
    
    # Test Bengali Database Handler
    try:
        from bengali_database_handler import BengaliDatabaseHandler
        handler = BengaliDatabaseHandler()
        logger.info("✓ Bengali Database Handler initialized")
        results['database'] = True
    except Exception as e:
        logger.error(f"✗ Bengali Database Handler failed: {e}")
        results['database'] = False
    
    # Test Channel Adapter
    try:
        from channel_adapter import ChannelAdapter
        adapter = ChannelAdapter()
        logger.info("✓ Channel Adapter initialized")
        results['channel'] = True
    except Exception as e:
        logger.error(f"✗ Channel Adapter failed: {e}")
        results['channel'] = False
    
    # Test Intent Entity Detector
    try:
        from intent_entity_detector import IntentEntityDetector
        detector = IntentEntityDetector()
        logger.info("✓ Intent Entity Detector initialized")
        results['intent'] = True
    except Exception as e:
        logger.error(f"✗ Intent Entity Detector failed: {e}")
        results['intent'] = False
    
    # Test Context Router
    try:
        from context_router import ContextRouter
        router = ContextRouter()
        logger.info("✓ Context Router initialized")
        results['context'] = True
    except Exception as e:
        logger.error(f"✗ Context Router failed: {e}")
        results['context'] = False
    
    # Test Business Rule Engine
    try:
        from business_rule_engine import BusinessRuleEngine
        engine = BusinessRuleEngine()
        logger.info("✓ Business Rule Engine initialized")
        results['business'] = True
    except Exception as e:
        logger.error(f"✗ Business Rule Engine failed: {e}")
        results['business'] = False
    
    # Test Decision Router
    try:
        from decision_router import DecisionRouter
        router = DecisionRouter()
        logger.info("✓ Decision Router initialized")
        results['decision'] = True
    except Exception as e:
        logger.error(f"✗ Decision Router failed: {e}")
        results['decision'] = False
    
    # Test Response Composer
    try:
        from response_composer import ResponseComposer
        composer = ResponseComposer()
        logger.info("✓ Response Composer initialized")
        results['response'] = True
    except Exception as e:
        logger.error(f"✗ Response Composer failed: {e}")
        results['response'] = False
    
    return results

if __name__ == '__main__':
    print("Testing chatbot components...")
    print("=" * 50)
    
    # Test Gemini API first
    gemini_ok = test_gemini_api()
    
    print("\n" + "=" * 50)
    print("Testing individual components...")
    
    # Test components
    component_results = test_components()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"Gemini API: {'✓' if gemini_ok else '✗'}")
    
    for component, status in component_results.items():
        print(f"{component.capitalize()}: {'✓' if status else '✗'}")
    
    failed_components = [comp for comp, status in component_results.items() if not status]
    
    if failed_components:
        print(f"\nFailed components: {', '.join(failed_components)}")
        print("These components need to be fixed before the system can start.")
    else:
        print("\nAll components initialized successfully!")
        
    if not gemini_ok:
        print("\nGemini API issue - check your API key configuration.")