"""
BDStall AI Training System
Trains the chatbot using database.csv and sets up Bengali language responses
"""
import pandas as pd
import logging
from typing import List, Dict, Any
from database_handler import DatabaseHandler
from bdstall_chatbot_system import BDStallChatbotSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BDStallAITrainer:
    def __init__(self):
        """Initialize the AI training system"""
        self.database_handler = DatabaseHandler("database.csv")
        self.chatbot_system = None
        self.training_data = []
        
    def load_database_knowledge(self):
        """Load Q&A pairs from database.csv"""
        try:
            logger.info("📚 Loading knowledge from database.csv...")
            
            # Read CSV file
            df = pd.read_csv("database.csv", encoding='utf-8')
            
            # Clean and process data
            for index, row in df.iterrows():
                question = str(row.iloc[0]).strip()  # First column (প্রশ্ন)
                answer = str(row.iloc[1]).strip()    # Second column (উত্তর)
                
                if question and answer and question != 'nan' and answer != 'nan':
                    # Skip header row
                    if question not in ['প্রশ্ন', 'প্রশ্ন ']:
                        self.training_data.append({
                            'question': question,
                            'answer': answer,
                            'language': 'bengali',
                            'category': self._categorize_qa(question, answer)
                        })
            
            logger.info(f"✅ Loaded {len(self.training_data)} Q&A pairs")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading database: {e}")
            return False
    
    def _categorize_qa(self, question: str, answer: str) -> str:
        """Categorize Q&A pairs based on content"""
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        # Product-related
        if any(word in question_lower for word in ['দাম', 'প্রাইস', 'price', 'কত', 'টাকা']):
            return 'product_pricing'
        elif any(word in question_lower for word in ['অর্ডার', 'order', 'কিভাবে', 'কিনব', 'buy']):
            return 'ordering'
        elif any(word in question_lower for word in ['ডেলিভারি', 'delivery', 'পৌঁছাবে', 'সময়']):
            return 'delivery'
        elif any(word in question_lower for word in ['গ্যারান্টি', 'warranty', 'guarantee']):
            return 'warranty'
        elif any(word in question_lower for word in ['customer', 'support', 'নাম্বার', 'number']):
            return 'support'
        elif any(word in question_lower for word in ['স্টক', 'stock', 'available', 'আছে']):
            return 'stock_inquiry'
        else:
            return 'general'
    
    def create_bengali_templates(self):
        """Create Bengali response templates based on training data"""
        templates = {}
        
        # Group by category
        categories = {}
        for item in self.training_data:
            category = item['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        # Create templates for each category
        for category, items in categories.items():
            templates[category] = {
                'bengali': [item['answer'] for item in items[:5]],  # Top 5 responses
                'patterns': [item['question'] for item in items[:5]]
            }
        
        logger.info(f"📝 Created templates for {len(templates)} categories")
        return templates
    
    def setup_chatbot_system(self):
        """Initialize and configure the chatbot system"""
        try:
            logger.info("🤖 Setting up BDStall Chatbot System...")
            
            # Initialize system with Bengali focus
            self.chatbot_system = BDStallChatbotSystem(
                enable_rag=True,
                enable_multimedia=True,
                enable_analytics=True
            )
            
            logger.info("✅ Chatbot system ready!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up chatbot: {e}")
            return False
    
    def train_intent_recognition(self):
        """Train intent recognition with Bengali patterns"""
        try:
            logger.info("🧠 Training intent recognition...")
            
            # Create intent patterns from training data
            intent_patterns = {}
            
            for item in self.training_data:
                category = item['category']
                question = item['question']
                
                if category not in intent_patterns:
                    intent_patterns[category] = []
                
                intent_patterns[category].append(question)
            
            # Update intent detector with new patterns
            if self.chatbot_system and self.chatbot_system.intent_detector:
                detector = self.chatbot_system.intent_detector
                
                # Add Bengali patterns
                for intent, patterns in intent_patterns.items():
                    for pattern in patterns[:10]:  # Top 10 patterns per intent
                        # Add to existing patterns
                        if intent not in detector.intent_patterns:
                            detector.intent_patterns[intent] = []
                        detector.intent_patterns[intent].append(pattern.lower())
            
            logger.info(f"✅ Trained {len(intent_patterns)} intent categories")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error training intents: {e}")
            return False
    
    def setup_business_rules(self):
        """Setup business rules based on training data"""
        try:
            logger.info("⚙️ Setting up business rules...")
            
            # Skip business rules setup for now to focus on Bengali database
            logger.info("✅ Business rules skipped - using Bengali database priority")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up business rules: {e}")
            return False
    
    def create_knowledge_base(self):
        """Create knowledge base from training data"""
        try:
            logger.info("📖 Creating knowledge base...")
            
            # Prepare knowledge documents
            knowledge_docs = []
            
            for item in self.training_data:
                # Create document for each Q&A pair
                doc_text = f"প্রশ্ন: {item['question']}\\nউত্তর: {item['answer']}"
                knowledge_docs.append({
                    'content': doc_text,
                    'metadata': {
                        'category': item['category'],
                        'language': 'bengali',
                        'type': 'qa_pair'
                    }
                })
            
            # Add to RAG store if available
            if (self.chatbot_system and 
                hasattr(self.chatbot_system, 'response_composer') and 
                self.chatbot_system.response_composer):
                
                composer = self.chatbot_system.response_composer
                
                # Store knowledge in response composer
                if not hasattr(composer, 'knowledge_base'):
                    composer.knowledge_base = []
                
                composer.knowledge_base.extend(knowledge_docs)
            
            logger.info(f"✅ Knowledge base created with {len(knowledge_docs)} documents")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating knowledge base: {e}")
            return False
    
    def test_trained_system(self):
        """Test the trained system with sample questions"""
        if not self.chatbot_system:
            logger.error("❌ Chatbot system not initialized")
            return False
        
        logger.info("🧪 Testing trained system...")
        
        # Test questions from training data
        test_questions = [
            "অর্ডার করবো কিভাবে?",
            "ডেলিভারি চার্জ কত?",
            "গ্যারান্টি আছে?",
            "কাস্টমার সাপোর্ট নাম্বার কত?",
            "প্রোডাক্ট কবে পাবো?"
        ]
        
        results = []
        for question in test_questions:
            try:
                response = self.chatbot_system.process_message(
                    user_id="trainer_test",
                    message=question,
                    channel="training"
                )
                
                results.append({
                    'question': question,
                    'response': response.get('response', 'No response'),
                    'success': response.get('success', False)
                })
                
                logger.info(f"✓ {question}")
                logger.info(f"  → {response.get('response', 'No response')[:100]}...")
                
            except Exception as e:
                logger.error(f"❌ Error testing '{question}': {e}")
                results.append({
                    'question': question,
                    'response': f"Error: {e}",
                    'success': False
                })
        
        success_rate = sum(1 for r in results if r['success']) / len(results) * 100
        logger.info(f"🎯 Test Success Rate: {success_rate:.1f}%")
        
        return results
    
    def run_full_training(self):
        """Run complete training pipeline"""
        logger.info("🚀 Starting BDStall AI Training Pipeline")
        logger.info("=" * 50)
        
        steps = [
            ("Loading Database Knowledge", self.load_database_knowledge),
            ("Setting up Chatbot System", self.setup_chatbot_system),
            ("Training Intent Recognition", self.train_intent_recognition),
            ("Setting up Business Rules", self.setup_business_rules), 
            ("Creating Knowledge Base", self.create_knowledge_base),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"🔄 {step_name}...")
            success = step_func()
            if not success:
                logger.error(f"❌ Failed at step: {step_name}")
                return False
            logger.info(f"✅ {step_name} completed")
        
        # Test the system
        logger.info("🧪 Testing trained system...")
        test_results = self.test_trained_system()
        
        # Training summary
        logger.info("=" * 50)
        logger.info("🎉 TRAINING COMPLETED!")
        logger.info("=" * 50)
        logger.info(f"📊 Training Data: {len(self.training_data)} Q&A pairs")
        logger.info(f"🌐 Language: Bengali (বাংলা)")
        logger.info(f"🎯 Test Success: {sum(1 for r in test_results if r['success'])}/{len(test_results)}")
        logger.info("=" * 50)
        logger.info("🚀 Your AI is ready! Start the chatbot with: python app.py")
        
        return True


def main():
    """Main training function"""
    trainer = BDStallAITrainer()
    success = trainer.run_full_training()
    
    if success:
        print("\\n🎉 AI Training Successful!")
        print("Your Bengali AI chatbot is now ready to use.")
        print("Run 'python app.py' to start the chatbot server.")
    else:
        print("\\n❌ Training Failed!")
        print("Check the logs above for error details.")


if __name__ == "__main__":
    main()