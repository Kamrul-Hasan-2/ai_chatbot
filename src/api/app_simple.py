"""
Simple API - Following Your Roadmap
Cleaner, simpler implementation
"""
import os
import sys
import logging
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from datetime import datetime
from typing import Any, Optional

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import simple chatbot
from core.simple_chatbot_flow import SimpleChatbot

# Import conversation context manager
try:
    from utils.conversation_context import get_context_manager
except ImportError:
    from src.utils.conversation_context import get_context_manager

# Import product link handler
try:
    from utils.product_link_handler import get_link_handler
except ImportError:
    from src.utils.product_link_handler import get_link_handler

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get project root
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'static')

# Initialize Flask
app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

# Initialize chatbot
chatbot = None

# BDStall chat message save API configuration
SAVE_MESSAGE_API_URL = os.getenv(
    'SAVE_MESSAGE_API_URL',
    'https://www.bdstall.com/api/item/chatbot_save_message/'
)
SAVE_MESSAGE_API_KEY = os.getenv('SAVE_MESSAGE_API_KEY', 'mkh677ddd2sxxkkdjff')

# Facebook Messenger configuration
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN', '')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'my_verify_token_12345')
FACEBOOK_GRAPH_API_VERSION = os.getenv('FACEBOOK_GRAPH_API_VERSION', 'v25.0')
MESSENGER_USER_NAME_CACHE = {}
USER_NAME_MAP_FILE = os.getenv(
    'USER_NAME_MAP_FILE',
    os.path.join(PROJECT_ROOT, 'data', 'user_names.json')
)
URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

def _log_api_call(
    api_name: str,
    method: str,
    url: str,
    request_payload,
    status_code: int,
    duration_ms: int,
    status: str,
    response_preview: str = ""
) -> None:
    """Write outbound API call details to daily API log file."""
    try:
        logs_dir = os.path.join(PROJECT_ROOT, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"api_calls_{datetime.now().strftime('%Y-%m-%d')}.log")

        entry = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "api_name": api_name,
            "method": method,
            "url": url,
            "request": request_payload,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "result": status,
            "response_preview": response_preview[:400]
        }

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(
            "[API_LOG] %s %s %s status=%s result=%s duration_ms=%s",
            api_name,
            method,
            url,
            status_code,
            status,
            duration_ms
        )
    except Exception as e:
        logger.warning("API log write failed: %s", e)


def _load_user_name_map() -> dict:
    """Load persistent user name map from local JSON file."""
    try:
        if not os.path.exists(USER_NAME_MAP_FILE):
            return {}
        with open(USER_NAME_MAP_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.info("[NAME_MAP] load failed: %s", e)
        return {}


def _save_user_name_map(name_map: dict) -> None:
    """Persist user name map to local JSON file."""
    try:
        folder = os.path.dirname(USER_NAME_MAP_FILE)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(USER_NAME_MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(name_map, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.info("[NAME_MAP] save failed: %s", e)


def get_known_user_name(user_id: str) -> Optional[str]:
    """Get a previously known display name for this user id."""
    if not user_id:
        return None

    # 1) In-memory fast cache
    cached = MESSENGER_USER_NAME_CACHE.get(str(user_id))
    if cached:
        return cached

    # 2) Persistent file cache
    name_map = _load_user_name_map()
    known_name = (name_map.get(str(user_id)) or '').strip()
    if known_name:
        MESSENGER_USER_NAME_CACHE[str(user_id)] = known_name
        return known_name

    return None


def remember_user_name(user_id: str, user_name: Optional[str]) -> None:
    """Remember user name in memory and local file for future webhook events."""
    clean_name = (user_name or '').strip()
    if not user_id or not clean_name:
        return

    MESSENGER_USER_NAME_CACHE[str(user_id)] = clean_name

    name_map = _load_user_name_map()
    if name_map.get(str(user_id)) != clean_name:
        name_map[str(user_id)] = clean_name
        _save_user_name_map(name_map)


def save_chat_message(user_id: str, sender_type: int, message: str, user_name: Optional[str] = None) -> bool:
    """Persist a single chat message to BDStall message history API."""
    if not message:
        return False

    payload = {
        "key": SAVE_MESSAGE_API_KEY,
        "user_id": str(user_id),
        "sender_type": int(sender_type),
        "message": message
    }
    if user_name:
        payload["user_name"] = str(user_name)

    def _is_success_response(resp: requests.Response) -> bool:
        """Treat 2xx as success, with optional JSON 'success' flag validation when present."""
        if not (200 <= resp.status_code < 300):
            return False
        try:
            data = resp.json()
            if isinstance(data, dict) and 'success' in data:
                return bool(data.get('success'))
        except Exception:
            pass
        return True

    # Try JSON first, then form-data fallback for stricter external API gateways.
    attempts = [
        ("json", lambda: requests.post(SAVE_MESSAGE_API_URL, json=payload, timeout=10)),
        ("form", lambda: requests.post(SAVE_MESSAGE_API_URL, data=payload, timeout=10))
    ]
    last_error = None

    for request_mode, request_fn in attempts:
        started = datetime.now()
        try:
            response = request_fn()
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            passed = _is_success_response(response)

            _log_api_call(
                api_name="chatbot_save_message",
                method=f"POST[{request_mode}]",
                url=SAVE_MESSAGE_API_URL,
                request_payload=payload,
                status_code=response.status_code,
                duration_ms=duration_ms,
                status="PASS" if passed else "FAIL",
                response_preview=response.text
            )

            if passed:
                return True

            logger.warning(
                "⚠️ Failed to save message via %s (status=%s, sender_type=%s, user_id=%s): %s",
                request_mode,
                response.status_code,
                sender_type,
                user_id,
                response.text
            )
        except Exception as e:
            duration_ms = int((datetime.now() - started).total_seconds() * 1000)
            _log_api_call(
                api_name="chatbot_save_message",
                method=f"POST[{request_mode}]",
                url=SAVE_MESSAGE_API_URL,
                request_payload=payload,
                status_code=0,
                duration_ms=duration_ms,
                status="FAIL",
                response_preview=str(e)
            )

            logger.warning(
                "⚠️ Error saving message via %s (sender_type=%s, user_id=%s): %s",
                request_mode,
                sender_type,
                user_id,
                e
            )
            last_error = e

    if last_error:
        logger.warning("⚠️ Message save ultimately failed after retries for user_id=%s", user_id)
    return False


def _strip_link_lines(message_text: str) -> str:
    """Remove raw link lines from bot text when dedicated Messenger buttons are used."""
    text = str(message_text or '')
    if not text.strip():
        return ''

    filtered_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower().startswith('লিংক:'):
            continue
        if line.lower().startswith('link:'):
            continue
        if URL_PATTERN.search(line):
            continue
        filtered_lines.append(raw_line)

    cleaned = '\n'.join(filtered_lines)
    cleaned = '\n'.join([ln.rstrip() for ln in cleaned.splitlines()]).strip()
    return cleaned


def _extract_urls(message_text: str) -> list[str]:
    """Extract unique URLs from text in order."""
    text = str(message_text or '')
    if not text:
        return []

    urls = []
    seen = set()
    for match in URL_PATTERN.findall(text):
        url = str(match).strip().rstrip('.,!?)')
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _send_facebook_payload(recipient_id: str, payload: dict) -> bool:
    """Send a prepared payload to Facebook Messenger Send API."""
    if not PAGE_ACCESS_TOKEN:
        logger.warning("PAGE_ACCESS_TOKEN not set; cannot send Messenger reply")
        return False

    url = f"https://graph.facebook.com/v25.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        response = requests.post(url, json=payload, timeout=10)
        if 200 <= response.status_code < 300:
            logger.info("✅ Messenger payload sent to %s", recipient_id)
            return True

        logger.warning(
            "Messenger send failed (status=%s): %s",
            response.status_code,
            response.text
        )
        return False
    except Exception as e:
        logger.warning("Messenger send error: %s", e)
        return False


def send_facebook_message(recipient_id: str, message_text: str, link_buttons: Optional[list[dict[str, Any]]] = None) -> bool:
    """Send a Messenger reply with optional web_url buttons for product links."""
    if not PAGE_ACCESS_TOKEN:
        logger.warning("PAGE_ACCESS_TOKEN not set; cannot send Messenger reply")
        return False

    buttons = [btn for btn in (link_buttons or []) if isinstance(btn, dict) and str(btn.get('url') or '').strip()]

    # Fallback: when response contains raw URLs but no structured buttons, build button cards automatically.
    if not buttons:
        for url in _extract_urls(message_text):
            buttons.append({
                'text': 'View Product',
                'url': url
            })

    if not buttons:
        plain_text = str(message_text or '').strip()
        if not plain_text:
            plain_text = "আপনার জন্য তথ্য প্রস্তুত আছে স্যার।"
        text_payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": plain_text}
        }
        return _send_facebook_payload(recipient_id, text_payload)

    plain_text = str(message_text or '').strip()
    intro_text = ''
    closing_text = ''
    if plain_text:
        lines = [line.strip() for line in plain_text.splitlines() if line.strip()]
        if lines:
            intro_text = lines[0]
            if 'আরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।' in plain_text:
                closing_text = 'আরও প্রোডাক্ট চাইলে বলুন, আমি দেখাচ্ছি।'

    if intro_text:
        intro_payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": intro_text}
        }
        if not _send_facebook_payload(recipient_id, intro_payload):
            return False

    fallback_title = _strip_link_lines(message_text)
    fallback_title = fallback_title.splitlines()[0].strip() if fallback_title else ''

    for index, btn in enumerate(buttons, 1):
        label = str(btn.get('text') or 'View Product').strip() or 'View Product'
        title = str(btn.get('title') or '').strip()
        price = str(btn.get('price') or '').strip()
        display_title = title or fallback_title or f'Link {index}'
        money_text = f"\nমূল্য: {price}" if price else ''
        card_text = f"{index}️⃣ {display_title}{money_text}"

        template_payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": card_text[:640],
                        "buttons": [
                            {
                                "type": "web_url",
                                "url": str(btn.get('url')).strip(),
                                "title": label[:20]
                            }
                        ]
                    }
                }
            }
        }

        if not _send_facebook_payload(recipient_id, template_payload):
            return False

    if closing_text:
        closing_payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": closing_text}
        }
        if not _send_facebook_payload(recipient_id, closing_payload):
            return False

    return True


def get_messenger_user_name(sender_id: str) -> Optional[str]:
    """Resolve Facebook sender display name from Graph API with simple in-memory cache."""
    if not sender_id:
        return None

    cached_name = MESSENGER_USER_NAME_CACHE.get(str(sender_id))
    if cached_name:
        return cached_name

    if not PAGE_ACCESS_TOKEN:
        return None

    try:
        profile_url = f"https://graph.facebook.com/{FACEBOOK_GRAPH_API_VERSION}/{sender_id}"
        params = {
            "fields": "name,first_name,last_name",
            "access_token": PAGE_ACCESS_TOKEN
        }
        response = requests.get(profile_url, params=params, timeout=10)
        if not (200 <= response.status_code < 300):
            logger.info(
                "[WEBHOOK] Could not fetch sender name for %s (status=%s): %s",
                sender_id,
                response.status_code,
                (response.text or '')[:300]
            )
            return None

        data = response.json() if response.text else {}
        full_name = (data.get("name") or "").strip()
        if not full_name:
            first_name = (data.get("first_name") or "").strip()
            last_name = (data.get("last_name") or "").strip()
            full_name = f"{first_name} {last_name}".strip()

        if full_name:
            MESSENGER_USER_NAME_CACHE[str(sender_id)] = full_name
            return full_name
    except Exception as e:
        logger.info("[WEBHOOK] sender name lookup failed for %s: %s", sender_id, e)

    return None


def get_responder_user_name(user_id: str) -> Optional[str]:
    """Resolve user name from BDStall responder API when Messenger profile lookup is unavailable."""
    if not user_id:
        return None

    try:
        url = "https://www.bdstall.com/api/item/chatbot_responder/"
        params = {
            "key": SAVE_MESSAGE_API_KEY,
            "user_id": str(user_id)
        }
        response = requests.get(url, params=params, timeout=8)
        if not (200 <= response.status_code < 300):
            return None

        data = response.json() if response.text else {}
        responder_data = data.get("data") if isinstance(data, dict) else {}
        resolved_name = (responder_data.get("user_name") or "").strip() if isinstance(responder_data, dict) else ""
        if resolved_name:
            MESSENGER_USER_NAME_CACHE[str(user_id)] = resolved_name
            return resolved_name
    except Exception as e:
        logger.info("[WEBHOOK] responder user_name lookup failed for %s: %s", user_id, e)

    return None


def _process_user_message(
    user_id: str,
    message: str,
    source: str = "web",
    user_name: Optional[str] = None
) -> dict:
    """Run the same chatbot pipeline for web and Messenger inputs."""
    clean_message = (message or '').strip()
    resolved_user_name = (
        (user_name or '').strip()
        or get_known_user_name(str(user_id))
        or get_responder_user_name(str(user_id))
    )
    remember_user_name(str(user_id), resolved_user_name)
    if not clean_message:
        return {
            "success": False,
            "user_id": str(user_id),
            "user_name": resolved_user_name,
            "message": message,
            "response": "",
            "mode": "ai",
            "error": "No message provided"
        }

    # Save visitor message first (3 = Visitor)
    visitor_saved = save_chat_message(
        user_id=user_id,
        sender_type=3,
        message=clean_message,
        user_name=resolved_user_name
    )
    if not visitor_saved:
        logger.warning(
            "[PIPELINE] visitor message not persisted source=%s user_id=%s",
            source,
            user_id
        )

    # Process message through roadmap
    result = get_chatbot().process_message(user_id, clean_message)

    response_text = (result.get('response') or '').strip()
    bot_saved = None
    if response_text:
        # Save chatbot response (2 = Bot) when available
        bot_saved = save_chat_message(
            user_id=user_id,
            sender_type=2,
            message=response_text,
            user_name=resolved_user_name
        )
        if not bot_saved:
            logger.warning(
                "[PIPELINE] bot response not persisted source=%s user_id=%s",
                source,
                user_id
            )

    logger.info(
        "[PIPELINE] source=%s user_id=%s mode=%s intent=%s has_response=%s visitor_saved=%s bot_saved=%s",
        source,
        user_id,
        result.get('mode'),
        result.get('intent'),
        bool(response_text),
        visitor_saved,
        bot_saved
    )

    # Always include user_name in API response when known.
    result['user_name'] = resolved_user_name

    return result


@app.route('/', methods=['GET'])
def index():
    """API Info"""
    return jsonify({
        "service": "Simple Chatbot API",
        "version": "1.0",
        "roadmap": {
            "step_1": "Message → Groq API (Intent Detection)",
            "step_2": "Intent → Search API",
            "step_3": "Results → Database Format",
            "step_4": "Database → AI Formatting",
            "step_5": "Track AI/HUMAN mode",
            "step_6": "Return JSON with mode"
        },
        "endpoints": {
            "/chat": "POST - Send message",
            "/agent/reply": "POST - Save manual human agent reply",
            "/save-message": "POST - Save any message (sender_type: 1/2/3)",
            "/health": "GET - Health check",
            "/webhook": "GET/POST - Facebook Messenger webhook",
            "/chatbot/webhook": "GET/POST - Facebook webhook (proxy-safe path)",
            "/mode/:user_id": "GET - Get user mode",
            "/mode/:user_id/human": "POST - Switch to human",
            "/mode/:user_id/ai": "POST - Switch to AI",
            "/test": "GET - Chat interface (web), POST - Send message"
        }
    }), 200


@app.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint
    
    Request:
    {
        "user_id": "user123",
        "message": "amake ekta 10k er modde laptop dekhan"
    }
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "message": "...",
        "response": "...",
        "mode": "ai",  ← Always shows: "ai" or "human"
        "intent": "laptop_search",
        "products_found": 3,
        "products": [...]
    }
    """
    try:
        data = request.get_json() or {}
        
        user_id = data.get('user_id', 'web_user')
        user_name = data.get('user_name')
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                "success": False,
                "error": "No message provided",
                "mode": "ai"
            }), 400
        
        result = _process_user_message(
            user_id=user_id,
            message=message,
            source='web',
            user_name=user_name
        )
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "response": "দুঃখিত স্যার, এই মুহূর্তে উত্তর দিতে সমস্যা হচ্ছে। অনুগ্রহ করে আপনার প্রশ্নটি আবার লিখুন বা প্রোডাক্টের নাম/বাজেট বলুন।",
            "mode": "human"
        }), 500


@app.route('/api/conversation/last-5/<user_id>', methods=['GET'])
def get_last_5_messages(user_id):
    """
    Get the last 5 messages for a user
    
    Query Parameters:
    - limit: Number of messages to retrieve (default: 5, max: 20)
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "count": 5,
        "messages": [
            {"sender_type": 3, "text": "laptop dekhaen", "timestamp": "..."},
            {"sender_type": 2, "text": "HP laptops...", "timestamp": "..."},
            ...
        ],
        "context_text": "User: laptop dekhaen\nBot: HP laptops...",
        "formatted_lines": ["User: laptop dekhaen", "Bot: HP laptops..."]
    }
    """
    try:
        limit = request.args.get('limit', 5, type=int)
        
        context_manager = get_context_manager()
        result = context_manager.get_last_n_messages(user_id, limit=limit)
        
        return jsonify({
            "success": result['success'],
            "user_id": user_id,
            "count": result['count'],
            "messages": result['messages'],
            "context_text": result['context_text'],
            "formatted_lines": result.get('formatted_lines', []),
            "error": result.get('error')
        }), 200 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"❌ Error getting last 5 messages: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e),
            "count": 0,
            "messages": []
        }), 500


@app.route('/api/conversation/context/<user_id>', methods=['POST'])
def build_conversation_context(user_id):
    """
    Build conversation context for AI prompt
    
    Request:
    {
        "message": "what was the last product we discussed?",
        "limit": 5
    }
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "prompt": "Recent conversation context (oldest to newest):\nUser: laptop dekhaen\nBot: HP laptops...\n\nCurrent User Message: what was...",
        "context_lines": 5
    }
    """
    try:
        data = request.get_json() or {}
        current_message = data.get('message', '')
        limit = data.get('limit', 5)
        
        if not current_message:
            return jsonify({
                "success": False,
                "error": "Message parameter required",
                "user_id": user_id
            }), 400
        
        context_manager = get_context_manager()
        prompt = context_manager.build_conversation_prompt(user_id, current_message, limit)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "prompt": prompt,
            "context_lines": limit
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error building context: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }), 500


@app.route('/api/conversation/summary/<user_id>', methods=['GET'])
def get_conversation_summary(user_id):
    """
    Get conversation summary for a user
    
    Query Parameters:
    - limit: Number of messages to analyze (default: 5)
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "total_messages": 5,
        "user_messages": 2,
        "bot_messages": 2,
        "agent_messages": 1,
        "summary": "Last 5 messages: 2 from user, 2 from bot, 1 from agent"
    }
    """
    try:
        limit = request.args.get('limit', 5, type=int)
        
        context_manager = get_context_manager()
        result = context_manager.get_conversation_summary(user_id, limit)
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"❌ Error getting conversation summary: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }), 500


@app.route('/api/product/extract-links/<user_id>', methods=['POST'])
def extract_product_links(user_id):
    """
    Extract product links and information from a message
    
    Request:
    {
        "message": "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/details/product-123/"
    }
    
    Response:
    {
        "success": true,
        "has_links": true,
        "has_products": true,
        "products_count": 1,
        "extracted": {...},
        "formatted": {...},
        "messenger_template": {...}
    }
    """
    try:
        data = request.get_json() or {}
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Message parameter required",
                "user_id": user_id
            }), 400
        
        link_handler = get_link_handler()
        result = link_handler.process_incoming_link_message(user_id, message)
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"❌ Error extracting links: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }), 500


@app.route('/api/product/create-template/<user_id>', methods=['POST'])
def create_product_template(user_id):
    """
    Create a Messenger template for product links in a message
    
    Request:
    {
        "message": "Check out this laptop: https://www.bdstall.com/details/hp-laptop-123/"
    }
    
    Response:
    {
        "success": true,
        "messenger_template": {
            "messaging_type": "RESPONSE",
            "message": {...}
        },
        "product_count": 1
    }
    """
    try:
        data = request.get_json() or {}
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Message parameter required"
            }), 400
        
        link_handler = get_link_handler()
        template = link_handler.create_messenger_template(message)
        
        extraction = link_handler.extract_product_info_from_message(message)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "product_count": extraction['total_products'],
            "messenger_template": template,
            "extraction": extraction
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error creating template: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }), 500


@app.route('/api/product/user-context/<user_id>', methods=['GET'])
def get_user_product_context(user_id):
    """
    Get product links discussed in user's conversation history
    
    Query Parameters:
    - limit: Number of products to return (default: 5)
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "products": [
            {
                "message": "Check out these laptops...",
                "extracted": {...},
                "products": [...]
            }
        ],
        "count": 3
    }
    """
    try:
        limit = request.args.get('limit', 5, type=int)
        
        link_handler = get_link_handler()
        products = link_handler.get_user_product_context(user_id, limit)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "count": len(products),
            "products": products
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error getting product context: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }), 500


@app.route('/api/product/parse-link', methods=['POST'])
def parse_single_link():
    """
    Parse a single product link and extract information
    
    Request:
    {
        "link": "https://www.bdstall.com/details/product-name-123/"
    }
    
    Response:
    {
        "success": true,
        "url": "https://www.bdstall.com/details/product-name-123/",
        "product_id": "product-name-123",
        "domain": "bdstall.com",
        "type": "product"
    }
    """
    try:
        data = request.get_json() or {}
        link = data.get('link', '')
        
        if not link:
            return jsonify({
                "success": False,
                "error": "Link parameter required"
            }), 400
        
        link_handler = get_link_handler()
        result = link_handler.parse_product_link(link)
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"❌ Error parsing link: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/product/enhanced-template/<user_id>', methods=['POST'])
def create_enhanced_template(user_id):
    """
    Create an enhanced Messenger template with product details
    Fetches product images, prices, and details from BDStall API
    
    Request:
    {
        "message": "Check out this laptop: https://www.bdstall.com/details/hp-laptop-123/"
    }
    
    Response:
    {
        "success": true,
        "user_id": "user123",
        "template": {...},  // Full Messenger template with images/prices
        "products_found": 1,
        "products": [...]
    }
    """
    try:
        data = request.get_json() or {}
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Message parameter required"
            }), 400
        
        link_handler = get_link_handler()
        template = link_handler.create_enhanced_template(message)
        
        extraction = link_handler.extract_product_info_from_message(message)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "products_found": extraction['total_products'],
            "template": template,
            "extraction": extraction
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error creating enhanced template: {e}")
        return jsonify({
            "success": False,
            "user_id": user_id,
            "error": str(e)
        }), 500


@app.route('/webhook', methods=['GET'])
@app.route('/chatbot/webhook', methods=['GET'])
def verify_webhook():
    """Verify Facebook webhook challenge."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge or '', 200

    logger.warning("Webhook verification failed (mode=%s, token_match=%s)", mode, token == VERIFY_TOKEN)
    return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
@app.route('/chatbot/webhook', methods=['POST'])
def messenger_webhook():
    """Handle incoming Facebook Messenger events using the simple chatbot flow."""
    try:
        data = request.get_json() or {}
        logger.info("[WEBHOOK] Payload received: %s", json.dumps(data, ensure_ascii=False)[:1000])

        if data.get('object') != 'page':
            logger.info("[WEBHOOK] Ignored non-page object: %s", data.get('object'))
            return jsonify({"status": "ignored"}), 200

        processed_count = 0
        replied_count = 0
        for entry in data.get('entry', []):
            for event in entry.get('messaging', []):
                message_obj = event.get('message') or {}
                if message_obj.get('is_echo'):
                    logger.info("[WEBHOOK] Skipping echo event")
                    continue

                sender_id = (event.get('sender') or {}).get('id')
                sender_name = (
                    (event.get('sender') or {}).get('name')
                    or (event.get('sender') or {}).get('username')
                    or None
                )
                if not sender_name and sender_id:
                    sender_name = get_messenger_user_name(sender_id)
                if not sender_name and sender_id:
                    sender_name = get_known_user_name(sender_id)
                if not sender_name and sender_id:
                    sender_name = get_responder_user_name(sender_id)
                remember_user_name(sender_id, sender_name)
                message_text = (message_obj.get('text') or '').strip()
                if not message_text:
                    quick_reply_payload = ((message_obj.get('quick_reply') or {}).get('payload') or '').strip()
                    postback_payload = ((event.get('postback') or {}).get('payload') or '').strip()
                    message_text = quick_reply_payload or postback_payload

                logger.info("[WEBHOOK] Event sender_id=%s has_text=%s", sender_id, bool(message_text))

                if not sender_id or not message_text:
                    continue

                processed_count += 1

                result = _process_user_message(
                    user_id=sender_id,
                    message=message_text,
                    source='messenger',
                    user_name=sender_name
                )
                response_text = (result.get('response') or '').strip()
                link_buttons = result.get('link_buttons') or []

                # In HUMAN handoff mode, chatbot intentionally returns empty response.
                if not response_text:
                    logger.info(
                        "[WEBHOOK] No bot reply for sender_id=%s (mode=%s, status=%s)",
                        sender_id,
                        result.get('mode'),
                        result.get('conversation_status')
                    )
                    continue

                logger.info("[WEBHOOK] Sending reply to sender_id=%s", sender_id)
                if send_facebook_message(sender_id, response_text, link_buttons=link_buttons):
                    replied_count += 1

        return jsonify({"status": "ok", "processed": processed_count, "replied": replied_count}), 200

    except Exception as e:
        logger.error("❌ Webhook error: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/agent/reply', methods=['POST'])
def agent_reply():
    """Save a manual human-agent message (1 = Human Agent)."""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        user_name = data.get('user_name', 'Human Agent')
        message = data.get('message', '')

        if not user_id or not message:
            return jsonify({
                "success": False,
                "error": "user_id and message are required"
            }), 400

        saved = save_chat_message(
            user_id=user_id,
            sender_type=1,
            message=message,
            user_name=user_name
        )

        return jsonify({
            "success": saved,
            "user_id": str(user_id),
            "user_name": user_name,
            "sender_type": 1,
            "message": message
        }), 200 if saved else 502

    except Exception as e:
        logger.error(f"❌ Agent reply save error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/save-message', methods=['POST'])
def save_message_endpoint():
    """Save a message by sender type: 1=Human Agent, 2=Bot, 3=Visitor."""
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        user_id = data.get('user_id')
        user_name = data.get('user_name')
        message = data.get('message', '')
        sender_type = data.get('sender_type')

        if not user_id or not message or sender_type is None:
            return jsonify({
                "success": False,
                "error": "user_id, sender_type and message are required"
            }), 400

        try:
            sender_type = int(sender_type)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "sender_type must be integer: 1, 2, or 3"
            }), 400

        if sender_type not in (1, 2, 3):
            return jsonify({
                "success": False,
                "error": "sender_type must be one of: 1 (Human Agent), 2 (Bot), 3 (Visitor)"
            }), 400

        saved = save_chat_message(
            user_id=user_id,
            sender_type=sender_type,
            message=message,
            user_name=user_name
        )

        return jsonify({
            "success": saved,
            "user_id": str(user_id),
            "user_name": user_name,
            "sender_type": sender_type,
            "message": message
        }), 200 if saved else 502

    except Exception as e:
        logger.error(f"❌ Save message endpoint error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    bot = get_chatbot()
    return jsonify({
        "status": "healthy",
        "chatbot_ready": bot is not None,
        "api_configured": bool(bot.api_url) if bot else False,
        "database_responses": len(bot.database) if bot else 0,
        "groq_available": bot.groq_client is not None if bot else False
    }), 200


@app.route('/debug/messenger', methods=['GET'])
def debug_messenger():
    """Runtime diagnostics for Messenger integration."""
    bot = get_chatbot()
    return jsonify({
        "ok": True,
        "entrypoint": "src.api.app_simple:app",
        "webhook_paths": ["/webhook", "/chatbot/webhook"],
        "verify_token_configured": bool(VERIFY_TOKEN),
        "page_access_token_configured": bool(PAGE_ACCESS_TOKEN),
        "page_access_token_prefix": PAGE_ACCESS_TOKEN[:12] if PAGE_ACCESS_TOKEN else "",
        "chatbot_initialized": bot is not None,
        "groq_available": bool(bot.groq_client) if bot else False,
        "database_responses": len(bot.database) if bot else 0,
        "notes": [
            "If page_access_token_configured is false, Messenger replies cannot be sent.",
            "Webhook in Meta must point to /webhook or /chatbot/webhook on this server."
        ]
    }), 200


@app.route('/mode/<user_id>', methods=['GET'])
def get_mode(user_id):
    """Get current mode for user"""
    mode = get_chatbot().get_user_mode(user_id)
    return jsonify({
        "user_id": user_id,
        "mode": mode
    }), 200


@app.route('/mode/<user_id>/human', methods=['POST'])
def switch_to_human(user_id):
    """Manually switch user to HUMAN mode"""
    get_chatbot().switch_to_human(user_id)
    return jsonify({
        "user_id": user_id,
        "mode": "human",
        "message": "User switched to HUMAN mode"
    }), 200


@app.route('/mode/<user_id>/ai', methods=['POST'])
def switch_to_ai(user_id):
    """Manually switch user back to AI mode"""
    get_chatbot().switch_to_ai(user_id)
    return jsonify({
        "user_id": user_id,
        "mode": "ai",
        "message": "User switched back to AI mode"
    }), 200


@app.route('/test', methods=['GET', 'POST'])
def test():
    """Test endpoint - GET for chat interface, POST same as /chat"""
    if request.method == 'GET':
        return send_from_directory(STATIC_FOLDER, 'chat.html')
    return chat()


# Valid API keys for ai_template endpoint
VALID_API_KEYS = [
    'mkh677ddd2sxxk',
    'mkh677ddd2sxxkkdjff',
    os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff')
]

SEARCH_INTENT_ITEMS_FILE = os.path.join(PROJECT_ROOT, 'data', 'search_intent_items.json')


def load_search_intent_items():
    """Load search_intent_items.json"""
    try:
        if os.path.exists(SEARCH_INTENT_ITEMS_FILE):
            with open(SEARCH_INTENT_ITEMS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load search_intent_items.json: {e}")
    return []


def normalize_category(category: str) -> str:
    """Normalize category name for comparison"""
    return category.lower().strip()


def find_category_in_list(category: str, items_list: list) -> bool:
    """Check if category exists in the items list (case-insensitive)"""
    normalized_category = normalize_category(category)
    for item in items_list:
        if normalize_category(item) == normalized_category:
            return True
    return False


def get_category_url(category: str) -> str:
    """Generate BDStall category URL"""
    # Replace spaces with hyphens and make lowercase
    url_slug = category.lower().replace(' ', '-').replace('_', '-')
    return f"https://www.bdstall.com/{url_slug}/"


@app.route('/api/item/ai_template/', methods=['GET'])
def ai_template_category_search():
    """
    AI Template Category Search Endpoint
    
    URL Format:
    /api/item/ai_template/?intent=category&category=laptop&key=mkh677ddd2sxxk
    
    Query Parameters:
    - intent: Operation type (currently "category")
    - category: Category name to search for
    - key: API key for authentication
    
    Response (if category found):
    {
        "success": true,
        "data": "আপনি laptop ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: https://www.bdstall.com/laptop/"
    }
    
    Response (if category not found):
    {
        "success": false,
        "error": "Category not found",
        "data": []
    }
    """
    try:
        # Get query parameters
        intent = request.args.get('intent', '').lower()
        category = request.args.get('category', '').strip()
        api_key = request.args.get('key', '').strip()
        
        # Validate API key
        if api_key not in VALID_API_KEYS:
            logger.warning(f"[AI_TEMPLATE] Invalid API key: {api_key}")
            return jsonify({
                "success": False,
                "error": "Invalid API key"
            }), 401
        
        # Validate required parameters
        if not category:
            return jsonify({
                "success": False,
                "error": "Category parameter is required"
            }), 400
        
        # Only support "category" intent for now
        if intent != 'category':
            return jsonify({
                "success": False,
                "error": f"Intent '{intent}' not supported. Use 'intent=category'",
                "supported_intents": ["category"]
            }), 400
        
        # Load search intent items
        items_list = load_search_intent_items()
        
        if not items_list:
            logger.warning("[AI_TEMPLATE] Failed to load search intent items")
            return jsonify({
                "success": False,
                "error": "Unable to load category database"
            }), 500
        
        # Check if category exists in the list
        category_exists = find_category_in_list(category, items_list)
        
        if category_exists:
            # Category found - return Bengali response with link
            category_url = get_category_url(category)
            bengali_message = f"আপনি {category} ক্যাটাগরিতে বিভিন্ন পণ্য দেখতে পারেন। এই লিংকে ক্লিক করুন: {category_url}"
            
            logger.info(f"[AI_TEMPLATE] Category found: {category}")
            
            return jsonify({
                "success": True,
                "data": bengali_message
            }), 200
        else:
            # Category not found
            logger.info(f"[AI_TEMPLATE] Category not found: {category}")
            
            return jsonify({
                "success": False,
                "error": f"Category '{category}' not found",
                "message": "Please search with a valid category name"
            }), 404
    
    except Exception as e:
        logger.error(f"[AI_TEMPLATE] Error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def initialize():
    """Initialize chatbot"""
    global chatbot
    
    print("=" * 60)
    print("🤖 Simple Chatbot API - Your Roadmap")
    print("=" * 60)
    print("Step 1: Message → Groq API (Intent)")
    print("Step 2: Intent → Search API")
    print("Step 3: Results → Database Format")
    print("Step 4: Database → AI Formatting")
    print("Step 5: Track AI/HUMAN mode")
    print("Step 6: Return JSON with mode")
    print("=" * 60)
    
    try:
        chatbot = SimpleChatbot()
        print("✅ Chatbot initialized successfully!")
        print(f"🔗 BDStall API: {chatbot.api_url}")
        print(f"🤖 Groq API: {'Available' if chatbot.groq_client else 'Not available'}")
        print("=" * 60)
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        raise


def get_chatbot():
    """Get or initialize chatbot (lazy initialization)"""
    global chatbot
    if chatbot is None:
        initialize()
    return chatbot


if __name__ == '__main__':
    # Initialize
    initialize()
    
    # Get port
    port = int(os.getenv('PORT', 5000))
    
    print()
    print("🌐 Server starting...")
    print(f"📍 URL: http://localhost:{port}")
    print(f"📖 Docs: http://localhost:{port}/")
    print()
    print("⏸️  Press CTRL+C to stop")
    print()
    
    # Run
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Under Gunicorn, lazily initialize on first request via get_chatbot().
    # This avoids hard startup failures if external services are temporarily unavailable.
    pass
