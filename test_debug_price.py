from src.core.simple_chatbot_flow import SimpleChatbot

c = SimpleChatbot()
uid = 'u_debug_price'

# First message
print("=== Message 1: hp laptop 10k ===")
r1 = c.process_message(uid, 'hp laptop 10k')
print(f"Stored intent_content: {c.user_intent_content.get(uid)}")
print(f"Response intent_content: {r1.get('intent_content')}")

# Second message
print("\n=== Message 2: dekhan 30k der ta ===")
r2 = c.process_message(uid, 'dekhan 30k der ta')
print(f"Stored intent_content: {c.user_intent_content.get(uid)}")
print(f"Response intent_content: {r2.get('intent_content')}")
print(f"Price should be: 30k, Actual: {r2.get('intent_content', {}).get('price')}")

# Third message
print("\n=== Message 3: 20-30k der ta ===")
r3 = c.process_message(uid, '20-30k der ta')
print(f"Stored intent_content: {c.user_intent_content.get(uid)}")
print(f"Response intent_content: {r3.get('intent_content')}")
print(f"Price should be: 20-30k, Actual: {r3.get('intent_content', {}).get('price')}")
