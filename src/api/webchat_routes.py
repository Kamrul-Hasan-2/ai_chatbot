"""
src/api/webchat_routes.py — website webchat widget backend.

New module only. Imports the shared, platform-agnostic pipeline from
src/controllers/chat_controller.py but never edits that file — Messenger
logic stays frozen (see CLAUDE.md / docs/WEBCHAT_API.md).
"""
import os
import re
import time
import threading
import logging

from flask import Blueprint, request, jsonify, Response

try:
    from controllers.chat_controller import _process_user_message, save_chat_message, get_known_user_name
except ImportError:
    from src.controllers.chat_controller import _process_user_message, save_chat_message, get_known_user_name

try:
    from services.api_client_service import (
        search_products, fetch_product_spec, fetch_product_details, fetch_category_filters,
    )
    from services.intent_handlers_service import _extract_product_id
    from services.intent_service import resolve_category_from_message
    from repositories.state_repository import (
        set_product_context, set_product_url, set_session_category, get_session_category, load_context,
    )
    from models.chatbot_config import LOOP_BACK, AI_ACTIVE_STATUS
except ImportError:
    from src.services.api_client_service import (
        search_products, fetch_product_spec, fetch_product_details, fetch_category_filters,
    )
    from src.services.intent_handlers_service import _extract_product_id
    from src.services.intent_service import resolve_category_from_message
    from src.repositories.state_repository import (
        set_product_context, set_product_url, set_session_category, get_session_category, load_context,
    )
    from src.models.chatbot_config import LOOP_BACK, AI_ACTIVE_STATUS

try:
    import markdown as _markdown
except ImportError:
    _markdown = None

logger = logging.getLogger(__name__)

webchat_bp = Blueprint('webchat', __name__, url_prefix='/api/webchat')
webchat_docs_bp = Blueprint('webchat_docs', __name__)

_SESSION_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_MESSAGE_MAX_LENGTH = 2000
_PAGE_CONTEXT_FIELD_MAX_LENGTH = 300

# ── Price emphasis (webchat display only) ──────────────────────────────────────
# The response text is rendered as plain text by design (see docs/WEBCHAT_API.md
# §6 — never innerHTML, to stay safe against XSS), so real bold formatting isn't
# available. Unicode "Mathematical Bold" digits look bold in any plain-text
# renderer with no frontend changes needed — only digits can be styled this way
# (the ৳ symbol and commas have no bold Unicode variant, so they stay as-is).
_BOLD_DIGITS = str.maketrans('0123456789', '𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗')
# Matches an optional existing "মূল্য" label and/or leading ": " (the shared
# pipeline uses both "Title: ৳429" and "Title\nমূল্য: ৳429" styles depending
# on the response type) together with the price itself, so whichever style
# was already there gets consumed as ONE match and replaced with exactly one
# clean "মূল্য:" (Price:) label on its own line — never a duplicate.
_PRICE_PATTERN = re.compile(r'(?:মূল্য\s*)?:?\s*৳\s*[\d,]+')
_PRICE_ONLY_PATTERN = re.compile(r'৳\s*[\d,]+')


def _emphasize_prices(text: str) -> str:
    """Put every price on its own 'মূল্য: ৳ N,NNN' line with bold-styled digits."""
    if not text or '৳' not in text:
        return text

    def _replace(m: 're.Match') -> str:
        price_only = _PRICE_ONLY_PATTERN.search(m.group(0)).group(0)
        return '\nমূল্য: ' + price_only.translate(_BOLD_DIGITS)

    return _PRICE_PATTERN.sub(_replace, text)


def _format_bold_taka(amount) -> str:
    """৳ + thousand separators + bold-styled digits, same convention as
    _emphasize_prices (see there for why bold digits rather than markup)."""
    try:
        n = int(float(amount))
    except (TypeError, ValueError):
        return str(amount)
    return f"৳ {n:,}".translate(_BOLD_DIGITS)


# ── Category price-range answers (webchat-only, deterministic) ────────────────
# The shared pipeline (chatbot_service.py) answers PRODUCT-level questions
# (price of *this* item) but has no notion of a whole category's price
# range/brand list — there's nothing to hook into there the way page-context
# grounding hooks into existing product-context state. So this is answered
# directly here instead, mirroring the deterministic-intercept style already
# used throughout this codebase (e.g. greeting/hate-speech signal sets) —
# rather than teaching the shared pipeline a new category-filters concept.
_PRICE_RANGE_SIGNALS = (
    'price range', 'range koto', 'range ki', 'দাম রেঞ্জ', 'দামের রেঞ্জ',
    'কত থেকে কত', 'কতো থেকে কতো', 'সর্বনিম্ন', 'সর্বোচ্চ দাম',
    'min price', 'max price', 'lowest price', 'highest price',
    'সর্বনিম্ন দাম', 'সর্বোচ্চ মূল্য',
)


def _try_price_range_answer(user_id: str, message: str, explicit_category: str, explicit_product: str) -> dict | None:
    """If the message asks about a category's price range and the category is
    known (explicit or previously seeded from page context), answer directly
    from fetch_category_filters(). Returns None to fall through to the normal
    pipeline when the message doesn't match or no category is known/found —
    never blocks the normal flow.
    """
    msg_lower = (message or '').lower()
    if not any(sig in msg_lower for sig in _PRICE_RANGE_SIGNALS):
        return None

    category = (explicit_category or '').strip()
    if not category:
        try:
            category = get_session_category(user_id)
        except Exception:
            category = ''
    if not category:
        return None

    try:
        filters = fetch_category_filters(category)
    except Exception as e:
        logger.warning("[WEBCHAT] fetch_category_filters failed: %s", e)
        filters = None
    if not filters or not (filters.get('price_min') and filters.get('price_max')):
        return None

    display_category = filters.get('category') or category
    response_text = (
        f"স্যার, {display_category} ক্যাটাগরিতে দামের রেঞ্জ:\n\n"
        f"সর্বনিম্ন মূল্য: {_format_bold_taka(filters['price_min'])}\n"
        f"সর্বোচ্চ মূল্য: {_format_bold_taka(filters['price_max'])}"
        + LOOP_BACK
    )

    # The normal pipeline persists intent_content (brand/cat/title/budget)
    # with every bot turn, and load_context() re-reads the MOST RECENT saved
    # intent_content at the start of the next turn to keep e.g. "brand: MSI"
    # alive across follow-up questions. Saving this turn with no intent_content
    # would overwrite that with nothing and silently drop the active brand —
    # so carry the existing context forward, only updating 'cat'. (#brand-drop)
    try:
        prev_ctx = load_context(user_id) or {}
    except Exception as e:
        logger.warning("[WEBCHAT] load_context failed for price-range continuity: %s", e)
        prev_ctx = {}
    intent_content = {
        'cat': display_category,
        'brand': prev_ctx.get('brand') or '',
        'title': prev_ctx.get('title') or '',
        'compare': prev_ctx.get('compare') or '',
        'buy': prev_ctx.get('buy') or '',
        'price_min': prev_ctx.get('price_min') or 0,
        'price_max': prev_ctx.get('price_max') or 0,
    }

    user_name = get_known_user_name(user_id) or f"User {user_id[-6:]}"
    try:
        save_chat_message(user_id=user_id, sender_type=3, message=message, user_name=user_name, platform_id=2)
        save_chat_message(
            user_id=user_id, sender_type=2, message=response_text, user_name=user_name,
            intent_content=intent_content, platform_id=2,
        )
    except Exception as e:
        logger.warning("[WEBCHAT] save_chat_message failed for price-range answer: %s", e)

    # Only attach the "view category" link when a specific product name was
    # also given — a bare price-range question with no product name attached
    # shouldn't get a promotional-feeling link back.
    link_buttons = []
    if (explicit_product or '').strip() and filters.get('url'):
        link_buttons = [{'text': f"{display_category} দেখুন", 'url': filters['url']}]

    return {
        'response': response_text,
        'mode': 'ai',
        'intent': 'category_price_range',
        'intent_content': intent_content,
        'conversation_status': AI_ACTIVE_STATUS,
        'products': [],
        'link_buttons': link_buttons,
        'processing_time': 0.0,
        'user_name': user_name,
        'platform_id': 'web',
    }


def _seed_page_context(user_id: str, product: str, category: str, page_link: str, product_id: str = '') -> None:
    """Ground the shared pipeline's next answer in a specific product the
    webchat visitor is currently looking at, by seeding the same session
    state `handle_product_link` seeds when a Messenger user pastes a product
    URL. The pipeline (src/services/chatbot_service.py) already checks this
    state on every turn and routes product-specific questions (price, spec,
    warranty, stock, ...) through `handle_product_detail_followup` against
    it instead of running a fresh search — this just primes that mechanism
    from page context instead of a pasted link. Webchat-only by construction:
    nothing else calls this.
    """
    product = (product or '').strip()[:_PAGE_CONTEXT_FIELD_MAX_LENGTH]
    category = (category or '').strip()[:_PAGE_CONTEXT_FIELD_MAX_LENGTH]
    page_link = (page_link or '').strip()[:_PAGE_CONTEXT_FIELD_MAX_LENGTH]
    # Listing ids are always numeric (e.g. 24652) — strip anything else so a
    # stray non-digit can't reach fetch_product_spec's URL building.
    product_id = re.sub(r'\D', '', str(product_id or ''))[:32]
    if not product and not page_link and not product_id:
        return

    resolved = None

    # Highest-confidence path: the frontend already knows the exact listing
    # id (it's the product's own primary key on their side) — no URL parsing
    # or title search needed, so try this before anything else.
    listing_id = product_id or (_extract_product_id(page_link) if page_link else None)
    if listing_id:
        # Try the richer chatbot-specific product_details API first (price,
        # discount, brand, category, stock, description). If it doesn't find
        # anything, fall back to the existing fetch_product_spec lookup —
        # unchanged from how this already worked before product_details
        # existed, so nothing regresses if that new API is ever unavailable.
        try:
            details = fetch_product_details(listing_id)
        except Exception as e:
            logger.warning("[WEBCHAT] fetch_product_details failed for page context: %s", e)
            details = None
        if details and details.get('title'):
            resolved = dict(details)
            resolved['url'] = resolved.get('url') or page_link

        if resolved is None:
            try:
                spec = fetch_product_spec(listing_id)
            except Exception as e:
                logger.warning("[WEBCHAT] fetch_product_spec failed for page context: %s", e)
                spec = None
            if spec and spec.get('title'):
                resolved = {
                    'title': spec.get('title') or product,
                    'price': spec.get('price') or '',
                    'url': page_link,
                    'image': '',
                }

    if resolved is None and product:
        try:
            search_result = search_products(product)
        except Exception as e:
            logger.warning("[WEBCHAT] search_products failed for page context: %s", e)
            search_result = {}
        if search_result.get('products_found'):
            top = search_result['products'][0]
            resolved = {
                'title': top.get('title') or product,
                'price': top.get('price', ''),
                'original_price': top.get('original_price', ''),
                'discount': top.get('discount', 0),
                'url': top.get('url') or page_link,
                'image': top.get('image', ''),
            }

    if resolved is None and product:
        # Enrichment failed (no matching listing found) — still ground the
        # answer in exactly what the frontend told us about this page.
        resolved = {'title': product, 'price': '', 'url': page_link, 'image': ''}

    if resolved is None:
        # No product title anywhere and page_link didn't resolve to a real
        # listing (e.g. a Referer-based fallback pointing at a non-product
        # page, like the homepage or search results) — nothing usable to
        # ground on. Don't seed junk state with an empty title.
        return

    set_product_context(user_id, [resolved])
    set_product_url(user_id, resolved.get('url') or page_link)

    if category:
        try:
            from services.chatbot_service import _categories
        except ImportError:
            from src.services.chatbot_service import _categories
        resolved_category = resolve_category_from_message(category, _categories)
        set_session_category(user_id, resolved_category or category)

# ── Per-IP sliding-window rate limit ──────────────────────────────────────────
# There is no rate limiting anywhere else in this app — fine when the only
# inbound channel was Facebook's authenticated webhook, not fine for a script
# embeddable on any public page. In-memory state is safe here because
# config/gunicorn_config.py pins the app to a single worker process.
_RATE_LIMIT_MAX_REQUESTS = 20
_RATE_LIMIT_WINDOW_SECONDS = 60
_request_log: dict = {}
_rate_limit_lock = threading.Lock()


def _is_rate_limited(ip: str) -> bool:
    """Return True and record the hit if `ip` is over the per-minute request budget."""
    now = time.time()
    with _rate_limit_lock:
        timestamps = [t for t in _request_log.get(ip, []) if now - t < _RATE_LIMIT_WINDOW_SECONDS]
        if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
            _request_log[ip] = timestamps
            return True
        timestamps.append(now)
        _request_log[ip] = timestamps
        return False


@webchat_bp.route('/message', methods=['POST'])
def webchat_message():
    """Handle a website webchat message through the same pipeline Messenger uses."""
    client_ip = request.remote_addr or 'unknown'
    if _is_rate_limited(client_ip):
        return jsonify({
            "success": False,
            "error": "Too many messages — please slow down and try again shortly.",
            "response": "একটু ধীরে স্যার! কিছুক্ষণ পর আবার চেষ্টা করুন।",
            "mode": "human"
        }), 429

    data = request.get_json(silent=True) or {}
    raw_session_id = str(data.get('session_id') or '').strip()
    message = str(data.get('message') or '').strip()
    page_product = data.get('product')
    page_category = data.get('category')
    page_link = data.get('pageLink')
    page_product_id = data.get('id')
    # Whether the frontend explicitly sent all three of product/category/
    # pageLink itself — checked before the Referer fallback below overwrites
    # page_link, so a Referer-derived link never counts as "explicit."
    page_context_explicit_and_complete = bool(page_product) and bool(page_category) and bool(page_link)

    # Fallback when the frontend hasn't (yet) wired up `pageLink`: browsers
    # automatically send the current page's URL in the Referer header on a
    # same-page fetch/XHR call. _seed_page_context only actually uses this
    # when it resolves to a real BDStall listing (_extract_product_id), so a
    # referrer that isn't a product page (homepage, search results, another
    # site) is safely ignored rather than seeding junk context.
    if not page_link and request.referrer:
        page_link = request.referrer
        logger.info("[WEBCHAT] using Referer header as pageLink fallback: %s", page_link)

    if not message:
        return jsonify({
            "success": False,
            "error": "No message provided",
            "response": "অনুগ্রহ করে একটি বার্তা লিখুন।",
            "mode": "human"
        }), 400

    if len(message) > _MESSAGE_MAX_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Message too long (max {_MESSAGE_MAX_LENGTH} characters)",
            "response": "স্যার, বার্তাটি অনেক বড় হয়ে গেছে। অনুগ্রহ করে একটু ছোট করে লিখুন।",
            "mode": "human"
        }), 400

    if not _SESSION_ID_PATTERN.match(raw_session_id):
        return jsonify({
            "success": False,
            "error": "Invalid or missing session_id",
            "response": "দুঃখিত, একটি কারিগরি সমস্যা হয়েছে। পেজ রিফ্রেশ করে আবার চেষ্টা করুন।",
            "mode": "human"
        }), 400

    # Namespace web session ids so they can never collide with a Facebook PSID
    # (always numeric) and cross-pollute another channel's conversation state.
    user_id = f"web_{raw_session_id}"

    if page_product or page_category or page_link or page_product_id:
        try:
            _seed_page_context(user_id, page_product, page_category, page_link, page_product_id)
        except Exception as e:
            # Page-context grounding is a best-effort enhancement — never let
            # it block the message from getting a normal reply.
            logger.warning("[WEBCHAT] page context seeding failed: %s", e)

    try:
        price_range_result = _try_price_range_answer(user_id, message, page_category, page_product)
    except Exception as e:
        # Best-effort shortcut — never let it block the normal reply.
        logger.warning("[WEBCHAT] price range answer failed: %s", e)
        price_range_result = None
    if price_range_result:
        return jsonify(price_range_result), 200

    try:
        result = _process_user_message(
            user_id=user_id,
            message=message,
            source='webchat',
            user_name=None,
            platform_id='web'
        )
        if page_context_explicit_and_complete:
            # The frontend already told us product + category + pageLink —
            # the visitor is already on this exact page, so a "view this
            # product" link button pointing back at it is redundant. Only
            # suppress when all three were explicitly given; a partial or
            # Referer-derived context still benefits from the link.
            result.pop('link_buttons', None)
        if isinstance(result.get('response'), str):
            result['response'] = _emphasize_prices(result['response'])
        return jsonify(result), 200
    except Exception as e:
        logger.error("Webchat message error: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "response": "দুঃখিত, এই মুহূর্তে উত্তর দিতে সমস্যা হচ্ছে। অনুগ্রহ করে আবার চেষ্টা করুন।",
            "mode": "human"
        }), 500


# ── Rendered API docs + interactive tester (GET /docs) ────────────────────────
# Uses %%TOKEN%% placeholders + str.replace() rather than str.format(), so the
# embedded JavaScript below can use plain { } without needing to escape every
# brace for Python's format mini-language.
_DOCS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'WEBCHAT_API.md')

_DOCS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BDStall Webchat API</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    max-width: 860px; margin: 0 auto; padding: 32px 24px 80px; color: #1c1e21; line-height: 1.6;
  }
  h1, h2, h3 { line-height: 1.3; }
  h1 { border-bottom: 2px solid #eee; padding-bottom: 8px; }
  h2 { border-bottom: 1px solid #eee; padding-bottom: 6px; margin-top: 40px; }
  code { background: #f0f2f5; padding: 2px 6px; border-radius: 4px; font-size: .9em; }
  pre { background: #1c1e21; color: #f0f2f5; padding: 14px 16px; border-radius: 8px; overflow-x: auto; }
  pre code { background: none; padding: 0; color: inherit; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; }
  th, td { border: 1px solid #dadde1; padding: 8px 12px; text-align: left; font-size: .92em; }
  th { background: #f8f9fa; }
  a { color: #1e88e5; }
  blockquote { border-left: 3px solid #4285f4; margin: 0; padding: 4px 16px; color: #555; background: #f8f9fa; }

  .tryit { border: 1px solid #dadde1; border-radius: 10px; padding: 20px 22px; margin: 24px 0 40px;
           background: #f8f9fa; }
  .tryit h2 { margin-top: 0; border: none; padding: 0; }
  .tryit .badge { display: inline-block; background: #34a853; color: #fff; font-size: 11px;
                  font-weight: 700; padding: 2px 8px; border-radius: 10px; margin-left: 8px;
                  vertical-align: middle; }
  .tryit label { display: block; font-size: 13px; font-weight: 600; margin: 14px 0 4px; }
  .tryit input, .tryit textarea { width: 100%; box-sizing: border-box; padding: 9px 12px;
                  border: 1px solid #dadde1; border-radius: 8px; font-size: 14px;
                  font-family: inherit; }
  .tryit textarea { min-height: 64px; resize: vertical; }
  .tryit .row { display: flex; gap: 10px; align-items: center; margin-top: 16px; }
  .tryit button { background: #4285f4; color: #fff; border: none; border-radius: 8px;
                  padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer; }
  .tryit button:disabled { background: #bdc1c6; cursor: not-allowed; }
  .tryit .regen { background: transparent; color: #4285f4; font-weight: 600; padding: 4px 0;
                  border: none; cursor: pointer; font-size: 12px; }
  .tryit .status { font-family: monospace; font-size: 13px; font-weight: 700; padding: 3px 8px;
                   border-radius: 6px; }
  .tryit .status.s2 { background: #e6f4ea; color: #137333; }
  .tryit .status.s4 { background: #fce8e6; color: #c5221f; }
  .tryit .status.s5 { background: #fce8e6; color: #c5221f; }
  .tryit .status.pending { background: #e8eaed; color: #5f6368; }
  .tryit pre#tryitOutput { margin-top: 10px; max-height: 340px; }
</style>
</head>
<body>

<div class="tryit">
  <h2>Try it out <span class="badge">LIVE</span></h2>
  <p style="margin:6px 0 0;color:#555;font-size:13px;">
    Sends a real POST request to <code id="tryitEndpoint">...</code> on this
    running server and shows the actual response — nothing here is mocked.
  </p>

  <label for="tryitSession">session_id</label>
  <input id="tryitSession" type="text" />
  <button class="regen" type="button" id="tryitRegen">regenerate session_id</button>

  <label for="tryitMessage">message</label>
  <textarea id="tryitMessage">Hi</textarea>

  <div class="row">
    <button id="tryitSend" type="button">Send request</button>
    <span id="tryitStatus" class="status pending" style="display:none;"></span>
  </div>

  <pre id="tryitOutput" style="display:none;"><code id="tryitOutputCode"></code></pre>
</div>

%%CONTENT%%

<script>
(function () {
  function genId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID().replace(/-/g, '').slice(0, 20);
    }
    var id = '';
    for (var i = 0; i < 20; i++) id += Math.floor(Math.random() * 16).toString(16);
    return id;
  }

  var sessionInput = document.getElementById('tryitSession');
  var messageInput = document.getElementById('tryitMessage');
  var sendBtn = document.getElementById('tryitSend');
  var regenBtn = document.getElementById('tryitRegen');
  var statusEl = document.getElementById('tryitStatus');
  var outputEl = document.getElementById('tryitOutput');
  var outputCode = document.getElementById('tryitOutputCode');

  sessionInput.value = genId();
  regenBtn.addEventListener('click', function () { sessionInput.value = genId(); });

  // This page (/docs) may be served either at the app root (e.g. local dev,
  // http://localhost:5000/docs) or behind a reverse-proxy prefix (e.g.
  // production, https://ai.bdstall.com/chatbot/docs). A hardcoded absolute
  // path like '/api/webchat/message' would miss the '/chatbot' prefix in
  // the second case. Derive the correct base from this page's own URL
  // instead — always correct regardless of how deep the app is mounted.
  var basePath = window.location.pathname.replace(/\\/docs\\/?$/, '');
  var endpointUrl = basePath + '/api/webchat/message';
  document.getElementById('tryitEndpoint').textContent = endpointUrl;

  function setStatus(code, pending) {
    statusEl.style.display = 'inline-block';
    if (pending) {
      statusEl.className = 'status pending';
      statusEl.textContent = 'sending...';
      return;
    }
    var cls = 'status ';
    if (code >= 200 && code < 300) cls += 's2';
    else if (code >= 400 && code < 500) cls += 's4';
    else cls += 's5';
    statusEl.className = cls;
    statusEl.textContent = code;
  }

  sendBtn.addEventListener('click', function () {
    var sessionId = sessionInput.value.trim();
    var message = messageInput.value;
    sendBtn.disabled = true;
    outputEl.style.display = 'block';
    outputCode.textContent = '';
    setStatus(0, true);

    fetch(endpointUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: message })
    })
      .then(function (res) {
        setStatus(res.status, false);
        return res.json().catch(function () { return { error: 'Non-JSON response' }; });
      })
      .then(function (data) {
        outputCode.textContent = JSON.stringify(data, null, 2);
      })
      .catch(function (err) {
        setStatus(0, false);
        statusEl.textContent = 'network error';
        outputCode.textContent = String(err);
      })
      .finally(function () {
        sendBtn.disabled = false;
      });
  });
})();
</script>

</body>
</html>
"""


@webchat_docs_bp.route('/docs', methods=['GET'])
def webchat_docs():
    """Render docs/WEBCHAT_API.md as a browsable page with a live 'try it out' tester."""
    try:
        with open(_DOCS_FILE, 'r', encoding='utf-8') as f:
            raw_markdown = f.read()
    except OSError:
        return "Documentation file not found.", 404

    if _markdown is None:
        # markdown package missing (e.g. not yet installed after a fresh
        # deploy) — fall back to plain text rather than 500.
        return Response(raw_markdown, mimetype='text/plain')

    html_body = _markdown.markdown(raw_markdown, extensions=['tables', 'fenced_code'])
    page_html = _DOCS_PAGE_TEMPLATE.replace('%%CONTENT%%', html_body)
    return Response(page_html, mimetype='text/html')
