
import requests
from config import BASE_URL, API_KEY

def load_context_api(user_id):
    try:
        url = BASE_URL + "chatbot_history/"
        params = {"user_id": user_id, "limit": 5, "key": API_KEY}
        res = requests.get(url, params=params, timeout=5).json()

        if res.get("success"):
            return res["user_info"].get("intent_content", {})
    except:
        pass

    return {}

def save_message_api(user_id, message, intent, context):
    try:
        url = BASE_URL + "chatbot_save_message/"
        payload = {
            "user_id": user_id,
            "message": message,
            "intent": intent,
            "intent_content": context,
            "key": API_KEY
        }
        requests.post(url, data=payload, timeout=5)
    except:
        pass
