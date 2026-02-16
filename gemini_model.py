"""
AI Model Handler for Google Gemini API
Manages API interactions and inference with Gemini with human-like responses
"""
from google import genai
from typing import List, Dict, Optional
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiAIModel:
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the Gemini API model
        
        Args:
            api_key: Google Gemini API key
            model_name: Model to use (gemini-2.0-flash or gemini-1.5-pro)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model_name = model_name
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not provided in environment or constructor")
        
        try:
            # Configure API client
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini model {model_name} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise
    
    def generate_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_length: int = 512,
        temperature: float = 0.8,
        top_p: float = 0.95
    ) -> str:
        """
        Generate a human-like response using Gemini API
        
        Args:
            user_message: The user's input message
            context: Additional context (e.g., admin data, knowledge base)
            conversation_history: List of previous messages
            max_length: Maximum length of response (used as hint)
            temperature: Sampling temperature (higher = more creative)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated response string
        """
        try:
            # Build the system prompt - more conversational and human-like
            system_prompt = """You are a friendly and helpful AI assistant for BDStall.com, a Bangladeshi e-commerce platform.

Key Personality Traits:
- Warm, friendly, and conversational
- Helpful and patient with customers
- Professional but not robotic
- Use natural Bengali (Bangla) language
- Respond naturally as a real person would

Communication Guidelines:
1. ALWAYS respond in Bengali (Bangla) language
2. Use appropriate Bengali greetings: "আসসালামু আলাইকুম" or "হ্যালো"
3. Address customers respectfully with "স্যার/ভাই" (for male) or "আপা/ম্যাম" (for female)
4. Keep responses natural and conversational (2-3 sentences max)
5. Ask follow-up questions if needed to better understand customer needs
6. Use friendly emojis when appropriate (😊, ✓, 👍, 🙏)

Response Examples:
- Greeting: "আসসালামু আলাইকুম! 👋 স্বাগতম BDStall.com এ। আমি কীভাবে আপনাকে সাহায্য করতে পারি?"
- Product Info: "দারাজ, আমরা সেই পণ্য পাওয়া যায়। দাম এবং বিস্তারিত জানতে পণ্যের নাম বলুন। 😊"
- Order Help: "অর্ডার করা খুবই সহজ! আপনি অ্যাপ বা ওয়েবসাইট থেকে পণ্য নির্বাচন করুন এবং চেকআউট করুন। ✓"
- Not Sure: "আমি এই বিষয়ে নিশ্চিত নই। আমাদের একজন বিশেষজ্ঞ শীঘ্রই আপনার সাথে যোগাযোগ করবে। ধন্যবাদ! 🙏"

Important Notes:
- Be concise but helpful
- Show enthusiasm for helping customers
- If you don't know something, admit it honestly
- Make the customer feel valued and cared for
"""
            
            # Build context string
            context_text = ""
            if context:
                context_text = f"\n\nContext Information:\n{context}"
            
            # Build the full message
            full_message = f"{user_message}{context_text}"
            
            # Add conversation history for context if provided
            messages = []
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 10 messages
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if content:
                        messages.append({
                            "role": "user" if role == "user" else "model",
                            "parts": [{"text": content}]
                        })
            
            logger.info(f"Sending request to Gemini API (model: {self.model_name})")
            logger.debug(f"User message: {user_message}")
            
            # Call Gemini API with proper configuration
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [{"text": system_prompt}]
                    },
                    {
                        "role": "user",
                        "parts": [{"text": full_message}]
                    }
                ],
                config={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_output_tokens": max_length,
                }
            )
            
            if response and response.text:
                result = response.text.strip()
                logger.info("Response generated successfully")
                logger.debug(f"Response: {result}")
                return result
            else:
                logger.warning("Empty response from Gemini API")
                return "দুঃখিত, আমি এখনই উত্তর দিতে পারছি না। দয়া করে একটু পরে চেষ্টা করুন। 🙏"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error generating response with Gemini: {type(e).__name__}: {e}", exc_info=True)
            
            # Handle specific errors
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                logger.warning("Gemini API quota exceeded - returning fallback response")
                return "আমাদের সার্ভার মোমেন্টে ব্যস্ত আছে। দয়া করে একটু পরে চেষ্টা করুন। আমাদের টিম সমস্যা সমাধানে কাজ করছে! 🔧"
            elif "invalid_argument" in error_msg.lower() or "api key" in error_msg.lower():
                logger.error("Invalid API key or configuration")
                return "আমাদের সিস্টেমে কনফিগারেশন সমস্যা আছে। দয়া করে প্রশাসকের সাথে যোগাযোগ করুন। 📞"
            else:
                # Generic error response
                return "দুঃখিত, আমি এখনই সেবা দিতে পারছি না। আমাদের সাপোর্ট টিম শীঘ্রই সাহায্য করবে। ⚙️"
