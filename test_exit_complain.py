import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.core.simple_chatbot_flow import SimpleChatbot


def print_case(label, payload):
    ic = payload.get('intent_content') or {}
    print(f"{label}")
    print(f"  mode={payload.get('mode')} intent={payload.get('intent')}")
    print(f"  complain={ic.get('complain')} exit={ic.get('exit')}")
    print(f"  response={str(payload.get('response') or '')[:120]}")


def main():
    bot = SimpleChatbot()
    user_id = "test_exit_complain_user"

    # Product search should keep complain=false, exit=0
    r1 = bot.process_message(user_id, "dell laptop 30k")
    print_case("CASE 1: product search", r1)

    # Exit style message should set exit=1 and return the exact closing style
    r2 = bot.process_message(user_id, "see you later")
    print_case("CASE 2: exit message", r2)

    # Complaint/slang should trigger human mode and complain=true
    r3 = bot.process_message(user_id, "apnader service kharap, eta scam naki")
    print_case("CASE 3: complaint", r3)


if __name__ == "__main__":
    main()
