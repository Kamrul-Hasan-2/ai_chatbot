"""
Simple API - Following Your Roadmap
Cleaner, simpler implementation
"""
import os
import sys
import logging
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from datetime import datetime
from typing import Optional

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import simple chatbot
from core.simple_chatbot_flow import SimpleChatbot

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


def send_facebook_message(recipient_id: str, message_text: str) -> bool:
    """Send a plain text response to a Facebook Messenger user."""
    if not PAGE_ACCESS_TOKEN:
        logger.warning("PAGE_ACCESS_TOKEN not set; cannot send Messenger reply")
        return False

    url = f"https://graph.facebook.com/v25.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": {"text": message_text}
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if 200 <= response.status_code < 300:
            logger.info("✅ Messenger reply sent to %s", recipient_id)
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


def _process_user_message(
    user_id: str,
    message: str,
    source: str = "web",
    user_name: Optional[str] = None
) -> dict:
    """Run the same chatbot pipeline for web and Messenger inputs."""
    clean_message = (message or '').strip()
    resolved_user_name = (user_name or '').strip() or get_known_user_name(str(user_id))
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
                if send_facebook_message(sender_id, response_text):
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
        data = request.get_json() or {}
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
