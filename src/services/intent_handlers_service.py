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

from models.chatbot_config import CATEGORY_PROMPT, LOOP_BACK
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
    lines = ["স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n"]
    buttons = []
    for i, p in enumerate(products[:3], 1):
        title = p.get('title', 'N/A')
        price = p.get('price', 'N/A')
        url   = p.get('url', '')
        lines.append(f"{i}. {title}\n   মূল্য: {price}")
        if url:
            buttons.append({'text': f"{i}. View", 'url': url,
                            'title': title, 'price': price})
    lines.append("\nআরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।" + LOOP_BACK)
    return '\n'.join(lines), buttons


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
        words = slug.replace('-', ' ').split()
        skip = {'with', 'and', 'the', 'for', 'from', 'plus', 'pro', 'max',
                'ultra', 'new', 'edition', 'version', 'series', 'set'}
        filtered = [w for w in words if w.lower() not in skip]
        return ' '.join(filtered[:6])
    except Exception:
        return ''


# ── Intent handlers ───────────────────────────────────────────────────────────

def handle_greeting(ctx: Dict, user_id: str, message: str) -> Dict:
    from repositories.state_repository import clear_product_state
    clear_product_state(user_id)
    ic = normalize_payload(load_context(user_id))
    return _ok("ওয়ালাইকুম আসসালাম! 😊 BDStall-এ স্বাগতম। আপনি কোন প্রোডাক্টটি খুঁজছেন?", 'greeting', ic)


def handle_goodbye(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    ic['exit'] = 1
    return _ok("ধন্যবাদ স্যার, ভালো থাকবেন। আবার প্রয়োজন হলে আমরা সর্বদা আছি। 😊", 'goodbye', ic)


def handle_thanks(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    return _ok("Most welcome! 😊" + LOOP_BACK, 'thanks', ic)


def handle_exit(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    ic['exit'] = 1
    return _ok("সাথে থাকার জন্য ধন্যবাদ। আবার প্রয়োজন হলে আমরা সর্বদা আছি। 😊", 'exit', ic)


def handle_buy(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = normalize_payload(load_context(user_id))
    prev_products = get_product_context(user_id)
    buttons = []
    if prev_products:
        for p in prev_products[:3]:
            url = p.get('url', '')
            title = (p.get('title') or 'প্রোডাক্ট দেখুন')[:40]
            if url:
                buttons.append({'text': 'Order Now', 'url': url, 'title': title})
    if not buttons:
        buttons = [{'text': 'Shopping Guide',
                    'url': 'https://www.bdstall.com/blog/safe-shopping-guide/'}]
    return _ok(
        "স্যার, অর্ডার করার নিয়ম:\n\n"
        "১. www.bdstall.com-এ গিয়ে প্রোডাক্ট সিলেক্ট করুন\n"
        "২. 'Order Now' বাটনে ক্লিক করুন\n"
        "৩. আপনার নাম, ঠিকানা ও ফোন নম্বর দিন\n"
        "৪. অর্ডার কনফার্ম করুন\n\n"
        "✅ Cash on Delivery সুবিধাও পাওয়া যায়। আমাদের টিম আপনাকে কল করে কনফার্ম করবে।"
        + LOOP_BACK,
        'buy', ic, link_buttons=buttons
    )


def handle_comparison(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    return _ok(
        "স্যার, আমাদের সকল প্রোডাক্টেই ভালো রেটিং এবং রিভিউ আছে। "
        "রিভিউ দেখে পছন্দের প্রোডাক্টটি নিতে পারেন: 👉 www.bdstall.com"
        + LOOP_BACK,
        'comparison', ic, link_buttons=_comparison_buttons(ctx)
    )


_DELIVERY_INFO = (
    "স্যার, ডেলিভারি সংক্রান্ত তথ্য:\n\n"
    "📦 ডেলিভারি চার্জ:\n"
    "  • ঢাকার ভেতরে: ৬০-৮০ টাকা\n"
    "  • ঢাকার বাইরে: ১২০-১৫০ টাকা (কুরিয়ার সার্ভিস)\n\n"
    "⏱️ ডেলিভারি সময়:\n"
    "  • ঢাকার ভেতরে: ১-২ কার্যদিবস\n"
    "  • ঢাকার বাইরে: ২-৫ কার্যদিবস\n\n"
    "(নোট: চার্জ পরিবর্তন হতে পারে, কনফার্ম করতে www.bdstall.com দেখুন)"
)


def handle_delivery(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    tmpl = fetch_delivery_template()
    if tmpl:
        return _ok(tmpl + LOOP_BACK, 'delivery', ic)
    faq = search_faq(message, faq_db)
    if faq:
        return _ok(faq + LOOP_BACK, 'delivery', ic)
    return _ok(_DELIVERY_INFO + LOOP_BACK, 'delivery', ic)


_WARRANTY_WORDS = {
    'warranty', 'warenty', 'warrenty', 'warrantee', 'guarantee',
    'ওয়ারেন্টি', 'গ্যারান্টি', 'গ্যারান্টি', 'waranti', 'garantee',
}

_WARRANTY_RESPONSE = (
    "স্যার, দয়া করে আমাদের ওয়েবসাইট ভিজিট করুন: 👉 www.bdstall.com"
)


def handle_faq(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    msg_lower = message.lower()
    if any(w in msg_lower for w in _WARRANTY_WORDS):
        return _ok(_WARRANTY_RESPONSE + LOOP_BACK, 'faq_warranty', ic)
    faq = search_faq(message, faq_db)
    if faq:
        return _ok(faq + LOOP_BACK, 'faq', ic)
    return _ok(
        "এই বিষয়ে আমি নিশ্চিত নই। আরও সাহায্যের জন্য আমাদের ওয়েবসাইট দেখুন: 👉 www.bdstall.com"
        + LOOP_BACK,
        'faq_not_found', ic
    )


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
            "এই বিষয়ে আমি নিশ্চিত নই। আরও সাহায্যের জন্য আমাদের ওয়েবসাইট দেখুন অথবা সরাসরি কল করুন।"
            + LOOP_BACK,
            'technical_advice_out_of_scope', ic
        )
    answer = (get_technical_advice(message, groq_client, groq_model)
              or "স্যার, এই বিষয়ে আমি নিশ্চিত নই।")
    full_answer = (answer
                   + "\n\nতবে স্যার, কেনার আগে অবশ্যই আরেকবার যাচাই করে নিন।"
                   + "\n\nকোন প্রোডাক্ট দেখতে চান বললে আমি এখনই দেখিয়ে দিতে পারি।"
                   + LOOP_BACK)
    return _ok(full_answer, 'technical_advice', ic)


def handle_product_search(ctx: Dict, user_id: str, message: str) -> Dict:
    if not ctx.get('category'):
        return _ask_category(ctx)

    price_max = ctx.get('price_max')
    price_min = ctx.get('price_min')
    keywords  = _build_keywords(ctx)
    result    = search_products(keywords, price_max, price_min)

    if result['products_found'] == 0:
        broader = _build_broader_keywords(ctx)
        if broader and broader != keywords:
            retry = search_products(broader, price_max, price_min)
            if retry['products_found'] > 0:
                keywords, result = broader, retry

    # If still no results and a budget was applied, retry without budget filter
    if result['products_found'] == 0 and (price_max is not None or price_min is not None):
        no_budget_retry = search_products(_build_broader_keywords(ctx) or keywords, None, None)
        if no_budget_retry['products_found'] > 0:
            result = no_budget_retry
            budget_str = ''
            if price_max:
                budget_str = f"৳{price_max:,}"
            elif price_min:
                budget_str = f"৳{price_min:,}"
            # Prepend a note that exact budget had no results
            ic = intent_to_normalized(ctx)
            products = result['products']
            set_product_context(user_id, products[:5])
            text, buttons = _format_listing(products[:3])
            note = f"স্যার, এই বাজেটে সরাসরি কোনো প্রোডাক্ট পাওয়া যায়নি। কাছাকাছি দামে এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
            return _ok(note + text, 'product_search', ic, products=products, link_buttons=buttons)

    ic = intent_to_normalized(ctx)

    if result['products_found'] == 0:
        label = ' '.join(v for v in [
            ctx.get('brand', ''), ctx.get('title', ''), ctx.get('category', '')
        ] if v)
        return _ok(
            f"দুঃখিত স্যার, এই মুহূর্তে {label} স্টকে নেই। "
            "স্টক আপডেটের জন্য আমাদের ওয়েবসাইট ফলো করুন: 👉 www.bdstall.com"
            + LOOP_BACK,
            'no_products_found', ic
        )

    products = result['products']
    set_product_context(user_id, products[:5])
    text, buttons = _format_listing(products[:3])
    return _ok(text, 'product_search', ic, products=products, link_buttons=buttons)


def handle_price_query(ctx: Dict, user_id: str, message: str) -> Dict:
    has_budget = (ctx.get('price_max') is not None or ctx.get('price_min') is not None)

    # If a budget filter is given, do a fresh search (ignore cache)
    if has_budget and ctx.get('category'):
        return handle_product_search(ctx, user_id, message)

    # If products already shown and no budget filter, list cached prices
    prev_products = get_product_context(user_id)
    if prev_products and not has_budget:
        ctx_reply = _reply_price_from_context(user_id)
        if ctx_reply:
            text, buttons = ctx_reply
            ic = intent_to_normalized(ctx)
            return _ok(text, 'price_from_context', ic, link_buttons=buttons)

    if not ctx.get('category'):
        ic = intent_to_normalized(ctx)
        return _ok(
            "স্যার, কোন প্রোডাক্টের দাম জানতে চাচ্ছেন? একটু বলুন।" + LOOP_BACK,
            'need_product', ic
        )

    return handle_product_search(ctx, user_id, message)


def handle_url_message(ctx: Dict, user_id: str, message: str, url: str) -> Dict:
    url_lower = url.lower()
    if re.search(r'bdstall\.com/(details|listing)/', url_lower):
        return handle_product_link(ctx, user_id, message, url)
    ic = normalize_payload(load_context(user_id))
    if re.search(r'(cdn\.bdstall\.com|bdstall\.com/.*\.(jpg|jpeg|png|webp|gif))', url_lower):
        return _ok("স্যার, কোন ক্যাটাগরি এবং মডেল সম্পর্কে জানতে চাচ্ছেন? একটু বলুন।" + LOOP_BACK, 'image_url', ic)
    if re.search(r'(www\.)?bdstall\.com', url_lower):
        return _ok("স্যার, কী জানতে চাচ্ছেন? একটু বলুন।" + LOOP_BACK, 'bdstall_url', ic)
    return _ok(
        "স্যার, আমি শুধুমাত্র BDStall.com এর প্রোডাক্ট লিংক সাপোর্ট করি।" + LOOP_BACK,
        'unsupported_url', ic
    )


def handle_product_link(ctx: Dict, user_id: str, message: str, url: str) -> Dict:
    from services.intent_service import resolve_category_from_message
    keywords = _extract_keywords_from_url(url)
    ic = normalize_payload(load_context(user_id))
    if not keywords:
        return _ok(
            "স্যার, লিংকটি সঠিকভাবে পড়তে পারছি না। অনুগ্রহ করে আবার চেষ্টা করুন।" + LOOP_BACK,
            'product_link_error', ic
        )

    # Try exact URL slug search first, then broader keyword
    result = search_products(keywords)
    if result['products_found'] == 0:
        broader = ' '.join(keywords.split()[:3])
        if broader != keywords:
            result = search_products(broader)

    if result['products_found'] == 0:
        return _ok(
            f"স্যার, এই লিংকের প্রোডাক্টটি ({keywords}) এই মুহূর্তে স্টকে নেই।"
            " সরাসরি লিংকে গিয়ে দেখতে পারেন।" + LOOP_BACK,
            'product_link_not_found', ic,
            link_buttons=[{'text': 'View on BDStall', 'url': url}]
        )

    products = result['products']
    set_product_context(user_id, products[:5])
    set_product_url(user_id, url)
    top = products[0]
    title = top.get('title', 'N/A')
    price = top.get('price', 'N/A')
    orig_price = top.get('original_price', '')
    discount = top.get('discount', 0)

    # Extract category from URL slug and store in session
    from services.chatbot_service import _categories, _session_category
    slug_text = url.replace('-', ' ')
    cat_from_url = resolve_category_from_message(slug_text, _categories)
    if cat_from_url:
        _session_category[user_id] = cat_from_url
        ic['cat'] = cat_from_url

    ic['product_url'] = url
    ic['title'] = title

    lines = [f"স্যার, এই প্রোডাক্টটি পেয়েছি:", f"", f"📦 {title}", f"💰 মূল্য: {price}"]
    if orig_price and discount:
        lines.append(f"🏷️ আগের দাম: {orig_price} ({discount}% ছাড়)")
    lines.append(f"\nদাম, স্টক বা বিস্তারিত জানতে নিচের লিংকে ক্লিক করুন।")
    lines.append(LOOP_BACK)

    return _ok(
        '\n'.join(lines),
        'product_link', ic, products=products,
        link_buttons=[{'text': 'View Product', 'url': url, 'title': title, 'price': price}]
    )


def handle_product_detail_followup(ctx: Dict, user_id: str, message: str,
                                   product_url: str) -> Optional[Dict]:
    msg = message.lower()
    signals = [
        'stock', 'ache', 'available', 'color', 'colour', 'rong',
        'quality', 'maan', 'durable', 'valo', 'price', 'dam', 'koto',
        'warranty', 'warenty', 'guarantee', 'original', 'kena jabe', 'pabo',
        'স্টক', 'রং', 'মান', 'দাম', 'ওয়ারেন্টি', 'spec', 'feature',
        'detail', 'বিস্তারিত', 'কেমন', 'kemon', 'review', 'rating',
    ]
    if not any(s in msg for s in signals):
        return None

    ic = normalize_payload(load_context(user_id))
    prev_products = get_product_context(user_id)
    top = prev_products[0] if prev_products else {}
    title = top.get('title', '')

    if any(w in msg for w in ('price', 'dam', 'দাম', 'koto', 'কত', 'মূল্য')):
        price = top.get('price', 'N/A')
        reply = f"স্যার, {title} এর মূল্য {price}।" if title else f"স্যার, দাম জানতে লিংকটি দেখুন।"
    elif any(w in msg for w in ('warranty', 'warenty', 'guarantee', 'ওয়ারেন্টি')):
        reply = "স্যার, ওয়ারেন্টি সংক্রান্ত বিস্তারিত তথ্য প্রোডাক্ট পেজে দেওয়া আছে।"
    elif any(w in msg for w in ('stock', 'ache', 'available', 'পাবো', 'pabo')):
        reply = "স্যার, স্টক আপডেট জানতে প্রোডাক্ট পেজটি দেখুন।"
    else:
        reply = f"স্যার, {title} এর বিস্তারিত তথ্য প্রোডাক্ট পেজে পাবেন।" if title else "স্যার, বিস্তারিত জানতে প্রোডাক্ট পেজটি দেখুন।"

    return _ok(
        reply + LOOP_BACK,
        'product_detail_followup', ic,
        link_buttons=[{'text': 'View Product', 'url': product_url, 'title': title}]
    )


def handle_fallback(ctx: Dict, user_id: str, message: str,
                    faq_db: List = None) -> Dict:
    if get_last_intent(user_id) == 'buy':
        return handle_buy(ctx, user_id, message)
    msg_lower = message.lower()
    # Warranty questions always get the fixed website response
    if any(w in msg_lower for w in _WARRANTY_WORDS):
        ic = normalize_payload(load_context(user_id))
        return _ok(_WARRANTY_RESPONSE + LOOP_BACK, 'faq_warranty', ic)
    # If products were shown and user asks about price/selection, route to price handler
    prev_products = get_product_context(user_id)
    if prev_products:
        _price_signals = {'price', 'dam', 'দাম', 'koto', 'কত', 'cost', 'rate', 'মূল্য', 'taka', 'টাকা'}
        if any(w in msg_lower for w in _price_signals):
            return handle_price_query(ctx, user_id, message)
    if ctx.get('category'):
        return handle_product_search(ctx, user_id, message)
    ic = normalize_payload(load_context(user_id))
    return _ok(
        "স্যার, কোন প্রোডাক্টটি খুঁজছেন? ক্যাটাগরি বা মডেলের নাম বলুন, আমি দেখাচ্ছি।"
        + LOOP_BACK,
        'unknown', ic
    )


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
            return (f"জি স্যার, {title} এর দাম {price}।" + LOOP_BACK,
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
    lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।" + LOOP_BACK)
    return '\n'.join(lines), buttons
