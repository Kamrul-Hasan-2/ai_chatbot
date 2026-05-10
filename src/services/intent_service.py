"""
src/services/intent_service.py — intent detection, context merge, normalisation.

Public functions:
  detect_intent(message, history, prev_ctx, category_names, groq_client, model)
  merge_context(groq_result, prev_ctx, intent, clear_fn)
  normalize_payload(ctx)
  intent_to_normalized(merged)
  resolve_category(text, categories)
  resolve_category_from_message(message, categories)
  get_technical_advice(message, groq_client, model)
  extract_budget_range(message)
"""
import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from models.chatbot_config import VALID_INTENTS, GROQ_SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


# ── Budget extraction ─────────────────────────────────────────────────────────

def extract_budget_range(message: str) -> Dict[str, Optional[int]]:
    text = str(message or '').strip().lower()
    text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

    def _to_taka(v, u):
        val = int(float(v))
        un = (u or '').strip().lower()
        if un in {'k', 'হাজার', 'hazar', 'thousand'}:
            return val * 1000
        if un in {'tk', 'taka', 'টাকা'}:
            return val
        return val * 1000 if val < 1000 else val

    rm = re.search(
        r'(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?\s*(?:-|to|থেকে)\s*'
        r'(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?', text)
    if rm:
        mn = _to_taka(rm.group(1), rm.group(2) or rm.group(4) or '')
        mx = _to_taka(rm.group(3), rm.group(4) or rm.group(2) or '')
        if mn > mx:
            mn, mx = mx, mn
        return {'min_price': mn, 'max_price': mx}

    um = re.search(
        r'(?:under|within|modde|budget|er modde|er vitor|vitor|এর মধ্যে|মধ্যে|below|less than)'
        r'\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?', text)
    if um:
        return {'min_price': None, 'max_price': _to_taka(um.group(1), um.group(2) or '')}

    gm = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)\b', text)
    if gm:
        return {'min_price': None, 'max_price': _to_taka(gm.group(1), gm.group(2) or '')}

    return {'min_price': None, 'max_price': None}


# ── Category resolution ───────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    return re.findall(r'[a-z0-9]+', text.lower())


def resolve_category(text: str, categories: List[Dict]) -> str:
    """Resolve a single word/phrase to a canonical category name."""
    if not text or not categories:
        return ''
    tl = text.strip().lower()
    by_name = {c['category_name'].lower(): c for c in categories}
    by_bn   = {c['bn_category_name'].lower(): c for c in categories if c.get('bn_category_name')}

    if tl in by_name:
        return by_name[tl]['category_name']
    if tl in by_bn:
        return by_bn[tl]['category_name']
    for bn, rec in by_bn.items():
        if bn and bn in tl:
            return rec['category_name']

    input_tokens = set(_tokenize(tl))
    if input_tokens:
        best, best_score = None, 0
        for rec in categories:
            cat_tokens = set(_tokenize(rec['category_name']))
            overlap = input_tokens & cat_tokens
            if not overlap:
                continue
            if len(cat_tokens) > 1 and not cat_tokens.issubset(input_tokens):
                if rec['category_name'].lower() not in tl:
                    continue
            score = len(overlap) * 100 + len(rec['category_name'])
            if score > best_score:
                best_score, best = score, rec
        if best:
            return best['category_name']

    if len(tl) <= 30:
        best_ratio, best_rec = 0.0, None
        for cname_lower, rec in by_name.items():
            for cand in [cname_lower] + _tokenize(cname_lower):
                if len(cand) < 3:
                    continue
                ratio = SequenceMatcher(None, tl, cand).ratio()
                if ratio > best_ratio:
                    best_ratio, best_rec = ratio, rec
        if best_rec and best_ratio >= 0.82:
            return best_rec['category_name']
    return ''


def resolve_category_from_message(message: str, categories: List[Dict]) -> str:
    """Scan a full message for any known category name."""
    if not message or not categories:
        return ''
    tl = message.lower()
    by_name = {c['category_name'].lower(): c for c in categories}
    by_bn   = {(c['bn_category_name'] or ''): c for c in categories if c.get('bn_category_name')}

    for bn_name, rec in by_bn.items():
        if bn_name and bn_name in message:
            return rec['category_name']

    best, best_len = '', 0
    for cname_lower, rec in by_name.items():
        if not cname_lower:
            continue
        if len(cname_lower) <= 4:
            if not re.search(rf'\b{re.escape(cname_lower)}\b', tl):
                continue
        else:
            if cname_lower not in tl:
                continue
        if len(cname_lower) > best_len:
            best_len = len(cname_lower)
            best = rec['category_name']
    if best:
        return best

    for tok in set(_tokenize(tl)):
        if len(tok) < 3:
            continue
        for rec in categories:
            if tok in _tokenize(rec['category_name']):
                return rec['category_name']
    return ''


# ── Groq intent extraction ────────────────────────────────────────────────────

def detect_intent(message: str, history: str, prev_ctx: Dict,
                  category_names: List[str], groq_client, groq_model: str) -> Dict[str, Any]:
    if not groq_client:
        return _fallback_intent(message)

    sample_str = ", ".join(category_names[:30]) or "(none)"
    system_prompt = GROQ_SYSTEM_PROMPT_TEMPLATE.format(
        sample_str=sample_str,
        previous_intent=json.dumps(prev_ctx or {}, ensure_ascii=False),
    )
    user_prompt = (
        f"Recent conversation:\n{history or 'N/A'}\n\n"
        f"Current user message:\n{message}\n\nReturn ONLY the JSON object."
    )
    try:
        resp = groq_client.chat.completions.create(
            model=groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        return _validate_groq(json.loads(raw))
    except json.JSONDecodeError as e:
        logger.warning("Groq JSON parse error: %s", e)
        return _fallback_intent(message)
    except Exception as e:
        logger.warning("Groq call failed: %s", e)
        return _fallback_intent(message)


def _validate_groq(parsed: Dict) -> Dict[str, Any]:
    intent = str(parsed.get('intent', 'unknown')).lower().strip()
    if intent not in VALID_INTENTS:
        intent = 'unknown'
    entities = parsed.get('entities') or {}

    def _price(v):
        if v is None or v == '':
            return None
        try:
            n = int(float(v))
            return n if 0 < n < 100_000_000 else None
        except (ValueError, TypeError):
            return None

    return {
        'intent':      intent,
        'entities': {
            'category':  str(entities.get('category') or '').strip(),
            'brand':     str(entities.get('brand') or '').strip().lower(),
            'title':     str(entities.get('title') or '').strip(),
            'price_max': _price(entities.get('price_max')),
            'price_min': _price(entities.get('price_min')),
        },
        'missing':     [str(m) for m in (parsed.get('missing') or []) if isinstance(m, str)],
        'is_followup': bool(parsed.get('is_followup', False)),
        'confidence':  max(0.0, min(1.0, float(parsed.get('confidence', 0.5)))),
    }


def _fallback_intent(message: str) -> Dict[str, Any]:
    budget = extract_budget_range(message)
    msg = message.lower().strip()

    _GREETING_WORDS = {
        'hi', 'hello', 'hey', 'hlw', 'hlo', 'helo', 'salam', 'salaam',
        'assalamu', 'assalamualaikum', 'walaikum', 'হাই', 'হ্যালো', 'সালাম',
        'হেলো', 'আসসালামু', 'ওয়ালাইকুম',
    }
    _GOODBYE_WORDS = {
        'bye', 'goodbye', 'good bye', 'alvida', 'বিদায়', 'আল্লাহ হাফেজ',
    }
    _THANKS_WORDS = {
        'thanks', 'thank you', 'thankyou', 'thx', 'tnx', 'ধন্যবাদ', 'শুকরিয়া',
    }
    _DELIVERY_WORDS = {
        'delivery', 'deliver', 'charge', 'shipping', 'courier',
        'ডেলিভারি', 'চার্জ', 'শিপিং',
    }
    _BUY_WORDS = {
        'buy', 'order', 'কিনতে', 'অর্ডার', 'purchase', 'কিনব',
    }
    _SEARCH_WORDS = {
        'ase', 'আছে', 'dekhan', 'দেখান', 'lagbe', 'লাগবে',
        'chai', 'চাই', 'show', 'find', 'search', 'khujchi',
        'খুঁজছি', 'dekhao', 'দেখাও', 'নিব', 'nibo',
    }

    intent = 'unknown'
    if any(w in msg for w in _GREETING_WORDS):
        intent = 'greeting'
    elif any(w in msg for w in _GOODBYE_WORDS):
        intent = 'goodbye'
    elif any(w in msg for w in _THANKS_WORDS):
        intent = 'thanks'
    elif any(w in msg for w in _DELIVERY_WORDS):
        intent = 'delivery'
    elif any(w in msg for w in _BUY_WORDS):
        intent = 'buy'
    elif any(w in msg for w in _SEARCH_WORDS):
        intent = 'product_search'

    return {
        'intent': intent,
        'entities': {
            'category': '', 'brand': '', 'title': '',
            'price_max': budget.get('max_price'),
            'price_min': budget.get('min_price'),
        },
        'missing': [],
        'is_followup': False,
        'confidence': 0.3,
    }


# ── Context merge (Rules 6, 7, 10) ────────────────────────────────────────────

def merge_context(groq_result: Dict, prev: Dict, intent: str, clear_fn) -> Dict:
    new_ent      = groq_result['entities']
    new_category = new_ent.get('category', '')
    is_followup  = groq_result.get('is_followup', False)

    prev_category  = prev.get('category', '') or prev.get('cat', '')
    prev_brand     = prev.get('brand', '')
    prev_title     = prev.get('title', '')
    prev_price_max = prev.get('price_max')
    prev_price_min = prev.get('price_min')

    # Rule 6: category switch → full reset
    if new_category and prev_category and new_category.lower() != prev_category.lower():
        logger.info("Category switch %s → %s. Full reset.", prev_category, new_category)
        clear_fn()
        return {
            'category':      new_category,  'prev_cat':      prev_category,
            'brand':         new_ent.get('brand', ''), 'prev_brand': '',
            'title':         new_ent.get('title', ''), 'prev_title': '',
            'price_max':     new_ent.get('price_max'), 'prev_price_max': None,
            'price_min':     new_ent.get('price_min'), 'prev_price_min': None,
            'updated_at':    datetime.now().isoformat(),
        }

    # Refinement-only → treat as follow-up
    if not new_category and (
        new_ent.get('price_max') is not None
        or new_ent.get('price_min') is not None
        or new_ent.get('brand')
        or new_ent.get('title')
    ):
        is_followup = True

    effective_category = new_category or prev_category

    return {
        'category':       effective_category,
        'prev_cat':       prev_category,
        'brand':          new_ent.get('brand') or prev_brand,
        'prev_brand':     prev_brand,
        'title':          new_ent.get('title') or prev_title,
        'prev_title':     prev_title,
        'price_max':      (new_ent['price_max'] if new_ent.get('price_max') is not None else prev_price_max),
        'prev_price_max': prev_price_max,
        'price_min':      (new_ent['price_min'] if new_ent.get('price_min') is not None else prev_price_min),
        'prev_price_min': prev_price_min,
        'updated_at':     datetime.now().isoformat(),
    }


# ── Intent content normalisation (Rule 12) ────────────────────────────────────

def normalize_payload(payload: Optional[Dict] = None) -> Dict[str, Any]:
    default: Dict[str, Any] = {
        'title': '', 'cat': '', 'brand': '',
        'price_max': 0, 'price_min': 0,
        'compare': '', 'buy': '',
    }
    if not isinstance(payload, dict):
        return default
    out = dict(default)
    out['title'] = str(payload.get('title') or '').strip()
    out['cat']   = str(payload.get('cat') or payload.get('category') or '').strip()
    out['brand'] = str(payload.get('brand') or '').strip().lower()
    try:
        out['price_max'] = int(payload.get('price_max') or 0)
    except (ValueError, TypeError):
        out['price_max'] = 0
    try:
        out['price_min'] = int(payload.get('price_min') or 0)
    except (ValueError, TypeError):
        out['price_min'] = 0
    out['compare'] = str(payload.get('compare') or '').strip()
    out['buy']     = str(payload.get('buy') or '').strip()
    if 'exit' in payload:
        try:
            out['exit'] = 1 if int(payload['exit']) else 0
        except Exception:
            out['exit'] = 0
    if payload.get('product_url'):
        out['product_url'] = str(payload['product_url'])
    return out


def intent_to_normalized(merged: Dict) -> Dict[str, Any]:
    """Build a clean intent_content dict from a merged context."""
    def _eff(new_key, prev_key):
        v = str(merged.get(new_key) or '').strip()
        return v or str(merged.get(prev_key) or '').strip()

    cat   = _eff('category', 'prev_cat')
    brand = _eff('brand', 'prev_brand').lower()
    title = _eff('title', 'prev_title')

    pm = merged.get('price_max')
    pn = merged.get('price_min')
    effective_max = pm if pm and pm > 0 else (merged.get('prev_price_max') or 0)
    effective_min = pn if pn and pn > 0 else (merged.get('prev_price_min') or 0)

    return {
        'title':      title,
        'cat':        cat,
        'brand':      brand,
        'price_max':  effective_max,
        'price_min':  effective_min,
        'compare':    '',
        'buy':        '',
        'updated_at': merged.get('updated_at', datetime.now().isoformat()),
    }


# ── Technical advice via Groq ─────────────────────────────────────────────────

def get_technical_advice(message: str, groq_client, model: str) -> Optional[str]:
    if not groq_client or not model:
        return None
    system = (
        "You are BDStall Assistant — the official AI customer support agent for BDStall.com, "
        "Bangladesh's trusted online electronics and gadget marketplace.\n"
        "Answer the user's technical question about product capability, compatibility, upgrade "
        "potential, or performance in 2-3 clear sentences.\n"
        "The user may write in English, Bangla, or Banglish. Always reply in the SAME language the user used.\n"
        "Be direct and helpful. Do NOT add disclaimers, recommend competitor brands, or mention specific prices."
    )
    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
            temperature=0.2,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("get_technical_advice failed: %s", e)
        return None
