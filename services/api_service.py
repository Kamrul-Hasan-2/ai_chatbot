
import requests
from config import BASE_URL, API_KEY

def search_products(context):
    try:
        url = BASE_URL + "chatbot_search/"
        params = {
            "category": context.get("cat"),
            "brand": context.get("brand"),
            "title": context.get("title"),
            "price": context.get("price"),
            "key": API_KEY
        }
        res = requests.get(url, params=params, timeout=5).json()
        return res.get("data", [])
    except:
        return []
