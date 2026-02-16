"""
Messenger Training Script
Loads messenger API data and trains the RAG store
"""
import logging
from messenger_api_loader import MessengerAPILoader
from rag_store import RAGStore
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessengerTrainer:
    def __init__(self, api_url: str):
        """
        Initialize messenger trainer
        
        Args:
            api_url: URL of messenger API endpoint
        """
        self.api_url = api_url
        self.loader = MessengerAPILoader(api_url)
        self.rag_store = RAGStore()
    
    def load_and_train(self) -> bool:
        """
        Load messenger data and train RAG store
        
        Returns:
            True if successful, False otherwise
        """
        # Fetch data from API
        logger.info("Fetching messenger conversation data...")
        if not self.loader.fetch_data():
            return False
        
        # Process conversations
        logger.info("Processing conversations...")
        training_pairs = self.loader.process_conversations()
        
        if not training_pairs:
            logger.error("No training pairs found")
            return False
        
        # Save training data
        self.loader.save_training_data()
        
        # Prepare documents for RAG
        logger.info("Preparing documents for RAG training...")
        documents = self._prepare_rag_documents(training_pairs)
        
        # Add to RAG store
        logger.info(f"Adding {len(documents)} documents to RAG store...")
        chunks_added = self.rag_store.add_documents(documents)
        logger.info(f"Successfully added {chunks_added} chunks to RAG store")
        
        # Save RAG index
        self.rag_store.save_index()
        
        return True
    
    def _prepare_rag_documents(self, training_pairs: List[tuple]) -> List[Dict]:
        """
        Prepare documents for RAG store from training pairs
        
        Args:
            training_pairs: List of (user_message, admin_response) tuples
            
        Returns:
            List of document dictionaries
        """
        documents = []
        
        for idx, (user_msg, admin_resp) in enumerate(training_pairs):
            # Create a Q&A document
            qa_text = f"User Question: {user_msg}\nAdmin Answer: {admin_resp}"
            
            documents.append({
                'content': qa_text,
                'metadata': {
                    'source': 'messenger_api',
                    'type': 'conversation',
                    'pair_id': idx,
                    'user_message': user_msg,
                    'admin_response': admin_resp
                }
            })
        
        return documents
    
    def get_training_stats(self) -> Dict:
        """Get statistics about training"""
        return self.loader.get_statistics()


def main():
    """Main function to train chatbot with messenger data"""
    
    print("=" * 60)
    print("Messenger API Chatbot Trainer")
    print("=" * 60)
    
    # API URL
    api_url = "https://ai.bdstall.com/rest_api/item/chatbot_grouped?limit=1000"
    
    # Initialize trainer
    trainer = MessengerTrainer(api_url)
    
    # Load and train
    print("\nStarting training process...")
    if trainer.load_and_train():
        print("\n✓ Training completed successfully!")
        
        # Print statistics
        stats = trainer.get_training_stats()
        print("\n" + "=" * 60)
        print("Training Statistics")
        print("=" * 60)
        print(f"Total Conversations: {stats['total_conversations']}")
        print(f"Total User Messages: {stats['total_user_messages']}")
        print(f"Total Admin Responses: {stats['total_admin_responses']}")
        print(f"Training Pairs Added: {stats['training_pairs']}")
        print("\nQuery Categories:")
        for category, count in stats['query_categories'].items():
            print(f"  • {category.replace('_', ' ').title()}: {count} queries")
        print("=" * 60)
        
        print("\n✓ RAG index saved successfully!")
        print("\nYour chatbot is now trained with real messenger conversations.")
        print("It will provide more human-like responses based on this data.")
    else:
        print("\n✗ Training failed. Please check the logs for errors.")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
