"""
Run on the server to test the seller-request API directly:
  python test_seller_api.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import requests
from models.chatbot_config import API_KEY, SELLER_REQUEST_URL

print("=== Seller Request API Test ===")
print(f"URL  : {SELLER_REQUEST_URL}")
print(f"KEY  : {API_KEY[:6]}***")

payload = {
    'key':    API_KEY,
    'name':   'Test User',
    'mobile': '01700000000',
    'note':   'Test note - direct API call from server',
}

try:
    resp = requests.post(SELLER_REQUEST_URL, json=payload, timeout=15)
    print(f"HTTP : {resp.status_code}")
    print(f"BODY : {resp.text[:500]}")
    if 200 <= resp.status_code < 300:
        print("RESULT: SUCCESS - API works from server")
    else:
        print("RESULT: FAIL - API returned non-2xx status")
except Exception as e:
    print(f"RESULT: FAIL - Exception: {e}")
