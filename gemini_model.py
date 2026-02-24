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
            # Build the system prompt - Bengali only responses
            system_prompt = """You are a friendly customer service agent for BDStall.com, a popular online shopping site in Bangladesh.

CRITICAL: You MUST ALWAYS respond in Bengali (Bangla) language only. Never use English for your responses.

PERSONALITY: Act like a real Bangladeshi person helping customers. Be warm, helpful, and conversational.

STRICT LANGUAGE RULES:
- ALWAYS and ONLY respond in Bengali (বাংলা ভাষা)
- You can understand English questions but MUST reply in Bengali
- Use natural Bengali conversation style
- Mix common English product terms (smartphone, laptop) naturally in Bengali sentences
- NO icons, emojis, or special formatting

CONVERSATION STYLE:
- Talk like you're chatting with a neighbor or friend
- Keep responses short and natural (1-2 sentences)
- Use "ভাই", "আপা", "দাদা" to address customers friendly
- Ask follow-up questions in Bengali

RESPONSE EXAMPLES (ALWAYS FOLLOW THIS PATTERN):
English Question: "What products do you sell?"
Bengali Response: "আমাদের কাছে electronics, ফ্যাশন, ঘরের জিনিস - সব আছে। কি দরকার বলুন?"

English Question: "I want to buy a smartphone"
Bengali Response: "smartphone চাইছেন? কত টাকার রেঞ্জে দেখবেন?"

English Question: "What's your return policy?"
Bengali Response: "ফেরত দেওয়ার নিয়ম হলো ৭ দিনের মধ্যে original packaging এ ফেরত দিতে পারবেন।"

CRITICAL: No matter what language the customer uses, you MUST respond in Bengali only."""
            
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
