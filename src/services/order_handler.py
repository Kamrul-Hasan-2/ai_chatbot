"""
src/services/order_handler.py — one-shot order placement flow.

The user is asked for ALL fields (name, mobile, address, city, area, qty) in
ONE message. Their reply is parsed for labelled lines like "নাম: ..." or
free-form (line 1 = name, any 11-digit Bangladeshi number = mobile, etc.).
Missing or invalid fields trigger a single combined re-prompt; once everything
is valid, the user confirms with "হ্যাঁ" and the order is POSTed.

Public entry points:
  start_order_flow(user_id, product)       → dict (combined ask)
  continue_order_flow(user_id, message)    → dict | None (None = not in flow)
  is_in_order_flow(user_id)                → bool
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

from models.chatbot_config import LOOP_BACK
from services.api_client_service import (
    fetch_city_list, fetch_area_list, place_order,
)
from repositories.state_repository import (
    get_order_flow, set_order_flow, clear_order_flow,
)

logger = logging.getLogger(__name__)


# ── Step constants ────────────────────────────────────────────────────────────

STEP_COLLECT = 'collect'   # waiting for the combined reply (or a fix)
STEP_CONFIRM = 'confirm'   # all fields parsed, waiting for "হ্যাঁ"

# Price-inquiry signals — "কত টাকা?", "দাম কত?", "price koto?" mid-order.
# Placed AFTER the product-search escape check so "laptop কত টাকা" still
# escapes the flow; a bare "কত টাকা" (no category/brand) stays here.
_PRICE_INQUIRY_SIGNALS = (
    'কত টাকা', 'টাকা কত', 'কতো টাকা', 'টাকা কতো',
    'দাম কত', 'কত দাম', 'দাম কতো', 'কতো দাম',
    'koto taka', 'taka koto', 'dam koto', 'koto dam',
    'price koto', 'koto price',
    'এর দাম', 'এটার দাম', 'এইটার দাম', 'etar dam', 'itar dam',
)

# Words that cancel an in-progress order
_CANCEL_WORDS = {
    'cancel', 'বাতিল', 'cancel korbo', 'বাদ দিন', 'বাদ দাও',
    'stop', 'বন্ধ', 'বন্ধ করো',
}

# Short greetings that should break out of the order flow entirely.
# When the user types one of these, they're starting fresh — not filling the
# form — so we silently clear in-progress state and let the main pipeline's
# greeting intercept run.
_GREETING_RESET_WORDS = {
    'hi', 'hii', 'hiii', 'hello', 'helo', 'hey', 'hlw', 'hloo',
    'salam', 'assalamualaikum', 'asalamualaikum', 'assalam', 'slm',
    'হাই', 'হ্যালো', 'হেলো', 'সালাম', 'আসসালামু আলাইকুম', 'আসসালামুয়ালাইকুম',
    'good morning', 'good evening', 'good afternoon',
}

# Product-search signals that should escape an in-progress order flow.
# When a user mid-order suddenly asks about a completely different product,
# they've abandoned the order — clear state and let Groq route normally.
_PRODUCT_SEARCH_SIGNALS = (
    'ase', 'আছে', 'ache', 'lagbe', 'লাগবে', 'chai', 'চাই',
    'dekhan', 'dekhao', 'দেখান', 'দেখাও',
    'khujtasi', 'khujchi', 'খুঁজছি',
    'price', 'dam', 'দাম', 'koto taka', 'koto daam',
    'laptop', 'mobile', 'phone', 'tv', 'ac', 'fridge',
    'computer', 'tablet', 'watch', 'camera', 'headphone',
    'charger', 'router', 'printer', 'monitor', 'keyboard',
)

# Brand names that, combined with a search signal, confirm a product query
_BRAND_WORDS = (
    'hp', 'dell', 'asus', 'acer', 'lenovo', 'samsung', 'apple', 'walton',
    'xiaomi', 'realme', 'oppo', 'vivo', 'nokia', 'sony', 'lg', 'toshiba',
)

# Phrases that mean the user is asking about discount / negotiating the price
# while mid-order. We answer with a fixed "price is fixed" message and re-show
# the order form, keeping all collected state intact.
_PRICE_NEGOTIATE_SIGNALS = (
    'price komano', 'price komabo', 'price kom', 'price reduce', 'price kobe',
    'dam komano', 'dam komabo', 'dam kom', 'dam kobe',
    'discount', 'discount dabo', 'discount koto', 'offer',
    'negotiate', 'negotiation', 'bargain',
    'kom kora', 'kom korte', 'kom hobe', 'komano jabe', 'komano hobe',
    'দাম কমানো', 'দাম কমাবো', 'দাম কমবে', 'কমানো যাবে', 'কমানো হবে',
    'ছাড়', 'ছাড় দিন', 'ছাড় দাও', 'অফার',
    'fixed naki', 'fix naki', 'fixed price', 'fix price',
)

# Words that confirm
_CONFIRM_WORDS = {
    'yes', 'হ্যাঁ', 'haa', 'confirm', 'confirmed', 'ok', 'okay', 'thik',
    'ঠিক আছে', 'thik ache', 'হাঁ', 'অবশ্যই', 'jee', 'জি', 'ji',
    'korun', 'korben', 'submit', 'place', 'order korun', 'order koro',
    'করুন', 'place korun',
}

# A negation anywhere in a confirm-step reply ("not ok", "ok na", "address ok na",
# "thik na") means the user is REJECTING, not confirming — never place an order
# on it. (review finding #1)
_NEGATION_WORDS = {
    'na', 'nah', 'no', 'nope', 'not', 'নাহ', 'না', 'nai', 'নাই', 'nei', 'নেই',
    'hobe na', 'হবে না', 'হবেনা', 'hobena', 'thik na', 'ঠিক না', 'thik nai',
    'lagbe na', 'লাগবে না', 'thik hoy nai', 'cancel',
}


# ── Response builder ──────────────────────────────────────────────────────────

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
    if not url:
        return ''
    m = re.search(r'[/-](\d{3,})/?(?:[?#].*)?$', url.rstrip('/') + '/')
    return m.group(1) if m else ''


def _normalize_token(text: str) -> str:
    return (text or '').strip().lower()


def _is_cancel(message: str) -> bool:
    msg = _normalize_token(message).rstrip('.!?।,')
    if not msg:
        return False
    return any(msg == w or msg.startswith(w + ' ') or msg.endswith(' ' + w)
               for w in _CANCEL_WORDS)


def _is_greeting_reset(message: str) -> bool:
    """True when the message is a short greeting that should break the order flow."""
    msg = _normalize_token(message).rstrip('.!?।,')
    if not msg or len(msg) > 25:
        return False
    return msg in _GREETING_RESET_WORDS


def _is_product_search_escape(message: str) -> bool:
    """True when the user is clearly asking about a product, not filling the order form.

    Catches messages like "hp laptop ase", "samsung phone lagbe", "AC dekhao" that
    arrive while order state is stale (user abandoned the previous order without
    explicitly cancelling). We clear the flow and let Groq route normally.

    Guard: require either (a) a brand word + any search signal, or (b) a product
    category word + a search signal. A bare brand name ("hp") or a bare search
    signal ("ase") alone is NOT enough — those could be legitimate form values.
    """
    msg = _normalize_token(message)
    if not msg:
        return False

    has_search = any(s in msg for s in _PRODUCT_SEARCH_SIGNALS)
    has_brand  = any(b in msg.split() or msg.startswith(b + ' ') or msg.endswith(' ' + b) or msg == b
                     for b in _BRAND_WORDS)

    # Brand + search signal → definitely a product query
    if has_brand and has_search:
        return True

    # Product category word + search signal (e.g. "laptop lagbe", "AC ase")
    _CATEGORY_WORDS = (
        'laptop', 'mobile', 'phone', 'tv', 'ac ', 'fridge',
        'computer', 'tablet', 'watch', 'camera', 'headphone',
        'charger', 'router', 'printer', 'monitor', 'keyboard',
    )
    has_category = any(c in msg for c in _CATEGORY_WORDS)
    if has_category and has_search:
        return True

    return False


def _is_price_negotiation(message: str) -> bool:
    """True when the user is asking about discount / price negotiation mid-order."""
    msg = _normalize_token(message)
    if not msg:
        return False
    return any(s in msg for s in _PRICE_NEGOTIATE_SIGNALS)


def _is_price_inquiry(message: str) -> bool:
    """True when the user is asking about the price of the product mid-order."""
    msg = _normalize_token(message)
    if not msg:
        return False
    return any(s in msg for s in _PRICE_INQUIRY_SIGNALS)


# ── Mid-order info-question interruptions ─────────────────────────────────────
# While we're collecting order fields, a buyer often pauses to ask an unrelated
# info question — "delivery koto din?", "cash on delivery hobe?", "eta ki
# nokol?", "warranty ase?". Without this guard the freeform parser swallows the
# question as a name/address and the half-built order gets corrupted. We answer
# the question with a short fixed reply and re-show the SAME prompt, keeping every
# already-collected field intact — exactly like the price-negotiation handler.
#
# Signals are substring-matched. Words that commonly appear in real names/areas
# (e.g. "notun" → "Notun Bazar", "used") are deliberately excluded to avoid
# false-triggering on a legitimate form value.
_INTERRUPTION_REPLIES = (
    # Payment/COD must be checked BEFORE delivery — "cash on delivery" contains
    # the word "delivery" and would otherwise match the delivery-timing answer.
    (('cash on delivery', 'ক্যাশ অন', 'hate peye', 'hate pe taka', 'payment',
      'পেমেন্ট', 'bkash', 'বিকাশ', 'nagad', 'নগদ', 'kivabe dibo', 'kibhabe taka'),
     "স্যার, ঢাকার ভেতরে পণ্য হাতে পেয়ে টাকা দিতে পারবেন (ক্যাশ অন ডেলিভারি)। "
     "ঢাকার বাইরে শুধু অগ্রিম পেমেন্ট প্রযোজ্য।"),
    (('delivery', 'ডেলিভারি', 'courier', 'কুরিয়ার', 'koto din', 'kotodin',
      'koy din', 'koydin', 'kobe pabo', 'kobe asbe', 'kobe dibe'),
     "স্যার, ঢাকার ভেতরে ১-২ কার্যদিবস এবং ঢাকার বাইরে ২-৫ কার্যদিবসে ডেলিভারি হয়। "
     "চার্জ ঢাকায় ৬০-৮০৳, ঢাকার বাইরে ১২০-১৫০৳।"),
    (('warranty', 'ওয়ারেন্টি', 'warenty', 'warrenty', 'guarantee', 'গ্যারান্টি',
      'garanti'),
     "স্যার, ওয়ারেন্টি প্রোডাক্ট ও বিক্রেতাভেদে ভিন্ন হয় — বিস্তারিত প্রোডাক্ট পেজে দেখে নিন।"),
    (('nokol', 'নকল', 'fake', 'ফেক', 'duplicate', 'genuine', 'vejal', 'ভেজাল',
      'asol na nokol'),
     "স্যার, আমাদের এখানের সকল প্রোডাক্টই ভালো, তবে কেনার আগে অবশ্যই দেখে নিবেন।"),
    (('return', 'ফেরত', 'refund', 'রিফান্ড'),
     "স্যার, পণ্যে সমস্যা থাকলে রিটার্ন পলিসি অনুযায়ী ফেরত বা পরিবর্তনের সুযোগ আছে।"),
    (('condition', 'কন্ডিশন', 'refurbish', 'refurbished'),
     "স্যার, প্রোডাক্টের কন্ডিশন প্রোডাক্ট পেজে উল্লেখ থাকে — সেখানে দেখে নিতে পারেন।"),
)


def _order_interruption_reply(message: str) -> Optional[str]:
    """Return a fixed info answer if the message is a mid-order question, else None.

    A message carrying a mobile number is treated as form data (never an
    interruption) so "amar number 017..., delivery koto?" still fills the form.
    """
    msg = _normalize_token(message)
    if not msg:
        return None
    if _parse_mobile(message):
        return None
    for signals, reply in _INTERRUPTION_REPLIES:
        if any(s in msg for s in signals):
            return reply
    return None


def _word_match(msg: str, w: str) -> bool:
    """Whole-word / whole-phrase match — avoids mid-word substring hits like
    'ok' inside 'nokol' or 'address ok na'."""
    return f' {w} ' in f' {msg} '


def _is_confirm(message: str) -> bool:
    msg = _normalize_token(message).rstrip('.!?।,')
    if not msg:
        return False
    # Reject first: a negation anywhere means the user is NOT confirming. (#1)
    if any(_word_match(msg, n) for n in _NEGATION_WORDS):
        return False
    # Whole-word confirm match (no substring), so "address ok na" / "not ok"
    # can never place an order. (#1)
    return any(_word_match(msg, w) for w in _CONFIRM_WORDS)


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


def _parse_qty(text: str) -> int:
    if not text:
        return 0
    digits = _to_en_digits(text)
    m = re.search(r'\d+', digits)
    if m:
        try:
            n = int(m.group(0))
            if n > 0:
                return n
        except Exception:
            pass
    t = _normalize_token(text)
    for word, val in _BN_NUM_WORDS.items():
        if word in t:
            return val
    return 0


def _parse_mobile(text: str) -> str:
    """Find a Bangladeshi 11-digit mobile starting with 01 anywhere in text."""
    if not text:
        return ''
    digits = _to_en_digits(text)
    digits = re.sub(r'[\s\-()]', '', digits)
    m = re.search(r'(?:\+?880)?(01\d{9})', digits)
    return m.group(1) if m else ''


def _match_city(text: str, cities: List[Dict]) -> Optional[Dict]:
    if not text:
        return None
    t = _normalize_token(text)

    # By city_id (digits)
    digits = re.findall(r'\d+', _to_en_digits(t))
    if digits:
        for d in digits:
            for c in cities:
                if c.get('city_id') == d:
                    return c

    # By name — longest substring wins
    best, best_len = None, 0
    for c in cities:
        name = (c.get('city_name') or '').lower()
        if not name:
            continue
        if (name in t or t in name) and len(name) > best_len:
            best, best_len = c, len(name)
    return best


def _match_area(text: str, areas: List[Dict], city_id: str) -> Optional[Dict]:
    if not text or not city_id:
        return None
    t = _normalize_token(text)
    candidates = [a for a in areas if str(a.get('city_id')) == str(city_id)]
    if not candidates:
        return None

    digits = re.findall(r'\d+', _to_en_digits(t))
    if digits:
        for d in digits:
            for a in candidates:
                if a.get('area_id') == d:
                    return a

    best, best_len = None, 0
    for a in candidates:
        name = (a.get('area_name') or '').lower()
        if not name:
            continue
        if (name in t or t in name) and len(name) > best_len:
            best, best_len = a, len(name)
    return best


# Replies that are conversational acks/negations — never an area name.
_AREA_ACK_TOKENS = frozenset({
    'ok', 'okay', 'hmm', 'hm', 'hum', 'huh', 'acha', 'accha', 'achha',
    'thik', 'thik ache', 'thik ase', 'acha thik ase', 'yes', 'no', 'na',
    'haa', 'hae', 'ji', 'jee', 'আচ্ছা', 'ঠিক আছে', 'হুম', 'হ্যাঁ', 'না', 'জি',
})


def _is_plausible_area(text: str) -> bool:
    """Sanity-gate for accepting an UNMATCHED area name (stored with null id).

    The smart single-missing follow-up feeds the WHOLE reply here, so questions,
    multi-line texts, long sentences and bare acks ("ok", "stock ase?") must be
    rejected — those re-prompt instead of becoming the recorded area.
    """
    raw = (text or '').strip()
    if not raw or '\n' in raw or '?' in raw:
        return False
    t = _normalize_token(raw).rstrip('.!।,')
    if not t or len(t) > 40 or t in _AREA_ACK_TOKENS:
        return False
    # Needs at least one Latin or Bangla LETTER (Bangla digits ০-৯ excluded).
    return bool(re.search(r'[A-Za-zঀ-৥ৰ-৿]', t))


# ── Combined-reply parser ─────────────────────────────────────────────────────

# Map label keywords (lowercase) → canonical field name
_LABEL_ALIASES: Dict[str, str] = {
    # name
    'name': 'name', 'নাম': 'name', 'naam': 'name',
    # mobile
    'mobile': 'mobile', 'phone': 'mobile', 'number': 'mobile', 'no': 'mobile',
    'contact': 'mobile', 'নম্বর': 'mobile', 'মোবাইল': 'mobile', 'ফোন': 'mobile',
    # address
    'address': 'address', 'addr': 'address', 'ঠিকানা': 'address',
    'thikana': 'address',
    # city
    'city': 'city', 'district': 'city', 'জেলা': 'city', 'শহর': 'city',
    'jela': 'city', 'shahor': 'city',
    # area
    'area': 'area', 'thana': 'area', 'এলাকা': 'area', 'থানা': 'area',
    # qty
    'qty': 'qty', 'quantity': 'qty', 'পরিমাণ': 'qty', 'সংখ্যা': 'qty',
    'কয়টি': 'qty', 'koyti': 'qty',
}

# Match "label : value" or "label = value" on a single line
_LABEL_LINE_RE = re.compile(
    r'^\s*([A-Za-zঀ-৿ঀ-৿]+)\s*[:=]\s*(.+?)\s*$',
    re.UNICODE,
)


def _parse_labelled_lines(text: str) -> Dict[str, str]:
    """Pull labelled fields from a multi-line reply. Returns whatever it finds."""
    out: Dict[str, str] = {}
    if not text:
        return out
    for raw_line in text.splitlines():
        m = _LABEL_LINE_RE.match(raw_line)
        if not m:
            continue
        label_word = (m.group(1) or '').strip().lower()
        value = (m.group(2) or '').strip()
        if not value:
            continue
        field = _LABEL_ALIASES.get(label_word)
        if field and field not in out:
            out[field] = value
    return out


def _parse_freeform(text: str) -> Dict[str, str]:
    """Best-effort parse when the user didn't use labels.

    Strategy:
      mobile  = first 11-digit BD mobile found anywhere
      name    = first non-empty line that isn't the mobile and has no digits
      address = longest remaining line
      qty     = last bare number (1–99) on its own line, if any
    Everything else is left to the validator.
    """
    out: Dict[str, str] = {}
    if not text:
        return out

    mobile = _parse_mobile(text)
    if mobile:
        out['mobile'] = mobile

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    remaining: List[str] = []
    for ln in lines:
        if mobile and mobile in _to_en_digits(ln).replace(' ', ''):
            continue
        remaining.append(ln)

    # name: first line with letters and no digits
    for ln in remaining:
        if re.search(r'[A-Za-zঀ-৿ঀ-৿]', ln) and not re.search(r'\d', _to_en_digits(ln)):
            out['name'] = ln
            remaining.remove(ln)
            break

    # qty: a line that is a small number (1–99) optionally followed by a unit
    for ln in list(remaining):
        if re.fullmatch(
            r'\s*\d{1,2}\s*(?:pcs?|piece|pieces|ta|ti|টি|টা|পিস)?\s*',
            _to_en_digits(ln), re.IGNORECASE
        ):
            out['qty'] = ln.strip()
            remaining.remove(ln)
            break

    # address: longest remaining line
    if remaining:
        out['address'] = max(remaining, key=len)

    return out


# "পরিমাণ ১" without a colon — buyers often drop the colon on the qty line.
# Line-anchored so a house number inside the address ("বাসা সংখ্যা ১২") can
# never be misread as qty; only a line that STARTS with a qty label matches.
# 'সংখ্যা' is deliberately absent — it's the generic word for "number".
_QTY_INLINE_RE = re.compile(
    r'^\s*(?:পরিমাণ|কয়টি|qty|quantity|koyti)\s*[:=]?\s*([০-৯\d]{1,4})(?![০-৯\d])',
    re.MULTILINE,
)


def _extract_fields(text: str) -> Dict[str, str]:
    """Combine labelled + freeform parsing. Labels win when both present."""
    labelled = _parse_labelled_lines(text)
    # Freeform must only guess from lines that weren't already consumed by a
    # RECOGNISED label — otherwise a lone labelled line like "পরিমাণ : 1" also
    # gets guessed as a free-text address (its only key is 'qty', which
    # doesn't collide with the freeform 'address' guess, so the bad guess
    # survives the merge below and corrupts the address field). A line with
    # an unrecognised label word ("নাম্বার : 017...") must still reach
    # freeform — that's how its bare-digit mobile detection finds it.
    consumed_lines = set()
    for raw_line in (text or '').splitlines():
        m = _LABEL_LINE_RE.match(raw_line)
        if m and _LABEL_ALIASES.get((m.group(1) or '').strip().lower()):
            consumed_lines.add(raw_line)
    remaining_lines = [
        ln for ln in (text or '').splitlines()
        if ln not in consumed_lines
    ]
    freeform = _parse_freeform('\n'.join(remaining_lines))
    out = dict(freeform)
    out.update(labelled)  # labelled overrides freeform guesses
    if 'qty' not in out:
        m = _QTY_INLINE_RE.search(text or '')
        if m:
            out['qty'] = m.group(1)
    return out


def _validate_and_resolve(
    state: Dict,
    extracted: Dict[str, str],
    cities: List[Dict],
    areas: List[Dict],
) -> Tuple[Dict, List[str]]:
    """Validate extracted fields against API lists, merge into state.

    Returns (updated_state, missing_field_labels). When the list is empty,
    every field is valid and the order is ready for confirmation.
    """
    # Name
    raw_name = extracted.get('name', '').strip() or state.get('name', '')
    if len(raw_name) >= 2:
        state['name'] = raw_name

    # Mobile
    raw_mobile = extracted.get('mobile', '').strip()
    mobile = _parse_mobile(raw_mobile or '') or state.get('mobile', '')
    if mobile:
        state['mobile'] = mobile

    # Address — accept any non-trivial string. The user may type a short label
    # like "Ulon" or "Savar"; rejecting these as "missing" surprises the user.
    raw_address = extracted.get('address', '').strip() or state.get('address', '')
    if len(raw_address) >= 2:
        state['address'] = raw_address

    # City
    raw_city = extracted.get('city', '').strip()
    if raw_city:
        match = _match_city(raw_city, cities)
        if match:
            state['city_id']   = match['city_id']
            state['city_name'] = match['city_name']
            state.pop('city_unmatched', None)
            # When city changes, drop any previously-resolved area — it may
            # belong to the old city.
            if state.get('area_city_id') and state['area_city_id'] != match['city_id']:
                state.pop('area_id', None)
                state.pop('area_name', None)
                state.pop('area_city_id', None)
        else:
            # The buyer explicitly named a district we don't recognise.
            # Accept the raw name (city_id=null) and proceed — re-asking
            # loops forever when the buyer's district isn't in BDStall's list.
            state['city_unmatched'] = raw_city
            state['city_name'] = raw_city
            state.pop('city_id', None)

    # Area (only resolvable once city is known)
    raw_area = extracted.get('area', '').strip()
    if raw_area and (state.get('city_id') or state.get('city_unmatched')):
        match = _match_area(raw_area, areas, state.get('city_id') or '')
        if match:
            state['area_id']      = match['area_id']
            state['area_name']    = match['area_name']
            state['area_city_id'] = match['city_id']
        else:
            city_match = _match_city(raw_area, cities)
            if (city_match
                    and _normalize_token(raw_area) ==
                        (city_match.get('city_name') or '').strip().lower()
                    and str(city_match['city_id']) != str(state.get('city_id'))):
                # The buyer typed a DISTRICT name at the area prompt — that's
                # a জেলা correction, not an area. Switch city, re-ask the area.
                state['city_id']   = city_match['city_id']
                state['city_name'] = city_match['city_name']
                state.pop('city_unmatched', None)
                state.pop('area_id', None)
                state.pop('area_name', None)
                state.pop('area_city_id', None)
            elif _is_plausible_area(raw_area):
                # Area not in BDStall's list for this city (e.g. "Baraipara"
                # under Chittagong). Re-asking loops forever — no respelling
                # will ever match — so accept the typed name with area_id null.
                # The name is appended to the address at place-order time.
                # city_id may be absent here (city itself was unmatched and
                # popped from state above) — .get() to avoid a KeyError crash.
                state['area_id']      = None
                state['area_name']    = raw_area
                state['area_city_id'] = state.get('city_id')
            # Junk (acks, questions, long texts) falls through — এলাকা stays
            # missing and the buyer is re-prompted.

    # City / area inference from the address string — name-only matching (never
    # ID-based) so house numbers like "lift-5" or postal codes like "1212"
    # can't accidentally match a city_id.  Only fires when the field wasn't
    # given explicitly: "uttar badda, dhaka-1212" → city=Dhaka, area=Badda.
    if not state.get('city_id') and not state.get('city_unmatched') and state.get('address'):
        _addr_t = _normalize_token(state['address'])
        _best_c, _best_clen = None, 0
        for _c in cities:
            _cn = (_c.get('city_name') or '').lower()
            if _cn and (_cn in _addr_t) and len(_cn) > _best_clen:
                _best_c, _best_clen = _c, len(_cn)
        if _best_c:
            state['city_id']   = _best_c['city_id']
            state['city_name'] = _best_c['city_name']

    if ('area_id' not in state and not state.get('city_unmatched')
            and state.get('city_id') and state.get('address')):
        _addr_t = _normalize_token(state['address'])
        _city_areas = [a for a in areas
                       if str(a.get('city_id')) == str(state['city_id'])]
        _best_a, _best_alen = None, 0
        for _a in _city_areas:
            _an = (_a.get('area_name') or '').lower()
            if _an and (_an in _addr_t) and len(_an) > _best_alen:
                _best_a, _best_alen = _a, len(_an)
        if _best_a:
            state['area_id']      = _best_a['area_id']
            state['area_name']    = _best_a['area_name']
            state['area_city_id'] = _best_a['city_id']

    # Qty — not mandatory. Use whatever was given; if the customer never
    # states a quantity, default to 1 rather than blocking the order on it.
    raw_qty = extracted.get('qty', '').strip()
    qty = _parse_qty(raw_qty) if raw_qty else int(state.get('qty', 0) or 0)
    state['qty'] = qty if qty > 0 else 1

    # Figure out what's still missing
    missing: List[str] = []
    if not (state.get('name') and len(state['name']) >= 2):
        missing.append('নাম')
    if not state.get('mobile'):
        missing.append('মোবাইল (01XXXXXXXXX)')
    if not (state.get('address') and len(state['address']) >= 2):
        missing.append('ঠিকানা')
    if not state.get('city_id') and not state.get('city_unmatched'):
        missing.append('জেলা')
    # Key-presence check: an unmatched area is stored as area_id=None (sent as
    # null to the API) and counts as provided — only a never-given area is missing.
    if 'area_id' not in state:
        missing.append('এলাকা')
    return state, missing


# ── Prompts ───────────────────────────────────────────────────────────────────

def _prompt_collect(product_title: str = '', product_url: str = '') -> str:
    if product_title:
        head = f"স্যার, আপনি \"{product_title}\" অর্ডার করতে চান।\n\n"
        if product_url:
            head += (
                f"🔗 প্রোডাক্ট লিংক: {product_url}\n\n"
                "অনুগ্রহ করে উপরের লিংকে ক্লিক করে ওয়েবসাইটে গিয়ে "
                "\"Buy Now\" বাটনে ক্লিক করে সরাসরি অর্ডার করুন। অথবা "
                "আমাদের মাধ্যমে অর্ডার করতে চাইলে নিচের সব তথ্য একসাথে দিন:\n\n"
            )
        else:
            head += "নিচের সব তথ্য একসাথে দিন:\n\n"
    else:
        head = "স্যার, অর্ডারের জন্য নিচের সব তথ্য একসাথে দিন:\n\n"
    template = (
        "নাম: <আপনার পূর্ণ নাম>\n"
        "মোবাইল: 017XXXXXXXX\n"
        "ঠিকানা: <বাসা, রোড, এলাকা>\n"
        "জেলা: Dhaka\n"
        "এলাকা: Mirpur\n"
        "পরিমাণ: 1\n\n"
        "(বাতিল করতে \"বাতিল\" লিখুন।)"
    )
    return head + template


def _prompt_missing(missing: List[str], state: Dict,
                    areas: Optional[List[Dict]] = None) -> str:
    head = "স্যার, নিচের তথ্যগুলো এখনো বাকি বা সঠিক হয়নি:\n\n"
    bullets = '\n'.join(f"• {m}" for m in missing)
    hint = ''
    if 'এলাকা' in missing and state.get('city_name'):
        # Example areas must come from the SELECTED city's list — a hardcoded
        # "Mirpur, Dhanmondi" misleads buyers outside Dhaka.
        examples = ''
        if areas and state.get('city_id'):
            names = [a.get('area_name') for a in areas
                     if str(a.get('city_id')) == str(state['city_id'])
                     and a.get('area_name')]
            examples = ', '.join(names[:2])
        example_part = f", যেমন: {examples}" if examples else ''
        hint = f"\n\n({state['city_name']}-এর এলাকার নাম দিন{example_part})"
    elif 'জেলা' in missing:
        hint = "\n\n(যেমন: Dhaka, Chittagong, Khulna)"
    return head + bullets + hint + "\n\nঅনুগ্রহ করে এগুলো লিখে পাঠান।"


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
        f"🏙️ জেলা: {state.get('city_name', '')}",
        f"📍 এলাকা: {state.get('area_name', '')}",
        "",
        "সব ঠিক থাকলে \"হ্যাঁ\" লিখুন। পরিবর্তন করতে \"বাতিল\" লিখে আবার শুরু করুন।",
    ]
    return '\n'.join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def is_in_order_flow(user_id: str) -> bool:
    state = get_order_flow(user_id)
    return bool(state and state.get('step'))


def start_order_flow(user_id: str, product: Dict) -> Dict:
    """Begin the order flow for a chosen product."""
    title = (product or {}).get('title', '')
    url   = (product or {}).get('url', '')
    listing_id = _extract_listing_id(url)
    if not listing_id:
        return _ok(
            "স্যার, এই প্রোডাক্টটির আইডি বের করা যাচ্ছে না। "
            "প্রোডাক্ট পেজে গিয়ে সরাসরি অর্ডার করুন।" + LOOP_BACK,
            'order_no_listing_id',
            link_buttons=[{'text': 'প্রোডাক্ট দেখুন', 'url': url, 'title': title}] if url else []
        )
    state = {
        'step':          STEP_COLLECT,
        'product_title': title,
        'product_url':   url,
        'listing_id':    listing_id,
    }
    set_order_flow(user_id, state)
    return _ok(_prompt_collect(title, url), 'order_collect')


def _finalize_order(user_id: str, state: Dict) -> Dict:
    """Call the place-order API and build the success/failure reply.

    Fires as soon as every required field is collected — regardless of
    whether the customer's city matched BDStall's known list (city_id may
    be '' for an unmatched district; the API still accepts the order with
    the raw address). No separate "হ্যাঁ" confirmation turn is required.
    """
    # An unmatched area has area_id=None and its name exists only in chat
    # state — the order payload has no area_name field, so carry the typed
    # area inside the address or it never reaches the seller.
    address = state.get('address', '')
    area_name = state.get('area_name', '')
    if (state.get('area_id') is None and area_name
            and area_name.lower() not in address.lower()):
        address = f"{address}, {area_name}" if address else area_name
    result = place_order(
        name=state.get('name', ''),
        mobile=state.get('mobile', ''),
        address=address,
        listing_id=state.get('listing_id', ''),
        qty=state.get('qty', 1),
        city_id=state.get('city_id', ''),
        area_id=state.get('area_id') or '',
    )
    product_url = state.get('product_url', '')
    buttons = ([{'text': 'প্রোডাক্ট দেখুন', 'url': product_url,
                 'title': state.get('product_title', '')}]
               if product_url else [])
    if result.get('success'):
        # Clear the flow ONLY after a confirmed order — otherwise a transient
        # API failure below would wipe the user's whole collected order. (#1)
        clear_order_flow(user_id)
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
        lines.append("আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করে ডেলিভারি কনফার্ম করবেন।")
        return _ok('\n'.join(lines) + LOOP_BACK, 'order_placed',
                   link_buttons=buttons)

    # Order NOT placed (timeout / 5xx / API error). Keep the flow at
    # STEP_CONFIRM so the user can retry with "হ্যাঁ" without re-entering
    # name / mobile / address / city / area / qty. (#1)
    state['step'] = STEP_CONFIRM
    set_order_flow(user_id, state)
    msg_err = result.get('message') or 'অর্ডার এখন প্রক্রিয়া করা যাচ্ছে না।'
    return _ok(
        f"দুঃখিত স্যার, অর্ডার সম্পন্ন হয়নি: {msg_err}\n\n"
        "আবার চেষ্টা করতে \"হ্যাঁ\" লিখুন, অথবা বাতিল করতে \"বাতিল\" লিখুন।"
        + LOOP_BACK,
        'order_failed', link_buttons=buttons
    )


def continue_order_flow(user_id: str, message: str) -> Optional[Dict]:
    """Advance the order flow. Returns None if user is not in flow or if the
    message is a fresh-start signal (greeting) — in which case the caller's
    main pipeline handles it as if no order were in progress."""
    state = get_order_flow(user_id)
    if not state or not state.get('step'):
        return None

    # Fresh-start signal: user typed "Hi" / "Hello" / "সালাম" etc. — that's
    # the start of a new conversation, not a form field. Silently drop the
    # in-progress order state and let the main pipeline reply with its
    # normal greeting.
    if _is_greeting_reset(message):
        clear_order_flow(user_id)
        return None

    if _is_cancel(message):
        clear_order_flow(user_id)
        return _ok(
            "ঠিক আছে স্যার, অর্ডার বাতিল করা হলো। আবার প্রয়োজন হলে বলবেন। 😊",
            'order_cancelled'
        )

    # Price-negotiation question mid-order — give the fixed reply and keep the
    # order state exactly where it was. The product, listing_id, and any fields
    # the user already provided stay intact so they can continue ordering.
    if _is_price_negotiation(message):
        title = state.get('product_title', '')
        intro = "স্যার, আমাদের দাম ফিক্সড। দাম কমানো বা ছাড় দেওয়ার সুযোগ নেই।"
        # Re-show the order form if we're still collecting, or the confirm
        # summary if we were about to place the order.
        if state.get('step') == STEP_CONFIRM:
            tail = _prompt_confirm(state)
        else:
            tail = _prompt_collect(title, state.get('product_url', ''))
        return _ok(intro + "\n\n" + tail, 'order_price_fixed')

    # Info-question interruption mid-order — answer briefly and re-show the
    # current prompt without losing any collected field (same model as the
    # price-negotiation handler above). Runs BEFORE the product-search escape so
    # an info question that mentions the product category ("ei laptop ki nokol?")
    # gets answered instead of abandoning the half-built order.
    _intr_reply = _order_interruption_reply(message)
    if _intr_reply:
        if state.get('step') == STEP_CONFIRM:
            tail = _prompt_confirm(state)
        else:
            tail = _prompt_collect(state.get('product_title', ''),
                                   state.get('product_url', ''))
        return _ok(_intr_reply + "\n\n" + tail, 'order_interruption')

    # Product-search escape: user sent a product query ("hp laptop ase",
    # "samsung phone lagbe") instead of filling the order form. They've
    # abandoned the previous order — clear state and fall through to Groq.
    if _is_product_search_escape(message):
        clear_order_flow(user_id)
        return None

    # Price inquiry mid-order ("এটা কত টাকা?", "দাম কত?"). The user wants to
    # verify the price before filling the form. Direct them to the product page
    # (which shows the price) and re-show the order form so they can continue.
    # Runs AFTER the product-search escape so "laptop কত টাকা" still escapes;
    # a bare "কত টাকা" with no brand/category stays here.
    if _is_price_inquiry(message):
        reply = "স্যার, প্রোডাক্টের সর্বশেষ দাম প্রোডাক্ট পেজে দেখুন।"
        if state.get('step') == STEP_CONFIRM:
            tail = _prompt_confirm(state)
        else:
            tail = _prompt_collect(state.get('product_title', ''),
                                   state.get('product_url', ''))
        return _ok(reply + "\n\n" + tail, 'order_interruption')

    step = state['step']

    if step == STEP_COLLECT:
        cities = fetch_city_list()
        areas  = fetch_area_list()
        if not cities or not areas:
            clear_order_flow(user_id)
            return _ok(
                "দুঃখিত স্যার, শহর/এলাকার তালিকা এখন লোড করা যাচ্ছে না। "
                "একটু পরে আবার চেষ্টা করুন।" + LOOP_BACK,
                'order_list_error'
            )

        # Smart follow-up: if the previous turn asked for ONE missing field
        # and the user's reply has no labels, treat the whole reply as that
        # field's value. Without this, an unlabelled "Abu Saiyed Market"
        # would be misread as a name by the freeform parser instead of an
        # address fix-up.
        _, missing_before = _validate_and_resolve(dict(state), {}, cities, areas)
        has_labels = bool(_LABEL_LINE_RE.search(message or '') or
                          re.search(r'[:=]', message or ''))
        extracted: Dict[str, str] = {}
        if len(missing_before) == 1 and not has_labels:
            single = missing_before[0]
            _FIELD_FROM_LABEL = {
                'নাম': 'name',
                'মোবাইল (01XXXXXXXXX)': 'mobile',
                'ঠিকানা': 'address',
                'জেলা': 'city',
                'এলাকা': 'area',
                'পরিমাণ': 'qty',
            }
            field = _FIELD_FROM_LABEL.get(single)
            if field:
                extracted[field] = (message or '').strip()

        if not extracted:
            extracted = _extract_fields(message)
        state, missing = _validate_and_resolve(state, extracted, cities, areas)
        set_order_flow(user_id, state)

        if missing:
            return _ok(_prompt_missing(missing, state, areas), 'order_collect')

        # Every required field is present — place the order right away
        # rather than stopping for a separate "হ্যাঁ" confirmation turn that
        # customers don't know to send (see _finalize_order).
        return _finalize_order(user_id, state)

    if step == STEP_CONFIRM:
        # Reached only as a retry after a previous place_order API failure —
        # _finalize_order sets step=STEP_CONFIRM on failure so the user can
        # retry with "হ্যাঁ" without re-entering every field. First-time
        # completion now places the order directly from STEP_COLLECT with no
        # separate confirmation turn (see _finalize_order).
        #
        # Labelled lines here are FIELD CORRECTIONS ("জেলা: Dhaka",
        # "পরিমাণ: 2") — re-validate them instead of stonewalling on
        # হ্যাঁ/বাতিল, which would force a full restart to fix one field.
        corrections = _parse_labelled_lines(message)
        if corrections:
            cities = fetch_city_list()
            areas  = fetch_area_list()
            if cities and areas:
                state, missing = _validate_and_resolve(state, corrections, cities, areas)
                if missing:
                    state['step'] = STEP_COLLECT
                    set_order_flow(user_id, state)
                    return _ok(_prompt_missing(missing, state, areas), 'order_collect')
                return _finalize_order(user_id, state)
            else:
                # City/area API unavailable — tell the user rather than silently
                # discarding the correction and looping on "হ্যাঁ লিখুন".
                return _ok(
                    "স্যার, এই মুহূর্তে সার্ভারের সাথে যোগাযোগ করা যাচ্ছে না। "
                    "একটু পরে আবার চেষ্টা করুন।",
                    'order_confirm_api_error'
                )
        if not _is_confirm(message):
            return _ok(
                "স্যার, আবার চেষ্টা করতে \"হ্যাঁ\" লিখুন, "
                "অথবা বাতিল করতে \"বাতিল\" লিখুন।",
                'order_confirm'
            )
        return _finalize_order(user_id, state)

    logger.warning("continue_order_flow: unknown step %r for user %s", step, user_id)
    clear_order_flow(user_id)
    return None
