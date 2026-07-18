from typing import Dict, Any, List, Tuple, Optional
import re
from urllib.parse import quote


def extract_keywords_from_bdstall_url(url: str) -> str:
    try:
        match = re.search(r'/details/([^/?#]+)', url)
        if not match:
            return ''
        slug = match.group(1).strip('/')
        slug = re.sub(r'-\d+$', '', slug)
        words = slug.replace('-', ' ').split()
        stop_words = {
            'core', 'intel', 'amd', 'gen', 'th', 'gb', 'tb', 'ssd',
            'hdd', 'ram', 'display', 'inch', 'fhd', 'hd', 'uhd',
            'touch', 'screen', 'series', 'laptop', 'desktop', 'pc',
            'windows', 'wifi', 'bluetooth', 'usb', 'with', 'and', 'the'
        }
        filtered = []
        for w in words:
            if w.lower() in stop_words:
                break
            filtered.append(w)
        return ' '.join(filtered[:4])
    except Exception:
        return ''


def extract_budget_range(message: str) -> Dict[str, Optional[int]]:
    text = str(message or '').strip().lower()
    if not text:
        return {'min_price': None, 'max_price': None, 'price_text': ''}
    text = text.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

    def _to_taka(v, u):
        val = int(float(v))
        un = (u or '').strip().lower()
        if un in {'k', 'হাজার', 'hazar', 'thousand'}:
            return val * 1000
        if un in {'tk', 'taka', 'টাকা'}:
            return val
        if val < 1000:
            return val * 1000
        return val

    rm = re.search(
        r'(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?\s*(?:-|to|থেকে)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?',
        text)
    if rm:
        mn = _to_taka(rm.group(1), rm.group(2) or rm.group(4) or '')
        mx = _to_taka(rm.group(3), rm.group(4) or rm.group(2) or '')
        if mn > mx:
            mn, mx = mx, mn
        return {'min_price': mn, 'max_price': mx, 'price_text': f"{mn}-{mx}"}

    um = re.search(
        r'(?:under|within|modde|modhhe|budget|er modde|er vitor|vitor|এর মধ্যে|মধ্যে|below|less than)\s*(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)?',
        text)
    if um:
        mx = _to_taka(um.group(1), um.group(2) or '')
        return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

    gm = re.search(r'\b(\d+(?:\.\d+)?)\s*(k|tk|taka|হাজার|টাকা|hazar)\b', text)
    if gm:
        mx = _to_taka(gm.group(1), gm.group(2) or '')
        return {'min_price': None, 'max_price': mx, 'price_text': f"under {mx}"}

    return {'min_price': None, 'max_price': None, 'price_text': ''}


def format_product_listing(products: List[Dict]) -> Tuple[str, List[Dict]]:
    text = "স্যার, এই প্রোডাক্টগুলো দেখতে পারেন:\n\nআরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।"
    link_buttons = []
    for i, p in enumerate(products[:3], 1):
        title = p.get('title', 'N/A')
        price = p.get('price', 'N/A')
        url = p.get('url', '')
        if url:
            link_buttons.append({
                'text': f"{i}. View",
                'url': url,
                'title': title,
                'price': price,
            })
    return text, link_buttons


def format_selected_product_response(product: Dict, index: int) -> str:
    title = product.get('title', 'N/A')
    price = product.get('price', 'N/A')
    url = product.get('url', '')
    text = f"দারুণ পছন্দ স্যার। আপনি {index} নম্বর প্রোডাক্টটি নির্বাচন করেছেন।\n\n"
    text += f"{index}. {title}\nমূল্য: {price}\n"
    if url:
        text += f"লিংক: {url}\n"
    text += "\nআপনি চাইলে আমি অর্ডার করার ধাপগুলোও বলে দিতে পারি।"
    return text


def build_comparison_link_buttons(merged: Dict) -> List[Dict]:
    category = merged.get('category', '')
    target = 'https://www.bdstall.com/'
    if category:
        slug = re.sub(r'\s+', '-', category.strip().lower())
        slug = re.sub(r'[^a-z0-9\-]', '', slug).strip('-')
        if slug:
            target = f"https://www.bdstall.com/{quote(slug, safe='-')}/"
    return [{'text': 'View', 'url': target}]


def parse_template_response(data: Any) -> Optional[str]:
    if isinstance(data, str):
        return data.strip() or None
    if isinstance(data, dict):
        if data.get('success') is False:
            return None
        for k in ['response', 'message', 'template', 'text', 'content', 'data']:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        if len(data) == 1:
            v = next(iter(data.values()))
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def build_missing_order_fields_prompt(missing: List[str]) -> str:
    labels = {
        'name': 'Name', 'phone_number': 'Phone Number',
        'address': 'Address', 'product_name': 'Product Name',
        'quantity': 'Quantity'
    }
    lines = "\n".join(f"{labels[k]}:" for k in missing if k in labels)
    return f"অর্ডার সম্পন্ন করতে শুধু বাকি তথ্যগুলো দিন:\n\n{lines}\n\nধন্যবাদ।"


def normalize_history_messages(payload: Any) -> List[str]:
    candidates = []
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for k in ['data', 'messages', 'history', 'chat_history', 'conversation', 'result']:
            v = payload.get(k)
            if isinstance(v, list):
                candidates = v; break
        if not candidates and isinstance(payload.get('data'), dict):
            nested = payload.get('data') or {}
            for k in ['messages', 'history', 'chat_history', 'conversation', 'items']:
                v = nested.get(k)
                if isinstance(v, list):
                    candidates = v; break
    lines = []
    for item in candidates:
        if isinstance(item, str):
            t = item.strip()
            if t: lines.append(f"User: {t}")
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get('message') or item.get('text') or
                   item.get('content') or item.get('body') or '').strip()
        if not text:
            continue
        sender = str(item.get('sender_type') or '').strip()
        role = str(item.get('role') or '').strip().lower()
        if sender == '2' or role in {'assistant', 'bot', 'ai'}:
            lines.append(f"Bot: {text}")
        elif sender == '1' or role in {'agent', 'human'}:
            lines.append(f"Agent: {text}")
        else:
            lines.append(f"User: {text}")
    return lines[-10:]


def extract_order_detail_fields(message: str) -> Dict[str, str]:
    text = str(message or '').strip()
    if not text:
        return {}
    label_to_key = [
        (r'product\s*name', 'product_name'),
        (r'phone\s*number', 'phone_number'),
        (r'quantity', 'quantity'),
        (r'address', 'address'),
        (r'mobile', 'phone_number'),
        (r'phone', 'phone_number'),
        (r'qty', 'quantity'),
        (r'পণ্যের\s*নাম', 'product_name'),
        (r'প্রোডাক্ট', 'product_name'),
        (r'ঠিকানা', 'address'),
        (r'নাম্বার', 'phone_number'),
        (r'নম্বর', 'phone_number'),
        (r'পরিমাণ', 'quantity'),
        (r'name', 'name'),
    ]
    regex = "|".join(lbl for lbl, _ in label_to_key)
    pat = re.compile(rf'(?i)(?P<label>{regex})\s*[:;=\-]\s*', re.DOTALL)
    matches = list(pat.finditer(text))
    if not matches:
        return {}
    out = {}
    for i, m in enumerate(matches):
        lbl = m.group('label').strip().lower()
        s = m.end()
        e = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        val = re.sub(r'\s+', ' ', text[s:e]).strip()
        if not val:
            continue
        key = None
        for lr, k in label_to_key:
            if re.fullmatch(lr, lbl, flags=re.IGNORECASE):
                key = k; break
        if key and key not in out:
            out[key] = val
    return out


def reply_price_from_context(
    selected: Optional[Dict], products: Optional[List]
) -> Optional[Tuple[str, List[Dict]]]:
    if selected:
        title = selected.get('title') or 'এই প্রোডাক্টটির'
        price = selected.get('price') or ''
        url = selected.get('url', '')
        if price and str(price).strip().upper() != 'N/A':
            text = f"জি স্যার, {title} এর দাম {price}।"
            buttons = [{'text': 'View', 'url': url, 'title': title, 'price': price}] if url else []
            return text, buttons
        return "স্যার, এই প্রোডাক্টটির দাম এখন দেখাতে পারছি না।", []

    if not products:
        return None
    if len(products) == 1:
        p = products[0]
        title = p.get('title') or 'এই প্রোডাক্টটির'
        price = p.get('price') or ''
        url = p.get('url', '')
        if price and str(price).strip().upper() != 'N/A':
            text = f"জি স্যার, {title} এর দাম {price}।"
            buttons = [{'text': 'View', 'url': url, 'title': title, 'price': price}] if url else []
            return text, buttons

    lines = ["স্যার, আপনার দেখা প্রোডাক্টগুলোর দাম:"]
    buttons = []
    for i, p in enumerate(products[:5], 1):
        t = str(p.get('title') or f'প্রোডাক্ট {i}').strip()
        pr = str(p.get('price') or 'N/A').strip()
        url = p.get('url', '')
        if not pr or pr.upper() == 'N/A':
            pr = 'দাম পাওয়া যায়নি'
        lines.append(f"{i}. {t} - {pr}")
        if url:
            buttons.append({'text': f"{i}. View", 'url': url, 'title': t, 'price': pr})
    lines.append("যেটা নিতে চান, নম্বর বলুন স্যার।")
    return "\n".join(lines), buttons


def extract_product_selection(message: str) -> Optional[int]:
    n = str(message or '').strip()
    if not n:
        return None
    if extract_order_detail_fields(n):
        return None
    n = n.translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))
    nl = n.lower()
    dm = re.fullmatch(r'\s*([1-5])\s*', nl)
    if dm:
        return int(dm.group(1))
    nums = re.findall(r'\b([1-5])\b', nl)
    if len(nums) != 1:
        return None
    cues_latin = ['number', 'no', 'option', 'choose', 'select', 'pick']
    cues_bn = ['নম্বর', 'নাম্বার', 'পছন্দ', 'নিবো', 'নেবো']
    has_cue = (
        any(re.search(r'\b' + re.escape(c) + r'\b', nl) for c in cues_latin)
        or any(c in nl for c in cues_bn)
    )
    if len(nl.split()) <= 3 or has_cue:
        return int(nums[0])
    return None
