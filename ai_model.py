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
            system_prompt = "You are a helpful AI assistant representing an admin. "
            
            if context:
                # Check if context contains RAG-retrieved information
                if "Relevant Information:" in context or "[Source" in context:
                    system_prompt += (
                        "Use the following information to answer the user's question accurately. "
                        "If the information provided contains the answer, use it. "
                        "If the provided information is not relevant or insufficient, "
                        "use your general knowledge to provide a helpful response.\n\n"
                        f"{context}\n\n"
                        "Base your response primarily on the information above when relevant. "
                    )
                else:
                    # Regular context without RAG
                    system_prompt += f"Here is important information you should know:\n{context}\n\n"
            
            system_prompt += (
                "Reply professionally and helpfully to user messages. "
                "Be concise and accurate. If you reference information from the provided sources, "
                "you can mention that you're using available knowledge to assist them."
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
