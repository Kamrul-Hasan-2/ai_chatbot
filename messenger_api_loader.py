"""
Messenger API Data Loader
Fetches and processes conversation data from messenger API
"""
import requests
import json
import logging
from typing import List, Dict, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessengerAPILoader:
    def __init__(self, api_url: str):
        """
        Initialize Messenger API loader
        
        Args:
            api_url: URL of the messenger API endpoint
        """
        self.api_url = api_url
        self.conversations = []
        self.training_pairs = []
    
    def fetch_data(self) -> bool:
        """
        Fetch conversation data from API
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Fetching data from: {self.api_url}")
            response = requests.get(self.api_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success') and 'data' in data:
                self.conversations = data['data']
                logger.info(f"Successfully fetched {len(self.conversations)} conversations")
                return True
            else:
                logger.error("API response does not contain expected data")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {e}")
            return False
    
    def process_conversations(self) -> List[Tuple[str, str]]:
        """
        Process conversations into user-admin message pairs
        
        Returns:
            List of (user_message, admin_response) tuples
        """
        training_pairs = []
        
        for user_id, messages in self.conversations.items():
            if not isinstance(messages, list):
                continue
            
            # Extract conversation pairs
            for i in range(len(messages) - 1):
                current_msg = messages[i]
                next_msg = messages[i + 1]
                
                # Look for user message followed by admin response
                if 'user_message' in current_msg and 'response' in next_msg:
                    user_msg = current_msg['user_message'].strip()
                    admin_resp = next_msg['response'].strip()
                    
                    # Filter out empty or very short messages
                    if len(user_msg) > 2 and len(admin_resp) > 2:
                        # Skip automated greetings
                        if not self._is_automated_message(admin_resp):
                            training_pairs.append((user_msg, admin_resp))
        
        self.training_pairs = training_pairs
        logger.info(f"Processed {len(training_pairs)} user-admin message pairs")
        return training_pairs
    
    def _is_automated_message(self, message: str) -> bool:
        """
        Check if message is an automated greeting
        
        Args:
            message: Message text to check
            
        Returns:
            True if automated, False otherwise
        """
        automated_phrases = [
            "We've received your question",
            "আপনার মেসেজ এর জন্য ধন্যবাদ",
            "replied to your automated welcome message",
            "Please let us know how we can help you"
        ]
        
        return any(phrase in message for phrase in automated_phrases)
    
    def extract_common_queries(self) -> Dict[str, List[str]]:
        """
        Extract and categorize common user queries
        
        Returns:
            Dictionary of query categories with examples
        """
        categories = {
            'product_inquiry': [],
            'price_inquiry': [],
            'availability': [],
            'delivery': [],
            'order_status': [],
            'general': []
        }
        
        for user_msg, _ in self.training_pairs:
            user_msg_lower = user_msg.lower()
            
            # Categorize based on keywords
            if any(word in user_msg_lower for word in ['price', 'দাম', 'koto', 'টাকা']):
                categories['price_inquiry'].append(user_msg)
            elif any(word in user_msg_lower for word in ['available', 'stock', 'আছে', 'ache']):
                categories['availability'].append(user_msg)
            elif any(word in user_msg_lower for word in ['delivery', 'পাঠা', 'কত দিন', 'কখন পাব']):
                categories['delivery'].append(user_msg)
            elif any(word in user_msg_lower for word in ['order', 'অর্ডার', 'কিনব']):
                categories['order_status'].append(user_msg)
            elif any(word in user_msg_lower for word in ['product', 'phone', 'laptop', 'প্রডাক্ট']):
                categories['product_inquiry'].append(user_msg)
            else:
                categories['general'].append(user_msg)
        
        return categories
    
    def save_training_data(self, output_file: str = "data/messenger_training.json"):
        """
        Save processed training data to JSON file
        
        Args:
            output_file: Path to output JSON file
        """
        import os
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        training_data = {
            'metadata': {
                'source': self.api_url,
                'total_conversations': len(self.conversations),
                'training_pairs': len(self.training_pairs),
                'processed_at': datetime.now().isoformat()
            },
            'conversations': [
                {
                    'user_message': user_msg,
                    'admin_response': admin_resp
                }
                for user_msg, admin_resp in self.training_pairs
            ],
            'query_categories': self.extract_common_queries()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Training data saved to: {output_file}")
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the loaded data
        
        Returns:
            Dictionary with statistics
        """
        total_user_messages = sum(
            1 for messages in self.conversations.values()
            if isinstance(messages, list)
            for msg in messages
            if 'user_message' in msg
        )
        
        total_admin_responses = sum(
            1 for messages in self.conversations.values()
            if isinstance(messages, list)
            for msg in messages
            if 'response' in msg
        )
        
        categories = self.extract_common_queries()
        
        return {
            'total_conversations': len(self.conversations),
            'total_user_messages': total_user_messages,
            'total_admin_responses': total_admin_responses,
            'training_pairs': len(self.training_pairs),
            'query_categories': {k: len(v) for k, v in categories.items()}
        }


def main():
    """Main function to fetch and process messenger API data"""
    
    # Initialize loader
    api_url = "https://ai.bdstall.com/rest_api/item/chatbot_grouped?limit=1000"
    loader = MessengerAPILoader(api_url)
    
    # Fetch data
    if not loader.fetch_data():
        logger.error("Failed to fetch data from API")
        return
    
    # Process conversations
    loader.process_conversations()
    
    # Save training data
    loader.save_training_data()
    
    # Print statistics
    stats = loader.get_statistics()
    print("\n=== Messenger API Data Statistics ===")
    print(f"Total Conversations: {stats['total_conversations']}")
    print(f"Total User Messages: {stats['total_user_messages']}")
    print(f"Total Admin Responses: {stats['total_admin_responses']}")
    print(f"Training Pairs: {stats['training_pairs']}")
    print("\nQuery Categories:")
    for category, count in stats['query_categories'].items():
        print(f"  {category}: {count}")
    print("=" * 40)


if __name__ == "__main__":
    main()
