"""
CSV Database Handler
Loads and searches the database.csv for matching responses
"""
import csv
import os
from difflib import SequenceMatcher
from typing import Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseHandler:
    def __init__(self, csv_file: str = "database.csv"):
        """
        Initialize database handler
        
        Args:
            csv_file: Path to CSV file with questions and answers
        """
        self.csv_file = csv_file
        self.database = []
        self.load_database()
    
    def load_database(self):
        """Load Q&A pairs from CSV file"""
        try:
            if not os.path.exists(self.csv_file):
                logger.warning(f"Database file not found: {self.csv_file}")
                return
            
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                for row in reader:
                    if len(row) >= 2 and row[0].strip() and row[1].strip():
                        question = row[0].strip()
                        answer = row[1].strip()
                        self.database.append({
                            'question': question,
                            'answer': answer
                        })
            
            logger.info(f"Loaded {len(self.database)} Q&A pairs from database")
            
        except Exception as e:
            logger.error(f"Error loading database: {e}")
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Convert to lowercase for comparison
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Direct match
        if text1 == text2:
            return 1.0
        
        # Check if one contains the other
        if text1 in text2 or text2 in text1:
            return 0.9
        
        # Calculate sequence similarity
        return SequenceMatcher(None, text1, text2).ratio()
    
    def search_database(
        self, 
        user_message: str, 
        threshold: float = 0.7
    ) -> Optional[str]:
        """
        Search database for matching question
        
        Args:
            user_message: User's message/question
            threshold: Minimum similarity threshold (0.0-1.0)
            
        Returns:
            Answer from database if match found, None otherwise
        """
        if not self.database:
            return None
        
        best_match = None
        best_score = 0.0
        
        # Search through all questions
        for entry in self.database:
            similarity = self.calculate_similarity(
                user_message, 
                entry['question']
            )
            
            if similarity > best_score:
                best_score = similarity
                best_match = entry
        
        # Return answer if similarity is above threshold
        if best_score >= threshold:
            logger.info(f"Database match found! Score: {best_score:.2f}")
            logger.info(f"Question: {best_match['question']}")
            return best_match['answer']
        
        logger.info(f"No database match. Best score: {best_score:.2f}")
        return None
    
    def reload_database(self):
        """Reload database from file"""
        self.database = []
        self.load_database()
