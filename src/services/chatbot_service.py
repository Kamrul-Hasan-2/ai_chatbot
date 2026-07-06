"""
src/services/chatbot_service.py — orchestrator.

Flow (strict order):
  1. load_context(user_id)
  2. detect_intent(message, ...)
  3. merge_context(groq_result, prev_ctx, ...)
  4. handle_intent(intent, ctx, ...)
  5. Response built and returned (caller's save_message does persistence)

Entry point: process_message(user_id, message) → dict
"""
import os
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

from models.chatbot_config import (
    ChatMode, AI_ACTIVE_STATUS, HUMAN_SUPPORT_REQUIRED_STATUS,
    GROQ_API_KEY, GROQ_MODEL, GROQ_ANSWER_MODEL, LOOP_BACK,
)
from services.api_client_service import (
    check_responder_type, assign_agent, assign_bot,
    fetch_history, fetch_categories, fetch_return_policy, fetch_faq_db,
    invalidate_user_cache,
)
from repositories.state_repository import (
    load_context, save_last_intent, get_last_intent,
    get_product_url, clear_product_state, load_faq_db,
    set_session_category, get_session_category,
    load_user_profile, save_user_profile,
    set_pending_question, get_pending_question,
)
from services.intent_service import (
    detect_intent, merge_context,
    resolve_category, normalize_payload,
    apply_post_groq_overrides, resolve_category_from_message,
)
from services.intent_handlers_service import (
    handle_greeting, handle_goodbye, handle_thanks, handle_exit,
    handle_buy, handle_comparison, handle_delivery, handle_faq,
    handle_technical_advice, handle_product_search, handle_price_query,
    handle_url_message, handle_product_detail_followup, handle_fallback,
    handle_clarification_selection, handle_product_spec_query,
    handle_order_status,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Startup: Groq client, categories, FAQ DB ──────────────────────────────────

_groq_client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq) else None
if not _groq_client:
    logger.warning("Groq not available — fallback mode active")

_categories: List[Dict] = []
_faq_db:     List[Dict] = []


def _boot() -> None:
    global _categories, _faq_db
    _categories = fetch_categories()
    _faq_db     = fetch_faq_db()   # live from API, falls back to [] on failure
    logger.info("Booted — %d categories, %d FAQ rows", len(_categories), len(_faq_db))


_boot()

# ── Advance payment signals (module-level, synced with _ADVANCE_PAYMENT_SIGNALS) ─
_ADVANCE_SIGNALS = frozenset({
    'অগ্রিম', 'agrim', 'ogrim', 'ogram', 'আগাম', 'আগে টাকা', 'আগে পেমেন্ট',
    'আগে দিতে হবে', 'আগে দিতে হয়', 'আগে পাঠাতে হবে',
    'upfront', 'prepaid', 'prepay', 'advance', 'advance pay', 'advance dite',
    'age taka', 'age payment', 'age dite', 'age pathate',
})

# ── Self-reference words that carry no question intent ────────────────────────
_BARE_SELF_REF = frozenset({
    'aita', 'eta', 'oita', 'eita', 'ita', 'this', 'it',
    'এটা', 'এইটা', 'ওইটা', 'ওটা',
    '1', '2', '3', '১', '২', '৩',
})

# ── Shop/showroom physical-visit signals ──────────────────────────────────────
# A buyer asking "ami ki apnader shop e eshe dekhe nite parbo?" (can I come to
# your shop and see in person?) carries NO location word, so the seller_query
# downgrade can miss it and Groq may hand the buyer to a sales agent. We catch
# (shop/showroom word) + (physical-visit verb) deterministically before Groq.
# Both sets are substring-matched against message.lower(); validated collision-
# free against genuine seller-onboarding phrasings.
_SHOP_WORDS = frozenset({
    'shop', 'শপ', 'dokan', 'দোকান', 'dukan', 'দুকান', 'store',
    'showroom', 'শোরুম', 'show room', 'শো রুম',
    'outlet', 'আউটলেট', 'office', 'অফিস',
})
_VISIT_SIGNALS = frozenset({
    # Unambiguous physical come/go verbs only. NOTE: do NOT add buy verbs
    # (kinte/kinbo/kena) or the bare see-verbs (dekhte/dekhe) — combined with the
    # common _SHOP_WORDS 'office'/'store'/'dokan'/'shop' they hijack ordinary buy
    # messages ("office er jonno laptop kinbo/dekhte chai") into the showroom
    # reply. Every real shop-visit message also carries a come/go verb below.
    'eshe', 'এসে', 'esye', 'eshey', 'eashe', 'eashey',
    'ashbo', 'asbo', 'আসবো', 'ashbe', 'asbe', 'ashle', 'asle', 'আসলে',
    'jete', 'jabo', 'যেতে', 'যাবো', 'giye', 'গিয়ে',
    'visit', 'ভিজিট', 'come to', 'come and', 'come by', 'come over', 'come visit',
    'serashori', 'সরাসরি', 'nijer chokhe', 'in person',
})

# ── Product authenticity (genuine vs fake) signals ────────────────────────────
# "apnader product asol na nokol?" (are your products genuine or fake?) is a
# trust question. BDStall hosts many independent sellers, so we can't promise
# every single unit is genuine — we answer reassuringly but honestly tell the
# buyer to verify before buying. Substring-matched against message.lower().
# Bare 'asol'/'original' are deliberately excluded — they collide with price
# questions ("asol dam koto", "original price") — so we key off the unambiguous
# fake-side words plus the explicit "asol na nokol" phrasings.
_AUTHENTICITY_SIGNALS = frozenset({
    'nokol', 'নকল', 'nokal', 'nakol',
    'duplicate', 'ডুপ্লিকেট', 'duplicat',
    'fake', 'ফেক',
    'vejal', 'ভেজাল', 'bhejal',
    'master copy', '1st copy', 'first copy', 'copy product',
    'genuine', 'authentic',
    'asol na nokol', 'asol naki nokol', 'asol naki fake',
    'আসল না নকল', 'নকল না আসল', 'real or fake', 'real naki fake',
})

_AUTHENTICITY_RESPONSE = (
    "স্যার, আমাদের এখানের সকল প্রোডাক্টই ভালো, তবে কেনার আগে অবশ্যই দেখে নিবেন।"
)

# ── Product review / rating inquiry signals ───────────────────────────────────
# "eitar review ki?", "review jante chai", "rating kemon", "product er review
# dekhte chai" — the bot can't summarise reviews; it points the buyer to the
# product page where the reviews & ratings live. Latin tokens are word-bounded so
# 'review'/'rating' never fire inside another word; Bangla terms stay substring so
# attached suffixes ("রিভিউটা", "রেটিংটা") still match. (per signal-set collision rule)
_REVIEW_LATIN = frozenset({
    'review', 'reviews', 'rivew', 'riview', 'rivu', 'rebhio', 'rebhiu',
    'rating', 'ratings',
})
_REVIEW_BANGLA = (
    'রিভিউ', 'রিভিও', 'রেটিং', 'মতামত',
)
_REVIEW_LATIN_RE = re.compile(
    r'\b(?:' + '|'.join(re.escape(w) for w in _REVIEW_LATIN) + r')\b'
)


def _is_contact_submission(message: str) -> bool:
    """True when the message is essentially just a BD phone number + label words.

    "আমার কন্টাক্ট নাম্বার ০১৩১৫৯২৮১৬১" → True.
    "Samsung phone 01712345678 price koto" → False (has non-label content).
    """
    if not _BD_MOBILE_RE.search(message):
        return False
    remaining = _BD_MOBILE_RE.sub(' ', message)
    remaining = _CONTACT_LABEL_RE.sub(' ', remaining)
    remaining = re.sub(r'[\s.,?!।:;+\-()০-৯0-9]+', '', remaining)
    return len(remaining) <= 3


def _is_bare_price_query(message: str) -> bool:
    """True when the message is ONLY a price question — no product name.

    "Prices?" → True.  "Samsung phone price" → False (has product token).
    """
    cleaned = re.sub(r'[?!।.,\'"]+', '', (message or '').lower()).strip()
    tokens = cleaned.split()
    if not tokens:
        return False
    # 'কত' / 'কতো' / 'koto' alone mean "how many?" — too ambiguous to treat as
    # a bare price query without an unambiguous price word like 'দাম' or 'টাকা'.
    _AMBIGUOUS_ALONE = {'কত', 'কতো', 'koto'}
    if all(t in _AMBIGUOUS_ALONE for t in tokens):
        return False
    return all(t in _BARE_PRICE_WORDS for t in tokens)


def _has_review_word(msg_lower: str) -> bool:
    if any(w in msg_lower for w in _REVIEW_BANGLA):
        return True
    return bool(_REVIEW_LATIN_RE.search(msg_lower))

# ── Order-status inquiry (existing order) signals ─────────────────────────────
# "Bai akta order chilo", "amar order ta kothay", "order korechilam status ki?"
# are buyers asking about an EXISTING order. With an order number we look it up;
# without one we ask for the order ID and remember we're waiting (_AWAITING_…)
# so the NEXT message — the bare ID — routes straight to the lookup, instead of
# handing the buyer to a human. We require an order word AND a past/status
# marker, and EXCLUDE future buy markers ("order korbo", "kivabe order dibo"),
# so purchase-process questions are NOT swallowed here.
_ORDER_WORDS = ('order', 'অর্ডার', 'অডার', 'ordar', 'ordr')
_ORDER_EXISTING_MARKERS = (
    'chilo', 'silo', 'chilam', 'silam', 'korechilam', 'korsilam', 'disilam',
    'diyechilam', 'dilam', 'korechi', 'korsi', 'disi', 'diyechi',
    'kothay', 'kuthay', 'koi', 'kobe pabo', 'kobe asbe', 'kobe debe',
    'koidur', 'koto dur', 'status', 'obostha', 'khobor', 'ki holo', 'ki hoilo',
    'pai nai', 'paini', 'pai ni', 'peyechi', 'ase nai', 'ase ni', 'aseni',
    'asena', 'asche na', 'elo na', 'elona',
    # "show me / view this order" — only ever evaluated next to an order word.
    'dekhao', 'dekhe dao', 'dekhe den', 'dekhte chai', 'dekhte chacchi',
    'dekhbo', 'dekhte', 'check koro', 'check kor',
    'ছিল', 'ছিলো', 'করেছিলাম', 'দিয়েছিলাম', 'কোথায়', 'অবস্থা', 'স্ট্যাটাস', 'খবর',
    # present-perfect "placed / gave" — Bangla script (Banglish covered above)
    'দিয়েছি', 'করেছি', 'দিছি', 'কিনেছি',
    # "hasn't arrived / hasn't been received yet" — common delivery complaint words
    'আসে নি', 'আসেনি', 'আসে নাই', 'আসেনাই', 'আসছে না', 'আসছে নি',
    'এখনো আসেনি', 'এখনও আসেনি', 'এখনো পাইনি', 'এখনও পাইনি',
    'পাই নি', 'পাইনি', 'পায়নি', 'পাই নাই', 'পাইনাই', 'পেলাম না', 'আসলো না',
    'দেখাও', 'দেখে দাও', 'দেখে দেন', 'দেখান', 'দেখতে চাই', 'দেখতে চাচ্ছি',
    'দেখব', 'দেখবো', 'দেখতে',
)
_ORDER_BUY_MARKERS = (
    'korbo', 'korte chai', 'korte chacchi', 'dibo', 'dite chai', 'kibhabe',
    'kivabe', 'kibabe', 'kemne', 'kinbo', 'kinte chai',
    'করব', 'করতে চাই', 'দিব', 'কিভাবে', 'কিনব',
)
_AWAITING_ORDER_ID_INTENT = 'awaiting_order_id'
_ASK_ORDER_ID_RESPONSE = (
    "স্যার, আপনার অর্ডার আইডিটি দিন, আমি অর্ডার স্ট্যাটাসটি জানিয়ে দিচ্ছি।"
)

# ── Picture / image reference signals ─────────────────────────────────────────
# The bot cannot read images. A pure image attachment is handled in the webhook
# controller, but when a buyer ALSO types a line like "পিকচার দিয়েছি" that text
# reaches Groq and produces a garbled technical-advice reply. Catch a picture
# reference deterministically and ask for the product name + model in text.
# _PICTURE_WORDS are substring-matched but ONLY trigger together with a sent
# marker (so "ছবি তোলার ক্যামেরা" stays a product search); a message that is
# purely a picture word (exact match in _PICTURE_STANDALONE) also triggers.
_PICTURE_WORDS = (
    'পিকচার', 'ছবি', 'ছবিটা', 'ফটো', 'স্ক্রিনশট',
    'picture', 'image', 'photo', 'foto', 'chobi', 'screenshot', 'screen shot',
)
_PICTURE_SENT_MARKERS = (
    # Bare ambiguous fragments removed (disi/dichi/sent/attach/upore) — combined
    # with a picture word they false-fired on camera/photo searches.
    'দিয়েছি', 'দিলাম', 'দিছি', 'দিয়েছিলাম', 'পাঠিয়েছি', 'পাঠালাম', 'পাঠাইছি',
    'পাঠিয়েছিলাম', 'উপরের',
    'diyechi', 'diechi', 'dilam', 'pathiyechi', 'pathalam',
    'pathaichi', 'pathailam', 'send korechi', 'send korlam', 'send dilam',
    'attach korechi', 'attach korlam', 'uporer',
)
_PICTURE_STANDALONE = frozenset({
    'পিকচার', 'ছবি', 'ছবিটা', 'ফটো', 'স্ক্রিনশট',
    'picture', 'pic', 'pics', 'image', 'img', 'photo', 'foto', 'chobi',
    'screenshot', 'screen shot',
})
_PICTURE_RESPONSE = (
    "স্যার, আপনি কোন প্রোডাক্টটি কিনতে চাচ্ছেন? "
    "দয়া করে প্রোডাক্টটির নাম এবং মডেল বলুন।"
)

# ── Business / partnership inquiry signals ────────────────────────────────────
# "Apnara j kono company r share/land/apartment sell koren naki leads share
# koren" — a B2B / lead-sharing / partnership question. Groq catches the
# "apartment sell" fragment and dumps apartment listings. These terms are
# unambiguously business-to-business (no buyer searching for a flat/land would
# use them), so we hand the inquiry to a human representative before Groq.
_BUSINESS_INQUIRY_SIGNALS = (
    'leads share', 'lead share', 'leads den', 'lead den', 'leads diben',
    'leads koren', 'lead koren', 'leads provide', 'lead provide',
    'leads sharing', 'lead sharing', 'lead generation',
    'affiliate', 'affiliation', 'reseller', 're-seller',
    'dealership', 'dealer hote', 'distributor', 'distributorship',
    'partnership', 'partner hote', 'franchise', 'b2b',
    'company share', 'companyr share', 'company r share', 'kompanir share',
    'shares sell', 'share sell koren', 'stock share', 'equity',
)
_BUSINESS_INQUIRY_RESPONSE = (
    "স্যার, ব্যবসায়িক বা পার্টনারশিপ সংক্রান্ত বিষয়ে আমাদের একজন "
    "প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"
)

# ── Contact-number submission detection ───────────────────────────────────────
# "আমার কন্টাক্ট নাম্বার ০১৩১৫৯২৮১৬১" — customer submitting their phone in
# response to a property/seller request. Groq reads "আমার" as "আম" (mango) and
# fires a Mango category search. Catch messages whose only content is a BD
# mobile number plus label words (নাম্বার, কন্টাক্ট, আমার, my, …).
_BD_MOBILE_RE = re.compile(
    r'(?:\+?880)?(?:0|০)(?:1|১)[০-৯0-9]{9}'
)
_CONTACT_LABEL_RE = re.compile(
    r'(?:'
    # Bangla tokens are full Unicode words — no \b needed
    r'আমার|আমর|এই|এটা|হলো|হল|'
    r'কন্টাক্ট|কনট্যাক্ট|'
    r'নাম্বার|নম্বর|'
    r'ফোন|মোবাইল|'
    r'দিচ্ছি|দিলাম|নিন|নিলেন|'
    # Latin tokens must be whole words so 'no' doesn't match inside Nokia, etc.
    r'\b(?:amar|amr|my|ei|eta|holo|contact|kontakt|'
    r'number|nambar|nombor|num|no|'
    r'phone|mobile|dichi|dilam|din|nilen|is|are)\b'
    r')',
    re.IGNORECASE | re.UNICODE,
)

# ── Suggestion / "which is best" request signals ──────────────────────────────
# "তুমি সাজেশন দিতে পারো?", "কোনটা ভালো হবে সুপার শপের জন্য?", "konta valo",
# "recommend korben?" — as a Virtual Assistant the bot must not pick a "best"
# product or give a personal suggestion; it offers information instead. Caught
# before Groq so these aren't re-routed to a category landing page or the buy
# flow ("konta kinbo" otherwise hits the buy intercept). Phrases only (never
# bare 'valo'/'best') so plain searches like "valo laptop dekhao" aren't caught.
_SUGGESTION_SIGNALS = (
    'সাজেশন', 'সাজেস্ট', 'সাজেশান', 'পরামর্শ', 'উপদেশ',
    'কোনটা ভালো', 'কোনটি ভালো', 'কোনটা ভাল', 'কোনটি ভাল', 'কোনটা বেস্ট',
    'সেরা কোনটা', 'সেরা কোনটি', 'কোনটা নিবো', 'কোনটা নেবো', 'কোনটা কিনবো',
    'কোনটা সবচেয়ে', 'কোনটি সেরা', 'কোনটা ভালো হবে',
    'suggestion', 'suggest', 'sajeshon', 'sajession', 'sagestion',
    'recommend', 'recommendation', 'poramorsho', 'poramorso',
    'konta valo', 'konti valo', 'kunta valo', 'konta bhalo', 'konti bhalo',
    'kon ta valo', 'konta nibo', 'konta nebo', 'konta kinbo', 'konta best',
    'best konta', 'best konti', 'sera konta', 'sera konti', 'konta beshi valo',
    'which is better', 'which one is better', 'which is best', 'which one is best',
    'which should i', 'recommend me', 'any suggestion', 'your suggestion',
)
_SUGGESTION_RESPONSE = (
    "স্যার, আমি Virtual Assistant, তাই সাজেশন নয়, তথ্যভিত্তিক সহায়তা দিতে পারি।"
)

# ── Payment-method / cash-on-delivery signals ─────────────────────────────────
# "cash on delivery hobe?", "kivabe payment korbo?", "bkash e dewa jabe?" asked
# OUTSIDE an order flow. Groq mislabels these as buy/product_search and replies
# "which model do you want?". We answer the payment question deterministically
# before Groq. (Inside an order flow these are handled by order_handler's
# interruption guard, which runs earlier.) Substring-matched against
# message.lower(); 'cod' is matched word-bounded so "code"/"barcode" don't hit.
_PAYMENT_SIGNALS = frozenset({
    'cash on delivery', 'ক্যাশ অন ডেলিভারি', 'ক্যাশ অন', 'c.o.d',
    'hate peye', 'haate peye', 'hate pe taka', 'হাতে পেয়ে',
    'payment', 'পেমেন্ট', 'pay korbo', 'pay korte',
    'bkash', 'বিকাশ', 'nagad', 'নগদ',
    'online payment', 'অনলাইন পেমেন্ট',
    'taka kivabe dibo', 'kivabe taka dibo', 'taka kibhabe dibo',
})

_PAYMENT_RESPONSE = (
    "স্যার, ঢাকার ভেতরে পণ্য হাতে পেয়ে টাকা দিতে পারবেন (ক্যাশ অন ডেলিভারি)। "
    "ঢাকার বাইরে শুধু অগ্রিম পেমেন্ট প্রযোজ্য।"
)

# ── Blocked automated message guard ──────────────────────────────────────────

_STORAGE_DRIVE_TERMS = (
    'ssd', 'hdd', 'hard disk', 'hard drive', 'nvme', 'm.2', 'sata ssd',
)
# Search-intent signals. Single Latin tokens are word-bounded (so 'dam' won't
# match 'damage', 'show' won't match 'showroom', 'chai' won't match 'chair');
# phrases and Bangla terms keep substring matching.
_STORAGE_DRIVE_SEARCH_SIGNALS = (
    'drive', 'external', 'portable', 'lagbe', 'chai', 'kinbo', 'kinte',
    'dekhan', 'dekhao', 'show', 'price', 'dam',
    'দাম', 'কিনতে', 'কিনব', 'লাগবে', 'চাই', 'দেখান', 'দেখাও',
)
# A damaged / return / complaint message about a drive is NOT a search — it must
# reach the complaint flow, not clear state and run a product search.
_STORAGE_COMPLAINT_SIGNALS = (
    'nosto', 'noshto', 'নষ্ট', 'damage', 'problem', 'সমস্যা',
    'refund', 'return', 'ferot', 'ferat', 'ফেরত',
    'broken', 'bhanga', 'ভাঙা', 'kaj kore na', 'kaj korche na',
)


def _is_storage_drive_search(message: str) -> bool:
    """True when SSD/HDD wording means a drive product search — not a laptop spec
    question, and not a complaint about a drive."""
    msg = (message or '').lower()
    if not any(term in msg for term in _STORAGE_DRIVE_TERMS):
        return False
    # Damaged/return/complaint about a drive → let the complaint flow handle it.
    if any(c in msg for c in _STORAGE_COMPLAINT_SIGNALS):
        return False
    for sig in _STORAGE_DRIVE_SEARCH_SIGNALS:
        if (' ' in sig) or any(ord(ch) > 127 for ch in sig):
            if sig in msg:                                    # phrase / Bangla
                return True
        elif re.search(r'\b' + re.escape(sig) + r'\b', msg):  # word-bounded Latin
            return True
    return False


# Bare price queries ("Prices?", "দাম কত?", "koto taka?") with no product
# name reach Groq and get random category hallucinations. Intercept them when
# words are ONLY price-query tokens so "Samsung phone price" still routes to
# product search (has product name).
_BARE_PRICE_WORDS = frozenset({
    'price', 'prices', 'দাম', 'dam', 'taka', 'টাকা', 'কত', 'কতো', 'koto',
})

# Emoji-only messages (e.g. 😡 Messenger reactions) must not reach Groq;
# Groq labels them as hate_speech and fires the "ভদ্র ভাষায়" warning.
_EMOJI_ONLY_RE = re.compile(
    r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF'
    r'\U0001FA00-\U0001FAFF\U00002702-\U000027B0︎️\s]+$'
)

# "Samsung A53 5G price?" — the trailing "price?" is a price-inquiry word, not a
# budget spec. Strip it before sending to Groq so it doesn't get mistaken for a
# price_max (Groq sometimes reads "price" or nearby numbers like "6" GB as a budget).
_PRICE_INQUIRY_SUFFIX_RE = re.compile(
    r'\s*\b(?:price|prices|দাম|dam|কত|koto)\s*\??\s*$',
    re.IGNORECASE | re.UNICODE,
)

# "Ara vai ami bolsi ja ami charger nibo ami nibo iphone" — "ami bolsi ja" /
# "bolechi je" / "bolesi je" are correction preambles meaning "I said that".
# Strip them before Groq so the actual product intent reaches the model cleanly.
_CORRECTION_PREAMBLE_RE = re.compile(
    r'^\s*(?:ara\s+)?(?:vai\s+|bhai\s+|bro\s+)?'
    r'(?:ami\s+)?(?:bolsi\s+(?:ja|je)|bolechi\s+(?:ja|je)|bolesi\s+(?:ja|je)|'
    r'bolsilam\s+(?:ja|je)|apnake\s+bolsi|apnake\s+bolechi)\s*',
    re.IGNORECASE,
)

# "Airokom machine gola hobe?" — "airokom" is Banglish for এইরকম (like this).
# Groq reads "Airo" as "Air" and fires an Air Conditioner search. Strip these
# demonstrative pronouns before Groq so only the noun ("machine") reaches it.
_BN_DEMONSTRATIVE_RE = re.compile(
    r'\b(?:airokom|eirokom|oirokom|erokom|airocome|eirocome|'
    r'oisob|eisob|aisob|oisbo|eisbo|aisbo|'
    r'oigula|eigula|aigula|oigulo|eigulo|aigulo)\b',
    re.IGNORECASE,
)

_BLOCKED_PHRASES = [
    'bdstall.com-এ আপনাকে স্বাগতম',
    'আপনার মেসেজ এর জন্য ধন্যবাদ',
    'খুব শীঘ্রই bdstall.com এর একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবে',
]


def _is_automated(message: str) -> bool:
    text = str(message or '').strip().lower()
    return sum(1 for p in _BLOCKED_PHRASES if p in text) >= 2


# ── Response builder ──────────────────────────────────────────────────────────

# Once an intent is detected, responses are emitted from formatted templates
# only — Groq is reserved for the knowledge (technical_advice) intent. The
# humanizer is intentionally disabled.

def _build_response(user_id: str, handler_result: Dict,
                    mode: ChatMode, conversation_status: str,
                    processing_time: float,
                    user_message: str = '',
                    profile=None) -> Dict[str, Any]:
    save_last_intent(user_id, handler_result.get('intent', 'unknown'))

    response_text = handler_result.get('response', '')
    intent = handler_result.get('intent', 'unknown')

    result: Dict[str, Any] = {
        'response':            response_text,
        'mode':                mode.value,
        'intent':              intent,
        'intent_content':      handler_result.get('intent_content', {}),
        'conversation_status': conversation_status,
        'products':            handler_result.get('products', []),
        'processing_time':     round(processing_time, 3),
    }
    link_buttons = handler_result.get('link_buttons')
    if link_buttons:
        result['link_buttons'] = link_buttons
    return result


def _handoff(user_id: str, intent_name: str, response_text: str,
             start_time: datetime) -> Dict[str, Any]:
    assign_agent(user_id, intent_name)
    ic = normalize_payload(load_context(user_id))
    handler_result = {'response': response_text, 'intent': intent_name,
                      'intent_content': ic, 'products': []}
    return _build_response(user_id, handler_result,
                           ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                           (datetime.now() - start_time).total_seconds())


def _observe_and_save(user_id: str, profile, message: str,
                      intent: str, ctx: Dict) -> None:
    """Update the rolling user profile from one turn and persist it.

    Never raises — profile updates must not break the user-facing reply.
    """
    try:
        profile.observe_message(
            message=message,
            intent=intent or None,
            category=(ctx.get('category') or ctx.get('cat') or '') if ctx else '',
            price_min=ctx.get('price_min') if ctx else None,
            price_max=ctx.get('price_max') if ctx else None,
        )
        save_user_profile(user_id, profile)
    except Exception as e:
        logger.warning("profile observe/save failed: %s", e)


# ── Main entry ────────────────────────────────────────────────────────────────

def process_message(user_id: str, message: str) -> Dict[str, Any]:
    start_time = datetime.now()
    logger.info("user=%s msg=%r", user_id, message)

    # Load profile up-front — every code path below benefits from it
    # (humanization, prompt injection, observation update on the way out).
    profile = load_user_profile(user_id)

    try:
        # ── STEP 1: load_context (single DB round-trip for the whole request) ──
        prev_ctx = load_context(user_id)

        # Blocked automated template
        if _is_automated(message):
            _observe_and_save(user_id, profile, message, 'ignored_automated_template', {})
            ic = normalize_payload(prev_ctx)
            return _build_response(user_id,
                {'response': '', 'intent': 'ignored_automated_template',
                 'intent_content': ic, 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # Human mode check
        if check_responder_type(user_id) == 'agent':
            _observe_and_save(user_id, profile, message, 'human_mode_active', {})
            ic = normalize_payload(prev_ctx)
            return _build_response(user_id,
                {'response': '', 'intent': 'human_mode_active',
                 'intent_content': ic, 'products': []},
                ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Order flow pump ──────────────────────────────────────────────────
        # If the user is mid-order (collecting name/mobile/address/city/area/qty,
        # or at the final confirm step), every incoming message must go through
        # the order handler so we don't kick them back into Groq routing.
        from services.order_handler import is_in_order_flow, continue_order_flow
        if is_in_order_flow(user_id):
            order_result = continue_order_flow(user_id, message)
            if order_result is not None:
                _observe_and_save(user_id, profile, message,
                                  order_result.get('intent', 'order_flow'), {})
                return _build_response(user_id, order_result,
                                       ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)

        # ── Emoji-only / reaction intercept ──────────────────────────────────
        # A lone emoji (e.g. 😡 as a Messenger reaction) is NOT hate_speech;
        # Groq labels it that way and fires "ভদ্র ভাষায়", which insults a
        # customer who was simply expressing frustration via a reaction.
        if _EMOJI_ONLY_RE.match(message.strip()):
            _emj_ctx = normalize_payload(prev_ctx)
            _observe_and_save(user_id, profile, message, 'emoji_reaction', {})
            return _build_response(
                user_id,
                {'response': "স্যার, কোনো সাহায্য লাগলে বলুন।" + LOOP_BACK,
                 'intent': 'emoji_reaction', 'intent_content': _emj_ctx,
                 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Advance payment intercept ────────────────────────────────────────
        # Groq often mislabels "অগ্রিম টাকা দিতে হবে?" as product_search.
        # Catch it deterministically before Groq.
        if any(s in message.lower() for s in _ADVANCE_SIGNALS):
            from services.intent_handlers_service import handle_delivery as _hd
            _adv_ctx = normalize_payload(prev_ctx)
            _adv_result = _hd(_adv_ctx, user_id, message, [])
            _observe_and_save(user_id, profile, message, 'delivery', {})
            return _build_response(user_id, _adv_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # ── Payment-method / cash-on-delivery intercept ──────────────────────
        # "cash on delivery hobe?", "bkash e payment kora jabe?" outside an order
        # flow. Groq sends these to buy/product_search and answers "which model?".
        # Answer the payment question deterministically before Groq.
        _msg_l_pay = message.lower()
        if (any(s in _msg_l_pay for s in _PAYMENT_SIGNALS)
                or re.search(r'\bcod\b', _msg_l_pay)):
            _pay_ctx = normalize_payload(prev_ctx)
            _observe_and_save(user_id, profile, message, 'faq_payment', {})
            return _build_response(
                user_id,
                {'response': _PAYMENT_RESPONSE,
                 'intent': 'faq_payment', 'intent_content': _pay_ctx,
                 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Order status lookup intercept ────────────────────────────────────
        # Catch buyers asking about an EXISTING order before Groq sends them to
        # the generic delivery FAQ or (worse) a human handoff. Two paths:
        #   1. Our previous reply asked for the order ID → treat the order-no in
        #      this message as the lookup key.
        #   2. The message references an existing order (an explicit status
        #      phrase, OR an order word + a past/status marker but NOT a future
        #      buy marker). With an order number → look it up; without one → ask
        #      for the order ID and remember we're waiting.
        _ORDER_STATUS_SIGNALS = (
            'order status', 'order track', 'track order', 'order check',
            'order kothay', 'order koi', 'order id', 'order no',
            'অর্ডার স্ট্যাটাস', 'অর্ডার চেক', 'অর্ডার ট্র্যাক', 'অর্ডার কোথায়',
            'অর্ডার নম্বর', 'অর্ডার আইডি', 'অর্ডার দেখান', 'অর্ডার আপডেট',
            'check my order', 'where is my order', 'status of my order',
        )
        _msg_l_os = message.lower()

        def _lookup_order_status():
            """Run the lookup; return a built response or None if no order-no."""
            os_ctx = normalize_payload(prev_ctx)
            os_result = handle_order_status(os_ctx, user_id, message)
            if os_result is None:
                return None
            _observe_and_save(user_id, profile, message,
                              os_result.get('intent', 'order_status'), {})
            return _build_response(user_id, os_result,
                                   ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Path 1 — we previously asked for the order ID. Any order-no in this
        # reply is the lookup key. If there's no valid number we fall through so
        # a topic change ("thik ache pore dibo") is handled normally.
        if get_last_intent(user_id) == _AWAITING_ORDER_ID_INTENT:
            _await_resp = _lookup_order_status()
            if _await_resp is not None:
                return _await_resp

        # Path 2 — order-status inquiry detection. An order word plus either an
        # order-number-shaped digit run (≥8 ASCII/Bangla digits) OR a past/
        # status/"show me" marker — but never a buy marker — is a status inquiry.
        _has_order_no_shape = bool(re.search(r'[\d০-৯]{8,}', message))
        _is_order_inquiry = (
            any(w in _msg_l_os for w in _ORDER_WORDS)
            and (_has_order_no_shape
                 or any(m in _msg_l_os for m in _ORDER_EXISTING_MARKERS))
            and not any(b in _msg_l_os for b in _ORDER_BUY_MARKERS)
        )
        if any(s in _msg_l_os for s in _ORDER_STATUS_SIGNALS) or _is_order_inquiry:
            _os_resp = _lookup_order_status()
            if _os_resp is not None:
                return _os_resp
            # No order number present — ask for the order ID and remember we're
            # waiting so the next message (the bare ID) routes straight to lookup.
            _observe_and_save(user_id, profile, message,
                              _AWAITING_ORDER_ID_INTENT, {})
            return _build_response(
                user_id,
                {'response': _ASK_ORDER_ID_RESPONSE,
                 'intent': _AWAITING_ORDER_ID_INTENT,
                 'intent_content': normalize_payload(prev_ctx), 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Suggestion / "which is best" intercept ───────────────────────────
        # The bot is a Virtual Assistant and must not pick a "best" product or
        # give a personal suggestion — it offers information instead. Caught
        # before Groq (and before the buy intercept, which would otherwise grab
        # "konta kinbo") so these don't get a category page or buy flow.
        _msg_l_sug = message.lower()
        if any(s in _msg_l_sug for s in _SUGGESTION_SIGNALS):
            _sug_ctx = normalize_payload(prev_ctx)
            _observe_and_save(user_id, profile, message, 'suggestion', {})
            return _build_response(
                user_id,
                {'response': _SUGGESTION_RESPONSE + LOOP_BACK,
                 'intent': 'suggestion', 'intent_content': _sug_ctx, 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Shop/showroom visit intercept ────────────────────────────────────
        # "ami ki apnader shop e eshe dekhe nite parbo?" (can I come to your shop
        # in person?) has no location word, so the seller_query downgrade can miss
        # it and Groq may hand the buyer to a sales agent. Catch (shop word) +
        # (physical-visit verb) deterministically before Groq → online-platform
        # answer. BDStall is online-only, so there is never a shop to visit.
        _msg_l_shop = message.lower()
        if (any(w in _msg_l_shop for w in _SHOP_WORDS)
                and any(v in _msg_l_shop for v in _VISIT_SIGNALS)):
            from services.intent_handlers_service import _SHOWROOM_RESPONSE
            _sv_ctx = normalize_payload(prev_ctx)
            _observe_and_save(user_id, profile, message, 'faq_showroom', {})
            return _build_response(
                user_id,
                {'response': _SHOWROOM_RESPONSE + LOOP_BACK,
                 'intent': 'faq_showroom', 'intent_content': _sv_ctx, 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Product authenticity intercept ───────────────────────────────────
        # "apnader product asol na nokol?" (genuine or fake?). Catch it before
        # Groq — otherwise it gets mislabelled as product_search (and re-shows
        # cached products) or routed to the product-detail followup. Fixed
        # reassure-but-verify reply; never hands off to a human.
        _msg_l_auth = message.lower()
        if any(s in _msg_l_auth for s in _AUTHENTICITY_SIGNALS):
            _auth_ctx = normalize_payload(prev_ctx)
            _observe_and_save(user_id, profile, message, 'faq_authenticity', {})
            return _build_response(
                user_id,
                {'response': _AUTHENTICITY_RESPONSE,
                 'intent': 'faq_authenticity', 'intent_content': _auth_ctx,
                 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Product review / rating intercept ────────────────────────────────
        # "eitar review koto?", "review jante chai", "rating kemon" — the bot
        # doesn't summarise reviews; it sends the buyer to the product page where
        # the reviews & ratings are shown. Fills the name + link from the most
        # recently discussed (cached) product; if nothing is cached we ask which
        # product. Runs before the product-detail followup so review questions
        # aren't answered as spec queries.
        _msg_l_rev = message.lower()
        if _has_review_word(_msg_l_rev):
            from repositories.state_repository import get_product_context as _gpc_rev
            _rev_ctx = normalize_payload(prev_ctx)
            _rev_products = _gpc_rev(user_id)
            if _rev_products:
                _rev_top = _rev_products[0]
                _rev_title = (_rev_top.get('title') or 'এই প্রোডাক্ট')[:60]
                _rev_url = _rev_top.get('url', '')
                _rev_buttons = ([{'text': 'প্রোডাক্ট দেখুন', 'url': _rev_url,
                                  'title': _rev_title}] if _rev_url else [])
                _rev_text = (f"স্যার, {_rev_title} এই প্রোডাক্টের রিভিউ দেখতে "
                             "প্রোডাক্ট পেজে ভিজিট করুন।")
                _observe_and_save(user_id, profile, message, 'product_review', {})
                return _build_response(
                    user_id,
                    {'response': _rev_text, 'intent': 'product_review',
                     'intent_content': _rev_ctx, 'products': [],
                     'link_buttons': _rev_buttons},
                    ChatMode.AI, AI_ACTIVE_STATUS,
                    (datetime.now() - start_time).total_seconds(),
                    user_message=message, profile=profile)
            # No product in context — ask which product the review is for.
            _observe_and_save(user_id, profile, message, 'product_review', {})
            return _build_response(
                user_id,
                {'response': ("স্যার, আপনি কোন প্রোডাক্টের রিভিউ দেখতে চান? "
                              "প্রোডাক্টটির নাম বলুন, আমি প্রোডাক্ট পেজের লিংক "
                              "দিয়ে দিচ্ছি।"),
                 'intent': 'product_review', 'intent_content': _rev_ctx,
                 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Bare price query intercept ───────────────────────────────────────
        # "Prices?" / "দাম কত?" with no product name → Groq hallucinates a
        # random category (e.g. Microsoft Office). If products are in context,
        # show their prices; otherwise ask which product the buyer means.
        if _is_bare_price_query(message):
            from repositories.state_repository import get_product_context as _gpc_price
            _price_ctx = normalize_payload(prev_ctx)
            _price_products = _gpc_price(user_id)
            if _price_products:
                _price_lines = []
                _price_buttons = []
                for _pp in _price_products[:3]:
                    _pp_title = (_pp.get('title') or '')[:55]
                    _pp_price = _pp.get('price') or ''
                    _pp_url   = _pp.get('url', '')
                    _price_lines.append(f"• {_pp_title}: {_pp_price}")
                    if _pp_url:
                        _price_buttons.append({'text': _pp_title[:30],
                                               'url': _pp_url, 'title': _pp_title})
                _price_text = ("স্যার, এই প্রোডাক্টগুলোর দাম:\n\n"
                               + '\n'.join(_price_lines) + LOOP_BACK)
                _observe_and_save(user_id, profile, message, 'price_query', {})
                return _build_response(
                    user_id,
                    {'response': _price_text, 'intent': 'price_query',
                     'intent_content': _price_ctx, 'products': [],
                     'link_buttons': _price_buttons},
                    ChatMode.AI, AI_ACTIVE_STATUS,
                    (datetime.now() - start_time).total_seconds(),
                    user_message=message, profile=profile)
            # No products in context — ask which product.
            _observe_and_save(user_id, profile, message, 'price_query', {})
            return _build_response(
                user_id,
                {'response': ("স্যার, কোন প্রোডাক্টের দাম জানতে চান? "
                              "প্রোডাক্টের নাম বলুন।" + LOOP_BACK),
                 'intent': 'price_query', 'intent_content': _price_ctx,
                 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Picture / image reference intercept ──────────────────────────────
        # "পিকচার দিয়েছি" / "ছবি পাঠিয়েছি" / "pic dilam" — the bot can't read
        # images, so Groq turns these into a garbled technical-advice reply. Ask
        # for the product name + model in text instead. Trigger when the message
        # is purely a picture word, OR a picture word co-occurs with a "sent"
        # marker (so a camera search like "ছবি তোলার ক্যামেরা" is NOT caught).
        _msg_l_pic = message.lower()
        _msg_pic_stripped = _msg_l_pic.strip().rstrip('.?!।, ')
        _has_pic_ref = (any(w in _msg_l_pic for w in _PICTURE_WORDS)
                        or bool(re.search(r'\b(pic|pics|img|imgs)\b', _msg_l_pic)))
        _has_pic_sent = any(s in _msg_l_pic for s in _PICTURE_SENT_MARKERS)
        if (_msg_pic_stripped in _PICTURE_STANDALONE
                or (_has_pic_ref and _has_pic_sent)):
            _pic_ctx = normalize_payload(prev_ctx)
            _observe_and_save(user_id, profile, message, 'faq_picture', {})
            return _build_response(
                user_id,
                {'response': _PICTURE_RESPONSE,
                 'intent': 'faq_picture', 'intent_content': _pic_ctx,
                 'products': []},
                ChatMode.AI, AI_ACTIVE_STATUS,
                (datetime.now() - start_time).total_seconds(),
                user_message=message, profile=profile)

        # ── Business / partnership inquiry intercept ─────────────────────────
        # B2B / lead-sharing / partnership questions ("leads share koren?",
        # "companyr share sell koren?") get mislabelled as product_search and
        # dump apartment/land listings. Hand them to a human before Groq.
        _msg_l_biz = message.lower()
        if any(s in _msg_l_biz for s in _BUSINESS_INQUIRY_SIGNALS):
            _observe_and_save(user_id, profile, message, 'seller_query', {})
            return _handoff(user_id, 'seller_query',
                            _BUSINESS_INQUIRY_RESPONSE, start_time)

        # ── Contact-number submission intercept ──────────────────────────────
        # "আমার কন্টাক্ট নাম্বার ০১৩১৫৯২৮১৬১" — customer submitting their
        # phone in response to a seller/property request. Groq extracts 'আম'
        # (mango) from 'আমার' and fires a Mango search. Catch it before Groq.
        if _is_contact_submission(message):
            _observe_and_save(user_id, profile, message, 'seller_query', {})
            return _handoff(
                user_id, 'seller_query',
                "স্যার, আপনার নাম্বার পাওয়া গেছে। আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।",
                start_time)

        # Deterministic greeting intercept — short hi/hello/salam messages should
        # never depend on Groq. Without this a Groq outage hands every new user
        # to a human via the strict-handoff policy.
        _GREETING_PHRASES = {
            'hi', 'hii', 'hiii', 'hello', 'helo', 'hey', 'hlw', 'hloo',
            'salam', 'assalamualaikum', 'asalamualaikum', 'assalam', 'slm',
            'হাই', 'হ্যালো', 'হেলো', 'সালাম', 'আসসালামু আলাইকুম', 'আসসালামুয়ালাইকুম',
        }
        _msg_norm = message.strip().lower().rstrip('.?!।,')
        if _msg_norm in _GREETING_PHRASES:
            greet_result = handle_greeting(normalize_payload(prev_ctx), user_id, message)
            _observe_and_save(user_id, profile, message, 'greeting', {})
            return _build_response(user_id, greet_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # URL in message
        url_match = re.search(r'https?://[^\s]+', message)
        if url_match:
            ic_ctx = normalize_payload(prev_ctx)
            flat_ctx = {
                'category':  ic_ctx.get('cat', ''),
                'brand':     ic_ctx.get('brand', ''),
                'title':     ic_ctx.get('title', ''),
                'price_max': ic_ctx.get('price_max'),
                'price_min': ic_ctx.get('price_min'),
            }
            # Extract any budget the user mentioned alongside the URL.
            # extract_budget_range returns 'max_price'/'min_price' (not 'price_*').
            from services.intent_service import extract_budget_range
            url_budget = extract_budget_range(message)
            if url_budget.get('max_price') is not None:
                flat_ctx['price_max'] = url_budget['max_price']
            if url_budget.get('min_price') is not None:
                flat_ctx['price_min'] = url_budget['min_price']
            result = handle_url_message(flat_ctx, user_id, message, url_match.group(0))
            _observe_and_save(user_id, profile, message, result.get('intent', ''), flat_ctx)
            return _build_response(user_id, result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Self-reference buy: "এইটা/এটা/this order dite chaicchi" with cached products
        # → skip Groq/budget, go straight to buy handler with the cached product.
        from repositories.state_repository import get_product_context as _gpc_buy
        _cached_buy = _gpc_buy(user_id)
        _msg_lower_buy = message.lower()
        _BUY_SELF_REF = {'এইটা', 'এটা', 'oita', 'eita', 'eta', 'this', 'এইটাই', 'এটাই'}
        _BUY_ORDER_WORDS = {'order', 'kinbo', 'নেবো', 'নিতে চাই', 'kinte chai', 'order dite',
                            'কিনতে চাই', 'অর্ডার', 'buy', 'purchase'}
        _has_self_ref = any(w in _msg_lower_buy for w in _BUY_SELF_REF)
        _has_buy_word = any(w in _msg_lower_buy for w in _BUY_ORDER_WORDS)
        if _has_self_ref and _has_buy_word and _cached_buy:
            from services.intent_service import normalize_payload as _np_buy
            _buy_ctx = normalize_payload(prev_ctx)
            _buy_ctx['category'] = (_cached_buy[0].get('category') or
                                    prev_ctx.get('cat') or prev_ctx.get('category') or '')
            buy_result = handle_buy(_buy_ctx, user_id, message)
            # If handle_buy returned a "which one?" prompt, remember the original
            # buy phrase so the next turn (e.g. "1") routes to the order flow.
            if buy_result.get('intent') == 'product_clarification':
                set_pending_question(user_id, message)
            _observe_and_save(user_id, profile, message, 'buy', _buy_ctx)
            return _build_response(user_id, buy_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Generic buy/order intent intercept — short messages like
        # "ami order korte chai", "kinte chai", "buy korbo" are purchase-process
        # questions, not new product searches. Groq sometimes mislabels them as
        # product_search and re-shows cached products. Catch them deterministically.
        _BUY_PHRASES = (
            'order korte chai', 'order korbo', 'order dibo', 'order dite chai',
            'order korte chacchi', 'order dite chacchi', 'অর্ডার করতে চাই',
            'অর্ডার করব', 'অর্ডার দিব', 'অর্ডার দিতে চাই',
            'kinte chai', 'kinbo', 'kinte chacchi', 'কিনতে চাই', 'কিনব',
            'buy korbo', 'buy korte chai', 'purchase korbo',
        )
        _msg_stripped = _msg_lower_buy.strip().rstrip('.?!।')
        if any(p in _msg_lower_buy for p in _BUY_PHRASES) and len(_msg_stripped) <= 40:
            _buy_ctx = normalize_payload(prev_ctx)
            if _cached_buy:
                _buy_ctx['category'] = (_cached_buy[0].get('category') or
                                        prev_ctx.get('cat') or prev_ctx.get('category') or '')
            buy_result = handle_buy(_buy_ctx, user_id, message)
            if buy_result.get('intent') == 'product_clarification':
                set_pending_question(user_id, message)
            _observe_and_save(user_id, profile, message, 'buy', _buy_ctx)
            return _build_response(user_id, buy_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # Clarification selection — user picks a numbered product after clarification prompt.
        # Must run BEFORE handle_product_detail_followup, otherwise the followup
        # intercept treats "1" as a stray query about cached products and answers
        # with the wrong handler (spec-fallback instead of routing to the original
        # pending question, e.g. buy → order flow).
        if get_last_intent(user_id) == 'product_clarification':
            pending_q = get_pending_question(user_id)
            selected = handle_clarification_selection(
                user_id, message,
                pending_question=pending_q,
                groq_client=_groq_client,
                groq_model=GROQ_ANSWER_MODEL,
            )
            if selected:
                _observe_and_save(user_id, profile, message, selected.get('intent', ''), {})
                return _build_response(user_id, selected, ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)
            # User typed a product name instead of a number — do a fresh search
            # for that product, then answer the pending condition/spec question.
            if pending_q:
                from services.api_client_service import search_products as _sp
                from repositories.state_repository import set_product_context as _spc
                from services.intent_handlers_service import _handle_condition_question, handle_product_spec_query
                _CONDITION_Q2 = {
                    'used', 'new', 'notun', 'purano', 'second hand', 'refurbished',
                    'condition', 'কন্ডিশন', 'fresh',
                    'intake', 'original intake', 'non intake', 'ইনটেক', 'নন ইনটেক',
                }
                pq_lower = pending_q.lower()
                has_condition_q = any(w in pq_lower for w in _CONDITION_Q2)
                has_spec_q = any(w in pq_lower for w in ('ram', 'gb', 'processor', 'display', 'battery', 'camera', 'storage', 'spec'))
                if has_condition_q or has_spec_q:
                    fresh = _sp(message)
                    if fresh['products_found'] > 0:
                        _spc(user_id, fresh['products'][:5])
                        # Now re-route to condition or spec handler with new cache
                        if has_condition_q:
                            from services.intent_handlers_service import _handle_condition_question
                            cond = _handle_condition_question(user_id, pending_q)
                            if cond:
                                _observe_and_save(user_id, profile, message, cond.get('intent', ''), {})
                                return _build_response(user_id, cond, ChatMode.AI, AI_ACTIVE_STATUS,
                                                       (datetime.now() - start_time).total_seconds(),
                                                       user_message=message, profile=profile)
                        if has_spec_q:
                            from repositories.state_repository import get_product_context as _gpc2
                            _fresh_prods = _gpc2(user_id)
                            _spec_ctx = {'category': '', 'brand': '', 'title': (_fresh_prods[0].get('title', '') if _fresh_prods else '')}
                            spec_r = handle_product_spec_query(_spec_ctx, user_id, pending_q, _groq_client, GROQ_ANSWER_MODEL)
                            _observe_and_save(user_id, profile, message, spec_r.get('intent', ''), {})
                            return _build_response(user_id, spec_r, ChatMode.AI, AI_ACTIVE_STATUS,
                                                   (datetime.now() - start_time).total_seconds(),
                                                   user_message=message, profile=profile)

        # Product detail follow-up.
        # Fire when either: (a) a specific product URL was pinned via set_product_url,
        # or (b) products from a search result are cached — use the first result's URL.
        # Runs AFTER the clarification-selection check so a numbered reply ("1")
        # routes through the correct pending-question handler (e.g. buy → order
        # flow) instead of being misread as a stray product question.
        from repositories.state_repository import get_product_context as _gpc_early
        _cached_products_early = _gpc_early(user_id)
        if _cached_products_early and _is_storage_drive_search(message):
            clear_product_state(user_id)
            set_session_category(user_id, '')
            # Extract any budget stated in the message (e.g. "5000 taka te ssd")
            # so price filtering isn't silently lost when Groq is bypassed here.
            _sds_price_m = re.search(
                r'(\d[\d,]*)\s*(?:taka|tk|টাকা|bdt)\b', message, re.IGNORECASE)
            _sds_price_max = (
                int(_sds_price_m.group(1).replace(',', '')) if _sds_price_m else None
            )
            storage_result = handle_product_search(
                {'category': '', 'brand': '', 'title': '',
                 'price_max': _sds_price_max, 'price_min': None},
                user_id,
                message,
            )
            _observe_and_save(user_id, profile, message,
                              storage_result.get('intent', 'product_search'),
                              {})
            return _build_response(user_id, storage_result, ChatMode.AI, AI_ACTIVE_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)
        product_url = (get_product_url(user_id)
                       or prev_ctx.get('product_url', '')
                       or (_cached_products_early[0].get('url', '')
                           if _cached_products_early else ''))
        if product_url:
            detail = handle_product_detail_followup(prev_ctx, user_id, message, product_url,
                                                     _groq_client, GROQ_ANSWER_MODEL)
            if detail:
                # When the followup handler asks the user to pick a product by number,
                # save the original message so the selection turn can answer WHAT was asked.
                # Don't save bare self-reference words ("aita", "eta", "oita") as the
                # pending question — they carry no intent and cause spec-fallback failures.
                if detail.get('intent') == 'product_clarification':
                    _msg_self = message.strip().lower().rstrip('.?!।')
                    if _msg_self not in _BARE_SELF_REF:
                        set_pending_question(user_id, message)
                    else:
                        set_pending_question(user_id, '')
                _observe_and_save(user_id, profile, message, detail.get('intent', ''), prev_ctx)
                return _build_response(user_id, detail, ChatMode.AI, AI_ACTIVE_STATUS,
                                       (datetime.now() - start_time).total_seconds(),
                                       user_message=message, profile=profile)

        # ── STEP 2: detect_intent ────────────────────────────────────────────
        history     = fetch_history(user_id)
        cat_names   = [c['category_name'] for c in _categories]
        # Strip trailing price-inquiry words before Groq to prevent it from
        # reading "price?" (or nearby spec numbers like "6" GB) as a budget.
        _groq_msg = _PRICE_INQUIRY_SUFFIX_RE.sub('', message).strip() or message
        _groq_msg = _BN_DEMONSTRATIVE_RE.sub('', _groq_msg).strip() or _groq_msg
        _groq_msg = _CORRECTION_PREAMBLE_RE.sub('', _groq_msg).strip() or _groq_msg
        groq_result = detect_intent(_groq_msg, history, prev_ctx,
                                    cat_names, _groq_client, GROQ_MODEL,
                                    user_profile_block=profile.to_prompt_block())

        # Apply deterministic post-Groq corrections (budget refinement,
        # over/under signals, search/comparison/buy overrides).
        # Must run BEFORE the category scan so _is_pure_budget_msg is known.
        override_result = apply_post_groq_overrides(groq_result, message, dict(prev_ctx))
        groq_result = override_result['groq_result']
        prev_ctx = override_result['prev_ctx']
        _is_pure_budget_msg = override_result['is_pure_budget_msg']

        # Resolve extracted category against canonical list.
        # Skip the message-scan fallback for pure budget messages — words like
        # "modde" (meaning "within") would otherwise fuzzy-match modem/WiFi categories.
        raw_cat = groq_result['entities'].get('category', '')
        if raw_cat:
            resolved = resolve_category(raw_cat, _categories)
            groq_result['entities']['category'] = resolved
        elif not _is_pure_budget_msg:
            # Groq missed category — scan message directly
            scanned = resolve_category_from_message(message, _categories)
            if scanned:
                groq_result['entities']['category'] = scanned
                # Promote unknown → product_search when we found a category
                if groq_result['intent'] == 'unknown':
                    groq_result['intent'] = 'product_search'

        # Clear filler titles BEFORE merge so they never overwrite a real prev title.
        _FILLER_WORDS = {
            'khujtasi', 'khujchi', 'lagbe', 'chai', 'ase', 'nibo', 'dekhan',
            'dekhao', 'bolun', 'jani', 'bolen', 'please', 'kindly',
            'apnader', 'apnar', 'amader', 'amra', 'ami', 'apni',
        }
        _raw_title = (groq_result['entities'].get('title') or '').lower().strip()
        if _raw_title:
            _title_words = set(_raw_title.split())
            if _title_words and _title_words.issubset(_FILLER_WORDS):
                groq_result['entities']['title'] = ''

        logger.info("Intent=%s entities=%s followup=%s confidence=%.2f",
                    groq_result['intent'], groq_result['entities'],
                    groq_result['is_followup'], groq_result.get('confidence', 0.0))

        # Strict policy: if Groq cannot classify (intent='unknown') or returns
        # very low confidence with no usable entities, hand the conversation off
        # to a human agent instead of guessing.
        _conf = float(groq_result.get('confidence') or 0.0)
        _has_entity = any(groq_result['entities'].get(k) for k in
                          ('category', 'brand', 'title', 'price_max', 'price_min'))
        if (groq_result['intent'] == 'unknown'
                or (_conf < 0.55 and not _has_entity
                    and not groq_result.get('is_followup'))):
            logger.info("Strict handoff — intent=%s conf=%.2f entities=%s",
                        groq_result['intent'], _conf, groq_result['entities'])
            try:
                assign_agent(user_id, 'unknown_intent')
            except Exception as e:
                logger.warning("assign_agent on unknown intent failed: %s", e)
            ic = normalize_payload(prev_ctx)
            handler_result = {
                'response': ("স্যার, আপনার মেসেজটি আমি ঠিকমতো বুঝতে পারিনি। "
                             "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"),
                'intent': 'unknown_handoff',
                'intent_content': ic,
                'products': [],
            }
            _observe_and_save(user_id, profile, message, 'unknown_handoff', {})
            return _build_response(user_id, handler_result,
                                   ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)

        # ── STEP 3: merge_context ────────────────────────────────────────────
        def _clear():
            clear_product_state(user_id)

        # Greeting is an explicit session reset. Clear category from prev_ctx NOW
        # so merge_context and the inheritance block below can't pull the old
        # category back from the DB snapshot on this turn.
        if groq_result['intent'] == 'greeting':
            prev_ctx['category'] = ''
            prev_ctx['cat'] = ''
            prev_ctx['prev_cat'] = ''

        # Category switch: when the user explicitly names a different category,
        # clear ALL stale state BEFORE merge_context so the old category can't
        # bleed in through prev_ctx inheritance.
        _fresh_cat = groq_result['entities'].get('category', '')
        if _fresh_cat and _fresh_cat != get_session_category(user_id):
            clear_product_state(user_id)
            invalidate_user_cache(user_id)
            set_session_category(user_id, _fresh_cat)
            # Wipe the old category from prev_ctx so merge can't inherit it
            for _k in ('category', 'cat', 'prev_cat'):
                prev_ctx[_k] = ''

        # Intent change: when the current intent differs from the last bot turn,
        # treat the previous conversation context as not applicable. Drop cached
        # products so a new intent never gets answered using stale product state.
        # Skipped for follow-ups (is_followup=true) — those depend on context.
        _prev_intent = get_last_intent(user_id)
        _cur_intent  = groq_result['intent']
        _NON_RESET_INTENTS = {
            'greeting', 'goodbye', 'thanks', 'exit',
            'product_clarification',  # mid-flow selection
        }
        if (_prev_intent and _cur_intent
                and _prev_intent != _cur_intent
                and _cur_intent not in _NON_RESET_INTENTS
                and not groq_result.get('is_followup')):
            logger.info("intent change %s -> %s — clearing product context",
                        _prev_intent, _cur_intent)
            clear_product_state(user_id)

        merged = merge_context(groq_result, prev_ctx, groq_result['intent'], _clear)

        # Inherit category for non-product intents when still empty.
        # Greeting resets the session, so never re-inherit on the turn after a greeting.
        # FAQ doesn't benefit from an inherited category — it just pollutes intent_content.
        _INHERIT_INTENTS = {
            'comparison', 'technical_advice', 'price_query',
            'unknown', 'seller_query', 'product_search',
        }
        if not merged.get('category') and groq_result['intent'] in _INHERIT_INTENTS:
            # Session memory is more reliable than DB (DB may have stale category)
            inherited = (get_session_category(user_id)
                         or prev_ctx.get('category') or prev_ctx.get('cat', ''))
            if inherited:
                merged['category'] = inherited

        # Promote unknown → product_search when category is now known
        if groq_result['intent'] == 'unknown' and merged.get('category'):
            groq_result['intent'] = 'product_search'

        # Save known category to session memory whenever we have one
        if merged.get('category'):
            set_session_category(user_id, merged['category'])

        # Pure budget refinement: clear any stale title the merge may have inherited.
        if _is_pure_budget_msg:
            stale = merged.get('title') or merged.get('prev_title')
            if stale:
                logger.info("Pure budget refinement — clearing stale merged title %r", stale)
            merged['title'] = ''
            merged['prev_title'] = ''

        # Budget follow-up: inherit prev category and force fresh product_search
        has_budget = (merged.get('price_max') is not None or merged.get('price_min') is not None)
        if has_budget and not merged.get('category'):
            # Session memory first (most reliable), then DB context
            prev_cat = (get_session_category(user_id)
                        or prev_ctx.get('category') or prev_ctx.get('cat', ''))
            if not prev_cat:
                from repositories.state_repository import get_product_context
                cached_products = get_product_context(user_id)
                if cached_products:
                    first_title = (cached_products[0].get('title') or '').lower()
                    for cat_rec in _categories:
                        cname = cat_rec['category_name'].lower()
                        if len(cname) >= 4 and cname in first_title:
                            prev_cat = cat_rec['category_name']
                            break
            if prev_cat:
                merged['category'] = prev_cat
        if has_budget and merged.get('category') and groq_result['intent'] not in ('buy', 'greeting', 'goodbye', 'thanks', 'exit', 'delivery', 'faq', 'complaint', 'human_request', 'seller_query', 'hate_speech'):
            groq_result['intent'] = 'product_search'

        # ── STEP 4: handle_intent ────────────────────────────────────────────
        handler_result = _dispatch(groq_result['intent'], merged, user_id, message, prev_ctx)

        # When a handler asks the user to pick a product by number, save the
        # current message as the pending question so the selection turn can
        # answer it correctly (spec / condition / whatever was originally asked).
        if handler_result.get('intent') == 'product_clarification':
            set_pending_question(user_id, message)

        # Update the rolling user profile from this turn's observations.
        # Use groq_result['entities'] (what the user actually said this turn),
        # not merged (which inherits previous-turn values and would corrupt the profile).
        _observe_and_save(user_id, profile, message,
                          handler_result.get('intent', groq_result['intent']),
                          groq_result['entities'])

        # ── STEP 5: build and return (persistence done by caller) ────────────
        # Handoff intents flip the mode to human so the next message bypasses AI.
        _HANDOFF_INTENT_NAMES = {
            'unknown_handoff', 'knowledge_limit_exceeded',
            'seller_query', 'hate_speech', 'explicit_human_request',
            'complaint_handoff',
        }
        _intent_out = handler_result.get('intent', '')
        if _intent_out in _HANDOFF_INTENT_NAMES:
            return _build_response(user_id, handler_result,
                                   ChatMode.HUMAN, HUMAN_SUPPORT_REQUIRED_STATUS,
                                   (datetime.now() - start_time).total_seconds(),
                                   user_message=message, profile=profile)
        return _build_response(user_id, handler_result, ChatMode.AI, AI_ACTIVE_STATUS,
                               (datetime.now() - start_time).total_seconds(),
                               user_message=message, profile=profile)

    except Exception as e:
        logger.error("process_message error: %s", e, exc_info=True)
        return {
            'response': "দুঃখিত স্যার, একটি সমস্যা হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।" + LOOP_BACK,
            'mode': 'ai', 'intent': 'system_error', 'intent_content': {},
            'conversation_status': AI_ACTIVE_STATUS, 'products': [],
            'processing_time': round((datetime.now() - start_time).total_seconds(), 3),
            'error': str(e),
        }


# ── Intent dispatch ───────────────────────────────────────────────────────────

_HANDOFF_MAP = {
    'seller_query':  (
        "স্যার, বিক্রয় সংক্রান্ত বিষয়ে আমাদের একজন প্রতিনিধি আপনাকে সাহায্য করবেন।",
        'seller_query'),
    'hate_speech':   (
        "স্যার, অনুগ্রহ করে ভদ্র ভাষায় কথা বলুন। আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।",
        'hate_speech'),
    'human_request': (
        "স্যার, আমাদের একজন প্রতিনিধি আপনার সাথে যোগাযোগ করবেন।" + LOOP_BACK,
        'explicit_human_request'),
    'complaint':     (
        "স্যার, এই বিষয়ে আমাদের একজন প্রতিনিধি এখনই আপনার সাথে যোগাযোগ করবেন।",
        'complaint_handoff'),
}


def _dispatch(intent: str, ctx: Dict, user_id: str, message: str,
              prev_ctx: Optional[Dict] = None) -> Dict:
    # Downgrade misclassified seller_query: a buyer asking "where is X sold" is
    # a location/marketplace question, not a seller-onboarding request.
    if intent == 'seller_query':
        msg_l = (message or '').lower()
        _BUYER_LOCATION_SIGNALS = (
            'কোথায়', 'kothay', 'kuthay', 'kothai', 'where',
            'কোন জায়গায়', 'kon jaygay', 'kon jayga',
            'koi', 'কই', 'কোই',
        )
        _is_shop_visit = (any(w in msg_l for w in _SHOP_WORDS)
                          and any(v in msg_l for v in _VISIT_SIGNALS))
        if any(s in msg_l for s in _BUYER_LOCATION_SIGNALS) or _is_shop_visit:
            from services.intent_handlers_service import _SHOWROOM_RESPONSE
            ic = normalize_payload(prev_ctx or load_context(user_id))
            return {'response': _SHOWROOM_RESPONSE + LOOP_BACK,
                    'intent': 'faq_showroom', 'intent_content': ic, 'products': []}

    # Return / refund complaint — fetch policy from API, no agent handoff needed
    if intent == 'complaint':
        msg_l = (message or '').lower()
        _RETURN_SIGNALS = (
            'return', 'ফেরত', 'ferot', 'ferat', 'refund',
            'bhanga', 'ভাঙা', 'nosto', 'নষ্ট', 'broken', 'damaged', 'problem',
            'call dore na', 'call dhore na', 'call dhorena', 'seller nai',
            'pathaise', 'পাঠাইছে', 'wrong product', 'wrong item',
        )
        if any(s in msg_l for s in _RETURN_SIGNALS):
            ic = normalize_payload(prev_ctx or load_context(user_id))
            policy_text = fetch_return_policy()
            # Formatted answer only — no Groq summarization. Trim to a clean
            # sentence boundary to fit a Messenger reply.
            if policy_text:
                trimmed = policy_text.strip()
                if len(trimmed) > 600:
                    cut = trimmed[:600].rsplit('।', 1)[0] or trimmed[:600].rsplit(' ', 1)[0]
                    summary = cut + '…'
                else:
                    summary = trimmed
            else:
                summary = "প্রোডাক্ট রিটার্ন বা সমস্যার ক্ষেত্রে আমাদের রিটার্ন পলিসি অনুযায়ী পদক্ষেপ নিন।"
            reply = "স্যার, অসুবিধার জন্য আন্তরিকভাবে দুঃখিত। 😔\n\n" + summary
            return {
                'response':       reply + LOOP_BACK,
                'intent':         'complaint_return',
                'intent_content': ic,
                'products':       [],
                'link_buttons':   [],
            }

    if intent in _HANDOFF_MAP:
        text, handoff_intent = _HANDOFF_MAP[intent]
        assign_agent(user_id, handoff_intent)
        ic = normalize_payload(prev_ctx or load_context(user_id))
        return {'response': text, 'intent': handoff_intent,
                'intent_content': ic, 'products': []}

    if intent == 'greeting':
        return handle_greeting(ctx, user_id, message)
    if intent == 'goodbye':
        return handle_goodbye(ctx, user_id, message)
    if intent == 'thanks':
        return handle_thanks(ctx, user_id, message)
    if intent == 'exit':
        return handle_exit(ctx, user_id, message)
    if intent in ('buy', 'ordering'):
        return handle_buy(ctx, user_id, message)
    if intent == 'comparison':
        return handle_comparison(ctx, user_id, message)
    if intent == 'delivery':
        return handle_delivery(ctx, user_id, message, fetch_faq_db())
    if intent == 'faq':
        return handle_faq(ctx, user_id, message, fetch_faq_db())
    if intent == 'product_spec_query':
        return handle_product_spec_query(ctx, user_id, message,
                                         _groq_client, GROQ_ANSWER_MODEL)
    if intent == 'technical_advice':
        return handle_technical_advice(ctx, user_id, message,
                                       _categories, _groq_client, GROQ_ANSWER_MODEL)
    if intent == 'price_query':
        return handle_price_query(ctx, user_id, message)
    if intent == 'product_search':
        # Re-route to comparison when: products are already cached AND the message
        # contains an explicit "which one is better" phrase. This catches follow-up
        # comparison questions that Groq labels product_search (e.g. "samsung dekhao
        # konti valo?") without affecting fresh first-time searches.
        from repositories.state_repository import get_product_context as _gpc
        _EXPLICIT_CMP = {
            'konti valo', 'konta valo', 'konti bhalo', 'konta bhalo',
            'কোনটা ভালো', 'কোনটি ভালো', 'valo hobe', 'bhalo hobe',
            'ভালো হবে', 'which one is better', 'which is better',
        }
        msg_l = (message or '').lower()
        if _gpc(user_id) and any(w in msg_l for w in _EXPLICIT_CMP):
            return handle_comparison(ctx, user_id, message)
        return handle_product_search(ctx, user_id, message)

    # Strict policy: no recognised intent → hand the conversation to a human.
    logger.info("Unrecognised intent %r — handing off to human agent", intent)
    try:
        assign_agent(user_id, 'unknown_intent')
    except Exception as e:
        logger.warning("assign_agent on unknown intent failed: %s", e)
    ic = normalize_payload(prev_ctx or load_context(user_id))
    return {
        'response': ("স্যার, আপনার মেসেজটি আমি ঠিকমতো বুঝতে পারিনি। "
                     "আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"),
        'intent': 'unknown_handoff',
        'intent_content': ic,
        'products': [],
    }


# ── Convenience wrappers (used by app_simple.py / controllers) ────────────────

def get_user_mode(user_id: str) -> str:
    return 'human' if check_responder_type(user_id) == 'agent' else 'ai'


def switch_to_human(user_id: str) -> None:
    assign_agent(user_id, 'manual_switch')


def switch_to_ai(user_id: str) -> None:
    assign_bot(user_id)


# ── Compatibility shim ────────────────────────────────────────────────────────

class SimpleChatbot:
    """Thin wrapper around module-level functions for legacy callers."""

    def __init__(self):
        from models.chatbot_config import SEARCH_URL
        self.api_url = SEARCH_URL
        self.groq_client = _groq_client

    @property
    def database(self):
        return _faq_db

    def process_message(self, user_id: str, message: str) -> dict:
        return process_message(user_id, message)

    def get_user_mode(self, user_id: str) -> str:
        return get_user_mode(user_id)

    def switch_to_human(self, user_id: str) -> None:
        switch_to_human(user_id)

    def switch_to_ai(self, user_id: str) -> None:
        switch_to_ai(user_id)
