"""
Fallback response handler for when Gemini API is unavailable
Provides simple, intelligent responses based on keywords
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FallbackResponder:
    """Provides fallback responses when API is unavailable"""
    
    def __init__(self):
        self.responses = {
            # Greetings
            ('হ্যালো', 'আলাইকুম', 'নমস্কার', 'হাই'): "আসসালামু আলাইকুম! 👋 স্বাগতম BDStall.com এ। আমি কীভাবে আপনাকে সাহায্য করতে পারি?",
            
            # Order related
            ('অর্ডার', 'কিনব', 'কিনতে', 'কেনাকাটা'): "অর্ডার করা খুবই সহজ! 😊 আপনি অ্যাপ বা ওয়েবসাইট থেকে পণ্য নির্বাচন করুন এবং চেকআউট করুন। ✓",
            
            # Delivery
            ('ডেলিভারি', 'পাঠান', 'কখন আসবে'): "আমরা ঢাকায় ২৪ ঘণ্টার মধ্যে এবং দেশব্যাপী ৩-৫ দিনে ডেলিভারি দিই। 🎁",
            
            # Payment
            ('পেম্যান্ট', 'পে', 'টাকা', 'মূল্য'): "আমরা সকল ধরনের পেমেন্ট গ্রহণ করি - ক্যাশ অন ডেলিভারি, অনলাইন পেমেন্ট এবং আরও অনেক কিছু। 💳",
            
            # Return/Refund
            ('রিটার্ন', 'রিফান্ড', 'পরিবর্তন', 'রেটুর্ন'): "আপনি পণ্য পাওয়ার ৭ দিনের মধ্যে রিটার্ন বা এক্সচেঞ্জ করতে পারবেন। 🔄",
            
            # Support
            ('সাপোর্ট', 'সমস্যা', 'সাহায্য', 'যোগাযোগ'): "আমাদের সাপোর্ট টিম ২৪/৭ উপলব্ধ। আপনি ফোন, ইমেইল বা চ্যাটে আমাদের সাথে যোগাযোগ করতে পারেন। 📞",
            
            # Product info
            ('পণ্য', 'পণ্যের', 'কি আছে', 'কী পাই'): "আমাদের কাছে ইলেকট্রনিক্স, পোশাক, খাদ্য এবং আরও অনেক কিছু আছে। কোন পণ্যের তথ্য চান? 🛍️",
        }
    
    def get_response(self, user_message: str) -> Optional[str]:
        """
        Get a fallback response based on message keywords
        
        Args:
            user_message: The user's message
            
        Returns:
            A response string if keywords match, None otherwise
        """
        user_message_lower = user_message.lower()
        
        # Check keywords
        for keywords, response in self.responses.items():
            for keyword in keywords:
                if keyword in user_message_lower:
                    logger.info(f"Fallback response matched keyword: {keyword}")
                    return response
        
        # Default response if no keywords match
        return "আমাদের একজন বিশেষজ্ঞ শীঘ্রই আপনার সাথে যোগাযোগ করবে। ধন্যবাদ! 🙏"
