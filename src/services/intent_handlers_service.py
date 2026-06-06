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

from models.chatbot_config import CATEGORY_PROMPT, LOOP_BACK, KNOWLEDGE_DAILY_LIMIT
from services.api_client_service import search_products, fetch_delivery_template, fetch_condition_template, fetch_category_template, fetch_product_spec, fetch_buy_template, fetch_order_status, assign_agent
from repositories.state_repository import (
    load_context, get_last_intent,
    set_product_context, get_product_context,
    set_product_url, search_faq,
    set_search_pool, get_search_pool, advance_search_offset,
    get_knowledge_count, increment_knowledge_count,
)
from services.intent_service import (
    normalize_payload, intent_to_normalized,
    get_technical_advice, resolve_category, resolve_category_from_message,
)

logger = logging.getLogger(__name__)


def _extract_product_id(url: str) -> str:
    """Extract numeric product ID from a BDStall listing URL.
    Handles formats:
      /details/some-slug-33323/
      /listing/33323/
      /33323/
    """
    if not url:
        return ''
    # Last numeric segment at end of URL path (before optional trailing slash/query)
    m = re.search(r'[/-](\d{3,})/?(?:[?#].*)?$', url.rstrip('/') + '/')
    return m.group(1) if m else ''


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
    if ctx.get('category'):
        parts.append(ctx['category'].lower())
    if ctx.get('title'):
        parts.append(ctx['title'].lower())
    return ' '.join(parts).strip()


def _build_broader_keywords(ctx: Dict) -> str:
    parts = []
    if ctx.get('brand'):
        parts.append(ctx['brand'].lower())
    if ctx.get('category'):
        parts.append(ctx['category'].lower())
    return ' '.join(parts).strip()


def _format_listing(products: List[Dict]) -> Tuple[str, List[Dict]]:
    lines = []
    buttons = []
    for i, p in enumerate(products[:3], 1):
        title = p.get('title', 'N/A')
        price = p.get('price', 'N/A')
        url   = p.get('url', '')
        lines.append(f"{i}. {title}\n   মূল্য: {price}")
        if url:
            buttons.append({'text': f"{i}. দেখুন", 'url': url,
                            'title': title, 'price': price})
    lines.append("\nস্যার, আপনি কোন প্রোডাক্টটি সম্পর্কে জানতে চান, ১, ২, ৩ যেকোনো নম্বর বলুন।")
    return '\n'.join(lines), buttons


def _comparison_buttons(ctx: Dict) -> List[Dict]:
    category = ctx.get('category', '')
    target = 'https://www.bdstall.com/'
    if category:
        slug = re.sub(r'[^a-z0-9\-]', '',
                      re.sub(r'\s+', '-', category.strip().lower())).strip('-')
        if slug:
            target = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
    return [{'text': 'দেখুন', 'url': target}]


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
    from repositories.state_repository import clear_product_state, set_session_category
    clear_product_state(user_id)
    set_session_category(user_id, '')
    # Reset all context so stale category/price don't bleed into next conversation
    ic = {'title': '', 'cat': '', 'brand': '', 'price_max': 0, 'price_min': 0, 'compare': '', 'buy': ''}
    return _ok("আসসালামু আলাইকুম স্যার! 😊 আমি BDStall-এর ভার্চুয়াল অ্যাসিস্ট্যান্ট। আপনাকে কীভাবে সাহায্য করতে পারি?", 'greeting', ic)


def handle_goodbye(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    ic['exit'] = 1
    return _ok("ধন্যবাদ স্যার, ভালো থাকবেন। আবার প্রয়োজন হলে আমরা সর্বদা আছি। 😊", 'goodbye', ic)


def handle_thanks(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    return _ok("Most welcome! 😊" + LOOP_BACK, 'thanks', ic)


def handle_exit(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    ic['exit'] = 1
    return _ok(
        "ঠিক আছে স্যার! BDStall.com Ltd-এর সাথেই থাকবেন। ধন্যবাদ। 😊",
        'exit', ic
    )


def handle_buy(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    prev_products = get_product_context(user_id)
    if not prev_products and not ctx.get('category'):
        return _ok(
            "স্যার, আপনি কোন মডেল কিনতে চান? "
            "মডেল এর নাম বা ক্যাটাগরি বললে আমি এখনই দেখিয়ে দিতে পারি।",
            'buy', ic
        )
    # Category known but no cached products — search first, then show buy instructions
    if not prev_products and ctx.get('category'):
        return handle_product_search(ctx, user_id, message)

    # Multiple cached products — ask user to pick one before starting the order
    if len(prev_products) > 1:
        product_list = '\n'.join(
            f"{i+1}. {p.get('title', '')[:50]}"
            for i, p in enumerate(prev_products[:3])
        )
        return _ok(
            (f"স্যার, কোন প্রোডাক্টটি অর্ডার করতে চান?\n\n{product_list}\n\n"
             "স্যার, আপনি কোন মডেল কিনতে চান, ১, ২, ৩ যেকোনো নম্বর বলুন।"),
            'product_clarification', ic
        )

    # Single product — decide route based on BDStall buy template:
    #   market_place_type == 'ecommerce' → start order flow (Buy Now)
    #   anything else (e.g. classified)  → show seller-contact text from API
    selected   = prev_products[0]
    product_url = selected.get('url', '')
    title       = (selected.get('title') or 'প্রোডাক্ট দেখুন')[:40]
    listing_id  = _extract_product_id(product_url)

    template = fetch_buy_template(listing_id) if listing_id else None
    market_type = (template or {}).get('market_place_type', '')

    if market_type == 'ecommerce':
        from services.order_handler import start_order_flow
        return start_order_flow(user_id, selected)

    # Classified / unknown → fall back to API-provided seller-contact text
    api_text = (template or {}).get('data', '').strip()
    buttons = ([{'text': 'প্রোডাক্ট দেখুন', 'url': product_url, 'title': title}]
               if product_url else
               [{'text': 'বিডিস্টল ভিজিট করুন', 'url': 'https://www.bdstall.com/'}])

    if api_text:
        return _ok(api_text + LOOP_BACK, 'buy', ic, link_buttons=buttons)

    # Hard fallback: API didn't return text (no listing id, network error etc.)
    reply = (
        "স্যার, এই প্রোডাক্টটি কিনতে:\n\n"
        "১. নিচের 'প্রোডাক্ট দেখুন' বাটনে ক্লিক করুন\n"
        "২. প্রোডাক্ট পেজে গিয়ে বিক্রেতাকে কল বা হোয়াটসঅ্যাপ করুন\n"
        "৩. দাম, কন্ডিশন ও ডেলিভারি নিশ্চিত করুন\n\n"
        "📞 বিক্রেতা সরাসরি আপনার সাথে যোগাযোগ করে ডেলিভারি দেবেন।"
    )
    return _ok(reply + LOOP_BACK, 'buy', ic, link_buttons=buttons)


def handle_comparison(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    prev_products = get_product_context(user_id)
    if prev_products:
        top = prev_products[0]
        title = top.get('title', '')
        price = top.get('price', '')
        url = top.get('url', '')
        # Avoid asserting "this is the best" — we can't know that.
        # Show the top result and let the user decide based on reviews.
        lines = ["স্যার, দেখানো প্রোডাক্টগুলোর মধ্যে এটি একটি ভালো অপশন হতে পারে:", ""]
        if title:
            lines.append(f"📦 {title}")
        if price:
            lines.append(f"💰 মূল্য: {price}")
        lines.append("")
        lines.append("রিভিউ ও রেটিং দেখে পছন্দ হলে অর্ডার করতে পারেন।")
        lines.append(LOOP_BACK)
        buttons = [{'text': 'প্রোডাক্ট দেখুন', 'url': url, 'title': title,
                    'price': price}] if url else _comparison_buttons(ctx)
        return _ok('\n'.join(lines), 'comparison', ic, link_buttons=buttons)
    # No cached products — if we know the category, surface a real search result.
    if ctx.get('category'):
        return handle_product_search(ctx, user_id, message)
    return _ok(
        "স্যার, আমাদের সকল প্রোডাক্টেই ভালো রেটিং এবং রিভিউ আছে। "
        "রিভিউ দেখে পছন্দের প্রোডাক্টটি নিতে পারেন: 👉 www.bdstall.com"
        + LOOP_BACK,
        'comparison', ic, link_buttons=_comparison_buttons(ctx)
    )


# ── Order status lookup ──────────────────────────────────────────────────────

# Bangla digits → English so we can match an order_no written like "১৭৮০..."
_BN_ORDER_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def _extract_order_no(message: str) -> str:
    """Pull a numeric order_no out of the user's message.

    BDStall order_no values seen so far are 9–14 digits. We require >= 8 digits
    so a "10k" budget or a phone number doesn't accidentally trigger the lookup.
    Mobile-shaped tokens (start with 01, 11 digits) are excluded.
    """
    if not message:
        return ''
    text = message.translate(_BN_ORDER_DIGITS)
    # Take the longest run of digits in the message
    runs = re.findall(r'\d+', text)
    if not runs:
        return ''
    runs.sort(key=len, reverse=True)
    for token in runs:
        if len(token) < 8:
            continue
        # Exclude Bangladeshi mobile pattern (01XXXXXXXXX) — that's not an order
        if len(token) == 11 and token.startswith('01'):
            continue
        return token
    return ''


def _format_order_status(data: Dict) -> str:
    """Render the order-status API payload as a short Bangla card.

    Customer only sees order number + status. Other fields (items, totals,
    address) intentionally omitted to keep the reply concise.
    """
    order_no   = str(data.get('OrderNo') or '').strip()
    status_raw = str(data.get('status') or '').strip()

    _STATUS_BN = {
        'pending':    'অপেক্ষমাণ',
        'submitted':  'গৃহীত',
        'processing': 'প্রক্রিয়াধীন',
        'confirmed':  'নিশ্চিত',
        'shipped':    'পাঠানো হয়েছে',
        'delivered':  'ডেলিভারি সম্পন্ন',
        'cancelled':  'বাতিল',
        'canceled':   'বাতিল',
        'returned':   'ফেরত',
    }
    status_bn = _STATUS_BN.get(status_raw.lower(), status_raw)

    lines = ["🧾 আপনার অর্ডারের তথ্য:", ""]
    if order_no:
        lines.append(f"অর্ডার নম্বর: {order_no}")
    if status_bn:
        lines.append(f"স্ট্যাটাস: {status_bn}")
    return '\n'.join(lines)


def handle_order_status(ctx: Dict, user_id: str, message: str) -> Optional[Dict]:
    """Look up and reply with an order's current status.

    Returns None if no order_no can be extracted from the message — that way
    the caller can fall through to other intent handling (delivery FAQ etc.).
    """
    ic = intent_to_normalized(ctx)
    order_no = _extract_order_no(message)
    if not order_no:
        return None
    result = fetch_order_status(order_no)
    if result.get('success') and result.get('data'):
        text = _format_order_status(result['data'])
        return _ok(text + LOOP_BACK, 'order_status', ic)
    api_msg = (result.get('message') or '').strip()
    detail = f" ({api_msg})" if api_msg else ''
    return _ok(
        f"দুঃখিত স্যার, অর্ডার নম্বর {order_no} এর তথ্য খুঁজে পাইনি{detail}। "
        "অনুগ্রহ করে অর্ডার নম্বরটি একবার যাচাই করে পাঠান।" + LOOP_BACK,
        'order_status_not_found', ic
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


_TRACK_SIGNALS = {
    'track', 'ট্র্যাক', 'trak', 'tracking', 'status', 'কোথায়',
    'order status', 'order track', 'order koi', 'order kothay',
    'shipment', 'parcel', 'courier status', 'delivery status',
}


def handle_delivery(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    msg_lower = message.lower()

    # Tracking / order-status questions go straight to FAQ — the delivery
    # template only has charge/time info and would be the wrong answer.
    is_tracking_query = any(s in msg_lower for s in _TRACK_SIGNALS)

    if not is_tracking_query:
        tmpl = fetch_delivery_template()
        if tmpl:
            return _ok(tmpl + LOOP_BACK, 'delivery', ic)

    faq = search_faq(message, faq_db)
    if faq:
        return _ok(faq + LOOP_BACK, 'delivery', ic)

    if is_tracking_query:
        return _ok(
            "স্যার, অর্ডার ট্র্যাক করতে BDStall-এ লগইন করুন এবং 'My Orders' সেকশনে যান। "
            "সেখানে আপনার অর্ডারের সর্বশেষ স্ট্যাটাস দেখতে পাবেন।"
            + LOOP_BACK,
            'delivery', ic
        )
    return _ok(_DELIVERY_INFO + LOOP_BACK, 'delivery', ic)


_WARRANTY_WORDS = {
    'warranty', 'warenty', 'warrenty', 'warrantee', 'guarantee',
    'ওয়ারেন্টি', 'গ্যারান্টি', 'গ্যারান্টি', 'waranti', 'garantee',
}

_WARRANTY_RESPONSE = (
    "স্যার, দয়া করে আমাদের ওয়েবসাইট ভিজিট করুন: 👉 www.bdstall.com"
)


_SHOWROOM_WORDS = {
    'showroom', 'show room', 'শোরুম', 'শো রুম', 'office', 'অফিস',
    'address', 'ঠিকানা', 'location', 'লোকেশন', 'kothay', 'কোথায়',
}

_SHOWROOM_RESPONSE = (
    "স্যার, BDStall একটি অনলাইন ই-কমার্স প্ল্যাটফর্ম। এখানে অসংখ্য ক্রেতা ও "
    "বিশ্বস্ত বিক্রেতা যুক্ত আছেন। আপনি ঘরে বসেই BDStall ভিজিট করে পছন্দের "
    "প্রোডাক্ট ক্রয় কিংবা বিক্রয় করতে পারবেন: 👉 www.bdstall.com"
)


_PROPERTY_WORDS = {
    'bari', 'বাড়ি', 'flat', 'ফ্ল্যাট', 'apartment', 'অ্যাপার্টমেন্ট',
    'plot', 'প্লট', 'land', 'জমি', 'real estate', 'property',
    'jomi', 'jomi ase', 'jomi chai', 'jomi lagbe', 'jomi kinte',
    'জমি আছে', 'জমি চাই', 'জমি লাগবে',
    'bari kinte', 'flat kinte', 'bari bikri', 'flat bikri',
    'bari chai', 'flat chai', 'bari lagbe', 'flat lagbe',
    'room rent', 'বাসা ভাড়া', 'basa vara', 'to let',
}

# Map user words → BDStall category name
_PROPERTY_CATEGORY_MAP = {
    'flat':       'Apartment',
    'ফ্ল্যাট':   'Apartment',
    'apartment':  'Apartment',
    'অ্যাপার্টমেন্ট': 'Apartment',
    'land':       'Land',
    'জমি':        'Land',
    'jomi':       'Land',
    'plot':       'Land',
    'প্লট':       'Land',
    'bari':       'Apartment',
    'বাড়ি':       'Apartment',
    'house':      'Apartment',
}


def _handle_property_query(user_id: str, message: str, ic: dict) -> Dict:
    msg_lower = message.lower()
    # Pick best matching category
    category = 'Apartment'
    for word, cat in _PROPERTY_CATEGORY_MAP.items():
        if word in msg_lower:
            category = cat
            break

    result = search_products(category)
    if result['products_found'] > 0:
        products = result['products']
        set_product_context(user_id, products[:5])
        text, buttons = _format_listing(products[:3])
        header = f"স্যার, BDStall-এ {category} বিজ্ঞাপন পেয়েছি:\n\n"
        return _ok(header + text, 'property_search', ic, products=products, link_buttons=buttons)

    return _ok(
        "স্যার, BDStall-এ বাড়ি, ফ্ল্যাট, প্লট ও জমি সংক্রান্ত বিজ্ঞাপনও পাওয়া যায়। "
        "বিস্তারিত দেখতে আমাদের ওয়েবসাইট ভিজিট করুন: 👉 www.bdstall.com" + LOOP_BACK,
        'faq_property', ic
    )

_AI_IDENTITY_WORDS = {
    'are you ai', 'are you a bot', 'are you robot', 'are you human',
    'tumi ki ai', 'tumi ki bot', 'tumi ki robot', 'tumi ki human',
    'apni ki ai', 'apni ki bot', 'apni ki robot', 'apni ki manush',
    'তুমি কি ai', 'তুমি কি বট', 'আপনি কি ai', 'আপনি কি বট',
    'তুমি কি রোবট', 'আপনি কি রোবট', 'তুমি কি মানুষ', 'আপনি কি মানুষ',
    'ki tumi ai', 'ki apni ai', 'bot naki', 'ai naki', 'robot naki',
}

_AI_IDENTITY_RESPONSE = (
    "স্যার, আমি BDStall-এর Virtual Assistant। "
    "যেকোনো প্রোডাক্ট বা কেনাকাটা সংক্রান্ত প্রশ্নে সাহায্য করতে পারি। 😊"
)


def handle_faq(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    msg_lower = message.lower()
    if any(w in msg_lower for w in _AI_IDENTITY_WORDS):
        return _ok(_AI_IDENTITY_RESPONSE + LOOP_BACK, 'faq_identity', ic)
    if any(w in msg_lower for w in _PROPERTY_WORDS):
        return _handle_property_query(user_id, message, ic)
    if any(w in msg_lower for w in _WARRANTY_WORDS):
        return _ok(_WARRANTY_RESPONSE + LOOP_BACK, 'faq_warranty', ic)
    if any(w in msg_lower for w in _SHOWROOM_WORDS):
        return _ok(_SHOWROOM_RESPONSE + LOOP_BACK, 'faq_showroom', ic)
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
    """Knowledge-style answer via Groq.

    Only this handler is allowed to generate Groq-backed text replies.
    Rate-limited to KNOWLEDGE_DAILY_LIMIT (5) calls per user per day.
    When the limit is exceeded, the conversation is handed off to a human agent.
    """
    ic = intent_to_normalized(ctx)
    resolved = resolve_category_from_message(message, categories)
    if not resolved:
        for word in message.split():
            resolved = resolve_category(word.strip(), categories)
            if resolved:
                break
    if not resolved:
        ctx_cat = ctx.get('category', '')
        if ctx_cat:
            resolved = resolve_category(ctx_cat, categories)
    if not resolved:
        return _ok(
            "এই বিষয়ে আমি নিশ্চিত নই। আরও সাহায্যের জন্য আমাদের ওয়েবসাইট দেখুন অথবা সরাসরি কল করুন।"
            + LOOP_BACK,
            'technical_advice_out_of_scope', ic
        )

    # Rate limit: 5 Groq-backed knowledge answers per user per day. After that
    # we switch the conversation to human-agent mode and ask the user to wait.
    used_today = get_knowledge_count(user_id)
    if used_today >= KNOWLEDGE_DAILY_LIMIT:
        logger.info("knowledge limit exceeded user=%s used=%d", user_id, used_today)
        try:
            assign_agent(user_id, 'knowledge_limit_exceeded')
        except Exception as e:
            logger.warning("assign_agent on knowledge limit failed: %s", e)
        return _ok(
            "স্যার, আজকের জন্য বিস্তারিত পরামর্শের সীমা শেষ হয়েছে। "
            "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।",
            'knowledge_limit_exceeded', ic
        )

    answer = get_technical_advice(message, groq_client, groq_model)
    if answer:
        increment_knowledge_count(user_id)
    else:
        answer = "স্যার, এই বিষয়ে আমি নিশ্চিত নই।"

    full_answer = (answer
                   + "\n\nতবে স্যার, কেনার আগে অবশ্যই আরেকবার যাচাই করে নিন।"
                   + "\n\nকোন প্রোডাক্ট দেখতে চান বললে আমি এখনই দেখিয়ে দিতে পারি।"
                   + LOOP_BACK)
    return _ok(full_answer, 'technical_advice', ic)


_CONDITION_WORDS = {
    'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
    'condition', 'কন্ডিশন', 'fresh', 'is it used', 'is it new',
    'nতুন', 'পুরনো', 'পুরাতন', 'naki purano', 'notun naki',
    'intake', 'original intake', 'non intake', 'ইনটেক', 'নন ইনটেক',
}


def _handle_condition_question(user_id: str, message: str) -> Optional[Dict]:
    """If user asks about condition and products are in cache, respond or ask clarification."""
    msg = message.lower()
    if not any(w in msg for w in _CONDITION_WORDS):
        return None
    prev_products = get_product_context(user_id)
    if not prev_products:
        return None

    # "brand new lagbe / notun chai / new want" — user wants a NEW unit, not asking
    # about condition of a specific product. Re-search with 'new' keyword filter.
    _WANT_SIGNALS = {'lagbe', 'chai', 'want', 'nibo', 'kinbo', 'দরকার', 'চাই', 'লাগবে'}
    _NEW_SIGNALS  = {'new', 'notun', 'brand new', 'নতুন', 'fresh'}
    _USED_SIGNALS = {'used', 'purano', 'second hand', 'refurbished', 'পুরনো', 'পুরাতন'}
    has_want   = any(w in msg for w in _WANT_SIGNALS)
    wants_new  = any(w in msg for w in _NEW_SIGNALS)
    wants_used = any(w in msg for w in _USED_SIGNALS)
    if has_want and (wants_new or wants_used):
        condition_kw = 'new' if wants_new else 'used'
        # Search with the condition keyword added to the existing category/title
        top = prev_products[0]
        base_kw = (top.get('title') or '').split()[:3]
        search_kw = f"{condition_kw} {' '.join(base_kw)}".strip()
        result = search_products(search_kw)
        ic = normalize_payload(load_context(user_id))
        if result['products_found'] > 0:
            products = result['products']
            set_product_context(user_id, products[:5])
            text, buttons = _format_listing(products[:3])
            label = 'নতুন' if wants_new else 'পুরনো/রিফার্বিশড'
            return _ok(f"স্যার, {label} প্রোডাক্টগুলো দেখুন:\n\n" + text,
                       'product_search', ic, products=products, link_buttons=buttons)
        # Nothing found — give honest answer
        label = 'নতুন' if wants_new else 'পুরনো/রিফার্বিশড'
        return _ok(
            f"স্যার, এই মুহূর্তে {label} কোনো প্রোডাক্ট পাওয়া যাচ্ছে না। "
            "প্রোডাক্ট পেজে বিক্রেতার সাথে যোগাযোগ করে কন্ডিশন নিশ্চিত করুন।"
            + LOOP_BACK,
            'product_condition', ic,
            link_buttons=[{'text': 'প্রোডাক্ট দেখুন', 'url': top.get('url', ''),
                           'title': top.get('title', '')}] if top.get('url') else []
        )

    ic = normalize_payload(load_context(user_id))
    if len(prev_products) > 1:
        msg_lower_cq = msg.lower()

        # If user says "atar / etar / its / 1 no" or a model identifier (has digits),
        # auto-select without asking again.
        _SELF_REF = {'atar', 'etar', 'otar', 'its', 'এটার', 'ওটার', 'এইটার'}
        auto_idx = -1
        if any(w in msg_lower_cq for w in _SELF_REF):
            auto_idx = 0  # most recently discussed = first in list
        else:
            # Look for a model-number token (e.g. "G10", "845", "g9") in message
            msg_tokens = re.findall(r'[a-z0-9]+', msg_lower_cq)
            model_tokens = [t for t in msg_tokens if re.search(r'\d', t)]
            for token in model_tokens:
                for i, p in enumerate(prev_products[:3]):
                    if token in (p.get('title') or '').lower():
                        auto_idx = i
                        break
                if auto_idx >= 0:
                    break

        if auto_idx >= 0:
            # Pin the auto-selected product
            from repositories.state_repository import set_product_url as _set_url_cq
            selected_cq = prev_products[auto_idx]
            set_product_context(user_id, [selected_cq])
            if selected_cq.get('url'):
                _set_url_cq(user_id, selected_cq['url'])
            prev_products = [selected_cq]
        else:
            product_list = '\n'.join(
                f"{i+1}. {p.get('title', '')[:50]}"
                for i, p in enumerate(prev_products[:3])
            )
            return _ok(
                f"স্যার, কোন প্রোডাক্টটি সম্পর্কে জানতে চান, ১, ২, ৩ যেকোনো নম্বর বলুন।\n\n{product_list}",
                'product_clarification', ic
            )
    top = prev_products[0]
    product_url_top = top.get('url', '')
    product_id = _extract_product_id(product_url_top)
    logger.info("condition_question: url=%r id=%r", product_url_top, product_id)
    api_reply = fetch_condition_template(product_id) if product_id else None
    logger.info("condition_question: api_reply=%r", api_reply)
    condition_text = (api_reply or
                      f"স্যার, {top.get('title', 'এই প্রোডাক্টটি')} এর কন্ডিশন জানতে "
                      "প্রোডাক্ট পেজটি দেখুন।")
    buttons = [{'text': 'প্রোডাক্ট দেখুন', 'url': product_url_top,
                'title': top.get('title', '')}] if product_url_top else []
    return _ok(condition_text + LOOP_BACK, 'product_condition', ic, link_buttons=buttons)


def handle_clarification_selection(user_id: str, message: str,
                                    pending_question: str = '',
                                    groq_client=None,
                                    groq_model: str = '') -> Optional[Dict]:
    """After product_clarification, detect numbered selection and answer the pending question.

    Steps:
      1. Detect which product the user selected (number or title keyword).
      2. Pin that product as the sole active product so future turns never re-ask.
      3. Route to the correct handler based on what was originally asked:
           - spec question  → handle_product_spec_query
           - condition      → fetch_condition_template
           - anything else  → handle_product_spec_query (safe default)
    """
    from repositories.state_repository import set_product_url as _set_url
    prev_products = get_product_context(user_id)
    if not prev_products:
        return None

    msg = message.strip()
    # Match leading number: "1", "1.", "1)", "#1"
    num_match = re.match(r'^[#\s]*([123])[.):\s]?$|^[#\s]*([123])[.):\s]', msg)
    if not num_match:
        # Try matching by product title keyword — require at least 2 words to match,
        # or a unique non-brand word (model number) to avoid brand-only false matches.
        msg_lower = msg.lower()
        msg_words = set(w for w in re.findall(r'[a-z0-9]+', msg_lower) if len(w) > 3)
        best_idx = -1
        best_score = 0
        for i, p in enumerate(prev_products[:3]):
            title_words = set(w for w in re.findall(r'[a-z0-9]+', (p.get('title') or '').lower()) if len(w) > 2)
            score = len(msg_words & title_words)
            if score > best_score:
                best_score = score
                best_idx = i
        # Require at least 2 matching words, OR 1 match that isn't a generic brand
        # (i.e. the matching word is a model number like "3310", "a55", etc.)
        if best_score >= 2:
            num_match = type('m', (), {'group': lambda self, x: str(best_idx+1)})()
        elif best_score == 1:
            # Check if the single match is a model-number-like token (has digits)
            matching_words = msg_words & set(w for w in re.findall(r'[a-z0-9]+', (prev_products[best_idx].get('title') or '').lower()) if len(w) > 2)
            if any(re.search(r'\d', w) for w in matching_words):
                num_match = type('m', (), {'group': lambda self, x: str(best_idx+1)})()
    if not num_match:
        return None

    idx = int(num_match.group(1) or num_match.group(2)) - 1
    if idx < 0 or idx >= len(prev_products):
        return None

    selected = prev_products[idx]
    product_url_sel = selected.get('url', '')
    title = selected.get('title', '')
    logger.info("clarification_selection: idx=%d url=%r title=%r", idx, product_url_sel, title)

    # ── Pin selected product so every future turn knows exactly which one ──────
    # Overwrite product context to just this one product so handlers never
    # see "multiple products" and never ask the clarification question again.
    set_product_context(user_id, [selected])
    if product_url_sel:
        _set_url(user_id, product_url_sel)

    ic = normalize_payload(load_context(user_id))
    buttons = [{'text': 'প্রোডাক্ট দেখুন', 'url': product_url_sel, 'title': title}] if product_url_sel else []

    # ── Route based on what the user originally asked ─────────────────────────
    _CONDITION_Q = {
        'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
        'condition', 'কন্ডিশন', 'fresh',
        'intake', 'original intake', 'non intake', 'ইনটেক', 'নন ইনটেক',
    }
    q = (pending_question or '').lower()

    if any(w in q for w in _CONDITION_Q):
        product_id = _extract_product_id(product_url_sel)
        api_reply = fetch_condition_template(product_id) if product_id else None
        logger.info("clarification_selection: condition route api_reply=%r", api_reply)
        reply = (api_reply or
                 f"স্যার, {title} এর কন্ডিশন জানতে প্রোডাক্ট পেজটি দেখুন।")
        return _ok(reply + LOOP_BACK, 'product_condition', ic, link_buttons=buttons)

    # Buy route: pending question was a purchase intent — route via the buy
    # template gate so ecommerce items kick off the order flow and classified
    # items fall back to seller-contact text.
    _BUY_Q = {'kinbo', 'kinte', 'buy', 'order', 'purchase',
              'কিনব', 'কিনতে', 'অর্ডার'}
    if any(w in q for w in _BUY_Q):
        listing_id_sel = _extract_product_id(product_url_sel)
        template_sel = fetch_buy_template(listing_id_sel) if listing_id_sel else None
        market_type_sel = (template_sel or {}).get('market_place_type', '')
        if market_type_sel == 'ecommerce':
            from services.order_handler import start_order_flow
            return start_order_flow(user_id, selected)
        api_text_sel = (template_sel or {}).get('data', '').strip()
        if api_text_sel:
            return _ok(api_text_sel + LOOP_BACK, 'buy', ic, link_buttons=buttons)
        return _ok(
            f"স্যার, {title} কিনতে প্রোডাক্ট পেজে গিয়ে বিক্রেতার সাথে যোগাযোগ করুন।"
            + LOOP_BACK,
            'buy', ic, link_buttons=buttons
        )

    # Default: spec query — handles ram/display/battery/full-spec/any other detail
    ctx = {'category': selected.get('category', ''), 'brand': '', 'title': title}
    return handle_product_spec_query(ctx, user_id,
                                     pending_question or message,
                                     groq_client, groq_model)


_MORE_WORDS = {
    # English
    'more', 'next', 'others', 'another', 'other', 'show more', 'see more',
    'next 3', 'next ones', 'next page', 'continue', 'go on', 'keep going',
    'load more', 'show next', 'show others', 'more options', 'more products',
    'more items', 'other options', 'other products', 'any other', 'anything else',
    'something else', 'different', 'different ones', 'alternative', 'alternatives',

    # Banglish (Bangla written in English letters)
    'aro', 'aaro', 'aro dekhao', 'aro dekhan', 'aro dekhi', 'aro dekhao plz',
    'arro', 'arrro', 'arroo', 'aroo',
    'r kichu', 'r kichue', 'r kichui', 'r kichu dekhao', 'r kichu dekhan',
    'r kichu ase', 'r ase ki', 'r ki ase', 'r ki ki ase',
    'r dekhao', 'r dekhan', 'r dekhi', 'r dekhabe', 'r dekhaben',
    'onno', 'onno gula', 'onno gulo', 'onnogulo', 'onno kichu', 'onno option',
    'onno product', 'onno gula dekhao', 'onno gulo dekhao', 'onno kichu dekhao',
    'baki', 'baki gula', 'baki gulo', 'baki kichu',
    'aroo dekhao', 'aroo dekhan', 'aroo dekhi',
    'aro option', 'aro product', 'aro item', 'aro model',
    'next ta', 'next gula', 'next gulo', 'porer ta', 'porer gula', 'porer gulo',
    'porer 3', 'porer tin', 'porer page',
    'ekto onno', 'ekta onno', 'aro vlo',

    # Bangla (Bengali script)
    'আরও', 'আরো', 'অন্য', 'অন্যগুলো', 'অন্য কিছু', 'অন্যটি', 'অন্যটা',
    'আরও দেখান', 'আরও দেখাও', 'আরও দেখি', 'আরও দেখতে চাই',
    'আরো দেখান', 'আরো দেখাও', 'আরো দেখি', 'আরো দেখতে চাই',
    'আরও কিছু', 'আরো কিছু', 'আরও কিছু দেখান', 'আরো কিছু দেখান',
    'আর কিছু', 'আর কিছু আছে', 'আর কী আছে', 'আর কি আছে',
    'আর দেখান', 'আর দেখাও', 'আর দেখি',
    'বাকি', 'বাকিগুলো', 'বাকি গুলো', 'বাকি কিছু',
    'পরের', 'পরেরটা', 'পরেরগুলো', 'পরের তিনটা', 'পরের ৩',
    'অন্য কোনো', 'অন্য কোন', 'অন্য অপশন', 'অন্য প্রোডাক্ট',
    'নতুন কিছু', 'ভিন্ন', 'অন্যরকম',
}


def _is_more_request(message: str) -> bool:
    msg = (message or '').lower().strip()
    if not msg:
        return False
    # Whole-word / phrase match to avoid "more" inside other words
    for w in _MORE_WORDS:
        wl = w.lower()
        if wl == msg or msg.startswith(wl + ' ') or msg.endswith(' ' + wl) or f' {wl} ' in f' {msg} ':
            return True
    return False


def _build_category_button_label(category_name: str) -> str:
    """Build a Messenger button label like 'Laptop List' within the 20-char limit.

    Falls back to the Bangla 'তালিকা দেখুন' for category names too long to fit
    with the ' List' suffix (e.g. 'Air Conditioner' = 15 + 5 = 20 chars OK,
    'Wall Mounted Split Type AC' would not fit).
    """
    name = (category_name or '').strip()
    suffix = ' List'
    if name and len(name) + len(suffix) <= 20:
        return f"{name}{suffix}"
    return 'তালিকা দেখুন'


def _find_cat_list_match(message: str, category: str, cat_list: List[Dict]) -> Optional[Dict]:
    """Find a cat_list entry whose name appears in the user message.

    Priority: longest category_name that is a substring of the lowercased
    message wins, so "used laptop" matches "Used Laptop" (12 chars) instead
    of "Laptop" (6 chars). Also tries the bn_category_name and the
    Groq-resolved `category` field as fallbacks.

    Returns the cat_list dict (with cat_url) or None.
    """
    if not cat_list:
        return None
    msg = (message or '').lower().strip()
    cat = (category or '').lower().strip()
    best: Optional[Dict] = None
    best_len = 0
    for entry in cat_list:
        if not entry.get('cat_url'):
            continue
        name_en = (entry.get('category_name') or '').lower().strip()
        name_bn = (entry.get('bn_category_name') or '').lower().strip()
        for candidate in (name_en, name_bn):
            if not candidate or len(candidate) <= best_len:
                continue
            if (candidate in msg) or (cat and candidate in cat) or (cat and cat == candidate):
                best = entry
                best_len = len(candidate)
                break
    return best


_REJECTION_PHRASES = {
    'হবে না', 'হবেনা', 'na hobe', 'hobe na', 'na hoi', 'hoi na',
    'পাওয়া যাবে না', 'পাবো না', 'paoa jabe na', 'pabo na',
    'এটা না', 'এগুলো না', 'এগুলো হবে না', 'এটা চাই না',
    # "নেই??" pattern — user asking if something exists in this budget
    'নেই', 'nei', 'পাওয়া যায় না', 'পাই না', 'নাই',
}


def handle_product_search(ctx: Dict, user_id: str, message: str) -> Dict:
    logger.info("handle_product_search ctx=%s", {k: ctx.get(k) for k in ('category','brand','title','price_min','price_max')})

    # Intercept property/real-estate queries — route to dedicated handler
    if any(w in (message or '').lower() for w in _PROPERTY_WORDS):
        ic = intent_to_normalized(ctx)
        return _handle_property_query(user_id, message, ic)

    # Rejection / "নেই?" message — user says shown products won't work OR asks if
    # something exists in this budget. Extract the new keyword and search with budget.
    msg_lower = (message or '').lower()
    if any(p in msg_lower for p in _REJECTION_PHRASES):
        # Strip rejection/filler words; keep meaningful product keywords
        _FILLER = (r'(হবে না|হবেনা|na hobe|hobe na|na hoi|hoi na|পাওয়া যাবে না|পাবো না|'
                   r'paoa jabe na|pabo na|এটা না|এগুলো না|এগুলো হবে না|এটা চাই না|'
                   r'নেই|nei|পাওয়া যায় না|পাই না|নাই|'
                   r'এই বাজেটের মধ্যে|এই বাজেটে|বাজেটের মধ্যে|বাজেটে|'
                   r'কোনো|কোন|আছে|আছে কি|কি|ki|ache|ase|'
                   r'\?\?|\?|।)')
        spec_text = re.sub(_FILLER, ' ', msg_lower).strip()
        spec_text = re.sub(r'\s+', ' ', spec_text).strip().rstrip('র ের এর ের').strip()
        category = ctx.get('category', '')
        price_max = ctx.get('price_max')
        price_min = ctx.get('price_min')
        search_kw = f"{spec_text} {category}".strip() if spec_text else category
        ic = intent_to_normalized(ctx)
        if search_kw:
            result = search_products(search_kw, price_max, price_min)
            if result['products_found'] == 0 and (price_max or price_min):
                result = search_products(search_kw)  # retry without budget
            if result['products_found'] > 0:
                products = result['products']
                set_search_pool(user_id, search_kw, products)
                set_product_context(user_id, products[:5])
                text, buttons = _format_listing(products[:3])
                return _ok("স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n\n" + text,
                           'product_search', ic, products=products, link_buttons=buttons)
        return _ok(
            "দুঃখিত স্যার, এই স্পেসিফিকেশনে এই মুহূর্তে কোনো প্রোডাক্ট পাওয়া যাচ্ছে না। "
            "বাজেট বা স্পেসিফিকেশন পরিবর্তন করে আবার খুঁজুন।" + LOOP_BACK,
            'no_products_found', ic
        )

    # Use-case / purpose intercept — "graphics er kajor jonni" / "video editing er jonno"
    # Pattern: <purpose> er kaje / er kajer jonno / er jonno / er jonni / for <purpose> work
    _PURPOSE_PATTERN = re.compile(
        r'(\w+)\s+(?:er\s+)?(?:kaj(?:or?|er?)\s*(?:jonno?|jonni)?|jonno?|jonni|kaje|kajer\s+jonno?)'
        r'|for\s+(\w+)\s+(?:work|use|task)',
        re.IGNORECASE
    )
    _GENERIC_PURPOSE = {'ami', 'apni', 'amar', 'apnar', 'ki', 'kono', 'sob', 'ei',
                        'oi', 'je', 'ta', 'to', 'na', 'hobe', 'chai', 'lagbe'}
    _purpose_match = _PURPOSE_PATTERN.search(msg_lower)
    if _purpose_match:
        purpose_word = (_purpose_match.group(1) or _purpose_match.group(2) or '').lower().strip()
        category = ctx.get('category', '')
        if purpose_word and purpose_word not in _GENERIC_PURPOSE and purpose_word != category.lower():
            purpose_kw = f"{purpose_word} {category}".strip() if category else purpose_word
            current_kw = _build_keywords(ctx)
            # Only re-search if purpose word is not already in the current keywords
            if purpose_word not in current_kw.lower():
                price_max = ctx.get('price_max')
                price_min = ctx.get('price_min')
                logger.info("purpose intercept: purpose=%r kw=%r", purpose_word, purpose_kw)
                result = search_products(purpose_kw, price_max, price_min)
                if result['products_found'] == 0 and (price_max or price_min):
                    result = search_products(purpose_kw)
                if result['products_found'] > 0:
                    products = result['products']
                    pool_key = f"{purpose_kw}|{price_min or ''}|{price_max or ''}"
                    set_search_pool(user_id, pool_key, products)
                    set_product_context(user_id, products[:5])
                    text, buttons = _format_listing(products[:3])
                    ic = intent_to_normalized(ctx)
                    if price_max:
                        header = f"স্যার, ৳{price_max:,} এর মধ্যে {purpose_word} কাজের জন্য উপযুক্ত প্রোডাক্টগুলো দেখুন:\n\n"
                    else:
                        header = f"স্যার, {purpose_word} কাজের জন্য উপযুক্ত প্রোডাক্টগুলো দেখুন:\n\n"
                    return _ok(header + text, 'product_search', ic, products=products, link_buttons=buttons)

    # Intercept condition questions — don't re-search, answer about cached products
    condition_result = _handle_condition_question(user_id, message)
    if condition_result:
        return condition_result

    if not ctx.get('category'):
        return _ask_category(ctx, user_id)

    price_max = ctx.get('price_max')
    price_min = ctx.get('price_min')

    # Generic-category intercept: when the user asks for a bare category
    # (no brand, no specific title, no budget), return the BDStall category
    # landing-page link instead of dumping 3 products. Falls back to the
    # normal product search if the ai_template API doesn't recognise the
    # category. The "more" branch below must not be short-circuited, so we
    # only run this for the first turn of a generic search.
    # Spec/model qualifiers in the raw message (CPU/GPU generation, RAM size,
    # storage, gaming, etc.) — if any are present, the user wants a filtered
    # search, not the generic category landing page.
    _SPEC_QUALIFIERS = (
        # CPU / chipset
        'i3', 'i5', 'i7', 'i9', 'ryzen', 'celeron', 'pentium', 'core',
        'snapdragon', 'mediatek', 'helio', 'dimensity', 'exynos', 'kirin',
        'gen', 'generation', 'th gen', 'nd gen', 'rd gen', 'st gen',
        # GPU
        'rtx', 'gtx', 'radeon', 'nvidia', 'amd', 'graphics', 'gpu',
        # Memory / storage
        'gb', 'tb', 'ram', 'ssd', 'hdd', 'storage', 'memory',
        # Display
        'inch', '"', 'fhd', 'hd', '4k', '2k', 'oled', 'amoled', 'lcd', 'led',
        'curved', 'touch',
        # Use-case
        'gaming', 'office', 'business', 'student', 'editing',
        # Network
        '4g', '5g', 'wifi', 'bluetooth',
        # Battery / camera (mobiles)
        'mah', 'mp', 'megapixel', 'camera',
        # Bangla
        'গেমিং', 'র‍্যাম', 'প্রসেসর', 'ব্যাটারি', 'ক্যামেরা',
    )
    _msg_l = (message or '').lower()
    _cat_l = (ctx.get('category') or '').lower()
    _has_spec_qualifier = any(
        q in _msg_l and q not in _cat_l for q in _SPEC_QUALIFIERS
    )

    _is_generic_category = (
        ctx.get('category')
        and not (ctx.get('brand') or '').strip()
        and not (ctx.get('title') or '').strip()
        and not price_min
        and not price_max
        and not _is_more_request(message)
        and not _has_spec_qualifier
    )
    if _is_generic_category:
        # First try the direct cat_list lookup — if the user's category (or raw
        # message) matches a known cat_list entry by substring, return its
        # cat_url directly. This handles "used laptop", "smart tv" etc. without
        # hitting the ai_template API or doing a product search. Falls through
        # to fetch_category_template when nothing matches.
        try:
            from services.chatbot_service import _categories as _cat_list
        except Exception:
            _cat_list = []
        _direct = _find_cat_list_match(message, ctx.get('category', ''), _cat_list)
        if _direct and _direct.get('cat_url'):
            cat_name_direct = _direct.get('category_name') or ctx.get('category') or ''
            cat_url_direct = _direct['cat_url']
            label_d = _build_category_button_label(cat_name_direct)
            ic_d = intent_to_normalized(ctx)
            reply_d = (f"স্যার, আপনি বিডিস্টলে {cat_name_direct} "
                       f"ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন।")
            buttons_d = [{'text': label_d, 'url': cat_url_direct,
                          'title': cat_name_direct}]
            return _ok(reply_d + LOOP_BACK, 'product_search', ic_d,
                       link_buttons=buttons_d)

        cat_template = fetch_category_template(ctx['category'])
        if cat_template:
            cat_text = cat_template.get('text', '')
            cat_url = cat_template.get('link', '')
            cat_name = (ctx['category'] or '').strip().title()
            cat_label = _build_category_button_label(cat_name)
            buttons = ([{'text': cat_label, 'url': cat_url,
                         'title': ctx['category']}]
                       if cat_url else [])
            ic = intent_to_normalized(ctx)
            return _ok(cat_text + LOOP_BACK, 'product_search', ic,
                       link_buttons=buttons)

    keywords  = _build_keywords(ctx)
    logger.info("handle_product_search keywords=%r price_min=%s price_max=%s", keywords, price_min, price_max)

    # "More" rotation: if user asked for more AND we have a pool for the same query, slice next 3.
    current_key = f"{keywords}|{price_min or ''}|{price_max or ''}"

    # If the query key changed (new brand, new title, new budget) reset the pool
    # so stale results from a previous search aren't served as "more".
    _, existing_key, _ = get_search_pool(user_id)
    if existing_key and existing_key != current_key and not _is_more_request(message):
        from repositories.state_repository import clear_product_state as _cps
        _cps(user_id)

    if _is_more_request(message):
        pool, pool_key, offset = get_search_pool(user_id)
        if pool and pool_key == current_key:
            next_off = advance_search_offset(user_id, by=3)
            slice_ = pool[next_off:next_off + 3]
            if slice_:
                logger.info("More rotation: offset=%d showing %d items", next_off, len(slice_))
                ic = intent_to_normalized(ctx)
                set_product_context(user_id, slice_)
                text, buttons = _format_listing(slice_)
                header = "স্যার, আরও কিছু প্রোডাক্ট দেখুন:\n\n"
                return _ok(header + text, 'product_search', ic, products=slice_, link_buttons=buttons)
            # Pool exhausted — tell user, don't loop back to the same top-3
            logger.info("More rotation: pool exhausted at offset=%d", next_off)
            ic = intent_to_normalized(ctx)
            return _ok(
                "স্যার, এই বাজেট ও ক্যাটাগরিতে আর প্রোডাক্ট পাওয়া যাচ্ছে না। "
                "বাজেট বা ক্যাটাগরি একটু পরিবর্তন করে দেখুন, "
                "অথবা সরাসরি ভিজিট করুন: 👉 www.bdstall.com" + LOOP_BACK,
                'no_more_products', ic,
                link_buttons=_comparison_buttons(ctx),
            )

    result    = search_products(keywords, price_max, price_min)

    if result['products_found'] == 0:
        broader = _build_broader_keywords(ctx)
        if broader and broader != keywords:
            retry = search_products(broader, price_max, price_min)
            if retry['products_found'] > 0:
                keywords, result = broader, retry

    # If still no results and a budget was applied, retry with category-only (no budget)
    if result['products_found'] == 0 and (price_max is not None or price_min is not None):
        category_only = ctx.get('category', '').strip()
        brand = ctx.get('brand', '').strip()
        if brand and category_only:
            category_only = f"{brand} {category_only}"
        elif brand:
            category_only = brand
        logger.info("handle_product_search no-budget retry: category_only=%r", category_only)
        if category_only:  # only retry if we have a concrete search term
            no_budget_retry = search_products(category_only, None, None)
            logger.info("no-budget retry found=%d first=%s", no_budget_retry['products_found'],
                        no_budget_retry['products'][0]['title'] if no_budget_retry['products'] else 'none')
            if no_budget_retry['products_found'] > 0:
                # Filter: keep only products whose title contains the category keyword
                cat_kw = ctx.get('category', '').lower().split()[0] if ctx.get('category') else ''
                filtered = [p for p in no_budget_retry['products']
                            if not cat_kw or cat_kw in p.get('title', '').lower()]
                if filtered:
                    result = {'products_found': len(filtered), 'products': filtered}
                    ic = intent_to_normalized(ctx)
                    products = filtered
                    set_search_pool(user_id, current_key, products)
                    set_product_context(user_id, products[:5])
                    text, buttons = _format_listing(products[:3])
                    note = "স্যার, এই বাজেটে সরাসরি কোনো প্রোডাক্ট পাওয়া যায়নি। কাছাকাছি দামে এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
                    return _ok(note + text, 'product_search', ic, products=products, link_buttons=buttons)
                # filtered is empty — fall through to out-of-stock message below

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
    # Cache the full pool (up to 15) for "more" rotation
    set_search_pool(user_id, current_key, products)
    set_product_context(user_id, products[:5])
    text, buttons = _format_listing(products[:3])
    title_kw = (ctx.get('title') or '').lower().strip()
    # Warn if specific model/type requested but results don't match
    if title_kw and not any(title_kw in p.get('title', '').lower() for p in products):
        header = f"স্যার, এই বাজেটে '{ctx.get('title')}' পাওয়া যায়নি। কাছাকাছি অপশন:\n\n"
    elif price_max and price_min:
        header = f"স্যার, ৳{price_min:,} - ৳{price_max:,} বাজেটে এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
    elif price_max:
        header = f"স্যার, ৳{price_max:,} এর মধ্যে এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
    elif price_min:
        header = f"স্যার, ৳{price_min:,} এর উপরে এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
    else:
        header = "স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n\n"
    return _ok(header + text, 'product_search', ic, products=products, link_buttons=buttons)


def handle_price_query(ctx: Dict, user_id: str, message: str) -> Dict:
    has_budget = (ctx.get('price_max') is not None or ctx.get('price_min') is not None)

    # If a budget filter is given, do a fresh search (ignore cache).
    # Pass '' as message so _is_more_request never fires on a price query
    # containing words like "aro" (e.g. "আরও কিছুর দাম কত?").
    if has_budget and ctx.get('category'):
        return handle_product_search(ctx, user_id, '')

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

    return handle_product_search(ctx, user_id, '')


def handle_url_message(ctx: Dict, user_id: str, message: str, url: str) -> Dict:
    url_lower = url.lower()
    if re.search(r'bdstall\.com/(details|listing)/', url_lower):
        return handle_product_link(ctx, user_id, message, url)
    ic = normalize_payload(ctx)
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
    ic = normalize_payload(ctx)
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
            link_buttons=[{'text': 'বিডিস্টলে দেখুন', 'url': url}]
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
    from services.chatbot_service import _categories
    from repositories.state_repository import set_session_category
    slug_text = url.replace('-', ' ')
    cat_from_url = resolve_category_from_message(slug_text, _categories)
    if cat_from_url:
        set_session_category(user_id, cat_from_url)
        ic['cat'] = cat_from_url

    ic['product_url'] = url
    ic['title'] = title

    # If the same message also asks a follow-up question (warranty / spec / price /
    # color / stock / discount), route it through the followup handler so the bot
    # answers the actual question instead of just echoing the product card.
    msg_lower = (message or '').lower()
    _FOLLOWUP_TRIGGERS = (
        'warranty', 'warenty', 'warrenty', 'guarantee', 'waranti',
        'ওয়ারেন্টি', 'গ্যারান্টি',
        'spec', 'specification', 'feature', 'ram', 'storage', 'processor',
        'battery', 'display', 'camera',
        'color', 'colour', 'rong', 'রং', 'রঙ',
        'discount', 'ছাড়', 'offer',
        'stock', 'স্টক', 'available',
        'price', 'dam', 'দাম', 'মূল্য',
    )
    if any(t in msg_lower for t in _FOLLOWUP_TRIGGERS):
        followup = handle_product_detail_followup(ic, user_id, message, url)
        if followup:
            return followup

    lines = [f"স্যার, এই প্রোডাক্টটি পেয়েছি:", f"", f"📦 {title}", f"💰 মূল্য: {price}"]
    if orig_price and discount:
        lines.append(f"🏷️ আগের দাম: {orig_price} ({discount}% ছাড়)")
    lines.append(f"\nদাম, স্টক বা বিস্তারিত জানতে নিচের লিংকে ক্লিক করুন।")
    lines.append(LOOP_BACK)

    return _ok(
        '\n'.join(lines),
        'product_link', ic, products=products,
        link_buttons=[{'text': 'প্রোডাক্ট দেখুন', 'url': url, 'title': title, 'price': price}]
    )


def handle_product_detail_followup(ctx: Dict, user_id: str, message: str,
                                   product_url: str,
                                   groq_client=None,
                                   groq_model: str = '') -> Optional[Dict]:
    msg = message.lower()

    # User is rejecting the shown products (e.g. "৪০ এম্পিয়ারের হবে না",
    # "এটা হবে না", "na hobe", "pabo na"). Let the full pipeline re-search.
    _REJECTION_SIGNALS = {
        'হবে না', 'হবেনা', 'na hobe', 'hobe na', 'na hoi', 'hoi na',
        'পাওয়া যাবে না', 'পাবো না', 'paoa jabe na', 'pabo na',
        'এটা না', 'এগুলো না', 'এগুলো হবে না', 'এটা চাই না',
        'different', 'alada', 'অন্যরকম',
    }
    if any(s in msg for s in _REJECTION_SIGNALS):
        return None

    # Plain acknowledgment ("ok", "thik ache", "haan") — user is just confirming
    # they received the previous reply. Don't re-show products; reply with a short
    # ack and keep the conversation open.
    _ACK_SIGNALS = {
        'ok', 'okay', 'k', 'kk', 'ohk', 'oki',
        'theek ache', 'thik ache', 'thikache', 'ঠিক আছে',
        'আচ্ছা', 'acha', 'achaa', 'accha', 'acca', 'aca', 'sure',
        'haan', 'হ্যাঁ', 'ha', 'haa', 'haaa', 'hmm', 'hm',
    }
    msg_stripped = msg.strip().rstrip('.!?।,')
    if msg_stripped in _ACK_SIGNALS:
        ic_ack = normalize_payload(load_context(user_id))
        return _ok("জি, স্যার! আর কোনো প্রোডাক্ট বা বিষয়ে সাহায্য করতে পারি? 😊",
                   'ack', ic_ack)

    # Explicit "let me see / show me" — user wants to view the currently shown
    # products. Re-show cached list with buttons instead of triggering a new search.
    _VIEW_CURRENT_SIGNALS = {
        'দেখি', 'dekhi', 'dekhbo', 'দেখান', 'dekhao', 'dekhan',
    }
    prev_products_vc = get_product_context(user_id)
    if msg_stripped in _VIEW_CURRENT_SIGNALS and prev_products_vc:
        ic_vc = normalize_payload(load_context(user_id))
        text_vc, buttons_vc = _format_listing(prev_products_vc[:3])
        return _ok("স্যার, এই প্রোডাক্টগুলো দেখুন:\n\n" + text_vc,
                   'product_search', ic_vc, products=prev_products_vc, link_buttons=buttons_vc)

    # Quantity / bulk order question (e.g. "চার সেট", "৩টা নেবো", "5 pieces").
    # Answer about bulk ordering via the seller — don't re-search.
    _QUANTITY_PATTERN = re.compile(
        r'(\d+|এক|দুই|তিন|চার|পাঁচ|ছয়|সাত|আট|নয়|দশ|'
        r'one|two|three|four|five|six|seven|eight|nine|ten)'
        r'\s*(সেট|set|টা|টি|পিছ|পিস|pcs|piece|pieces|নগ|nos|copy|copies)',
        re.IGNORECASE
    )
    prev_products_qty = get_product_context(user_id)
    if _QUANTITY_PATTERN.search(msg) and prev_products_qty:
        ic_qty = normalize_payload(load_context(user_id))
        top_qty = prev_products_qty[0]
        url_qty = top_qty.get('url', '')
        title_qty = top_qty.get('title', '')
        buttons_qty = [{'text': 'প্রোডাক্ট দেখুন', 'url': url_qty, 'title': title_qty}] if url_qty else []
        return _ok(
            "স্যার, একাধিক পিস বা বাল্ক অর্ডারের জন্য সরাসরি বিক্রেতার সাথে যোগাযোগ করুন। "
            "প্রোডাক্ট পেজে বিক্রেতার নম্বর ও WhatsApp পাবেন।" + LOOP_BACK,
            'bulk_order_query', ic_qty, link_buttons=buttons_qty
        )

    # "more / aro / onno / dekhao" signals the user wants a NEW search, not a
    # follow-up question about the current product. Let the full pipeline handle it.
    _EXIT_SIGNALS = {
        'more', 'aro', 'onno', 'dekhao', 'dekhan', 'notun', 'alada',
        'অন্য', 'আরও', 'আরো', 'nতুন',
    }
    if any(s in msg for s in _EXIT_SIGNALS):
        return None

    # Technical/advice questions that span multiple products or are general
    # knowledge ("kon motherboard valo", "upgrade kora jabe ki") must NOT be
    # intercepted here — they belong to technical_advice.
    _TECHNICAL_ADVICE_SIGNALS = {
        'motherboard', 'upgrade', 'compatible', 'compatibility', 'difference',
        'better for', 'good for', 'gaming er jonno', 'er jonno kon', 'jonno valo',
        'jonno bhalo', 'suggest', 'recommend', 'konta nibo', 'konta kinbo',
        'which is better', 'konti valo', 'konta valo',
    }
    if any(s in msg for s in _TECHNICAL_ADVICE_SIGNALS):
        return None

    signals = [
        'stock', 'ache', 'available', 'color', 'colour', 'rong',
        'quality', 'maan', 'durable', 'price', 'dam', 'koto',
        'warranty', 'warenty', 'warrenty', 'warrantee', 'waranti', 'guarantee', 'original', 'kena jabe', 'pabo',
        'intake', 'original intake', 'non intake', 'নন ইনটেক', 'ইনটেক',
        'স্টক', 'রং', 'মান', 'দাম', 'ওয়ারেন্টি', 'spec', 'feature',
        'detail', 'details', 'বিস্তারিত', 'কেমন', 'kemon', 'review', 'rating',
        'used', 'new', 'পুরনো', 'purano', 'second hand', 'refurbished',
        'condition', 'কন্ডিশন', 'fresh',
        'discount', 'ছাড়', 'offer', 'fixed', 'negotiate', 'কমানো', 'কমবে',
        # spec query signals — caught here so they don't fall to technical_advice
        'ram', 'gb', 'storage', 'memory', 'processor', 'cpu', 'battery', 'mah',
        'display', 'screen', 'camera', 'mp', 'os', 'weight', 'configuration',
        'র‍্যাম', 'প্রসেসর', 'ব্যাটারি', 'ডিসপ্লে', 'ক্যামেরা',
    ]
    if not any(s in msg for s in signals):
        return None

    # If the message contains a new product name different from what's cached,
    # treat it as a new search ("trimmer ache" after laptop results = search trimmer).
    # We detect this by checking if a non-trivial noun in the message matches none
    # of the cached product titles — in that case let the full pipeline handle it.
    _prev_products_check = get_product_context(user_id)
    if _prev_products_check:
        cached_titles_lower = ' '.join(
            p.get('title', '').lower() for p in _prev_products_check[:3]
        )
        # Words in message that are not pure availability/signal words
        _SIGNAL_ONLY_WORDS = {
            'ache', 'ase', 'available', 'stock', 'আছে', 'কি', 'ki', 'pabo',
            'hobe', 'paoa', 'jabe', 'আপনাদের', 'apnader', 'কাছে', 'kache',
        }
        # Any followup signal word (warranty/spec/price/color/etc.) is also not a
        # product noun — without this, "warrenty ase" was treated as a new product
        # search for "warrenty" instead of a warranty question about the cached item.
        _signals_lower = {s.lower() for s in signals}
        msg_nouns = [w for w in re.findall(r'[a-zঀ-৿]+', msg)
                     if len(w) > 3
                     and w not in _SIGNAL_ONLY_WORDS
                     and w not in _signals_lower]
        if msg_nouns and not any(noun in cached_titles_lower for noun in msg_nouns):
            return None  # New product — let pipeline do a fresh search

    ic = normalize_payload(load_context(user_id))
    prev_products = get_product_context(user_id)

    # If multiple products shown and user asks a general question, ask which one
    _AMBIGUOUS_SIGNALS = {
        'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
        'condition', 'কন্ডিশন', 'fresh',
        'intake', 'original intake', 'non intake', 'ইনটেক', 'নন ইনটেক',
    }
    if len(prev_products) > 1 and any(s in msg for s in _AMBIGUOUS_SIGNALS):
        # Try to auto-select by self-reference ("atar", "etar") or model token in message
        _SELF_REF_FU = {'atar', 'etar', 'otar', 'its', 'এটার', 'ওটার', 'এইটার', 'mane', 'মানে'}
        auto_idx_fu = -1
        if any(w in msg for w in _SELF_REF_FU):
            auto_idx_fu = 0
        else:
            msg_tokens_fu = re.findall(r'[a-z0-9]+', msg)
            model_tokens_fu = [t for t in msg_tokens_fu if re.search(r'\d', t)]
            for token in model_tokens_fu:
                for i, p in enumerate(prev_products[:3]):
                    if token in (p.get('title') or '').lower():
                        auto_idx_fu = i
                        break
                if auto_idx_fu >= 0:
                    break

        if auto_idx_fu >= 0:
            from repositories.state_repository import set_product_url as _set_url_fu
            selected_fu = prev_products[auto_idx_fu]
            set_product_context(user_id, [selected_fu])
            if selected_fu.get('url'):
                _set_url_fu(user_id, selected_fu['url'])
            prev_products = [selected_fu]
        else:
            product_list = '\n'.join(
                f"{i+1}. {p.get('title', '')[:50]}"
                for i, p in enumerate(prev_products[:3])
            )
            return _ok(
                f"স্যার, কোন প্রোডাক্টটি সম্পর্কে জানতে চান, ১, ২, ৩ যেকোনো নম্বর বলুন।\n\n{product_list}",
                'product_clarification', ic
            )

    top = prev_products[0] if prev_products else {}
    title = top.get('title', '')

    _SPEC_SIGNALS = {
        'ram', 'gb', 'storage', 'memory', 'processor', 'cpu', 'battery', 'mah',
        'display', 'screen', 'camera', 'mp', 'os', 'weight', 'configuration',
        'hard disk', 'ssd', 'hdd', 'ghz', 'chipset', 'graphics', 'gpu',
        'র‍্যাম', 'প্রসেসর', 'ব্যাটারি', 'ডিসপ্লে', 'ক্যামেরা',
        'spec', 'specification', 'full spec',
    }
    _COLOR_SIZE_SIGNALS = {
        'color', 'colour', 'rong', 'রং', 'রঙ', 'ki ki color', 'কি কি রং',
        'size', 'সাইজ', 'কত সাইজ', 'variant', 'option',
    }
    _STOCK_SIGNALS = {
        'stock', 'available', 'পাবো', 'pabo', 'পাওয়া যাবে', 'আছে কি', 'স্টক আছে',
    }

    buttons = [{'text': 'প্রোডাক্ট দেখুন', 'url': product_url, 'title': title}] if product_url else []

    if any(w in msg for w in ('warranty', 'warenty', 'warrenty', 'guarantee', 'ওয়ারেন্টি', 'গ্যারান্টি', 'waranti')):
        warranty_value = ''
        listing_id = _extract_product_id(product_url)
        if listing_id:
            spec_data = fetch_product_spec(listing_id)
            warranty_value = str(((spec_data or {}).get('features') or {}).get('Warranty') or '').strip()
        if warranty_value:
            reply = f"🛡️ ওয়ারেন্টি\n━━━━━━━━━━━━━━━\n{warranty_value}"
        else:
            reply = "🛡️ ওয়ারেন্টি\n━━━━━━━━━━━━━━━\nওয়ারেন্টি সংক্রান্ত বিস্তারিত তথ্য প্রোডাক্ট পেজে দেওয়া আছে।"

    elif any(w in msg for w in ('price', 'dam', 'দাম', 'মূল্য')) and not any(w in msg for w in _SPEC_SIGNALS):
        _raw_price = str(top.get('price') or '').strip()
        price = _raw_price if (_raw_price and _raw_price not in ('N/A', '0', '0.00')) else ''
        if not price:
            listing_id = _extract_product_id(product_url)
            if listing_id:
                spec_data = fetch_product_spec(listing_id)
                price = str((spec_data or {}).get('price') or '').strip()
                if price in ('N/A', '0', '0.00'):
                    price = ''
        if price:
            reply = f"💰 মূল্য\n━━━━━━━━━━━━━━━\n৳ {price}"
        elif title:
            reply = f"💰 মূল্য\n━━━━━━━━━━━━━━━\n{title} এর সর্বশেষ মূল্য জানতে প্রোডাক্ট পেজটি দেখুন।"
        else:
            reply = "স্যার, দাম জানতে প্রোডাক্ট পেজটি দেখুন।"

    elif any(w in msg for w in ('discount', 'ছাড়', 'offer', 'fixed', 'negotiate', 'কমানো', 'কমবে')):
        discount = int(top.get('discount') or 0)
        _raw_price = str(top.get('price') or '').strip()
        price = _raw_price if (_raw_price and _raw_price not in ('N/A', '0', '0.00')) else ''
        orig   = str(top.get('original_price') or '').strip()
        if discount and price:
            price_fmt = price if price.lstrip().startswith('৳') else f"৳ {price}"
            orig_fmt = orig if orig.lstrip().startswith('৳') else f"৳ {orig}"
            reply = (
                f"🏷️ মূল্য ও ছাড়\n━━━━━━━━━━━━━━━\n"
                f"বর্তমান মূল্য: {price_fmt}\n"
                f"আগের মূল্য: {orig_fmt} ({discount}% ছাড়)\n\n"
                f"এই মূল্যটি ইতোমধ্যে ডিসকাউন্টেড — আরও বেশি সাশ্রয়ের সুযোগ থাকলে আমরা অবশ্যই জানাবো!"
            )
        else:
            reply = (
                f"🏷️ মূল্য ও অফার\n━━━━━━━━━━━━━━━\n"
                f"আমাদের ওয়েবসাইটে প্রোডাক্টের মূল্য সাধারণত ফিক্সড থাকে, "
                f"তবে সময়ে সময়ে বিশেষ অফার ও ডিসকাউন্ট দেওয়া হয়। "
                f"সর্বশেষ অফার দেখতে প্রোডাক্ট পেজটি চেক করুন।"
            )

    elif any(w in msg for w in _STOCK_SIGNALS):
        reply = ("📦 স্টক\n━━━━━━━━━━━━━━━\n"
                 "স্টক তথ্য প্রতিনিয়ত আপডেট হয়। সর্বশেষ স্টক জানতে প্রোডাক্ট পেজটি দেখুন।")

    elif any(w in msg for w in _COLOR_SIZE_SIGNALS):
        reply = ("🎨 রং ও ভেরিয়েন্ট\n━━━━━━━━━━━━━━━\n"
                 "রং ও স্টক প্রতিনিয়ত পরিবর্তন হয়। সর্বশেষ অপশন দেখতে প্রোডাক্ট পেজটি দেখুন।")

    elif any(w in msg for w in ('used', 'new', 'notun', 'purano', 'second hand',
                                'refurbished', 'condition', 'কন্ডিশন', 'fresh')):
        product_id = _extract_product_id(product_url)
        api_reply = fetch_condition_template(product_id) if product_id else None
        if api_reply:
            reply = f"🔍 কন্ডিশন\n━━━━━━━━━━━━━━━\n{api_reply}"
        else:
            reply = ("🔍 কন্ডিশন\n━━━━━━━━━━━━━━━\n"
                     + (f"{title} এর কন্ডিশন জানতে প্রোডাক্ট পেজটি দেখুন।"
                        if title else "প্রোডাক্টের কন্ডিশন জানতে পেজটি দেখুন।"))

    elif any(w in msg for w in _SPEC_SIGNALS):
        # Spec question — delegate to handle_product_spec_query for DB lookup.
        # Defined later in this file; forward reference is fine at call time.
        ctx_for_spec = {'category': '', 'brand': '', 'title': title}
        return handle_product_spec_query(ctx_for_spec, user_id, message, groq_client, groq_model)

    else:
        reply = (f"{title} সম্পর্কে আরও তথ্য প্রোডাক্ট পেজে পাবেন।"
                 if title else "বিস্তারিত তথ্য প্রোডাক্ট পেজে পাবেন।")

    return _ok(
        reply + LOOP_BACK,
        'product_detail_followup', ic,
        link_buttons=buttons
    )


# ── Spec keyword → ListingFeatures key mapping ────────────────────────────────
# Real field names verified from the live API across product types:
#   Laptop : Processor Type, Processor Speed, Chipset, Screen Size, RAM,
#            Hard Disk, Disk Type, Graphics Card, Battery, Product Weight (Kg)
#   Mobile : CPU, Display, RAM, Built In Memory, Battery Capacity, Camera,
#            OS, Network, SIM, Weight
#   TV     : Screen Size, Resolution, Refresh Rate, Panel, Technology
#   AC     : BTU, Coverage, AC Type, Energy Efficient, Power Consumption
#   Fridge : Capacity, Freezer Type, Dimension
#   GPU    : Capacity (MB), Clock Speed, Memory Type, Graphics Processor
#
# Rule: first matching api_key with a non-empty value wins.
# To add a new product type: just append a row — no other code needs changing.

_SPEC_KEYWORD_MAP = [
    # ── RAM ───────────────────────────────────────────────────────────────────
    (['ram', 'র‍্যাম', 'memory gb', 'gb ram'],
     ['RAM']),

    # ── Processor / CPU ───────────────────────────────────────────────────────
    # "speed" alone matches processor speed (not clock speed / refresh rate).
    # Order matters: check Processor Speed before plain Processor Type.
    (['processor speed', 'cpu speed', 'ghz', 'clock speed', 'processor frequency',
      'প্রসেসর স্পিড'],
     ['Processor Speed', 'Clock Speed']),

    (['processor', 'cpu', 'chipset', 'প্রসেসর', 'chip', 'core'],
     ['Processor Type', 'CPU', 'Processor', 'Chipset', 'Graphics Processor']),

    # ── Storage / HDD / SSD ───────────────────────────────────────────────────
    (['storage', 'hard disk', 'hdd', 'ssd', 'disk', 'hard drive',
      'হার্ড', 'hard', 'built in', 'internal memory'],
     ['Hard Disk', 'Built In Memory', 'Storage', 'Internal Memory']),

    (['disk type', 'storage type'],
     ['Disk Type']),

    # ── Display / Screen ──────────────────────────────────────────────────────
    (['display size', 'screen size', 'screen inch', 'display inch',
      'কত ইঞ্চি', 'inch', 'ডিসপ্লে', 'স্ক্রিন'],
     ['Screen Size', 'Display', 'Display Size']),

    (['resolution', 'রেজোলিউশন'],
     ['Resolution']),

    (['refresh rate', 'hz', 'panel'],
     ['Refresh Rate', 'Panel', 'Response Time']),

    # ── Battery ───────────────────────────────────────────────────────────────
    (['battery', 'mah', 'ব্যাটারি', 'backup', 'talk time', 'stand by'],
     ['Battery Capacity', 'Battery', 'Talk Time', 'Stand By']),

    # ── Camera ────────────────────────────────────────────────────────────────
    (['camera', 'mp', 'megapixel', 'ক্যামেরা', 'selfie', 'front camera'],
     ['Camera', 'Main Camera', 'Rear Camera', 'Primary Camera', 'Front Camera']),

    # ── GPU / Graphics ────────────────────────────────────────────────────────
    (['gpu', 'graphics', 'gfx', 'গ্রাফিক্স', 'graphics card', 'vram'],
     ['Graphics Card', 'GPU', 'Graphics', 'Capacity (MB)', 'Memory Type']),

    # ── OS ────────────────────────────────────────────────────────────────────
    (['os', 'operating system', 'windows', 'android', 'ios', 'software',
      'অপারেটিং'],
     ['OS', 'Operating System', 'Software']),

    # ── Weight ────────────────────────────────────────────────────────────────
    (['weight', 'ওজন', 'kg', 'heavy'],
     ['Product Weight (Kg)', 'Weight']),

    # ── Network / Connectivity ────────────────────────────────────────────────
    (['network', '5g', '4g', 'lte', 'wifi', 'wi-fi', 'bluetooth',
      'connectivity', 'networking'],
     ['Network', 'Networking', 'Connectivity', 'WLAN', 'Bluetooth']),

    (['sim', 'সিম'],
     ['SIM']),

    # ── AC specific ───────────────────────────────────────────────────────────
    (['btu', 'ton', 'কত টন'],
     ['BTU']),

    (['coverage', 'square feet', 'room size', 'area'],
     ['Coverage']),

    (['inverter', 'energy efficient', 'energy saving', 'power consumption'],
     ['Energy Efficient', 'Power Consumption']),

    (['ac type', 'split', 'window ac'],
     ['AC Type']),

    (['cooling speed', 'fan speed', 'airflow'],
     ['Cooling Speed', 'Fan Speed', 'Air Control']),

    # ── Fridge / freezer specific ─────────────────────────────────────────────
    (['capacity', 'liter', 'litre', 'ধারণ ক্ষমতা', 'freezer'],
     ['Capacity', 'Freezer Type']),

    # ── TV specific ───────────────────────────────────────────────────────────
    (['smart', 'hdmi', 'usb port', 'tv tuner', 'technology'],
     ['Technology', 'Connectivity', 'TV Tuner']),

    # ── Dimensions ────────────────────────────────────────────────────────────
    (['dimension', 'size', 'measure'],
     ['Dimensions (W x D x H)', 'Dimension (L x W x H)', 'Dimension']),

    # ── Warranty ─────────────────────────────────────────────────────────────
    (['warranty', 'guarantee', 'ওয়ারেন্টি'],
     ['Warranty']),

    # ── Condition ────────────────────────────────────────────────────────────
    (['condition', 'used', 'new', 'refurbished', 'কন্ডিশন'],
     ['Condition']),
]


def _match_spec_key(message: str, features: Dict) -> Optional[str]:
    """Return "FeatureName: value" for the best matching spec.

    Two-pass strategy:
      Pass 1 — explicit map: scan _SPEC_KEYWORD_MAP in order; first row whose
               keywords hit the message AND has a non-empty API value wins.
      Pass 2 — fuzzy scan: if no map hit, check every feature name directly
               against the message words (handles rare/new field names without
               needing a map update).
    """
    msg = message.lower()

    # Pass 1 — keyword map
    for keywords, api_keys in _SPEC_KEYWORD_MAP:
        if any(kw in msg for kw in keywords):
            for api_key in api_keys:
                val = features.get(api_key, '')
                if val:
                    return f"{api_key}: {val}"

    # Pass 2 — fuzzy: split message into words, check if any word appears
    # inside a feature name (or vice-versa). Avoids false positives from
    # very short words by requiring length >= 4.
    msg_words = [w for w in re.findall(r'[a-z0-9]+', msg) if len(w) >= 4]
    for feat_name, feat_val in features.items():
        if not feat_val:
            continue
        feat_lower = feat_name.lower()
        if any(w in feat_lower or feat_lower in w for w in msg_words):
            return f"{feat_name}: {feat_val}"

    return None


def _get_technical_answer_from_review(message: str, review: str,
                                      groq_client, groq_model: str) -> Optional[str]:
    """Ask Groq to extract a specific spec from the product's own description.

    Groq is constrained to only use the provided text — it cannot fall back to
    its training knowledge about other products.
    """
    if not groq_client or not review:
        return None
    system = (
        "You are a product spec extractor for BDStall.com.\n"
        "Answer the user's question using ONLY the product description text provided.\n"
        "Give a short, direct answer in the same language the user used (Bangla/Banglish/English).\n"
        "If the answer is not found in the description, reply with exactly: NOT_FOUND"
    )
    user_prompt = f"Product description:\n{review}\n\nQuestion: {message}"
    try:
        resp = groq_client.chat.completions.create(
            model=groq_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=150,
        )
        answer = resp.choices[0].message.content.strip()
        return None if answer == 'NOT_FOUND' else answer
    except Exception as e:
        logger.warning("_get_technical_answer_from_review failed: %s", e)
        return None


def handle_product_spec_query(ctx: Dict, user_id: str, message: str,
                               groq_client=None, groq_model: str = '') -> Dict:
    """Answer a spec question (RAM, display, battery…) about the product on screen.

    Flow:
      1. Get listing_id from cached product URL
      2. Call fetch_product_spec(listing_id) → structured features + plain review
      3. Keyword-match the user's question to a feature key → direct answer
      4. If no structured match, ask Groq constrained to the product's own review text
      5. If nothing → redirect to product page
    """
    ic = intent_to_normalized(ctx)
    msg = message.lower()

    # Resolve the product URL — prefer the dedicated product_url store,
    # fall back to the first cached search result.
    prev_products = get_product_context(user_id)
    from repositories.state_repository import get_product_url
    product_url = get_product_url(user_id) or (prev_products[0].get('url', '') if prev_products else '')

    # When there are multiple products and the question is ambiguous, ask which one
    if len(prev_products) > 1 and not get_product_url(user_id):
        product_list = '\n'.join(
            f"{i+1}. {p.get('title', '')[:50]}"
            for i, p in enumerate(prev_products[:3])
        )
        return _ok(
            f"স্যার, কোন প্রোডাক্টটি সম্পর্কে জানতে চান, ১, ২, ৩ যেকোনো নম্বর বলুন।\n\n{product_list}",
            'product_clarification', ic
        )

    listing_id = _extract_product_id(product_url)
    logger.info("handle_product_spec_query: url=%r id=%r msg=%r", product_url, listing_id, message)

    if not listing_id:
        # No product on screen — treat as general technical advice instead.
        # Rate-limited: Groq-backed knowledge answers cap at KNOWLEDGE_DAILY_LIMIT/day.
        if get_knowledge_count(user_id) >= KNOWLEDGE_DAILY_LIMIT:
            try:
                assign_agent(user_id, 'knowledge_limit_exceeded')
            except Exception as e:
                logger.warning("assign_agent on knowledge limit failed: %s", e)
            return _ok(
                "স্যার, আজকের জন্য বিস্তারিত পরামর্শের সীমা শেষ হয়েছে। "
                "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।",
                'knowledge_limit_exceeded', ic
            )
        from services.intent_service import get_technical_advice
        answer = get_technical_advice(message, groq_client, groq_model)
        if answer:
            increment_knowledge_count(user_id)
            return _ok(
                answer + "\n\nতবে স্যার, কেনার আগে অবশ্যই আরেকবার যাচাই করে নিন।" + LOOP_BACK,
                'technical_advice', ic
            )
        return _ok(
            "স্যার, কোন প্রোডাক্টটি সম্পর্কে জানতে চাইছেন? প্রোডাক্টের লিংক দিন বা নাম বলুন।"
            + LOOP_BACK,
            'product_spec_query', ic
        )

    spec_data = fetch_product_spec(listing_id)
    logger.info("handle_product_spec_query: spec_data keys=%s",
                list(spec_data['features'].keys()) if spec_data else 'None')

    if not spec_data:
        return _ok(
            "স্যার, এই মুহূর্তে প্রোডাক্টের তথ্য লোড করা যাচ্ছে না। "
            "সরাসরি প্রোডাক্ট পেজটি দেখুন।" + LOOP_BACK,
            'product_spec_query', ic,
            link_buttons=[{'text': 'প্রোডাক্ট দেখুন', 'url': product_url}] if product_url else []
        )

    features = spec_data['features']
    title    = spec_data.get('title', '')
    review   = spec_data.get('review', '')

    # ── Check if user wants full spec sheet ───────────────────────────────────
    _FULL_SPEC_WORDS = {'full spec', 'specs', 'specification', 'configuration',
                        'সব স্পেক', 'full specification', 'বিস্তারিত স্পেক'}
    wants_full = any(w in msg for w in _FULL_SPEC_WORDS)

    if wants_full or not features:
        if features:
            lines = [f"📋 {title}", "─────────────────────", ""]
            for feat_name, feat_val in list(features.items())[:15]:
                lines.append(f"▪ {feat_name}: {feat_val}")
            lines.append("")
            lines.append(LOOP_BACK)
            return _ok('\n'.join(lines), 'product_spec_query', ic)
        # No features at all — fall through to review-based Groq answer

    # ── Try structured feature match first ────────────────────────────────────
    matched = _match_spec_key(msg, features)
    if matched:
        feat_name, feat_val = matched.split(': ', 1)
        reply = f"✅ {feat_name}\n━━━━━━━━━━━━━━━\n{feat_val}"
        logger.info("handle_product_spec_query: structured match %r → %r", feat_name, feat_val)
        return _ok(reply + LOOP_BACK, 'product_spec_query', ic)

    # ── Groq constrained to this product's own review text ────────────────────
    # Rate-limited: this is a knowledge-style answer, counts against daily quota.
    if get_knowledge_count(user_id) < KNOWLEDGE_DAILY_LIMIT:
        groq_answer = _get_technical_answer_from_review(message, review, groq_client, groq_model)
        if groq_answer:
            increment_knowledge_count(user_id)
            logger.info("handle_product_spec_query: Groq review-based answer returned")
            return _ok(groq_answer + LOOP_BACK, 'product_spec_query', ic)
    else:
        logger.info("handle_product_spec_query: knowledge limit reached, skipping Groq")

    # ── Nothing found — warm redirect with product page link ─────────────────
    _LIVE_INVENTORY_WORDS = {
        'color', 'colour', 'rong', 'রং', 'রঙ',
        'size', 'সাইজ', 'variant',
        'stock', 'available', 'ache', 'আছে',
    }
    if any(w in msg for w in _LIVE_INVENTORY_WORDS):
        reply = (
            f"স্যার, রং, সাইজ ও স্টক তথ্য প্রতিনিয়ত পরিবর্তন হয়, "
            f"তাই আমাদের ডেটাবেজে সবসময় আপডেট থাকে না। "
            f"সর্বশেষ তথ্য জানতে প্রোডাক্ট পেজটি দেখুন"
            + (f" অথবা আমাদের টিমের সাথে যোগাযোগ করুন।" if title else "।")
        )
    else:
        reply = (
            f"স্যার, এই তথ্যটি এই মুহূর্তে আমাদের কাছে নেই। "
            f"বিস্তারিত জানতে প্রোডাক্ট পেজটি দেখুন।"
            if title else
            "স্যার, বিস্তারিত তথ্য প্রোডাক্ট পেজে পাবেন।"
        )
    buttons = [{'text': 'প্রোডাক্ট দেখুন', 'url': product_url,
                'title': title}] if product_url else []
    return _ok(reply + LOOP_BACK, 'product_spec_query', ic, link_buttons=buttons)


def handle_fallback(ctx: Dict, user_id: str, message: str,
                    faq_db: List = None) -> Dict:
    # Re-fire buy only when the current message also has buy-related words.
    # Without this guard, any unknown message after a buy turn (e.g. "delivery
    # charge koto?") would incorrectly return the order instructions again.
    _BUY_CONTINUATION = {'kinbo', 'kinte', 'buy', 'order', 'কিনব', 'কিনতে',
                         'অর্ডার', 'payment', 'cod', 'cash on delivery'}
    if (get_last_intent(user_id) == 'buy'
            and any(w in message.lower() for w in _BUY_CONTINUATION)):
        return handle_buy(ctx, user_id, message)
    msg_lower = message.lower()
    if any(w in msg_lower for w in _AI_IDENTITY_WORDS):
        ic = intent_to_normalized(ctx)
        return _ok(_AI_IDENTITY_RESPONSE + LOOP_BACK, 'faq_identity', ic)
    if any(w in msg_lower for w in _PROPERTY_WORDS):
        ic = intent_to_normalized(ctx)
        return _handle_property_query(user_id, message, ic)
    # Warranty questions always get the fixed website response
    if any(w in msg_lower for w in _WARRANTY_WORDS):
        ic = intent_to_normalized(ctx)
        return _ok(_WARRANTY_RESPONSE + LOOP_BACK, 'faq_warranty', ic)
    # Showroom / address / location questions get the fixed response
    if any(w in msg_lower for w in _SHOWROOM_WORDS):
        ic = intent_to_normalized(ctx)
        return _ok(_SHOWROOM_RESPONSE + LOOP_BACK, 'faq_showroom', ic)
    # If products were shown, handle product-specific questions
    prev_products = get_product_context(user_id)
    if prev_products:
        _price_signals = {'price', 'dam', 'দাম', 'koto', 'কত', 'cost', 'rate', 'মূল্য', 'taka', 'টাকা'}
        _buy_signals_fallback = {'kinbo', 'kinte', 'buy', 'order', 'কিনব', 'কিনতে', 'অর্ডার'}
        # Don't re-route to price_query when the message also has buy intent —
        # "kinbo, dam koto?" should stay as buy, not become price_query.
        is_buy_message = any(w in msg_lower for w in _buy_signals_fallback)
        if not is_buy_message and any(w in msg_lower for w in _price_signals):
            return handle_price_query(ctx, user_id, message)
        condition_result = _handle_condition_question(user_id, message)
        if condition_result:
            return condition_result
    if ctx.get('category'):
        return handle_product_search(ctx, user_id, message)
    ic = intent_to_normalized(ctx)
    # Smart clarification: if we know the user's recent interests, ask a
    # targeted question instead of dumping the generic category prompt.
    return _ok(
        _smart_clarification_prompt(ctx, user_id) + LOOP_BACK,
        'unknown', ic
    )


# ── Category prompt ───────────────────────────────────────────────────────────

def _ask_category(ctx: Dict, user_id: str = '') -> Dict:
    ic = intent_to_normalized(ctx)
    return _ok(_smart_clarification_prompt(ctx, user_id), 'need_category', ic)


def _smart_clarification_prompt(ctx: Dict, user_id: str = '') -> str:
    """Build a clarification that uses user profile when available.

    Falls back to CATEGORY_PROMPT when there's no profile signal worth
    referencing — never produces a worse message than the default.
    """
    try:
        from repositories.state_repository import load_user_profile, get_session_category
        profile = load_user_profile(user_id) if user_id else None
        session_cat = get_session_category(user_id) if user_id else ''
    except Exception:
        profile = None
        session_cat = ''

    if not profile or profile.message_count == 0:
        return CATEGORY_PROMPT

    brand_hint = profile.preferred_brands[0] if profile.preferred_brands else ''
    cat_hint = profile.interested_categories[0] if profile.interested_categories else ''

    # Don't reference the profile category if the session already switched to a new one
    if session_cat and cat_hint and session_cat.lower() != cat_hint.lower():
        cat_hint = ''
        brand_hint = ''
    lang = profile.language

    if cat_hint and brand_hint:
        if lang == 'bangla':
            return (f"স্যার, আগে আপনি {brand_hint.title()} {cat_hint} দেখছিলেন। "
                    "এবার কী খুঁজছেন — একই ক্যাটাগরি, নাকি অন্য কিছু?")
        if lang == 'english':
            return (f"Earlier you were looking at {brand_hint.title()} {cat_hint}. "
                    "Same category this time, or something different?")
        # banglish (default)
        return (f"স্যার, আগে {brand_hint.title()} {cat_hint} dekhcilen. "
                "Ebar ki same category, naki onno kichu?")

    if cat_hint:
        if lang == 'bangla':
            return f"স্যার, আবার {cat_hint} দেখাবো, নাকি অন্য কোনো ক্যাটাগরি?"
        if lang == 'english':
            return f"Want me to show you {cat_hint} again, or a different category?"
        return f"স্যার, abar {cat_hint} dekhabo, naki onno category?"

    if brand_hint:
        if lang == 'bangla':
            return (f"স্যার, {brand_hint.title()}-এর কী প্রোডাক্ট খুঁজছেন? "
                    "phone, laptop, না অন্য কিছু?")
        if lang == 'english':
            return (f"Which {brand_hint.title()} product are you looking for — "
                    "phone, laptop, or something else?")
        return (f"স্যার, {brand_hint.title()}-er ki product khujchen — "
                "phone, laptop, naki onno kichu?")

    return CATEGORY_PROMPT


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
                    [{'text': 'দেখুন', 'url': url, 'title': title, 'price': price}] if url else [])
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
