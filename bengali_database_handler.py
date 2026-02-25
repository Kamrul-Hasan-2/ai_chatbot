"""
Enhanced Bengali Database Handler
Integrates with BDStall Chatbot System and prioritizes Bengali responses
"""
import pandas as pd
import json
import logging
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BengaliDatabaseHandler:
    def __init__(self, csv_file: str = "database.csv"):
        """Initialize Bengali-focused database handler"""
        self.csv_file = csv_file
        self.qa_pairs = []
        self.categories = {}
        self.bengali_patterns = []
        self.load_database()
        self.setup_bengali_matching()
    
    def load_database(self):
        """Load and process database with Bengali support"""
        try:
            logger.info(f"📚 Loading database from {self.csv_file}...")
            
            # Read CSV with proper encoding for Bengali
            df = pd.read_csv(self.csv_file, encoding='utf-8')
            
            processed_count = 0
            
            for index, row in df.iterrows():
                try:
                    # Get question and answer from first two columns
                    question = str(row.iloc[0]).strip()
                    answer = str(row.iloc[1]).strip()
                    
                    # Skip empty or header rows
                    if (question and answer and 
                        question not in ['প্রশ্ন', 'প্রশ্ন ', 'nan'] and
                        answer not in ['উত্তর', 'উত্তর ', 'nan']):
                        
                        # Clean the text
                        question = self.clean_bengali_text(question)
                        answer = self.clean_bengali_text(answer)
                        
                        # Categorize the Q&A pair
                        category = self.categorize_question(question, answer)
                        
                        qa_pair = {
                            'id': processed_count,
                            'question': question,
                            'answer': answer,
                            'category': category,
                            'language': self.detect_language(question),
                            'keywords': self.extract_keywords(question),
                            'priority': self.calculate_priority(question, answer)
                        }
                        
                        self.qa_pairs.append(qa_pair)
                        
                        # Group by category
                        if category not in self.categories:
                            self.categories[category] = []
                        self.categories[category].append(qa_pair)
                        
                        processed_count += 1
                        
                except Exception as e:
                    logger.debug(f"Skipping row {index}: {e}")
                    continue
            
            logger.info(f"✅ Loaded {len(self.qa_pairs)} Q&A pairs")
            logger.info(f"📂 Categories: {list(self.categories.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error loading database: {e}")
    
    def clean_bengali_text(self, text: str) -> str:
        """Clean Bengali text for better processing"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\\s+', ' ', text.strip())
        
        # Remove special characters that might cause issues
        text = text.replace('\\n', ' ').replace('\\r', ' ')
        
        # Remove URLs if present (keep only domain)
        url_pattern = r'https?://[^\\s]+'
        text = re.sub(url_pattern, '[লিংক]', text)
        
        return text
    
    def detect_language(self, text: str) -> str:
        """Detect if text is primarily Bengali or English"""
        if not text:
            return "bengali"
        
        # Count Bengali characters
        bengali_chars = len(re.findall(r'[\\u0980-\\u09FF]', text))
        total_chars = len([c for c in text if c.isalpha()])
        
        if total_chars == 0:
            return "bengali"
        
        bengali_ratio = bengali_chars / total_chars
        
        return "bengali" if bengali_ratio > 0.3 else "mixed"
    
    def categorize_question(self, question: str, answer: str) -> str:
        """Categorize questions for better matching"""
        q_lower = question.lower()
        a_lower = answer.lower()
        
        # Delivery related FIRST (includes romanized Bengali) - Check before pricing since both can have "কত"
        if any(word in q_lower for word in ['ডেলিভারি', 'delivery', 'পৌঁছাবে', 'পৌঁছায়', 'shipping']):
            if any(word in q_lower for word in ['কবে', 'কত দিন', 'কত', 'koy din', 'koto din', 'koto', 'lagbe', 'ashbe', 'somoy', 'din', 'দিন', 'সময়']):
                return 'delivery'
        
        # Pricing related (includes romanized Bengali)
        if any(word in q_lower for word in ['দাম', 'প্রাইস', 'price', 'কত', 'টাকা', 'cost', 'dam', 'taka', 'koto', 'budget', 'বাজেট', 'kom budget', 'affordable', 'সাশ্রয়ী']):
            return 'pricing'
        
        # Ordering related (includes romanized Bengali)
        elif any(word in q_lower for word in ['অর্ডার', 'order', 'কিভাবে', 'কিনব', 'buy', 'purchase', 'kibabe', 'kivabe', 'kemne', 'korbo']):
            return 'ordering'
        
        # Stock related (includes romanized Bengali)
        elif any(word in q_lower for word in ['স্টক', 'stock', 'available', 'আছে', 'পাওয়া যাবে', 'ache', 'pawa', 'jabe']):
            return 'availability'
        
        # Support related (includes romanized Bengali)
        elif any(word in q_lower for word in ['customer', 'support', 'নাম্বার', 'number', 'যোগাযোগ', 'contact', 'phone', 'call']):
            return 'support'
        
        # Warranty/Guarantee
        elif any(word in q_lower for word in ['গ্যারান্টি', 'warranty', 'guarantee', 'গ্যারান্টী', 'guaranty']):
            return 'warranty'
        
        # Product inquiry
        elif any(word in q_lower for word in ['প্রোডাক্ট', 'product', 'আইটেম', 'item', 'জিনিস', 'jinish']):
            return 'product_inquiry'
        
        # Greeting (includes romanized Bengali)
        elif any(word in q_lower for word in ['hi', 'hello', 'হাই', 'হ্যালো', 'আসসালামু', 'সালাম', 'assalamu', 'salam']):
            return 'greeting'
        
        else:
            return 'general'
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text"""
        if not text:
            return []
        
        # Bengali stopwords (common words to ignore)
        bengali_stopwords = {
            'এর', 'এই', 'ওই', 'তার', 'তাদের', 'আমার', 'আমাদের', 'তুমি', 'তোমার', 
            'আপনি', 'আপনার', 'সে', 'তারা', 'আমি', 'আমরা', 'কি', 'কী', 'কে', 'কেন',
            'কোথায়', 'কখন', 'কিভাবে', 'কতটা', 'কত', 'হয়', 'হবে', 'ছিল', 'আছে',
            'থাকে', 'দেয়', 'নেয়', 'করে', 'করা', 'হওয়া', 'যাওয়া', 'আসা'
        }
        
        # Split text and extract meaningful words
        words = re.findall(r'[\\w\\u0980-\\u09FF]+', text.lower())
        keywords = []
        
        for word in words:
            if (len(word) > 2 and 
                word not in bengali_stopwords and 
                not word.isdigit()):
                keywords.append(word)
        
        return keywords[:10]  # Return top 10 keywords
    
    def calculate_priority(self, question: str, answer: str) -> int:
        """Calculate priority score for Q&A pairs"""
        priority = 1
        
        # Higher priority for common inquiries
        high_priority_words = ['অর্ডার', 'delivery', 'ডেলিভারি', 'দাম', 'price']
        if any(word in question.lower() for word in high_priority_words):
            priority += 2
        
        # Higher priority for complete answers
        if len(answer) > 100:
            priority += 1
        
        # Higher priority for Bengali content
        if self.detect_language(question) == "bengali":
            priority += 1
        
        return priority
    
    def setup_bengali_matching(self):
        """Setup Bengali-specific text matching patterns"""
        self.bengali_patterns = [
            # Question patterns
            (r'(কিভাবে|কেমনে).*([অর্ডার|কিনব|কিনতে])', 'ordering'),
            (r'(কত|কতো).*([দাম|টাকা|প্রাইস])', 'pricing'),
            (r'(কবে|কত দিন).*([পাবো|আসবে|ডেলিভারি])', 'delivery'),
            (r'(আছে|পাওয়া যাবে).*([স্টক|প্রোডাক্ট])', 'availability'),
            (r'(নাম্বার|ফোন|যোগাযোগ)', 'support'),
            (r'(গ্যারান্টি|ওয়ারেন্টি)', 'warranty'),
        ]
        
        # Romanized Bengali patterns
        self.romanized_patterns = {
            # Ordering patterns
            'kibabe order korbo': 'অর্ডার করবো কিভাবে ?',
            'kivabe order korbo': 'অর্ডার করবো কিভাবে ?', 
            'kemne order korbo': 'অর্ডার করবো কিভাবে ?',
            'order kivabe korbo': 'অর্ডার করবো কিভাবে ?',
            'order korbo kivabe': 'অর্ডার করবো কিভাবে ?',
            'order ?': 'অর্ডার করবো কিভাবে ?',
            'order': 'অর্ডার করবো কিভাবে ?',
            
            # Delivery time patterns
            'koy din delivery': 'Delivery dite koto din lagbe',
            'koto din delivery': 'Delivery dite koto din lagbe', 
            'koy din er modde delivery': 'Delivery dite koto din lagbe',
            'koto din er modde delivery hoy': 'Delivery dite koto din lagbe',
            'koy din er modde delivery hoy': 'Delivery dite koto din lagbe',
            'delivery time': 'Delivery dite koto din lagbe',
            'delivery koto din': 'Delivery dite koto din lagbe',
            'koto din lagbe': 'Delivery dite koto din lagbe',
            
            # Price patterns
            'dam koto': 'দাম কত',
            'price koto': 'দাম কত',
            'koto taka': 'দাম কত',
            
            # Stock/availability
            'ache naki': 'স্টক আছে',
            'stock ache': 'স্টক আছে',
            
            # Support
            'number': 'Customer Support Number ?',
            'contact number': 'Customer Support Number ?',
            'phone number': 'Customer Support Number ?',
        }
    
    def normalize_romanized_bengali(self, text: str) -> str:
        """Convert romanized Bengali to proper Bengali or standardized form"""
        text_lower = text.lower().strip()
        
        # Check for direct romanized patterns
        for romanized, bengali in self.romanized_patterns.items():
            if romanized in text_lower:
                return bengali
        
        # Partial matching for flexibility
        best_match = None
        best_score = 0
        
        for romanized, bengali in self.romanized_patterns.items():
            # Check if key words from romanized pattern exist in text
            romanized_words = set(romanized.split())
            text_words = set(text_lower.split())
            
            if romanized_words:
                overlap = len(romanized_words.intersection(text_words))
                score = overlap / len(romanized_words)
                
                if score > 0.5 and score > best_score:  # At least 50% word match
                    best_score = score
                    best_match = bengali
        
        return best_match if best_match else text
    
    def calculate_similarity_bengali(self, text1: str, text2: str) -> float:
        """Enhanced similarity calculation for Bengali text with romanization support"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize text
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # Try to normalize romanized Bengali first
        normalized_t1 = self.normalize_romanized_bengali(t1)
        if normalized_t1 != t1:
            t1 = normalized_t1.lower().strip()
        
        # Exact match
        if t1 == t2:
            return 1.0
        
        # Check substring matching
        if t1 in t2 or t2 in t1:
            return 0.9
            
        # Enhanced keyword matching for mixed language
        score_components = []
        
        # 1. Direct keyword overlap
        keywords1 = set(self.extract_keywords(t1))
        keywords2 = set(self.extract_keywords(t2))
        
        if keywords1 and keywords2:
            keyword_overlap = len(keywords1.intersection(keywords2))
            total_keywords = len(keywords1.union(keywords2))
            keyword_score = keyword_overlap / total_keywords if total_keywords > 0 else 0
            score_components.append((keyword_score, 0.4))
        
        # 2. Cross-language keyword matching (English <-> Bengali)
        cross_lang_score = self.calculate_cross_language_similarity(t1, t2)
        if cross_lang_score > 0:
            score_components.append((cross_lang_score, 0.3))
        
        # 3. Sequence similarity
        sequence_score = SequenceMatcher(None, t1, t2).ratio()
        score_components.append((sequence_score, 0.2))
        
        # 4. Semantic similarity for common patterns
        semantic_score = self.calculate_semantic_similarity(t1, t2)
        if semantic_score > 0:
            score_components.append((semantic_score, 0.1))
        
        # Calculate weighted average
        if score_components:
            total_weight = sum(weight for _, weight in score_components)
            final_score = sum(score * weight for score, weight in score_components) / total_weight
        else:
            final_score = sequence_score
        
        return final_score
    
    def calculate_cross_language_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between English/Romanized and Bengali text"""
        # Common word translations
        translations = {
            'order': ['অর্ডার', 'order'],
            'delivery': ['ডেলিভারি', 'delivery'],
            'price': ['দাম', 'প্রাইস', 'price'],
            'how': ['কিভাবে', 'কেমনে'],
            'when': ['কবে', 'কখন'],
            'how much': ['কত', 'কতো'],
            'day': ['দিন', 'din'], 
            'time': ['সময়', 'time'],
            'available': ['আছে', 'পাওয়া যাবে'],
            'stock': ['স্টক', 'stock'],
            'number': ['নাম্বার', 'number', 'নম্বর'],
            'customer': ['কাস্টমার', 'customer'],
            'support': ['সাপোর্ট', 'support']
        }
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        matches = 0
        total_concepts = len(translations)
        
        for concept, translations_list in translations.items():
            found_in_1 = any(trans in ' '.join(words1) for trans in translations_list)
            found_in_2 = any(trans in ' '.join(words2) for trans in translations_list)
            
            if found_in_1 and found_in_2:
                matches += 1
        
        return matches / total_concepts if total_concepts > 0 else 0
    
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity for common question patterns"""
        # Question pattern matching
        patterns = {
            'ordering': ['order', 'অর্ডার', 'কিনব', 'করবো', 'কিভাবে'],
            'delivery_time': ['delivery', 'ডেলিভারি', 'কত দিন', 'সময়', 'lagbe', 'হয়'],
            'pricing': ['price', 'দাম', 'কত', 'টাকা', 'taka'],
            'availability': ['stock', 'স্টক', 'আছে', 'পাওয়া'], 
            'support': ['number', 'নাম্বার', 'support', 'customer']
        }
        
        def get_pattern_type(text):
            text_lower = text.lower()
            for pattern_type, keywords in patterns.items():
                if any(keyword in text_lower for keyword in keywords):
                    return pattern_type
            return None
        
        pattern1 = get_pattern_type(text1)
        pattern2 = get_pattern_type(text2)
        
        if pattern1 and pattern2 and pattern1 == pattern2:
            return 0.7  # High semantic similarity for same pattern type
        elif pattern1 and pattern2:
            return 0.0  # Different patterns
        else:
            return 0.0  # No clear pattern
    
    def search_database(self, user_message: str, threshold: float = 0.6) -> Dict:
        """Enhanced search with Bengali support and categorization"""
        if not self.qa_pairs:
            return {
                'success': False,
                'message': 'Database not loaded',
                'response': 'দুঃখিত, ডাটাবেস লোড হয়নি।'
            }
        
        logger.info(f"🔍 Searching for: {user_message}")
        
        # Detect category first
        user_category = self.categorize_question(user_message, "")
        
        best_matches = []
        
        # Search through all Q&A pairs
        for qa_pair in self.qa_pairs:
            similarity = self.calculate_similarity_bengali(
                user_message, 
                qa_pair['question']
            )
            
            # Boost score if category matches
            if qa_pair['category'] == user_category:
                similarity += 0.1
            
            # Boost score for higher priority items
            similarity += (qa_pair['priority'] - 1) * 0.05
            
            if similarity >= threshold:
                best_matches.append({
                    'qa_pair': qa_pair,
                    'similarity': similarity,
                    'category': qa_pair['category']
                })
        
        # Sort by similarity score
        best_matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        if best_matches:
            best_match = best_matches[0]
            qa_pair = best_match['qa_pair']
            
            logger.info(f"✅ Found match: {qa_pair['question']}")
            logger.info(f"📊 Similarity: {best_match['similarity']:.2f}")
            logger.info(f"📂 Category: {best_match['category']}")
            
            return {
                'success': True,
                'response': qa_pair['answer'],
                'category': qa_pair['category'],
                'similarity': best_match['similarity'],
                'question_matched': qa_pair['question']
            }
        
        # No match found
        logger.info(f"❌ No match found (threshold: {threshold})")
        
        # Return category-based fallback
        fallback_response = self.get_category_fallback(user_category)
        
        return {
            'success': False,
            'response': fallback_response,
            'category': user_category,
            'similarity': 0.0,
            'message': 'No direct match found'
        }
    
    def get_category_fallback(self, category: str) -> str:
        """Get fallback response based on category"""
        fallback_responses = {
            'pricing': 'দাম জানতে চাইলে আমাদের ওয়েবসাইট দেখুন অথবা কাস্টমার সার্ভিসে যোগাযোগ করুন।',
            'ordering': 'অর্ডার করতে আমাদের ওয়েবসাইটে যান অথবা ফোন করুন।',
            'delivery': 'ডেলিভারি সংক্রান্ত তথ্যের জন্য আমাদের সাথে যোগাযোগ করুন।',
            'availability': 'পণ্যের স্টক জানতে আমাদের ওয়েবসাইট চেক করুন।',
            'support': 'কাস্টমার সার্ভিস: 01612378255',
            'warranty': 'গ্যারান্টি সংক্রান্ত বিস্তারিত জানতে আমাদের সাথে যোগাযোগ করুন।',
            'product_inquiry': 'পণ্য সংক্রান্ত তথ্যের জন্য আমাদের ওয়েবসাইট দেখুন।',
            'greeting': 'আসসালামু আলাইকুম! কিভাবে সাহায্য করতে পারি?',
            'general': 'আরও তথ্যের জন্য আমাদের সাথে যোগাযোগ করুন।'
        }
        
        return fallback_responses.get(category, 'দুঃখিত, এই বিষয়ে আমি নিশ্চিত নই। আমাদের কাস্টমার সার্ভিসে যোগাযোগ করুন।')
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        stats = {
            'total_qa_pairs': len(self.qa_pairs),
            'categories': {cat: len(pairs) for cat, pairs in self.categories.items()},
            'language_distribution': {},
            'avg_answer_length': 0
        }
        
        if self.qa_pairs:
            # Language distribution
            languages = [qa['language'] for qa in self.qa_pairs]
            for lang in set(languages):
                stats['language_distribution'][lang] = languages.count(lang)
            
            # Average answer length
            answer_lengths = [len(qa['answer']) for qa in self.qa_pairs]
            stats['avg_answer_length'] = sum(answer_lengths) / len(answer_lengths)
        
        return stats


def test_database_handler():
    """Test the Bengali database handler"""
    print("🧪 Testing Bengali Database Handler")
    print("=" * 40)
    
    handler = BengaliDatabaseHandler()
    
    # Show statistics
    stats = handler.get_statistics()
    print(f"📊 Total Q&A pairs: {stats['total_qa_pairs']}")
    print(f"📂 Categories: {list(stats['categories'].keys())}")
    
    # Test queries
    test_queries = [
        "অর্ডার করবো কিভাবে?",
        "ডেলিভারি চার্জ কত?", 
        "গ্যারান্টি আছে?",
        "কাস্টমার সার্ভিস নাম্বার?",
        "প্রোডাক্ট কবে পাবো?"
    ]
    
    print("\\n🔍 Testing Queries:")
    for query in test_queries:
        result = handler.search_database(query)
        print(f"\\n❓ {query}")
        print(f"✅ {result['response']}")
        print(f"📊 Similarity: {result.get('similarity', 0):.2f}")
    
    print("\\n✅ Test completed!")


if __name__ == "__main__":
    test_database_handler()