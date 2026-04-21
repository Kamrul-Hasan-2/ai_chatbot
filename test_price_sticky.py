from src.core.simple_chatbot_flow import SimpleChatbot

c = SimpleChatbot()
uid = 'u_price_sticky'

# First message: 'hp laptop 10k'
print('=== Message 1: hp laptop 10k ===')
r1 = c.process_message(uid, 'hp laptop 10k')
print(f'intent_content: {r1.get("intent_content")}')
print(f'price extracted: {r1.get("intent_content", {}).get("price")}')

# Second message: 'dekhan 30k der ta' (trying to mention 30k)
print('\n=== Message 2: dekhan 30k der ta ===')
r2 = c.process_message(uid, 'dekhan 30k der ta')
print(f'intent_content: {r2.get("intent_content")}')
print(f'price (should still be 10k): {r2.get("intent_content", {}).get("price")}')
print(f'Expected: 10k, Actual: {r2.get("intent_content", {}).get("price")}')

# Third message: '20-30k der ta' (different price range)
print('\n=== Message 3: 20-30k der ta ===')
r3 = c.process_message(uid, '20-30k der ta')
print(f'intent_content: {r3.get("intent_content")}')
print(f'price (should still be 10k): {r3.get("intent_content", {}).get("price")}')
print(f'Expected: 10k, Actual: {r3.get("intent_content", {}).get("price")}')
