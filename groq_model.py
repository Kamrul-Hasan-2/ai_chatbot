"""
AI Model Handler for Groq API
Manages API interactions and inference with Groq's fast LLM models
"""
from groq import Groq
from typing import List, Dict, Optional
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GroqAIModel:
    def __init__(self, api_key: str = None, model_name: str = "llama-3.1-8b-instant"):
        """
        Initialize the Groq API model
        
        Args:
            api_key: Groq API key
            model_name: Model to use (llama3-8b-8192, llama3-70b-8192, mixtral-8x7b-32768, etc.)
        """
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        self.model_name = model_name
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not provided in environment or constructor")
        
        try:
            # Configure API client
            self.client = Groq(api_key=self.api_key)
            logger.info(f"Groq model {model_name} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Groq: {e}")
            raise
    
    def generate_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_length: int = 150,
        temperature: float = 0.6,
        top_p: float = 0.9
    ) -> str:
        """
        Generate a human-like response using Groq API
        
        Args:
            user_message: The user's input message
            context: Additional context (e.g., admin data, knowledge base)
            conversation_history: List of previous messages
            max_length: Maximum length of response tokens
            temperature: Sampling temperature (higher = more creative)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated response string
        """
        try:
            # Build the system prompt - Bengali only responses
            system_prompt = """You are a professional customer service representative for BDStall.com, Bangladesh's trusted online shopping platform.

CRITICAL RULES:
- ALWAYS respond in Bengali (বাংলা) language ONLY
- NEVER mention specific people's names or personal information
- Be professional, helpful, and courteous
- Keep responses relevant to the customer's query
- Focus on products, services, and shopping assistance

RESPONSE GUIDELINES:
- Use natural Bengali conversation
- Be specific and helpful about products/services
- Ask relevant follow-up questions
- Provide useful shopping guidance
- Use polite terms like "আপনি", "স্যার/ম্যাডাম"

PRODUCT ASSISTANCE:
- For product inquiries: Ask about budget, specifications, preferences
- For availability: Mention checking stock and delivery options
- For pricing: Guide to website or suggest contacting customer service
- For technical items: Ask about specific requirements

EXAMPLES:
Query: "stun gun"
Response: "আমাদের কাছে সিকিউরিটি পণ্য আছে। আপনার বাজেট কত? কোন ধরনের প্রয়োজন?"

Query: "hp laptop ase"
Response: "জি হ্যাঁ, HP ল্যাপটপ আছে! আপনি কোন কাজের জন্য চান? গেমিং, অফিস নাকি স্টুডেন্ট ব্যবহার?"

Query: "ki ase"
Response: "আমাদের কাছে ইলেকট্রনিক্স, ফ্যাশন, হোম অ্যাপ্লায়েন্স - সব ধরনের পণ্য আছে। আপনার কী প্রয়োজন?"

REMEMBER: Be helpful, professional, and focused on customer needs without personal references."""
            
            # Build context string
            context_text = ""
            if context:
                context_text = f"\n\nContext Information:\n{context}"
            
            # Build the full message
            full_message = f"{user_message}{context_text}"
            
            # Build messages for the API call
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 10 messages
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if content:
                        messages.append({
                            "role": "user" if role == "user" else "assistant",
                            "content": content
                        })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": full_message
            })
            
            logger.info(f"Sending request to Groq API (model: {self.model_name})")
            logger.debug(f"User message: {user_message}")
            
            # Call Groq API with better parameters
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_length,
                stream=False
            )
            
            if response and response.choices:
                result = response.choices[0].message.content.strip()
                logger.info("Response generated successfully")
                logger.debug(f"Response: {result}")
                return result
            else:
                logger.warning("Empty response from Groq API")
                return "দুঃখিত, আমি এখনই উত্তর দিতে পারছি না। দয়া করে একটু পরে চেষ্টা করুন। 🙏"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error generating response with Groq: {type(e).__name__}: {e}", exc_info=True)
            
            # Handle specific errors
            if "429" in error_msg or "rate_limit_exceeded" in error_msg.lower():
                logger.warning("Groq API rate limit exceeded - returning fallback response")
                return "আমাদের সার্ভার মোমেন্টে ব্যস্ত আছে। দয়া করে একটু পরে চেষ্টা করুন। আমাদের টিম সমস্যা সমাধানে কাজ করছে! 🔧"
            elif "invalid" in error_msg.lower() or "api key" in error_msg.lower():
                logger.error("Invalid API key or configuration")
                return "আমাদের সিস্টেমে কনফিগারেশন সমস্যা আছে। দয়া করে প্রশাসকের সাথে যোগাযোগ করুন। 📞"
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                logger.error(f"Model {self.model_name} not found")
                return "আমাদের AI সিস্টেম আপডেট হচ্ছে। দয়া করে একটু পরে চেষ্টা করুন। 🔄"
            else:
                # Generic error response
                return "দুঃখিত, আমি এখনই সেবা দিতে পারছি না। আমাদের সাপোর্ট টিম শীঘ্রই সাহায্য করবে। ⚙️"

    def get_available_models(self) -> List[str]:
        """Get list of available Groq models"""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return [
                "llama-3.1-8b-instant",
                "llama-3.1-70b-versatile", 
                "mixtral-8x7b-32768",
                "gemma-7b-it"
            ]

    def test_connection(self) -> bool:
        """Test if the API connection is working"""
        try:
            response = self.generate_response(
                user_message="test",
                max_length=10,
                temperature=0.1
            )
            return "দুঃখিত" not in response or "সার্ভার" not in response
        except Exception:
            return False