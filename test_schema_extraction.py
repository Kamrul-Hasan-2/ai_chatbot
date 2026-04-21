from src.core.simple_chatbot_flow import SimpleChatbot

c = SimpleChatbot()

messages = [
    'hp laptop 10k',
    'dekhan 30k der ta',
    '20-30k der ta',
]

for msg in messages:
    schema = c._extract_intent_schema(msg)
    price_text = c._extract_price_text_for_intent(msg)
    print(f"\nMessage: '{msg}'")
    print(f"  Schema price: {schema.get('price')}")
    print(f"  Price from text: {price_text}")
    print(f"  Schema title: {schema.get('title')}")
