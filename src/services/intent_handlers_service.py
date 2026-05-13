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
from services.api_client_service import search_products, fetch_delivery_template, fetch_condition_template
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
    from repositories.state_repository import clear_product_state, set_session_category
    clear_product_state(user_id)
    set_session_category(user_id, '')
    # Reset all context so stale category/price don't bleed into next conversation
    ic = {'title': '', 'cat': '', 'brand': '', 'price_max': 0, 'price_min': 0, 'compare': '', 'buy': ''}
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
    # Show Order Now only for the most recently viewed single product
    if prev_products:
        p = prev_products[0]
        url = p.get('url', '')
        title = (p.get('title') or 'প্রোডাক্ট দেখুন')[:40]
        if url:
            buttons.append({'text': 'Order Now', 'url': url, 'title': title})
    if not buttons:
        buttons = [{'text': 'BDStall.com দেখুন', 'url': 'https://www.bdstall.com/'}]
    return _ok(
        "স্যার, অর্ডার করার নিয়ম:\n\n"
        "১. পছন্দের প্রোডাক্টের 'Order Now' বাটনে ক্লিক করুন\n"
        "২. আপনার নাম, ঠিকানা ও ফোন নম্বর দিন\n"
        "৩. অর্ডার সাবমিট করুন\n\n"
        "✅ ক্যাশ অন ডেলিভারি সুবিধা পাওয়া যায়। "
        "আমাদের টিম আপনাকে কল করে অর্ডার কনফার্ম করবে।\n\n"
        "আরও সাহায্যের জন্য 👉 www.bdstall.com ভিজিট করুন।"
        + LOOP_BACK,
        'buy', ic, link_buttons=buttons
    )


def handle_comparison(ctx: Dict, user_id: str, message: str) -> Dict:
    ic = intent_to_normalized(ctx)
    prev_products = get_product_context(user_id)
    if prev_products:
        top = prev_products[0]
        title = top.get('title', '')
        price = top.get('price', '')
        url = top.get('url', '')
        lines = [f"স্যার, দেখানো প্রোডাক্টগুলোর মধ্যে এটি সবচেয়ে ভালো হবে:", ""]
        if title:
            lines.append(f"📦 {title}")
        if price:
            lines.append(f"💰 মূল্য: {price}")
        lines.append("")
        lines.append("রিভিউ ও বিস্তারিত দেখে পছন্দ হলে অর্ডার করতে পারেন।")
        lines.append(LOOP_BACK)
        buttons = [{'text': 'View Product', 'url': url, 'title': title,
                    'price': price}] if url else _comparison_buttons(ctx)
        return _ok('\n'.join(lines), 'comparison', ic, link_buttons=buttons)
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


_SHOWROOM_WORDS = {
    'showroom', 'show room', 'শোরুম', 'শো রুম', 'office', 'অফিস',
    'address', 'ঠিকানা', 'location', 'লোকেশন', 'kothay', 'কোথায়',
}

_SHOWROOM_RESPONSE = (
    "বিডিস্টলের নির্দিষ্ট কোনো শোরুম নেই। তবে এখানে অনেক বিক্রেতা আছেন, "
    "আপনি চাইলে তাদের দেখতে পারেন: 👉 www.bdstall.com"
)


def handle_faq(ctx: Dict, user_id: str, message: str, faq_db: List) -> Dict:
    ic = intent_to_normalized(ctx)
    msg_lower = message.lower()
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


_CONDITION_WORDS = {
    'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
    'condition', 'কন্ডিশন', 'fresh', 'is it used', 'is it new',
    'nতুন', 'পুরনো', 'পুরাতন', 'naki purano', 'notun naki',
}


def _handle_condition_question(user_id: str, message: str) -> Optional[Dict]:
    """If user asks about condition and products are in cache, respond or ask clarification."""
    msg = message.lower()
    if not any(w in msg for w in _CONDITION_WORDS):
        return None
    prev_products = get_product_context(user_id)
    if not prev_products:
        return None
    ic = normalize_payload(load_context(user_id))
    if len(prev_products) > 1:
        product_list = '\n'.join(
            f"{i+1}. {p.get('title', '')[:50]}"
            for i, p in enumerate(prev_products[:3])
        )
        return _ok(
            f"স্যার, কোন প্রোডাক্টটি সম্পর্কে জানতে চাইছেন?\n\n{product_list}" + LOOP_BACK,
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
    buttons = [{'text': 'View Product', 'url': product_url_top,
                'title': top.get('title', '')}] if product_url_top else []
    return _ok(condition_text + LOOP_BACK, 'product_condition', ic, link_buttons=buttons)


def handle_clarification_selection(user_id: str, message: str) -> Optional[Dict]:
    """After product_clarification, detect numbered selection and call condition API."""
    prev_products = get_product_context(user_id)
    if not prev_products:
        return None
    msg = message.strip()
    # Match leading number: "1", "1.", "1)", "#1", or message starting with product title fragment
    num_match = re.match(r'^[#\s]*([123])[.):\s]?$|^[#\s]*([123])[.):\s]', msg)
    if not num_match:
        # Try matching by product title keyword
        for i, p in enumerate(prev_products[:3]):
            title_words = (p.get('title') or '').lower().split()[:3]
            if any(w in msg.lower() for w in title_words if len(w) > 3):
                num_match = type('m', (), {'group': lambda self, x: str(i+1)})()
                break
    if not num_match:
        return None
    idx = int(num_match.group(1) or num_match.group(2)) - 1
    if idx < 0 or idx >= len(prev_products):
        return None
    selected = prev_products[idx]
    product_url_sel = selected.get('url', '')
    product_id = _extract_product_id(product_url_sel)
    logger.info("clarification_selection: idx=%d url=%r id=%r", idx, product_url_sel, product_id)
    api_reply = fetch_condition_template(product_id) if product_id else None
    logger.info("clarification_selection: api_reply=%r", api_reply)
    title = selected.get('title', '')
    condition_text = (api_reply or
                      f"স্যার, {title} এর কন্ডিশন জানতে প্রোডাক্ট পেজটি দেখুন।")
    ic = normalize_payload(load_context(user_id))
    buttons = [{'text': 'View Product', 'url': product_url_sel, 'title': title}] if product_url_sel else []
    return _ok(condition_text + LOOP_BACK, 'product_condition', ic, link_buttons=buttons)


def handle_product_search(ctx: Dict, user_id: str, message: str) -> Dict:
    logger.info("handle_product_search ctx=%s", {k: ctx.get(k) for k in ('category','brand','title','price_min','price_max')})

    # Intercept condition questions — don't re-search, answer about cached products
    condition_result = _handle_condition_question(user_id, message)
    if condition_result:
        return condition_result

    if not ctx.get('category'):
        return _ask_category(ctx)

    price_max = ctx.get('price_max')
    price_min = ctx.get('price_min')
    keywords  = _build_keywords(ctx)
    logger.info("handle_product_search keywords=%r price_min=%s price_max=%s", keywords, price_min, price_max)
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
        'used', 'new', 'nতুন', 'পুরনো', 'purano', 'second hand', 'refurbished',
        'condition', 'কন্ডিশন', 'notun', 'fresh',
    ]
    if not any(s in msg for s in signals):
        return None

    ic = normalize_payload(load_context(user_id))
    prev_products = get_product_context(user_id)

    # If multiple products shown and user asks a general question, ask which one
    _AMBIGUOUS_SIGNALS = {
        'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
        'condition', 'কন্ডিশন', 'fresh',
    }
    if len(prev_products) > 1 and any(s in msg for s in _AMBIGUOUS_SIGNALS):
        product_list = '\n'.join(
            f"{i+1}. {p.get('title', '')[:50]}"
            for i, p in enumerate(prev_products[:3])
        )
        return _ok(
            f"স্যার, কোন প্রোডাক্টটি সম্পর্কে জানতে চাইছেন?\n\n{product_list}"
            + LOOP_BACK,
            'product_clarification', ic
        )

    top = prev_products[0] if prev_products else {}
    title = top.get('title', '')

    if any(w in msg for w in ('price', 'dam', 'দাম', 'koto', 'কত', 'মূল্য')):
        price = top.get('price', 'N/A')
        reply = f"স্যার, {title} এর মূল্য {price}।" if title else "স্যার, দাম জানতে লিংকটি দেখুন।"
    elif any(w in msg for w in ('warranty', 'warenty', 'guarantee', 'ওয়ারেন্টি')):
        reply = "স্যার, ওয়ারেন্টি সংক্রান্ত বিস্তারিত তথ্য প্রোডাক্ট পেজে দেওয়া আছে।"
    elif any(w in msg for w in ('stock', 'ache', 'available', 'পাবো', 'pabo')):
        reply = "স্যার, স্টক আপডেট জানতে প্রোডাক্ট পেজটি দেখুন।"
    elif any(w in msg for w in ('used', 'new', 'notun', 'purano', 'second hand',
                                'refurbished', 'condition', 'কন্ডিশন', 'fresh')):
        product_id = _extract_product_id(product_url)
        api_reply = fetch_condition_template(product_id) if product_id else None
        reply = (api_reply or
                 (f"স্যার, {title} এর কন্ডিশন জানতে প্রোডাক্ট পেজটি দেখুন।"
                  if title else "স্যার, প্রোডাক্টের কন্ডিশন জানতে পেজটি দেখুন।"))
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
    # Showroom / address / location questions get the fixed response
    if any(w in msg_lower for w in _SHOWROOM_WORDS):
        ic = normalize_payload(load_context(user_id))
        return _ok(_SHOWROOM_RESPONSE + LOOP_BACK, 'faq_showroom', ic)
    # If products were shown, handle product-specific questions
    prev_products = get_product_context(user_id)
    if prev_products:
        _price_signals = {'price', 'dam', 'দাম', 'koto', 'কত', 'cost', 'rate', 'মূল্য', 'taka', 'টাকা'}
        if any(w in msg_lower for w in _price_signals):
            return handle_price_query(ctx, user_id, message)
        condition_result = _handle_condition_question(user_id, message)
        if condition_result:
            return condition_result
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
