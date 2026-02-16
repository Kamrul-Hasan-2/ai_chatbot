"""
Enhanced AI Model with Human-like Response Generation
Includes better prompting and multilingual support
"""
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from typing import List, Dict, Optional
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedQwenAIModel:
    def __init__(self, model_name: str = "Qwen/Qwen2-VL-2B-Instruct", device: str = None):
        """
        Initialize the Enhanced Qwen2-VL model with human-like response capabilities
        
        Args:
            model_name: HuggingFace model identifier
            device: Device to run model on ('cuda' or 'cpu'). Auto-detects if None
        """
        self.model_name = model_name
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Initializing enhanced model on device: {self.device}")
        
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
            logger.info("Enhanced model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def _detect_language(self, text: str) -> str:
        """
        Detect if text is primarily Bengali or English
        
        Args:
            text: Input text
            
        Returns:
            'bengali' or 'english'
        """
        # Count Bengali Unicode characters
        bengali_chars = sum(1 for char in text if '\u0980' <= char <= '\u09FF')
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return 'english'
        
        bengali_ratio = bengali_chars / total_chars
        return 'bengali' if bengali_ratio > 0.3 else 'english'
    
    def _create_system_prompt(self, language: str, response_style: str = 'friendly') -> str:
        """
        Create system prompt based on language and style
        
        Args:
            language: 'bengali' or 'english'
            response_style: 'friendly', 'professional', or 'casual'
            
        Returns:
            System prompt string
        """
        if language == 'bengali':
            if response_style == 'friendly':
                return \"\"\"আপনি একজন সহায়ক এবং বন্ধুত্বপূর্ণ কাস্টমার সার্ভিস প্রতিনিধি। 
আপনার কাজ হল গ্রাহকদের সাহায্য করা এবং তাদের প্রশ্নের উত্তর দেওয়া।

নির্দেশনা:
- সবসময় বিনয়ী এবং সহায়ক থাকুন
- প্রয়োজনে বাংলা এবং ইংরেজি উভয় ব্যবহার করুন
- সংক্ষিপ্ত এবং স্পষ্ট উত্তর দিন
- গ্রাহকের প্রশ্ন ভালোভাবে বুঝে উত্তর দিন
- যদি কোনো তথ্য না জানেন, সৎভাবে বলুন এবং কীভাবে সাহায্য পাওয়া যাবে তা জানান
- মানুষের মতো স্বাভাবিক ভাষা ব্যবহার করুন, রোবটের মতো নয়\"\"\"
            else:
                return \"\"\"আপনি একজন পেশাদার কাস্টমার সার্ভিস প্রতিনিধি। 
গ্রাহকদের প্রশ্নের সঠিক এবং সহায়ক উত্তর প্রদান করুন।\"\"\"
        else:
            if response_style == 'friendly':
                return \"\"\"You are a helpful and friendly customer service representative.
Your job is to  help customers and answer their questions warmly.

Guidelines:
- Always be polite and helpful
- Use both Bengali and English as needed
- Keep responses concise and clear
- Understand the customer's question well before responding
- If you don't know something, say so honestly and guide them on how to get help
- Use natural, human-like language, not robotic responses
- Show empathy and understanding
- Be conversational and engaging\"\"\"
            else:
                return \"\"\"You are a professional customer service representative.
Provide accurate and helpful responses to customer inquiries.\"\"\"
    
    def generate_response(
        self,
        user_message: str,
        context: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        response_style: str = "friendly",
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> str:
        """
        Generate a human-like response with enhanced prompting
        
        Args:
            user_message: The user's message
            context: Additional context (admin data, RAG results, etc.)
            conversation_history: Previous conversation turns
            response_style: 'friendly', 'professional', or 'casual'
            max_length: Maximum response length
            temperature: Sampling temperature (higher = more creative)
            top_p: Nucleus sampling parameter
            
        Returns:
            Generated response
        """
        try:
            # Detect language
            language = self._detect_language(user_message)
            logger.info(f"Detected language: {language}")
            
            # Create system prompt
            system_prompt = self._create_system_prompt(language, response_style)
            
            # Build conversation messages
            messages = []
            
            # Add system message
            messages.append({
                "role": "system",
                "content": system_prompt
            })
            
            # Add context if available
            if context:
                context_message = f\"\"\"Here is relevant information to help answer the question:

{context}

Use this information to provide an accurate and helpful response.\"\"\"
                messages.append({
                    "role": "system",
                    "content": context_message
                })
            
            # Add conversation history
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 5 exchanges
                    messages.append(msg)
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Prepare input
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
            
            # Generate with enhanced parameters for human-like responses
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_length,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    repetition_penalty=1.2,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            ).strip()
            
            # Post-process response
            response = self._post_process_response(response, language)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            if language == 'bengali':
                return \"দুঃখিত, আমি এই মুহূর্তে আপনার প্রশ্নের উত্তর দিতে পারছি না। দয়া করে আবার চেষ্টা করুন।\"
            else:
                return \"I apologize, but I'm having trouble processing your request right now. Please try again.\"
    
    def _post_process_response(self, response: str, language: str) -> str:
        """
        Post-process the generated response for better quality
        
        Args:
            response: Generated response
            language: Detected language
            
        Returns:
            Post-processed response
        """
        # Remove extra whitespace
        response = re.sub(r'\s+', ' ', response).strip()
        
        # Remove incomplete sentences at the end
        sentences = response.split('।') if language == 'bengali' else response.split('.')
        if sentences and len(sentences[-1].strip()) < 5:
            response = '।'.join(sentences[:-1]) + '।' if language == 'bengali' else '.'.join(sentences[:-1]) + '.'
        
        # Ensure proper ending
        if language == 'bengali':
            if not response.endswith(('।', '?', '!')):
                response += '।'
        else:
            if not response.endswith(('.', '?', '!')):
                response += '.'
        
        return response
    
    def generate_batch_responses(
        self,
        messages: List[str],
        context: str = "",
        **kwargs
    ) -> List[str]:
        """
        Generate responses for multiple messages
        
        Args:
            messages: List of user messages
            context: Shared context for all messages
            **kwargs: Additional arguments for generate_response
            
        Returns:
            List of generated responses
        """
        responses = []
        for msg in messages:
            response = self.generate_response(msg, context=context, **kwargs)
            responses.append(response)
        return responses


if __name__ == "__main__":
    # Test the enhanced model
    print("Testing Enhanced AI Model...")
    model = EnhancedQwenAIModel()
    
    # Test Bengali
    test_msg_bn = "আপনাদের কাছে কি iPhone আছে?"
    print(f"\\nBengali Test:\\nUser: {test_msg_bn}")
    response = model.generate_response(test_msg_bn)
    print(f"Bot: {response}")
    
    # Test English
    test_msg_en = "Do you have iPhone available?"
    print(f"\\nEnglish Test:\\nUser: {test_msg_en}")
    response = model.generate_response(test_msg_en)
    print(f"Bot: {response}")
