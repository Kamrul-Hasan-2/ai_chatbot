"""
src/services/order_handler.py — multi-step order placement flow.

The flow collects: name → mobile → address → city → area → qty → confirm,
then POSTs to chatbot_place_order. State is held in state_repository._order_flow.

Public entry points:
  start_order_flow(user_id, product)       → dict (first step prompt)
  continue_order_flow(user_id, message)    → dict | None  (None = not in flow)
  is_in_order_flow(user_id)                → bool
"""
import re
import logging
from typing import Dict, List, Optional

from models.chatbot_config import LOOP_BACK
from services.api_client_service import (
    fetch_city_list, fetch_area_list, place_order,
)
from repositories.state_repository import (
    get_order_flow, set_order_flow, clear_order_flow,
)

logger = logging.getLogger(__name__)


# ── Step constants ────────────────────────────────────────────────────────────

STEP_NAME    = 'name'
STEP_MOBILE  = 'mobile'
STEP_ADDRESS = 'address'
STEP_CITY    = 'city'
STEP_AREA    = 'area'
STEP_QTY     = 'qty'
STEP_CONFIRM = 'confirm'

# Words that cancel an in-progress order
_CANCEL_WORDS = {
    'cancel', 'bad', 'বাদ', 'বাতিল', 'cancel korbo', 'বাদ দিন',
    'thak', 'থাক', 'na', 'না', 'stop', 'বন্ধ',
}

# Words that confirm
_CONFIRM_WORDS = {
    'yes', 'হ্যাঁ', 'ha', 'haa', 'confirm', 'ok', 'okay', 'thik',
    'ঠিক আছে', 'thik ache', 'হাঁ', 'অবশ্যই', 'jee', 'জি', 'ji',
    'kor', 'korun', 'korben', 'submit', 'place', 'order korun',
}


# ── Response builder (matches intent_handlers_service._ok shape) ──────────────

def _ok(response: str, intent: str, intent_content: Dict = None,
        link_buttons: List = None) -> Dict:
    return {
        'response':       response,
        'intent':         intent,
        'intent_content': intent_content or {},
        'products':       [],
        'link_buttons':   link_buttons or [],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_listing_id(url: str) -> str:
    """Extract numeric listing id from a BDStall URL."""
    if not url:
        return ''
    m = re.search(r'[/-](\d{3,})/?(?:[?#].*)?$', url.rstrip('/') + '/')
    return m.group(1) if m else ''


def _normalize_token(text: str) -> str:
    return (text or '').strip().lower()


def _is_cancel(message: str) -> bool:
    msg = _normalize_token(message)
    if not msg:
        return False
    return any(msg == w or msg.startswith(w + ' ') or msg.endswith(' ' + w)
               for w in _CANCEL_WORDS)


def _is_confirm(message: str) -> bool:
    msg = _normalize_token(message).rstrip('.!?।,')
    if not msg:
        return False
    for w in _CONFIRM_WORDS:
        if msg == w or msg.startswith(w + ' ') or msg.endswith(' ' + w) or w in msg:
            return True
    return False


_BN_DIGIT_MAP = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def _to_en_digits(text: str) -> str:
    return (text or '').translate(_BN_DIGIT_MAP)


_BN_NUM_WORDS = {
    'এক': 1, 'দুই': 2, 'তিন': 3, 'চার': 4, 'পাঁচ': 5,
    'ছয়': 6, 'সাত': 7, 'আট': 8, 'নয়': 9, 'দশ': 10,
    'ek': 1, 'dui': 2, 'tin': 3, 'char': 4, 'panch': 5, 'pach': 5,
    'choy': 6, 'sat': 7, 'aat': 8, 'noy': 9, 'dosh': 10,
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
}


def _parse_qty(message: str) -> int:
    """Parse a quantity from text (digits or Bangla/Banglish words). Returns 0 if not found."""
    text = _to_en_digits(message or '')
    m = re.search(r'\d+', text)
    if m:
        try:
            n = int(m.group(0))
            if n > 0:
                return n
        except Exception:
            pass
    msg_l = _normalize_token(message)
    for word, val in _BN_NUM_WORDS.items():
        if word in msg_l:
            return val
    return 0


def _parse_mobile(message: str) -> str:
    """Extract a Bangladeshi mobile number from text (returns '' if not valid)."""
    text = _to_en_digits(message or '')
    # Bangladeshi mobiles: 11 digits starting with 01, optionally prefixed with +880
    text = re.sub(r'[\s\-()]', '', text)
    m = re.search(r'(?:\+?880)?(01\d{9})', text)
    return m.group(1) if m else ''


def _match_city(message: str, cities: List[Dict]) -> Optional[Dict]:
    """Find a city by id (digits) or fuzzy name match. Returns the city dict or None."""
    msg = _normalize_token(message)
    if not msg:
        return None

    # Digits = direct city_id
    digits = re.findall(r'\d+', _to_en_digits(msg))
    if digits:
        for d in digits:
            for c in cities:
                if c.get('city_id') == d:
                    return c

    # Substring match against city_name (longest wins so "Dhaka" beats no match)
    best = None
    best_len = 0
    for c in cities:
        name = (c.get('city_name') or '').lower()
        if name and (name in msg or msg in name) and len(name) > best_len:
            best = c
            best_len = len(name)
    return best


def _match_area(message: str, areas: List[Dict], city_id: str) -> Optional[Dict]:
    """Find an area within the given city by id or name."""
    msg = _normalize_token(message)
    if not msg or not city_id:
        return None

    candidates = [a for a in areas if str(a.get('city_id')) == str(city_id)]
    if not candidates:
        return None

    digits = re.findall(r'\d+', _to_en_digits(msg))
    if digits:
        for d in digits:
            for a in candidates:
                if a.get('area_id') == d:
                    return a

    best = None
    best_len = 0
    for a in candidates:
        name = (a.get('area_name') or '').lower()
        if name and (name in msg or msg in name) and len(name) > best_len:
            best = a
            best_len = len(name)
    return best


# ── Step prompts ──────────────────────────────────────────────────────────────

def _prompt_name(product_title: str = '') -> str:
    head = (f"স্যার, আপনি \"{product_title}\" অর্ডার করতে চান। "
            if product_title else "স্যার, অর্ডার করতে কিছু তথ্য দরকার। ")
    return head + ("\n\n১) আপনার নাম কী?\n\n"
                   "(অর্ডার বাতিল করতে \"বাতিল\" লিখুন।)")


def _prompt_mobile() -> str:
    return "ধন্যবাদ। এবার আপনার মোবাইল নম্বরটি দিন (১১ ডিজিট, যেমন: 017XXXXXXXX)।"


def _prompt_address() -> str:
    return "এবার আপনার সম্পূর্ণ ঠিকানা দিন (বাসা/রোড/এলাকা)।"


def _prompt_city(cities: List[Dict]) -> str:
    top = [c['city_name'] for c in cities[:10] if c.get('city_name')]
    sample = ', '.join(top) if top else ''
    extra = f"\n\nযেমন: {sample}" if sample else ''
    return ("আপনি কোন জেলা/শহরে আছেন? জেলার নাম লিখুন।" + extra)


def _prompt_area(city_name: str, areas: List[Dict], city_id: str) -> str:
    in_city = [a['area_name'] for a in areas if str(a.get('city_id')) == str(city_id)][:10]
    sample = ', '.join(in_city) if in_city else ''
    extra = f"\n\nযেমন: {sample}" if sample else ''
    return (f"{city_name}-এর কোন এলাকা? এলাকার নাম লিখুন।" + extra)


def _prompt_qty() -> str:
    return "কয়টি প্রোডাক্ট নিবেন? (সংখ্যা লিখুন, যেমন: 1)"


def _prompt_confirm(state: Dict) -> str:
    title = state.get('product_title') or 'এই প্রোডাক্ট'
    lines = [
        "স্যার, অর্ডার নিশ্চিত করার আগে একবার দেখে নিন:",
        "",
        f"📦 প্রোডাক্ট: {title}",
        f"🔢 পরিমাণ: {state.get('qty', 1)}",
        f"👤 নাম: {state.get('name', '')}",
        f"📞 মোবাইল: {state.get('mobile', '')}",
        f"🏠 ঠিকানা: {state.get('address', '')}",
        f"🏙️ শহর: {state.get('city_name', '')}",
        f"📍 এলাকা: {state.get('area_name', '')}",
        "",
        "সব তথ্য ঠিক থাকলে \"হ্যাঁ\" লিখুন। পরিবর্তন করতে \"বাতিল\" লিখে আবার শুরু করুন।",
    ]
    return '\n'.join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def is_in_order_flow(user_id: str) -> bool:
    state = get_order_flow(user_id)
    return bool(state and state.get('step'))


def start_order_flow(user_id: str, product: Dict) -> Dict:
    """Begin the order flow for a chosen product (dict with title/url)."""
    title = (product or {}).get('title', '')
    url   = (product or {}).get('url', '')
    listing_id = _extract_listing_id(url)
    if not listing_id:
        # Can't order without a listing id — fall back gracefully
        return _ok(
            "স্যার, এই প্রোডাক্টটির আইডি বের করা যাচ্ছে না। "
            "প্রোডাক্ট পেজে গিয়ে সরাসরি অর্ডার করুন।" + LOOP_BACK,
            'order_no_listing_id',
            link_buttons=[{'text': 'প্রোডাক্ট দেখুন', 'url': url, 'title': title}] if url else []
        )
    state = {
        'step':          STEP_NAME,
        'product_title': title,
        'product_url':   url,
        'listing_id':    listing_id,
    }
    set_order_flow(user_id, state)
    return _ok(_prompt_name(title), 'order_collect_name')


def continue_order_flow(user_id: str, message: str) -> Optional[Dict]:
    """Advance the order flow by one step. Returns None if user not in flow."""
    state = get_order_flow(user_id)
    if not state or not state.get('step'):
        return None

    if _is_cancel(message):
        clear_order_flow(user_id)
        return _ok(
            "ঠিক আছে স্যার, অর্ডার বাতিল করা হলো। আবার প্রয়োজন হলে বলবেন। 😊",
            'order_cancelled'
        )

    step = state['step']
    msg = (message or '').strip()

    if step == STEP_NAME:
        if len(msg) < 2:
            return _ok("স্যার, অনুগ্রহ করে আপনার পূর্ণ নাম লিখুন।", 'order_collect_name')
        state['name'] = msg
        state['step'] = STEP_MOBILE
        set_order_flow(user_id, state)
        return _ok(_prompt_mobile(), 'order_collect_mobile')

    if step == STEP_MOBILE:
        mobile = _parse_mobile(msg)
        if not mobile:
            return _ok(
                "স্যার, মোবাইল নম্বরটি সঠিক বলে মনে হচ্ছে না। "
                "বাংলাদেশী ১১ ডিজিটের নম্বর লিখুন (যেমন: 017XXXXXXXX)।",
                'order_collect_mobile'
            )
        state['mobile'] = mobile
        state['step'] = STEP_ADDRESS
        set_order_flow(user_id, state)
        return _ok(_prompt_address(), 'order_collect_address')

    if step == STEP_ADDRESS:
        if len(msg) < 5:
            return _ok(
                "স্যার, একটু বিস্তারিত ঠিকানা লিখুন (বাসা/রোড/এলাকা সহ)।",
                'order_collect_address'
            )
        state['address'] = msg
        state['step'] = STEP_CITY
        set_order_flow(user_id, state)
        cities = fetch_city_list()
        return _ok(_prompt_city(cities), 'order_collect_city')

    if step == STEP_CITY:
        cities = fetch_city_list()
        if not cities:
            clear_order_flow(user_id)
            return _ok(
                "দুঃখিত স্যার, শহরের তালিকা এখন লোড করা যাচ্ছে না। "
                "একটু পরে আবার চেষ্টা করুন।" + LOOP_BACK,
                'order_city_list_error'
            )
        match = _match_city(msg, cities)
        if not match:
            return _ok(
                "স্যার, শহরটি খুঁজে পাইনি। সঠিক জেলার নাম লিখুন "
                "(যেমন: Dhaka, Chittagong, Khulna)।",
                'order_collect_city'
            )
        state['city_id']   = match['city_id']
        state['city_name'] = match['city_name']
        state['step']      = STEP_AREA
        set_order_flow(user_id, state)
        areas = fetch_area_list()
        return _ok(_prompt_area(match['city_name'], areas, match['city_id']),
                   'order_collect_area')

    if step == STEP_AREA:
        areas = fetch_area_list()
        if not areas:
            clear_order_flow(user_id)
            return _ok(
                "দুঃখিত স্যার, এলাকার তালিকা এখন লোড করা যাচ্ছে না। "
                "একটু পরে আবার চেষ্টা করুন।" + LOOP_BACK,
                'order_area_list_error'
            )
        match = _match_area(msg, areas, state.get('city_id', ''))
        if not match:
            return _ok(
                f"স্যার, {state.get('city_name', '')}-এর মধ্যে এই এলাকাটি খুঁজে পাইনি। "
                "অনুগ্রহ করে সঠিক এলাকার নাম লিখুন।",
                'order_collect_area'
            )
        state['area_id']   = match['area_id']
        state['area_name'] = match['area_name']
        state['step']      = STEP_QTY
        set_order_flow(user_id, state)
        return _ok(_prompt_qty(), 'order_collect_qty')

    if step == STEP_QTY:
        qty = _parse_qty(msg)
        if qty <= 0:
            return _ok(
                "স্যার, কয়টি নিবেন সংখ্যায় লিখুন (যেমন: 1, 2)।",
                'order_collect_qty'
            )
        state['qty']  = qty
        state['step'] = STEP_CONFIRM
        set_order_flow(user_id, state)
        return _ok(_prompt_confirm(state), 'order_confirm')

    if step == STEP_CONFIRM:
        if not _is_confirm(msg):
            return _ok(
                "স্যার, অর্ডার নিশ্চিত করতে \"হ্যাঁ\" লিখুন, "
                "অথবা বাতিল করতে \"বাতিল\" লিখুন।",
                'order_confirm'
            )
        result = place_order(
            name=state.get('name', ''),
            mobile=state.get('mobile', ''),
            address=state.get('address', ''),
            listing_id=state.get('listing_id', ''),
            qty=state.get('qty', 1),
            city_id=state.get('city_id', ''),
            area_id=state.get('area_id', ''),
        )
        clear_order_flow(user_id)
        product_url = state.get('product_url', '')
        buttons = ([{'text': 'প্রোডাক্ট দেখুন', 'url': product_url,
                     'title': state.get('product_title', '')}]
                   if product_url else [])
        if result.get('success'):
            order_no = (result.get('order_no') or '').strip()
            order_id = (result.get('order_id') or '').strip()
            order_ref = order_no or order_id
            lines = ["✅ অর্ডার সফলভাবে গ্রহণ করা হয়েছে স্যার!", ""]
            if order_ref:
                lines.append(f"🧾 অর্ডার নম্বর: {order_ref}")
            lines.append(f"📦 প্রোডাক্ট: {state.get('product_title', '')}")
            lines.append(f"🔢 পরিমাণ: {state.get('qty', 1)}")
            lines.append(f"📞 মোবাইল: {state.get('mobile', '')}")
            lines.append(
                f"🏠 ঠিকানা: {state.get('address', '')}, "
                f"{state.get('area_name', '')}, {state.get('city_name', '')}"
            )
            lines.append("")
            lines.append("বিক্রেতা শীঘ্রই আপনার সাথে যোগাযোগ করে ডেলিভারি কনফার্ম করবেন।")
            return _ok('\n'.join(lines) + LOOP_BACK, 'order_placed',
                       link_buttons=buttons)
        # Failure: surface API message when available
        msg_err = result.get('message') or 'অর্ডার এখন প্রক্রিয়া করা যাচ্ছে না।'
        return _ok(
            f"দুঃখিত স্যার, অর্ডার সম্পন্ন হয়নি: {msg_err}\n\n"
            "একটু পরে আবার চেষ্টা করুন অথবা প্রোডাক্ট পেজে গিয়ে সরাসরি অর্ডার করুন।"
            + LOOP_BACK,
            'order_failed', link_buttons=buttons
        )

    # Unknown step — clear and bail out
    logger.warning("continue_order_flow: unknown step %r for user %s", step, user_id)
    clear_order_flow(user_id)
    return None
