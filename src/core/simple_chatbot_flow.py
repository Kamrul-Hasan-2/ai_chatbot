"""
Simple Chatbot Flow — slim orchestrator.
=================================================================
Rules enforced:
- Rule 1:  NO HARDCODING — all data from APIs/runtime
- Rule 2:  API-only — no static fallback data
- Rule 3:  intent_content returned on every response; saving done by API layer
- Rule 4:  category mandatory for product/price/compare/order intents
- Rule 5:  category validated via CategoryValidator (cat_list API)
- Rule 6:  category switch → FULL reset
- Rule 7:  post-merge category guard — empty category → ask user
- Rule 8:  separated handlers per intent
- Rule 9:  comparison/buy intents return fixed messages
- Rule 10: short message + previous context = follow-up
- Rule 11: human handoff only on explicit request or complaint
- Rule 12: intent_content schema = {title, cat, brand, price, compare, buy}
- Rule 13: mode NEVER stored in memory — responder API is sole source of truth
- Rule 14: intent_content NEVER stored in local memory — always read from DB via API
"""
import os
import sys
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from .category_validator import CategoryValidator
except ImportError:
    from category_validator import CategoryValidator  # type: ignore

from .chatbot_config import (
    ChatMode, AI_ACTIVE_STATUS, HUMAN_SUPPORT_REQUIRED_STATUS, _log_api_call
)
from .state_manager import StateManager
from .api_client import ApiClient
from .intent_processor import IntentProcessor
from .intent_handlers import IntentHandlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleChatbot(IntentHandlers):

    def __init__(self) -> None:
        project_root = os.path.join(os.path.dirname(__file__), '..', '..')

        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key and Groq:
            groq_client = Groq(api_key=groq_api_key)
            groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
            groq_answer_model = os.getenv('GROQ_ANSWER_MODEL', 'llama-3.3-70b-versatile')
        else:
            groq_client = None
            groq_model = None
            groq_answer_model = None
            logger.warning("⚠️ Groq API not available")

        api_key = os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff')
        try:
            history_limit = int(os.getenv('CHATBOT_HISTORY_LIMIT', '5'))
        except Exception:
            history_limit = 5

        self._state = StateManager(project_root)
        self._api = ApiClient(
            api_key=api_key,
            api_url="https://www.bdstall.com/api/chatbot/ai_search/",
            delivery_intent_api_url="https://www.bdstall.com/api/chatbot/ai_template/",
            assign_agent_api_url=os.getenv(
                'ASSIGN_AGENT_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_assign_agent/'
            ),
            assign_agent_api_key=os.getenv('ASSIGN_AGENT_API_KEY', api_key),
            assign_bot_api_url=os.getenv(
                'ASSIGN_BOT_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_assign_bot/'
            ),
            responder_api_url=os.getenv(
                'RESPONDER_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_responder/'
            ),
            responder_api_key=os.getenv('RESPONDER_API_KEY', api_key),
            chatbot_history_api_url=os.getenv(
                'CHATBOT_HISTORY_API_URL', 'https://www.bdstall.com/api/chatbot/chatbot_history/'
            ),
            chatbot_history_limit=history_limit,
        )
        self.category_validator = CategoryValidator(
            cat_list_url=os.getenv(
                'CATLIST_API_URL', 'https://www.bdstall.com/api/chatbot/cat_list/'
            ),
            api_key=api_key,
        )
        self._processor = IntentProcessor(
            groq_client=groq_client,
            groq_model=groq_model,
            groq_answer_model=groq_answer_model,
            category_validator=self.category_validator,
        )
        self._database = self._state.load_database()

        logger.info("✅ SimpleChatbot initialized")
        logger.info("📚 Loaded %d FAQ rows", len(self._database))
        logger.info("📂 Loaded %d categories", len(self.category_validator.names_english()))

    # ─────────────────────────────────────────────────────────────
    # Public API (backward-compatible surface)
    # ─────────────────────────────────────────────────────────────
    def get_user_mode(self, user_id: str) -> str:
        return 'human' if self._api.check_responder_type(user_id) == 'agent' else 'ai'

    def switch_to_human(self, user_id: str) -> None:
        self._api.assign_agent(user_id, intent='manual_switch')

    def switch_to_ai(self, user_id: str) -> None:
        self._api.assign_bot(user_id)

    # ─────────────────────────────────────────────────────────────
    # Previous intent (Rule 14) — thin wrapper used by handlers
    # ─────────────────────────────────────────────────────────────
    def _load_previous_intent(self, user_id: str) -> Dict:
        return self._processor.load_previous_intent(
            user_id, self._api.fetch_intent_content_from_db
        )

    # ─────────────────────────────────────────────────────────────
    # MAIN ENTRY
    # ─────────────────────────────────────────────────────────────
    def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        try:
            start_time = datetime.now()
            logger.info("📨 user=%s msg=%r", user_id, message)

            if self._is_blocked_automated_message(message):
                return self._create_response(
                    user_id=user_id, message=message, response="",
                    mode=ChatMode.AI, intent='ignored_automated_template', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=AI_ACTIVE_STATUS
                )

            responder_type = self._api.check_responder_type(user_id)
            if responder_type == 'agent':
                return self._create_response(
                    user_id=user_id, message=message, response="",
                    mode=ChatMode.HUMAN, intent='human_mode_active', products=None,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS
                )

            url_match = re.search(r'https?://[^\s]+', message)
            if url_match:
                return self.handle_url_message(user_id, message, url_match.group(0), start_time)

            product_url = self._state.user_product_url.get(user_id, '')
            if not product_url:
                prev = self._load_previous_intent(user_id)
                product_url = prev.get('product_url', '')
            if product_url:
                detail = self.handle_product_detail_followup(
                    user_id, message, product_url, start_time
                )
                if detail:
                    return detail

            return self._handle_main_flow(user_id, message, start_time)

        except Exception as e:
            logger.error("❌ Unhandled error: %s", e, exc_info=True)
            return {
                'response': "দুঃখিত স্যার, একটি সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।",
                'mode': 'ai', 'intent': 'system_error', 'intent_content': {},
                'conversation_status': AI_ACTIVE_STATUS, 'products': [],
                'processing_time': 0.0, 'error': str(e)
            }

    # ─────────────────────────────────────────────────────────────
    # Main flow — Groq classification → handler dispatch
    # ─────────────────────────────────────────────────────────────
    def _handle_main_flow(self, user_id: str, message: str,
                          start_time: datetime) -> Dict[str, Any]:
        conversation_context = self._api.get_history_cached(user_id)
        previous_intent = self._load_previous_intent(user_id)
        groq_result = self._processor.step1_groq_extract(message, conversation_context, previous_intent)
        intent = groq_result['intent']
        entities = groq_result['entities']

        resolved_cat = None
        if entities.get('category'):
            resolved_cat = self.category_validator.resolve(entities['category'])
        entities['category'] = resolved_cat['category_name'] if resolved_cat else ''

        logger.info("✅ Intent=%s entities=%s followup=%s resolved=%s",
                    intent, entities, groq_result['is_followup'],
                    resolved_cat['category_name'] if resolved_cat else None)

        merged = self._processor.merge_intent_context(
            user_id, groq_result, previous_intent, intent,
            self._state.clear_product_search_cache
        )

        if not merged.get('category') and self._state.user_product_context.get(user_id):
            merged['category'] = previous_intent.get('category') or previous_intent.get('cat', '')

        if not merged.get('category') and (previous_intent.get('cat') or previous_intent.get('category')):
            if intent in ('comparison', 'technical_advice', 'price_query', 'faq', 'unknown', 'seller_query'):
                merged['category'] = previous_intent.get('category') or previous_intent.get('cat', '')

        return self._dispatch_intent(user_id, message, intent, merged, start_time)

    def _dispatch_intent(self, user_id: str, message: str, intent: str,
                         merged: Dict, start_time: datetime) -> Dict[str, Any]:
        handoff_map = {
            'seller_query': "স্যার, বিক্রয় সংক্রান্ত বিষয়ে আমাদের একজন প্রতিনিধি আপনাকে সাহায্য করবেন।",
            'hate_speech': "স্যার, অনুগ্রহ করে ভদ্র ভাষায় কথা বলুন। আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।",
            'human_request': "স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।",
            'complaint': "স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি এখনই আপনার সাথে যোগাযোগ করবেন।",
        }
        handoff_intent_map = {
            'seller_query': 'seller_query',
            'hate_speech': 'hate_speech',
            'human_request': 'explicit_human_request',
            'complaint': 'complaint_handoff',
        }
        if intent in handoff_map:
            return self._handoff_to_human(user_id, message, start_time,
                intent=handoff_intent_map[intent], response_text=handoff_map[intent])

        if intent == 'greeting':
            return self._create_response(
                user_id=user_id, message=message,
                response="আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?",
                mode=ChatMode.AI, intent='greeting', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )
        if intent == 'goodbye':
            prev = self._processor.normalize_intent_content_payload(self._load_previous_intent(user_id))
            prev['exit'] = 1
            return self._create_response(
                user_id=user_id, message=message, response="ধন্যবাদ স্যার, ভালো থাকবেন।",
                mode=ChatMode.AI, intent='goodbye', products=None, intent_content=prev,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )
        if intent == 'thanks':
            return self._create_response(
                user_id=user_id, message=message, response="Most welcome",
                mode=ChatMode.AI, intent='thanks', products=None,
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        handler_map = {
            'exit': lambda: self.handle_exit(user_id, message, start_time),
            'buy': lambda: self.handle_buy(user_id, message, start_time),
            'technical_advice': lambda: self.handle_technical_advice(user_id, message, merged, start_time),
            'comparison': lambda: self.handle_comparison(user_id, message, merged, start_time),
            'delivery': lambda: self.handle_delivery(user_id, message, merged, start_time),
            'faq': lambda: self.handle_faq(user_id, message, merged, start_time),
            'price_query': lambda: self.handle_price_query(user_id, message, merged, start_time),
            'product_search': lambda: self.handle_product_search(user_id, message, merged, start_time),
        }
        handler = handler_map.get(intent)
        if handler:
            return handler()
        return self.handle_fallback(user_id, message, merged, start_time)

    # ─────────────────────────────────────────────────────────────
    # Human handoff
    # ─────────────────────────────────────────────────────────────
    def _handoff_to_human(self, user_id: str, message: str, start_time: datetime,
                          intent: str = 'human_handoff',
                          response_text: str = "স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।",
                          error: Optional[str] = None) -> Dict[str, Any]:
        self._api.assign_agent(user_id, intent)
        intent_content = self._processor.normalize_intent_content_payload(
            self._load_previous_intent(user_id)
        )
        if error:
            intent_content['error'] = str(error)[:200]
        return self._create_response(
            user_id=user_id, message=message, response=response_text,
            mode=ChatMode.HUMAN, intent=intent, products=None,
            intent_content=intent_content,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=HUMAN_SUPPORT_REQUIRED_STATUS,
        )

    # ─────────────────────────────────────────────────────────────
    # Single exit point for all responses
    # ─────────────────────────────────────────────────────────────
    def _create_response(
        self, user_id: str, message: str, response: str, mode: ChatMode,
        intent: str, products: Optional[List[Dict]], processing_time: float = 0.0,
        search_keywords: str = '', intent_content: Optional[Dict[str, Any]] = None,
        link_buttons: Optional[List[Dict]] = None,
        conversation_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        if conversation_status is None:
            conversation_status = AI_ACTIVE_STATUS
        if intent_content is None:
            intent_content = self._processor.normalize_intent_content_payload(
                self._load_previous_intent(user_id)
            )
        else:
            intent_content = self._processor.normalize_intent_content_payload(intent_content)

        self._state.user_last_intent[user_id] = intent
        self._state.save_state()

        result: Dict[str, Any] = {
            'response': response, 'mode': mode.value, 'intent': intent,
            'intent_content': intent_content, 'conversation_status': conversation_status,
            'products': products or [], 'processing_time': round(processing_time, 3),
        }
        if search_keywords:
            result['search_keywords'] = search_keywords
        if link_buttons:
            result['link_buttons'] = link_buttons
        return result

    # ─────────────────────────────────────────────────────────────
    # Misc
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _is_blocked_automated_message(message: str) -> bool:
        text = str(message or '').strip().lower()
        if not text:
            return False
        blocked = [
            'bdstall.com-এ আপনাকে স্বাগতম',
            'আপনার মেসেজ এর জন্য ধন্যবাদ',
            'খুব শীঘ্রই bdstall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে',
        ]
        return sum(1 for p in blocked if p in text) >= 2
