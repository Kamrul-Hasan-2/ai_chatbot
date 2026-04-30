"""
External API interactions for SimpleChatbot.
Covers: responder check, agent/bot assignment, product search, delivery template,
        and chat-history fetching.
"""
import os
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from .chatbot_config import _log_api_call
from .flow_helpers import normalize_history_messages, parse_template_response, extract_budget_range

logger = logging.getLogger(__name__)


class ApiClient:
    """Wraps all outbound HTTP calls used by SimpleChatbot."""

    def __init__(self, api_key: str, api_url: str, delivery_intent_api_url: str,
                 assign_agent_api_url: str, assign_agent_api_key: str,
                 assign_bot_api_url: str, responder_api_url: str,
                 responder_api_key: str, chatbot_history_api_url: str,
                 chatbot_history_limit: int) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.delivery_intent_api_url = delivery_intent_api_url
        self.assign_agent_api_url = assign_agent_api_url
        self.assign_agent_api_key = assign_agent_api_key
        self.assign_bot_api_url = assign_bot_api_url
        self.responder_api_url = responder_api_url
        self.responder_api_key = responder_api_key
        self.chatbot_history_api_url = chatbot_history_api_url
        self.chatbot_history_limit = chatbot_history_limit

        self._search_cache: Dict[str, Tuple[float, Dict]] = {}
        self._search_cache_ttl = 300
        self._search_cache_max = 200
        self._history_cache: Dict[str, Tuple[float, str]] = {}
        self._history_cache_ttl = 60

    # ─────────────────────────────────────────────────────────────
    # Responder / mode
    # ─────────────────────────────────────────────────────────────
    def check_responder_type(self, user_id: str) -> Optional[str]:
        now = time.time()
        try:
            url = f"{self.responder_api_url}?key={self.responder_api_key}&user_id={user_id}"
            resp = requests.get(url, timeout=3)
            duration_ms = int((time.time() - now) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') and data.get('data'):
                    label = data['data'].get('responder_label', 'bot')
                    _log_api_call(
                        'responder_type_check', 'GET', url,
                        {'user_id': user_id}, resp.status_code,
                        duration_ms, 'PASS',
                        json.dumps(data.get('data', {}), ensure_ascii=False)[:200]
                    )
                    return label
            return None
        except Exception as e:
            logger.warning("Responder check error: %s", e)
            return None

    def assign_agent(self, user_id: str, intent: str) -> None:
        try:
            started = datetime.now()
            payload = {
                'key': self.assign_agent_api_key,
                'user_id': user_id,
                'intent': intent,
            }
            resp = requests.post(self.assign_agent_api_url, json=payload, timeout=5)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                'assign_agent', 'POST', self.assign_agent_api_url,
                payload, resp.status_code, duration_ms,
                'PASS' if resp.status_code == 200 else 'FAIL',
                resp.text[:400] if resp.text else '',
            )
        except Exception as e:
            logger.warning("assign_agent call failed: %s", e)

    def assign_bot(self, user_id: str) -> None:
        try:
            requests.post(
                self.assign_bot_api_url,
                json={'key': self.api_key, 'user_id': user_id},
                timeout=5
            )
        except Exception as e:
            logger.warning("assign_bot failed: %s", e)

    # ─────────────────────────────────────────────────────────────
    # Product search
    # ─────────────────────────────────────────────────────────────
    def cached_search(self, keywords: str, max_price: Optional[int] = None,
                      min_price: Optional[int] = None) -> Dict[str, Any]:
        cache_key = f"{keywords}|{min_price or ''}|{max_price or ''}"
        now = time.time()
        cached = self._search_cache.get(cache_key)
        if cached and (now - cached[0]) < self._search_cache_ttl:
            return cached[1]
        result = self._do_search(keywords, max_price, min_price)
        self._search_cache[cache_key] = (now, result)
        if len(self._search_cache) > self._search_cache_max:
            oldest = min(self._search_cache.keys(), key=lambda k: self._search_cache[k][0])
            self._search_cache.pop(oldest, None)
        return result

    def _do_search(self, keywords: str, explicit_max_price: Optional[int] = None,
                   explicit_min_price: Optional[int] = None) -> Dict[str, Any]:
        try:
            params = {
                'term': keywords.strip(),
                'key': self.api_key,
                'minPrice': explicit_min_price or '',
                'maxPrice': explicit_max_price or '',
            }
            started = datetime.now()
            response = requests.get(self.api_url, params=params, timeout=10)
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call('ai_search', 'GET', self.api_url, params,
                          response.status_code, duration_ms,
                          "PASS" if response.status_code == 200 else "FAIL",
                          response.text[:400])
            if response.status_code != 200:
                return {'products_found': 0, 'products': []}

            data = response.json()
            if not data.get('getListingItem') or len(data['getListingItem']) < 2:
                return {'products_found': 0, 'products': []}

            total_count = data['getListingItem'][0]
            products_array = data['getListingItem'][1] or []
            if not products_array:
                return {'products_found': 0, 'products': []}

            top = products_array[:5]
            products_list = [{
                'title': p.get('ListingTitle', 'N/A'),
                'price': p.get('ListingPrice', 'N/A'),
                'original_price': p.get('app_ListingOriginalPrice', ''),
                'discount': p.get('ListingDiscountPercentage', 0),
                'url': p.get('ListingURL', ''),
                'image': p.get('ListingThumbAvator', ''),
            } for p in top]

            return {
                'products_found': len(top),
                'total_products': total_count,
                'products': products_list,
            }
        except Exception as e:
            logger.error("Search failed: %s", e)
            return {'products_found': 0, 'products': []}

    # ─────────────────────────────────────────────────────────────
    # Chat history
    # ─────────────────────────────────────────────────────────────
    def get_history_cached(self, user_id: str) -> str:
        now = time.time()
        cached = self._history_cache.get(user_id)
        if cached and (now - cached[0]) < self._history_cache_ttl:
            return cached[1]
        ctx = self._fetch_recent_chat_context(user_id, self.chatbot_history_limit)
        self._history_cache[user_id] = (now, ctx)
        return ctx

    def _fetch_recent_chat_context(self, user_id: str, limit: int = 5) -> str:
        if not user_id:
            return ''
        safe_limit = max(1, min(int(limit or 5), 20))
        urls = self.build_chat_history_urls(user_id, safe_limit)
        for url in urls:
            try:
                resp = requests.get(url, timeout=8)
                if not (200 <= resp.status_code < 300):
                    continue
                payload = resp.json() if resp.text else {}
                lines = normalize_history_messages(payload)
                return '\n'.join(lines).strip()
            except Exception:
                continue
        return ''

    def build_chat_history_urls(self, user_id: str, limit: int) -> list:
        base = str(self.chatbot_history_api_url or '').strip()
        if not base:
            return []
        tail = f"user_id={user_id}&limit={limit}&key={self.api_key}"
        return [f"{base.rstrip('/')}?{tail}"]

    def fetch_intent_content_from_db(self, user_id: str) -> Dict:
        """Pull the last saved intent_content from the chat history API (Rule 14)."""
        try:
            urls = self.build_chat_history_urls(user_id, 10)
            for url in urls:
                try:
                    logger.info("[INTENT_DB] Fetching: %s", url)
                    resp = requests.get(url, timeout=2)
                    logger.info("[INTENT_DB] Response: status=%s len=%s",
                                resp.status_code, len(resp.text))
                    if not (200 <= resp.status_code < 300):
                        continue
                    data = resp.json() if resp.text else {}
                    candidates: list = []
                    if isinstance(data, list):
                        candidates = data
                    elif isinstance(data, dict):
                        for k in ['data', 'messages', 'history',
                                  'chat_history', 'conversation', 'result']:
                            v = data.get(k)
                            if isinstance(v, list):
                                candidates = v
                                break
                    for item in reversed(candidates):
                        if not isinstance(item, dict):
                            continue
                        if str(item.get('sender_type') or '').strip() != '2':
                            continue
                        ic = item.get('intent_content')
                        if isinstance(ic, str):
                            try:
                                ic = json.loads(ic)
                            except Exception:
                                continue
                        if isinstance(ic, dict) and (
                            ic.get('cat') or ic.get('brand')
                            or ic.get('title') or ic.get('product_url')
                        ):
                            logger.info("[INTENT_DB] Restored for %s: cat=%s brand=%s title=%s",
                                        user_id, ic.get('cat'), ic.get('brand'), ic.get('title'))
                            return ic
                except Exception:
                    continue
        except Exception as e:
            logger.warning("fetch_intent_content_from_db failed: %s", e)
        return {}

    # ─────────────────────────────────────────────────────────────
    # Delivery template
    # ─────────────────────────────────────────────────────────────
    def fetch_delivery_intent_response(self) -> Optional[str]:
        try:
            resp = requests.get(
                self.delivery_intent_api_url,
                params={'intent': 'delivery', 'key': self.api_key},
                timeout=10
            )
            if resp.status_code != 200:
                return None
            return parse_template_response(resp.json() if resp.text else {})
        except Exception as e:
            logger.warning("delivery template failed: %s", e)
            return None

    # ─────────────────────────────────────────────────────────────
    # Budget helper (delegated from flow)
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def extract_budget_range(message: str) -> Dict[str, Optional[int]]:
        return extract_budget_range(message)
