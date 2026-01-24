"""
Main Chatbot Logic
Handles conversation management and data integration with RAG
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import logging
from ai_model import QwenAIModel
from database_handler import DatabaseHandler
from rag_store import RAGStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdminChatbot:
    def __init__(
        self, 
        data_file: str = "data/admin_data.json", 
        csv_database: str = "database.csv",
        enable_rag: bool = True,
        rag_top_k: int = 3
    ):
        """
        Initialize the chatbot with AI model, RAG, and data
        
        Args:
            data_file: Path to JSON file containing admin data/context
            csv_database: Path to CSV file with Q&A database
            enable_rag: Whether to enable RAG retrieval
            rag_top_k: Number of documents to retrieve from RAG
        """
        self.data_file = data_file
        self.admin_context = ""
        self.conversation_history: Dict[str, List[Dict[str, str]]] = {}
        self.enable_rag = enable_rag
        self.rag_top_k = rag_top_k
        
        # Load CSV database (priority responses)
        logger.info("Loading CSV database...")
        self.database = DatabaseHandler(csv_database)
        
        # Initialize RAG store
        if self.enable_rag:
            logger.info("Initializing RAG store...")
            self.rag_store = RAGStore()
        else:
            self.rag_store = None
        
        # Load admin data
        self.load_admin_data()
        
        # Initialize AI model
        logger.info("Loading AI model...")
        self.ai_model = QwenAIModel()
        logger.info("Chatbot initialized successfully")
    
    def load_admin_data(self):
        """Load admin data from JSON file to use as context"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Convert data to context string
                self.admin_context = self._format_context(data)
                logger.info(f"Loaded admin data from {self.data_file}")
            else:
                logger.warning(f"Data file not found: {self.data_file}")
                self.admin_context = "No specific admin data loaded."
                
        except Exception as e:
            logger.error(f"Error loading admin data: {e}")
            self.admin_context = ""
    
    def _format_context(self, data: dict) -> str:
        """
        Format the admin data into a readable context string
        
        Args:
            data: Dictionary containing admin data
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        # Handle different data structures
        if "company_info" in data:
            context_parts.append(f"Company: {data['company_info']}")
        
        if "products" in data:
            products_str = "\n".join([f"- {p}" for p in data['products']])
            context_parts.append(f"Products/Services:\n{products_str}")
        
        if "faq" in data:
            faq_str = "\n".join([f"Q: {q['question']}\nA: {q['answer']}" 
                                for q in data['faq']])
            context_parts.append(f"FAQs:\n{faq_str}")
        
        if "policies" in data:
            context_parts.append(f"Policies: {data['policies']}")
        
        if "contact" in data:
            context_parts.append(f"Contact Info: {data['contact']}")
        
        # For any other data, just stringify it
        for key, value in data.items():
            if key not in ["company_info", "products", "faq", "policies", "contact"]:
                context_parts.append(f"{key}: {value}")
        
        return "\n\n".join(context_parts)
    
    def get_response(
        self, 
        user_id: str, 
        message: str,
        maintain_history: bool = True
    ) -> str:
        """
        Get AI response for a user message with RAG enhancement
        
        Args:
            user_id: Unique identifier for the user
            message: User's message
            maintain_history: Whether to maintain conversation history
            
        Returns:
            AI-generated response
        """
        try:
            # STEP 1: First check CSV database for exact/similar match
            db_response = self.database.search_database(message, threshold=0.7)
            
            if db_response:
                logger.info("Response from CSV database")
                self._log_conversation(user_id, message, db_response)
                return db_response
            
            # STEP 2: Retrieve relevant context from RAG store
            rag_context = ""
            if self.enable_rag and self.rag_store:
                logger.info("Retrieving context from RAG store...")
                rag_context = self.rag_store.get_context_for_query(
                    message, 
                    top_k=self.rag_top_k,
                    max_context_length=2000
                )
                
                if rag_context:
                    logger.info(f"Retrieved RAG context ({len(rag_context)} chars)")
            
            # STEP 3: Combine admin context with RAG context
            combined_context = self.admin_context
            if rag_context:
                combined_context += f"\n\nRelevant Information:\n{rag_context}"
            
            # STEP 4: Use AI model with enhanced context
            logger.info("Generating response with AI model (RAG-enhanced)")
            
            # Get or create conversation history for this user
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            history = self.conversation_history[user_id] if maintain_history else None
            
            # Generate response using AI model
            response = self.ai_model.generate_response(
                user_message=message,
                context=combined_context,
                conversation_history=history
            )
            
            # Update conversation history
            if maintain_history:
                self.conversation_history[user_id].append({
                    "role": "user",
                    "content": message
                })
                self.conversation_history[user_id].append({
                    "role": "assistant",
                    "content": response
                })
                
                # Keep only last 10 exchanges (20 messages)
                if len(self.conversation_history[user_id]) > 20:
                    self.conversation_history[user_id] = self.conversation_history[user_id][-20:]
            
            # Log conversation
            self._log_conversation(user_id, message, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again later."
    
    def _log_conversation(self, user_id: str, message: str, response: str):
        """Log conversation to file for record keeping"""
        try:
            log_dir = "logs"
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, f"conversations_{datetime.now().strftime('%Y-%m-%d')}.log")
            
            with open(log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n[{timestamp}] User {user_id}:\n")
                f.write(f"Message: {message}\n")
                f.write(f"Response: {response}\n")
                f.write("-" * 80 + "\n")
                
        except Exception as e:
            logger.error(f"Error logging conversation: {e}")
    
    def clear_history(self, user_id: str):
        """Clear conversation history for a specific user"""
        if user_id in self.conversation_history:
            self.conversation_history[user_id] = []
            logger.info(f"Cleared history for user {user_id}")
    
    def reload_data(self):
        """Reload admin data from file"""
        self.load_admin_data()
        self.database.reload_database()
        logger.info("Admin data and database reloaded")
    
    def add_documents_to_rag(
        self, 
        documents: List[str], 
        metadata: Optional[List[Dict]] = None
    ) -> int:
        """
        Add documents to RAG knowledge base
        
        Args:
            documents: List of document texts
            metadata: Optional metadata for each document
            
        Returns:
            Number of chunks added
        """
        if not self.enable_rag or not self.rag_store:
            logger.warning("RAG is not enabled")
            return 0
        
        return self.rag_store.add_documents(documents, metadata)
    
    def get_rag_stats(self) -> Dict:
        """Get RAG store statistics"""
        if not self.enable_rag or not self.rag_store:
            return {"enabled": False}
        
        stats = self.rag_store.get_stats()
        stats["enabled"] = True
        return stats
