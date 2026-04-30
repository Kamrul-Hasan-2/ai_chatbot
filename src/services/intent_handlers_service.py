"""
src/services/intent_handlers_service.py — one function per intent.
All business logic lives here. No HTTP calls — delegates to api_client_service.

Each handle_* receives:
  ctx     — merged context dict
  user_id — str
  message — str
  (some handlers take extra args: faq_db, categories, groq_client, groq_model)

Returns: dict {response, intent, intent_content, products, link_buttons}
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from models.chatbot_config import CATEGORY_PROMPT
from services.api_client_service import search_products, fetch_delivery_template
from repositories.state_repository import (
    load_context, get_last_intent,
    set_product_context, get_product_context,
    set_product_url, search_faq,
)
from services.intent_service import (
    normalize_payload, intent_to_normalized,
    get_technical_advice, resolve_category, resolve_category_from_message,
)

logger = logging.getLogger(__name__)


# ── Response builder helper ───────────────────────────────────────────────────

def _ok(response: str, intent: str, intent_content: Dict,
        products: List = None, link_buttons: List = None) -> Dict:
    return {
        'response':       response,
        'intent':         intent,
        'intent_content': intent_content,
        'products':       products or [],
        'link_buttons':   link_buttons or [],
    }


# ── Shared product-listing helpers ────────────────────────────────────────────

def _build_keywords(ctx: Dict) -> str:
    parts = []
    if ctx.get('brand'):
        parts.append(ctx['brand'].lower())
    if ctx.get('title'):
        parts.append(ctx['title'].lower())
    elif ctx.get('category'):
        parts.append(ctx['category'].lower())
    return ' '.join(parts).strip()


def _build_broader_keywords(ctx: Dict) -> str:
    parts = []
    if ctx.get('brand'):
        parts.append(ctx['brand'].lower())
    if ctx.get('category'):
        parts.append(ctx['category'].lower())
    elif ctx.get('title'):
        parts.append(ctx['title'].lower())
    return ' '.join(parts).strip()


def _format_listing(products: List[Dict]) -> Tuple[str, List[Dict]]:
    text = "স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n\nআরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।"
    buttons = []
    for i, p in enumerate(products[:3], 1):
        url = p.get('url', '')
        if url:
            buttons.append({'text': f"{i}. View", 'url': url,
                            'title': p.get('title', 'N/A'), 'price': p.get('price', 'N/A')})
    return text, buttons


def _comparison_buttons(ctx: Dict) -> List[Dict]:
    category = ctx.get('category', '')
    target = 'https://www.bdstall.com/'
    if category:
        slug = re.sub(r'[^a-z0-9\-]', '',
                      re.sub(r'\s+', '-', category.strip().lower())).strip('-')
        if slug:
            target = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
    return [{'text': 'View', 'url': target}]


def _extract_keywords_from_url(url: str) -> str:
    try:
        match = re.search(r'/details/([^/?#]+)', url)
        if not match:
            return ''
        slug = re.sub(r'-\d+$', '', match.group(1).strip('/'))
        stop = {'core', 'intel', 'amd', 'gen', 'th', 'gb', 'tb', 'ssd', 'hdd', 'ram',
                'display', 'inch', 'fhd', 'hd', 'uhd', 'touch', 'screen', 'series',
                'laptop', 'desktop', 'pc', 'windows', 'wifi', 'bluetooth', 'usb',
                'with', 'and', 'the'}
        filtered = []
        for w in slug.replace('-', ' ').split():
            if w.lower() in stop:
                break
            filtered.append(w)
        return ' '.join(filtered[:4])
    except Exception:
        return ''


# ── Intent handlers ───────────────────────────────────────────────────────────

def handle_greeting(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    return _ok("আসসালামু-আলাইকুম স্যার, কোন বিষয়ে জানতে চাচ্ছেন?", 'greeting', ic)


def handle_goodbye(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    ic['exit'] = 1
    return _ok("ধন্যবাদ স্যার, ভালো থাকবেন।", 'goodbye', ic)


def handle_thanks(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    return _ok("Most welcome", 'thanks', ic)


def handle_exit(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    ic['exit'] = 1
    return _ok("সাথে থাকার জন্য ধন্যবাদ।", 'exit', ic)


def handle_buy(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    buttons = [{'text': 'Shopping Guide',
                'url': 'https://www.bdstall.com/blog/safe-shopping-guide/'}]
    return _ok(
        "স্যার এই লিংকে গিয়ে আপনি দেখতে পারেন কিভাবে অর্ডার অথবা বাই করা যায়",
        'buy', ic, link_buttons=buttons
    )


def handle_comparison(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    return _ok(
        "স্যার, আমাদের সকল প্রোডাক্টই ভালো। আপনি প্রোডাক্ট পেইজে গিয়ে রেটিং ও রিভিউ দেখে নিতে পারেন।",
        'comparison', ic, link_buttons=_comparison_buttons(ctx)
    )


def handle_delivery(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    tmpl = fetch_delivery_template()
    if tmpl:
        return _ok(tmpl, 'delivery', ic)
    faq = search_faq(message, faq_db)
    if faq:
        return _ok(faq, 'delivery', ic)
    return handle_fallback(ctx, user_id, message, faq_db)


def handle_faq(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    faq = search_faq(message, faq_db)
    if faq:
        return _ok(faq, 'faq', ic)
    return handle_fallback(ctx, user_id, message, faq_db)


def handle_technical_advice(ctx: Dict, user_id: str, message: str,
                             categories: List[Dict],
                             groq_client, groq_model: str) -> Dict:
    ic = intent_to_normalized(ctx)
    resolved = resolve_category_from_message(message, categories)
    if not resolved:
        for word in message.split():
            resolved = resolve_category(word.strip(), categories)
            if resolved:
                break
    if not resolved:
        return _ok(
            "স্যার, এই বিষয়ে আমি সাহায্য করতে পারব না। আপনি কি কোনো প্রোডাক্ট খুঁজছেন?",
            'technical_advice_out_of_scope', ic
        )
    answer = (get_technical_advice(message, groq_client, groq_model)
              or "স্যার, এই বিষয়ে আমি নিশ্চিত নই।")
    full_answer = (answer
                   + "\n\nতবে স্যার, কেনার আগে অবশ্যই আরেকবার যাচাই করে নিন।"
                   + "\n\nকোন প্রোডাক্ট দেখতে চান বললে আমি এখনই দেখিয়ে দিতে পারি।")
    return _ok(full_answer, 'technical_advice', ic)


def handle_product_search(ctx: Dict, user_id: str, message: str) -> Dict:
    if not ctx.get('category'):
        return _ask_category(ctx)

    keywords = _build_keywords(ctx)
    result   = search_products(keywords, ctx.get('price_max'), ctx.get('price_min'))

    if result['products_found'] == 0:
        broader = _build_broader_keywords(ctx)
        if broader and broader != keywords:
            retry = search_products(broader, ctx.get('price_max'), ctx.get('price_min'))
            if retry['products_found'] > 0:
                keywords, result = broader, retry

    ic = intent_to_normalized(ctx)

    if result['products_found'] == 0:
        label = ' '.join(v for v in [
            ctx.get('brand', ''), ctx.get('title', ''), ctx.get('category', '')
        ] if v)
        return _ok(
            f"দুঃখিত স্যার, এই মুহূর্তে {label} স্টকে নেই। অন্য কোনো ব্র্যান্ড বা মডেল দেখাবো?",
            'no_products_found', ic
        )

    products = result['products']
    set_product_context(user_id, products[:5])
    text, buttons = _format_listing(products[:3])
    return _ok(text, 'product_search', ic, products=products, link_buttons=buttons)


def handle_price_query(ctx: Dict, user_id: str, message: str) -> Dict:
    if not ctx.get('category'):
        return _ask_category(ctx)

    prev_products = get_product_context(user_id)
    if prev_products:
        first_title = (prev_products[0].get('title') or '').lower()
        current_cat = ctx.get('category', '').lower()
        if current_cat and current_cat in first_title:
            ctx_reply = _reply_price_from_context(user_id)
            if ctx_reply:
                text, buttons = ctx_reply
                ic = intent_to_normalized(ctx)
                return _ok(text, 'price_from_context', ic, link_buttons=buttons)

    return handle_product_search(ctx, user_id, message)


def handle_url_message(ctx: Dict, user_id: str, message: str, url: str) -> Dict:
    url_lower = url.lower()
    if re.search(r'bdstall\.com/(details|listing)/', url_lower):
        return handle_product_link(ctx, user_id, message, url)
    ic = normalize_payload(load_context(user_id))
    if re.search(r'(cdn\.bdstall\.com|bdstall\.com/.*\.(jpg|jpeg|png|webp|gif))', url_lower):
        return _ok("স্যার, কোন ক্যাটাগরি এবং মডেল সম্পর্কে জানতে চাচ্ছেন? একটু বলুন।", 'image_url', ic)
    if re.search(r'(www\.)?bdstall\.com', url_lower):
        return _ok("স্যার, কী জানতে চাচ্ছেন? একটু বলুন।", 'bdstall_url', ic)
    return _ok("স্যার, আমি শুধুমাত্র BDStall.com এর প্রোডাক্ট লিংক সাপোর্ট করি।", 'unsupported_url', ic)


def handle_product_link(ctx: Dict, user_id: str, message: str, url: str) -> Dict:
    keywords = _extract_keywords_from_url(url)
    ic = normalize_payload(load_context(user_id))
    if not keywords:
        return _ok(
            "স্যার, লিংকটি সঠিকভাবে পড়তে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।",
            'product_link_error', ic
        )
    result = search_products(keywords)
    if result['products_found'] == 0:
        return _ok(
            "দুঃখিত স্যার, এই প্রোডাক্টটি এই মুহূর্তে পাওয়া যাচ্ছে না।",
            'product_link_not_found', ic,
            link_buttons=[{'text': 'View on BDStall', 'url': url}]
        )
    products = result['products']
    set_product_context(user_id, products[:5])
    set_product_url(user_id, url)
    top = products[0]
    title = top.get('title', 'N/A')
    price = top.get('price', 'N/A')
    ic['product_url'] = url
    ic['title']       = title
    ic['cat']         = top.get('category', ic.get('cat', ''))
    return _ok(
        f"স্যার, এই প্রোডাক্টটি পেয়েছি:\n\n{title}\nমূল্য: {price}",
        'product_link', ic, products=products,
        link_buttons=[{'text': 'View Product', 'url': url, 'title': title, 'price': price}]
    )


def handle_product_detail_followup(ctx: Dict, user_id: str, message: str,
                                   product_url: str) -> Optional[Dict]:
    signals = [
        'stock', 'ache', 'available', 'color', 'colour', 'rong',
        'quality', 'maan', 'durable', 'valo', 'price', 'dam', 'koto',
        'warranty', 'guarantee', 'original', 'kena jabe', 'pabo',
        'স্টক', 'রং', 'মান', 'দাম', 'ওয়ারেন্টি',
    ]
    if not any(s in message.lower() for s in signals):
        return None
    ic = normalize_payload(load_context(user_id))
    return _ok(
        "স্যার, এই প্রোডাক্টের সকল তথ্য আমাদের পেজে দেওয়া আছে।",
        'product_detail_followup', ic,
        link_buttons=[{'text': 'View Product', 'url': product_url}]
    )


def handle_fallback(ctx: Dict, user_id: str, message: str,
                    faq_db: List = None) -> Dict:
    if get_last_intent(user_id) == 'buy':
        return handle_buy(ctx, user_id, message)
    if ctx.get('category'):
        return handle_product_search(ctx, user_id, message)
    return _ask_category(ctx)


# ── Category prompt ───────────────────────────────────────────────────────────

def _ask_category(ctx: Dict) -> Dict:
    ic = intent_to_normalized(ctx)
    return _ok(CATEGORY_PROMPT, 'need_category', ic)


# ── Price-from-context helper ─────────────────────────────────────────────────

def _reply_price_from_context(user_id: str) -> Optional[Tuple[str, List[Dict]]]:
    products = get_product_context(user_id)
    if not products:
        return None
    if len(products) == 1:
        p     = products[0]
        title = p.get('title') or 'এই প্রোডাক্টটির'
        price = str(p.get('price') or '')
        url   = p.get('url', '')
        if price and price.upper() != 'N/A':
            return (f"জি স্যার, {title} এর দাম {price}।",
                    [{'text': 'View', 'url': url, 'title': title, 'price': price}] if url else [])
    lines   = ["স্যার, আপনার দেখা প্রোডাক্টগুলোর দাম:"]
    buttons = []
    for i, p in enumerate(products[:5], 1):
        t   = str(p.get('title') or f'প্রোডাক্ট {i}').strip()
        pr  = str(p.get('price') or 'N/A').strip()
        url = p.get('url', '')
        if not pr or pr.upper() == 'N/A':
            pr = 'দাম পাওয়া যায়নি'
        lines.append(f"{i}. {t} - {pr}")
        if url:
            buttons.append({'text': f"{i}. View", 'url': url, 'title': t, 'price': pr})
    lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।")
    return '\n'.join(lines), buttons
