"""
TYPO CORRECTOR - Optional Enhancement
Provides explicit spell-checking for product searches
Improves robustness for severe typos like "lptpp"

This is optional - your system already handles most typos well!
But use this for extra confidence.
"""

import difflib
import logging
from typing import List, Tuple, Optional, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TypoCorrector:
    """Spell-check and typo correction for product searches"""
    
    def __init__(self):
        """Initialize with common product keywords"""
        self.product_keywords = {
            # Electronics
            'laptop': ['lapto', 'laptap', 'laptpp', 'labtop', 'lpatop', 'latop'],
            'mouse': ['mous', 'moose', 'muse', 'mice', 'mouze'],
            'keyboard': ['keyboar', 'keybord', 'keybaord', 'keybodard'],
            'headphone': ['heaphone', 'headfone', 'hedphone', 'headfone'],
            'webcam': ['webca', 'web cam', 'webcma', 'webkam'],
            'monitor': ['moniter', 'montor', 'monitr'],
            'printer': ['print', 'printr', 'priner', 'prnter'],
            'speaker': ['speakr', 'speker', 'spreaker'],
            'router': ['ruter', 'routr', 'routere'],
            'tablet': ['tabet', 'table', 'tablit', 'talbet'],
            'charger': ['chargr', 'chager', 'charger', 'chager'],
            'cable': ['cabel', 'cabl', 'kabul'],
            'adapter': ['adaptr', 'adpter', 'adaptere'],
            'battery': ['batry', 'battry', 'batter'],
            'microphone': ['mic', 'microfone', 'micropohone'],
            'earphone': ['earfone', 'earphon', 'airphone'],
            'wireless': ['wireles', 'wireless', 'wireles'],
            'gaming': ['gamin', 'gamming', 'gamng'],
            'smartphone': ['smartfone', 'smartpohne', 'smartfon'],
            'camera': ['camer', 'camra', 'kamera'],
            'display': ['displya', 'display'],
            'screen': ['scren', 'screan', 'scream'],
            'fan': ['fann', 'phan'],
            'cooler': ['culer', 'coolar'],
            'heatsink': ['heatsync', 'heatsink'],
            'motherboard': ['mothaboard', 'motherborad'],
            'graphics card': ['graphic card', 'grafics card'],
            'power supply': ['powersupply', 'power suply'],
            'cpu': ['cpi', 'cpu processor'],
            'ram': ['rimm', 'ram memory'],
            'ssd': ['sdd', 'ssd storage'],
            'hdd': ['hd', 'hard drive'],
        }
        
        # Build reverse lookup for fuzzy matching
        self.all_keywords = list(self.product_keywords.keys())
        for variations in self.product_keywords.values():
            self.all_keywords.extend(variations)
    
    def suggest_corrections(self, text: str, num_suggestions: int = 1) -> List[str]:
        """
        Suggest corrections using difflib
        
        Args:
            text: Input text with potential typos
            num_suggestions: Number of suggestions to return
            
        Returns:
            List of suggested corrections
        """
        # Split text into words
        words = text.lower().split()
        corrected_words = []
        corrections_made = False
        
        for word in words:
            # Try to find close matches
            close_matches = difflib.get_close_matches(
                word,
                self.all_keywords,
                n=1,
                cutoff=0.6  # 60% similarity threshold
            )
            
            if close_matches and close_matches[0] != word:
                corrected_words.append(close_matches[0])
                corrections_made = True
                logger.info(f"Typo detected: '{word}' → '{close_matches[0]}'")
            else:
                corrected_words.append(word)
        
        corrected_text = ' '.join(corrected_words)
        return [corrected_text] if corrections_made else [text]
    
    def batch_correct_text(self, text: str, strategy: str = 'auto') -> Tuple[str, Dict]:
        """
        Correct typos using specified strategy
        
        Args:
            text: Input text
            strategy: 'strict', 'lenient', or 'auto'
                - strict: Only correct high-confidence matches (cutoff=0.8)
                - lenient: Correct any similarity > 0.6 (cutoff=0.6)
                - auto: Use lenient if text is short, strict if long
        
        Returns:
            Tuple of (corrected_text, metadata)
        """
        cutoff = 0.6
        
        if strategy == 'strict':
            cutoff = 0.8
        elif strategy == 'lenient':
            cutoff = 0.6
        elif strategy == 'auto':
            # Short text is likely a product name - be lenient
            cutoff = 0.65 if len(text) < 20 else 0.75
        
        words = text.lower().split()
        corrected_words = []
        corrections = []
        
        for word in words:
            close_matches = difflib.get_close_matches(
                word,
                self.all_keywords,
                n=1,
                cutoff=cutoff
            )
            
            if close_matches:
                corrected_word = close_matches[0]
                corrected_words.append(corrected_word)
                if corrected_word != word:
                    corrections.append({
                        'original': word,
                        'corrected': corrected_word,
                        'similarity': difflib.SequenceMatcher(None, word, corrected_word).ratio()
                    })
            else:
                corrected_words.append(word)
        
        result = {
            'original': text,
            'corrected': ' '.join(corrected_words),
            'corrections_found': len(corrections),
            'corrections': corrections,
            'strategy': strategy
        }
        
        return ' '.join(corrected_words), result
    
    def is_likely_typo(self, word: str, threshold: float = 0.7) -> bool:
        """
        Check if a word is likely a typo
        
        Args:
            word: Word to check
            threshold: Similarity threshold
            
        Returns:
            True if word appears to be a typo
        """
        # Exact match - not a typo
        if word.lower() in self.all_keywords:
            return False
        
        # Check if close to any known keyword
        close_matches = difflib.get_close_matches(
            word.lower(),
            self.all_keywords,
            n=1,
            cutoff=threshold
        )
        
        return len(close_matches) > 0
    
    def correct_with_feedback(self, text: str) -> Dict:
        """
        Correct typos and provide detailed feedback
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with correction details
        """
        corrected, details = self.batch_correct_text(text, strategy='auto')
        
        return {
            'success': True,
            'input': text,
            'output': corrected,
            'has_corrections': len(details['corrections']) > 0,
            'corrections': details['corrections'],
            'confidence': (
                (len(text) - len(details['corrections'])) / len(text) 
                if len(text) > 0 else 1.0
            ),
            'recommended_action': 'CORRECT_NOW' if len(details['corrections']) > 0 else 'USE_AS_IS',
            'details': details
        }


# ============================================================================
# INTEGRATION WITH GROQ 3-STEP SEARCH
# ============================================================================

def integrate_typo_corrector_into_groq_3step():
    """
    Example of how to integrate TypoCorrector into groq_3step_search.py
    
    Add this to _step1_groq_intent_detection() method:
    """
    
    code_example = '''
    def _step1_groq_intent_detection_with_typo_check(self, user_message: str) -> Dict:
        """
        STEP 1: Check for typos, then detect intent with Groq
        """
        # NEW: Spell-check the input first
        typo_corrector = TypoCorrector()
        spell_check = typo_corrector.correct_with_feedback(user_message)
        
        if spell_check['has_corrections']:
            logger.info(f"⚠️ Typo detected: {user_message}")
            logger.info(f"✓ Corrected to: {spell_check['output']}")
            corrected_message = spell_check['output']
        else:
            corrected_message = user_message
        
        # THEN: Send corrected message to Groq
        if not self.groq:
            return {
                'success': True,
                'intent': 'product_search',
                'search_terms': corrected_message,
                'confidence': 0.5,
                'method': 'fallback',
                'typo_correction': spell_check
            }
        
        # ... rest of Groq processing with corrected_message ...
    '''
    
    return code_example


# ============================================================================
# TEST CASES
# ============================================================================

def test_typo_corrector():
    """Test the typo corrector with various inputs"""
    
    corrector = TypoCorrector()
    
    test_cases = [
        ("laptpp", "Double letter typo"),
        ("wireles mouse", "Missing letter"),
        ("headfone", "Wrong letter"),
        ("hp lapto", "Incomplete word"),
        ("gamin mouse", "Missing letter"),
        ("smartfone", "Wrong letter"),
        ("web cma", "Transposed letters"),
        ("printer", "Correct - no typo"),
        ("keyboard", "Correct - no typo"),
    ]
    
    print("\n" + "="*80)
    print("TYPO CORRECTOR TEST")
    print("="*80 + "\n")
    
    for text, description in test_cases:
        print(f"Input: '{text}' ({description})")
        
        result = corrector.correct_with_feedback(text)
        
        print(f"Output: '{result['output']}'")
        print(f"Has Corrections: {result['has_corrections']}")
        
        if result['corrections']:
            for corr in result['corrections']:
                print(f"  - '{corr['original']}' → '{corr['corrected']}' (similarity: {corr['similarity']:.1%})")
        
        print(f"Action: {result['recommended_action']}")
        print("-" * 80)


if __name__ == "__main__":
    test_typo_corrector()
    
    # Print integration example
    print("\n\nINTEGRATION EXAMPLE:\n")
    print(integrate_typo_corrector_into_groq_3step())
