from src.core.simple_chatbot_flow import SimpleChatbot

c = SimpleChatbot()
uid = 'u_intent_check'

messages = [
    'hp laptop 10k',
    'dekhan 30k der ta',
    '20-30k der ta'
]

for msg in messages:
    r = c.process_message(uid, msg)
    print(f"Message: '{msg}'")
    print(f"  Intent: {r.get('intent')}")
    print(f"  Response: {r.get('response')[:50]}...")
    print()
