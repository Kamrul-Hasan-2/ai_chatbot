"""
AI Model Handler for Qwen2-VL-2B-Instruct
Manages model loading and inference
"""
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QwenAIModel:
    def __init__(self, model_name: str = "Qwen/Qwen2-VL-2B-Instruct", device: str = None):
        """
        Initialize the Qwen2-VL model
        
        Args:
            model_name: HuggingFace model identifier
            device: Device to run model on ('cuda' or 'cpu'). Auto-detects if None
        """
        self.model_name = model_name
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Initializing model on device: {self.device}")
        
        try:
            # Load tokenizer and processor
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            self.processor = AutoProcessor.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            
            # Load model
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32,
                device_map="auto" if self.device == 'cuda' else None,
                trust_remote_code=True
            )
            
            if self.device == 'cpu':
                self.model = self.model.to(self.device)
            
            self.model.eval()
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def generate_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """
        Generate a response to the user message
        
        Args:
            user_message: The user's input message
            context: Additional context (e.g., admin data, knowledge base)
            conversation_history: List of previous messages [{"role": "user/assistant", "content": "..."}]
            max_length: Maximum length of generated response
            temperature: Sampling temperature (higher = more creative)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated response string
        """
        try:
            # Build conversation messages
            messages = []
            
            # Add system prompt with admin context and RAG instructions
            system_prompt = """You are a helpful AI customer support assistant for BDStall.com, a Bangladeshi e-commerce platform.

IMPORTANT INSTRUCTIONS:
1. ALWAYS respond in Bengali (Bangla) language
2. Be polite and professional
3. Use "স্যার" (Sir) or "ম্যাম" (Madam) to address customers
4. Keep responses short and helpful
5. If you don't have specific information, politely say you'll connect them with a representative

Response Guidelines:
- For greetings: Respond with "আসসালামু আলাইকুম" and ask how you can help
- For product inquiries: Politely ask for product name/model
- For pricing: Ask which product they're interested in
- For availability: Say "স্যার/ম্যাম, দয়া করে প্রোডাক্ট এর নাম বা ছবি দিন"
- For orders: Explain the order process in Bengali
- If unsure: "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবে।"

"""
            
            if context:
                # Check if context contains RAG-retrieved information
                if "Relevant Information:" in context or "[Source" in context:
                    system_prompt += (
                        "\n\nপ্রাসঙ্গিক তথ্য (Relevant Information):\n"
                        f"{context}\n\n"
                        "উপরের তথ্য ব্যবহার করে বাংলায় উত্তর দিন। যদি উপরের তথ্যে উত্তর না থাকে, তাহলে ভদ্রভাবে বলুন যে আপনি একজন প্রতিনিধির সাথে সংযুক্ত করবেন।"
                    )
                else:
                    # Regular context without RAG
                    system_prompt += f"Here is important information you should know:\n{context}\n\n"
            
                    system_prompt += f"\n\nকোম্পানির তথ্য:\n{context}\n\n"
            
            system_prompt += (
                "\nমনে রাখবেন: সবসময় বাংলায় উত্তর দিন এবং পেশাদার থাকুন। "
                "সংক্ষিপ্ত এবং সহায়ক উত্তর দিন।"
            )
            
            messages.append({
                "role": "system",
                "content": system_prompt
            })
            
            # Add conversation history if available
            if conversation_history:
                messages.extend(conversation_history[-5:])  # Keep last 5 messages for context
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Prepare input for model
            text = self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            ).to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_length,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            generated_text = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            )
            
            logger.info(f"Generated response: {generated_text[:100]}...")
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again."
    
    def unload_model(self):
        """Unload model from memory"""
        if hasattr(self, 'model'):
            del self.model
            del self.tokenizer
            del self.processor
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded successfully")
