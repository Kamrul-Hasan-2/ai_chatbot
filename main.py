
from core.intent_service import detect_intent
from core.context_service import load_context_api, save_message_api
from core.merge_service import merge_context
from handlers.router import route_intent

def process_message(user_id, message):
    prev_context = load_context_api(user_id)

    intent_data = detect_intent(message)

    merged = merge_context(intent_data.get("entities", {}), prev_context)

    response = route_intent(intent_data.get("intent"), merged, prev_context, message)

    save_message_api(user_id, message, intent_data.get("intent"), merged)

    return response
