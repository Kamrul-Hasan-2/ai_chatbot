"""
Intent handler methods for SimpleChatbot.
Each handle_* method corresponds to one classified intent.
"""
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models.chatbot_config import ChatMode, AI_ACTIVE_STATUS, CATEGORY_PROMPT
from utils.flow_helpers import (
    extract_keywords_from_bdstall_url,
    format_product_listing,
    build_comparison_link_buttons,
)

logger = logging.getLogger(__name__)


class IntentHandlers:
    """
    Mixin providing all handle_* methods.
    Expects the host class to expose:
      self._api, self._state, self._processor, self.category_validator,
      self._create_response(), self._load_previous_intent()
    """

    def handle_product_search(self, user_id: str, message: str, merged: Dict,
                              start_time: datetime) -> Dict[str, Any]:
        if not merged.get('category'):
            return self._ask_for_category(user_id, message, merged, start_time)

        category = merged['category']
        brand = merged.get('brand', '')
        title = merged.get('title', '')
        price_max = merged.get('price_max')
        price_min = merged.get('price_min')

        keywords = self._build_search_keywords(merged)
        result = self._api.cached_search(keywords, price_max, price_min)

        if result['products_found'] == 0:
            broader = self._build_broader_keywords(merged)
            if broader and broader != keywords:
                retry = self._api.cached_search(broader, price_max, price_min)
                if retry['products_found'] > 0:
                    keywords, result = broader, retry

        if result['products_found'] == 0:
            label = ' '.join(v for v in [brand, title, category] if v) or category
            return self._create_response(
                user_id=user_id, message=message,
                response=f"দুঃখিত স্যার, এই মুহূর্তে {label} স্টকে নেই। অন্য কোনো ব্র্যান্ড বা মডেল দেখাবো?",
                mode=ChatMode.AI, intent='no_products_found', products=None,
                search_keywords=keywords,
                intent_content=self._processor.intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        products = result['products']
        self._state.user_product_context[user_id] = products[:5]
        listing_text, listing_buttons = format_product_listing(products[:3])
        return self._create_response(
            user_id=user_id, message=message, response=listing_text,
            mode=ChatMode.AI, intent='product_search', products=products,
            search_keywords=keywords, link_buttons=listing_buttons,
            intent_content=self._processor.intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds()
        )

    def _build_search_keywords(self, merged: Dict) -> str:
        parts = []
        if merged.get('brand'):
            parts.append(merged['brand'].lower())
        if merged.get('title'):
            parts.append(merged['title'].lower())
        elif merged.get('category'):
            parts.append(merged['category'].lower())
        return ' '.join(parts).strip()

    def _build_broader_keywords(self, merged: Dict) -> Optional[str]:
        parts = []
        if merged.get('brand'):
            parts.append(merged['brand'].lower())
        if merged.get('category'):
            parts.append(merged['category'].lower())
        elif merged.get('title'):
            parts.append(merged['title'].lower())
        return ' '.join(parts).strip() or None

    def handle_price_query(self, user_id: str, message: str, merged: Dict,
                           start_time: datetime) -> Dict[str, Any]:
        if not merged.get('category'):
            return self._ask_for_category(user_id, message, merged, start_time)

        ctx_reply = None
        prev_products = self._state.user_product_context.get(user_id, [])
        if prev_products:
            first_title = (prev_products[0].get('title') or '').lower()
            current_cat = merged.get('category', '').lower()
            if current_cat and current_cat in first_title:
                ctx_reply = self._reply_price_from_context(user_id)

        if ctx_reply:
            ctx_text, ctx_buttons = ctx_reply
            return self._create_response(
                user_id=user_id, message=message, response=ctx_text,
                mode=ChatMode.AI, intent='price_from_context', products=None,
                link_buttons=ctx_buttons or None,
                intent_content=self._processor.intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )
        return self.handle_product_search(user_id, message, merged, start_time)

    def _reply_price_from_context(self, user_id: str) -> Optional[Tuple[str, List[Dict]]]:
        from utils.flow_helpers import reply_price_from_context
        return reply_price_from_context(
            self._state.user_selected_product.get(user_id),
            self._state.user_product_context.get(user_id),
        )

    def handle_comparison(self, user_id: str, message: str, merged: Dict,
                          start_time: datetime) -> Dict[str, Any]:
        if not merged.get('category') and self._state.user_product_context.get(user_id):
            prev = self._load_previous_intent(user_id)
            merged['category'] = prev.get('category') or prev.get('cat', '')
        return self._create_response(
            user_id=user_id, message=message,
            response="স্যার, আমাদের সকল প্রোডাক্টই ভালো। আপনি প্রোডাক্ট পেইজে গিয়ে রেটিং ও রিভিউ দেখে নিতে পারেন।",
            mode=ChatMode.AI, intent='comparison', products=None,
            link_buttons=build_comparison_link_buttons(merged),
            intent_content=self._processor.intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_buy(self, user_id: str, message: str, start_time: datetime) -> Dict[str, Any]:
        return self._create_response(
            user_id=user_id, message=message,
            response="স্যার এই লিংকে গিয়ে আপনি দেখতে পারেন কিভাবে অর্ডার অথবা বাই করা যায়",
            mode=ChatMode.AI, intent='buy', products=None,
            link_buttons=[{'text': 'Shopping Guide',
                           'url': 'https://www.bdstall.com/blog/safe-shopping-guide/'}],
            intent_content=self._processor.normalize_intent_content_payload(
                self._load_previous_intent(user_id)
            ),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_exit(self, user_id: str, message: str, start_time: datetime) -> Dict[str, Any]:
        prev = self._processor.normalize_intent_content_payload(self._load_previous_intent(user_id))
        prev['exit'] = 1
        return self._create_response(
            user_id=user_id, message=message, response="সাথে থাকার জন্য ধন্যবাদ।",
            mode=ChatMode.AI, intent='exit', products=None, intent_content=prev,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_delivery(self, user_id: str, message: str, merged: Dict,
                        start_time: datetime) -> Dict[str, Any]:
        tmpl = self._api.fetch_delivery_intent_response()
        if tmpl:
            return self._create_response(
                user_id=user_id, message=message, response=tmpl,
                mode=ChatMode.AI, intent='delivery', products=None,
                intent_content=self._processor.intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        faq = self._state.search_faq(message, self._database, self._is_blocked_automated_message)
        if faq:
            return self._create_response(
                user_id=user_id, message=message, response=faq,
                mode=ChatMode.AI, intent='delivery', products=None,
                intent_content=self._processor.intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        return self.handle_fallback(user_id, message, merged, start_time)

    def handle_faq(self, user_id: str, message: str, merged: Dict,
                   start_time: datetime) -> Dict[str, Any]:
        faq = self._state.search_faq(message, self._database, self._is_blocked_automated_message)
        if faq:
            return self._create_response(
                user_id=user_id, message=message, response=faq,
                mode=ChatMode.AI, intent='faq', products=None,
                intent_content=self._processor.intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
        return self.handle_fallback(user_id, message, merged, start_time)

    def handle_technical_advice(self, user_id: str, message: str, merged: Dict,
                                start_time: datetime) -> Dict[str, Any]:
        resolved = self.category_validator.resolve_from_message(message)
        if not resolved:
            for word in message.split():
                resolved = self.category_validator.resolve(word.strip())
                if resolved:
                    break
        if not resolved:
            return self._create_response(
                user_id=user_id, message=message,
                response="স্যার, এই বিষয়ে আমি সাহায্য করতে পারব না। আপনি কি কোনো প্রোডাক্ট খুঁজছেন?",
                mode=ChatMode.AI, intent='technical_advice_out_of_scope', products=None,
                intent_content=self._processor.intent_to_normalized(merged, message),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        answer = self._processor.get_technical_advice(message) or "স্যার, এই বিষয়ে আমি নিশ্চিত নই।"
        DISCLAIMER = "\n\nতবে স্যার, কেনার আগে অবশ্যই আরেকবার যাচাই করে নিন।"
        FOLLOWUP = "\n\nকোন প্রোডাক্ট দেখতে চান বললে আমি এখনই দেখিয়ে দিতে পারি।"
        return self._create_response(
            user_id=user_id, message=message, response=answer + DISCLAIMER + FOLLOWUP,
            mode=ChatMode.AI, intent='technical_advice', products=None,
            intent_content=self._processor.intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_url_message(self, user_id: str, message: str, url: str,
                           start_time: datetime) -> Dict[str, Any]:
        url_lower = url.lower()
        if re.search(r'bdstall\.com/(details|listing)/', url_lower):
            return self.handle_product_link(user_id, message, url, start_time)
        if re.search(r'(cdn\.bdstall\.com|bdstall\.com/.*\.(jpg|jpeg|png|webp|gif))', url_lower):
            return self._simple_response(user_id, message, start_time,
                "স্যার, কোন ক্যাটাগরি এবং মডেল সম্পর্কে জানতে চাচ্ছেন? একটু বলুন।", 'image_url')
        if re.search(r'(www\.)?bdstall\.com', url_lower):
            return self._simple_response(user_id, message, start_time,
                "স্যার, কী জানতে চাচ্ছেন? একটু বলুন।", 'bdstall_url')
        return self._simple_response(user_id, message, start_time,
            "স্যার, আমি শুধুমাত্র BDStall.com এর প্রোডাক্ট লিংক সাপোর্ট করি।", 'unsupported_url')

    def handle_product_link(self, user_id: str, message: str, url: str,
                            start_time: datetime) -> Dict[str, Any]:
        keywords = extract_keywords_from_bdstall_url(url)
        if not keywords:
            return self._simple_response(user_id, message, start_time,
                "স্যার, লিংকটি সঠিকভাবে পড়তে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।",
                'product_link_error')

        result = self._api.cached_search(keywords)
        if result['products_found'] == 0:
            return self._create_response(
                user_id=user_id, message=message,
                response="দুঃখিত স্যার, এই প্রোডাক্টটি এই মুহূর্তে পাওয়া যাচ্ছে না।",
                mode=ChatMode.AI, intent='product_link_not_found', products=None,
                link_buttons=[{'text': 'View on BDStall', 'url': url}],
                intent_content=self._processor.normalize_intent_content_payload(
                    self._load_previous_intent(user_id)
                ),
                processing_time=(datetime.now() - start_time).total_seconds(),
                conversation_status=AI_ACTIVE_STATUS
            )

        products = result['products']
        self._state.user_product_context[user_id] = products[:5]
        self._state.user_product_url[user_id] = url
        top = products[0]
        title = top.get('title', 'N/A')
        price = top.get('price', 'N/A')

        intent_content = self._processor.normalize_intent_content_payload(
            self._load_previous_intent(user_id)
        )
        intent_content['product_url'] = url
        intent_content['title'] = title
        intent_content['cat'] = top.get('category', intent_content.get('cat', ''))

        return self._create_response(
            user_id=user_id, message=message,
            response=f"স্যার, এই প্রোডাক্টটি পেয়েছি:\n\n{title}\nমূল্য: {price}",
            mode=ChatMode.AI, intent='product_link', products=products,
            link_buttons=[{'text': 'View Product', 'url': url, 'title': title, 'price': price}],
            intent_content=intent_content,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_product_detail_followup(self, user_id: str, message: str,
                                       product_url: str,
                                       start_time: datetime) -> Optional[Dict[str, Any]]:
        detail_signals = [
            'stock', 'ache', 'available', 'color', 'colour', 'rong',
            'quality', 'maan', 'durable', 'valo', 'price', 'dam', 'koto',
            'warranty', 'guarantee', 'original', 'kena jabe', 'pabo',
            'স্টক', 'রং', 'মান', 'দাম', 'ওয়ারেন্টি',
        ]
        if not any(s in message.lower() for s in detail_signals):
            return None
        intent_content = self._processor.normalize_intent_content_payload(
            self._load_previous_intent(user_id)
        )
        return self._create_response(
            user_id=user_id, message=message,
            response="স্যার, এই প্রোডাক্টের সকল তথ্য আমাদের পেজে দেওয়া আছে।",
            mode=ChatMode.AI, intent='product_detail_followup', products=None,
            link_buttons=[{'text': 'View Product', 'url': product_url}],
            intent_content=intent_content,
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def handle_fallback(self, user_id: str, message: str, merged: Dict,
                        start_time: datetime) -> Dict[str, Any]:
        last_intent = self._state.user_last_intent.get(user_id, '')
        if last_intent == 'buy':
            return self.handle_buy(user_id, message, start_time)
        if merged.get('category'):
            return self.handle_product_search(user_id, message, merged, start_time)
        resolved = self.category_validator.resolve(message.strip())
        if resolved:
            merged['category'] = resolved['category_name']
            return self.handle_product_search(user_id, message, merged, start_time)
        return self._ask_for_category(user_id, message, merged, start_time)

    def _ask_for_category(self, user_id: str, message: str, merged: Dict,
                          start_time: datetime) -> Dict[str, Any]:
        if not merged.get('category'):
            prev = self._load_previous_intent(user_id)
            if prev.get('cat') or prev.get('category'):
                merged['category'] = prev.get('category') or prev.get('cat', '')
                return self.handle_product_search(user_id, message, merged, start_time)
        return self._create_response(
            user_id=user_id, message=message, response=CATEGORY_PROMPT,
            mode=ChatMode.AI, intent='need_category', products=None,
            intent_content=self._processor.intent_to_normalized(merged, message),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )

    def _simple_response(self, user_id: str, message: str, start_time: datetime,
                         response: str, intent: str) -> Dict[str, Any]:
        return self._create_response(
            user_id=user_id, message=message, response=response,
            mode=ChatMode.AI, intent=intent, products=None,
            intent_content=self._processor.normalize_intent_content_payload(
                self._load_previous_intent(user_id)
            ),
            processing_time=(datetime.now() - start_time).total_seconds(),
            conversation_status=AI_ACTIVE_STATUS
        )
