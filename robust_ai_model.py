"""
Enhanced AI Model with Fallback Options
Provides graceful fallbacks when Groq API fails
"""
import logging
from typing import Optional, List, Dict
import os
from groq_model import GroqAIModel

logger = logging.getLogger(__name__)

class RobustAIModel:
    """AI model with multiple fallback options"""
    
    def __init__(self):
        self.groq_model = None
        self.api_working = False
        self.consecutive_failures = 0
        
        # Try to initialize Groq
        try:
            api_key = os.getenv('GROQ_API_KEY')
            if api_key:
                self.groq_model = GroqAIModel(api_key=api_key)
                self.api_working = True
                logger.info("✅ Groq API initialized successfully")
            else:
                logger.warning("⚠️ Groq API key not configured")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Groq: {e}")
            
    def generate_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """Generate response with fallback options"""
        
        # Try Groq API first if available
        if self.api_working and self.groq_model and self.consecutive_failures < 3:
            try:
                logger.debug("Trying Groq API...")
                response = self.groq_model.generate_response(
                    user_message=user_message,
                    context=context,
                    conversation_history=conversation_history,
                    **kwargs
                )
                
                # Check if it's the quota exceeded message
                if "আমাদের সার্ভার মোমেন্টে ব্যস্ত আছে" not in response:
                    self.consecutive_failures = 0  # Reset on success
                    return response
                else:
                    raise Exception("API quota exceeded")
                    
            except Exception as e:
                self.consecutive_failures += 1
                logger.warning(f"Groq API failed (attempt {self.consecutive_failures}): {e}")
                
                if self.consecutive_failures >= 3:
                    self.api_working = False
                    logger.error("❌ Groq API marked as unavailable after 3 failures")
        
        # Use intelligent fallback responses
        return self._get_smart_fallback_response(user_message, context)
    
    def _get_smart_fallback_response(self, user_message: str, context: Optional[str] = None) -> str:
        """Generate intelligent fallback responses"""
        message_lower = user_message.lower()
        
        # Greeting responses
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'সালাম', 'আসসালামু']):
            return "আসসালামু আলাইকুম! আমি BDStall এর সহায়ক। আপনাকে কিভাবে সাহায্য করতে পারি? 😊"
        
        # Product inquiry responses
        elif any(word in message_lower for word in ['laptop', 'computer', 'পিসি']):
            return "আমাদের কাছে বিভিন্ন ব্র্যান্ডের ল্যাপটপ আছে! আপনি কোন কাজের জন্য চান? অফিস, গেমিং নাকি স্টুডেন্ট ইউজ? 💻"
            
        elif any(word in message_lower for word in ['phone', 'mobile', 'smartphone', 'ফোন']):
            return "স্মার্টফোনের জন্য আমাদের কাছে সব ব্র্যান্ড আছে! আপনার বাজেট কত? ক্যামেরা ভালো লাগবে নাকি পারফরমেন্স বেশি দরকার? 📱"
            
        elif any(word in message_lower for word in ['stun', 'gun', 'security', 'সিকিউরিটি']):
            return "আমাদের কাছে সিকিউরিটি পণ্য আছে। আপনার প্রয়োজন অনুসারে বিভিন্ন অপশন আছে। বিস্তারিত জানতে কাস্টমার সার্ভিসে যোগাযোগ করুন। 🛡️"
            
        elif any(word in message_lower for word in ['price', 'দাম', 'কত', 'টাকা']):
            return "পণ্যের দাম জানতে আপনি আমাদের ওয়েবসাইট check করতে পারেন অথবা কাস্টমার সার্ভিসে call করুন। 📞"
            
        elif any(word in message_lower for word in ['delivery', 'ডেলিভারি', 'পৌঁছাবে']):
            return "আমাদের সব এলাকায় delivery আছে! সাধারণত ২-৩ দিনের মধ্যে পৌঁছে যায়। 🚚"
            
        elif any(word in message_lower for word in ['available', 'stock', 'আছে', 'পাওয়া']):
            return "পণ্যের availability জানতে আমাদের website দেখুন অথবা hotline এ যোগাযোগ করুন: ০১৭xxxxxxxx 📱"
            
        elif any(word in message_lower for word in ['return', 'exchange', 'ফেরত']):
            return "৭ দিনের মধ্যে original packaging সহ ফেরত দিতে পারবেন। শর্ত apply হবে। 📦"
            
        elif any(word in message_lower for word in ['support', 'help', 'সাহায্য', 'সহায্য']):
            return "আমাদের কাস্টমার সার্ভিস টিম ২ৄ/৭ available! Facebook page বা hotline এ যোগাযোগ করুন। 🛠️"
            
        # Default response for unrecognized queries
        else:
            return f"আপনার প্রশ্ন বুঝতে পেরেছি। আমাদের কাছে ইলেকট্রনিক্স, ফ্যাশন, হোম অ্যাপ্লায়েন্স সব পণ্য আছে। নির্দিষ্ট কিছু খুঁজছেন? আমাদের ওয়েবসাইট দেখুন বা কল করুন। 📞"
    
    def get_system_status(self) -> Dict[str, any]:
        """Get current system status"""
        return {
            "groq_api_working": self.api_working,
            "consecutive_failures": self.consecutive_failures,
            "fallback_mode": not self.api_working
        }