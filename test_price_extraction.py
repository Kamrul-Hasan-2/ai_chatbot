from src.core.simple_chatbot_flow import SimpleChatbot

c = SimpleChatbot()

# Test price extraction
messages = [
    'hp laptop 10k',
    'dekhan 30k der ta',
    '20-30k der ta',
    '20-30k modde ase'
]

for msg in messages:
    price = c._extract_price_text_for_intent(msg)
    print(f"Message: '{msg}' → Price extracted: '{price}'")
