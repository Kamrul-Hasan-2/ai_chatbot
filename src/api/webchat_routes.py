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
    from controllers.chat_controller import _process_user_message
except ImportError:
    from src.controllers.chat_controller import _process_user_message

try:
    import markdown as _markdown
except ImportError:
    _markdown = None

logger = logging.getLogger(__name__)

webchat_bp = Blueprint('webchat', __name__, url_prefix='/api/webchat')
webchat_docs_bp = Blueprint('webchat_docs', __name__)

_SESSION_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
_MESSAGE_MAX_LENGTH = 2000

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
            "error": "Too many messages — please slow down and try again shortly."
        }), 429

    data = request.get_json(silent=True) or {}
    raw_session_id = str(data.get('session_id') or '').strip()
    message = str(data.get('message') or '').strip()

    if not message:
        return jsonify({"success": False, "error": "No message provided"}), 400

    if len(message) > _MESSAGE_MAX_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Message too long (max {_MESSAGE_MAX_LENGTH} characters)"
        }), 400

    if not _SESSION_ID_PATTERN.match(raw_session_id):
        return jsonify({"success": False, "error": "Invalid or missing session_id"}), 400

    # Namespace web session ids so they can never collide with a Facebook PSID
    # (always numeric) and cross-pollute another channel's conversation state.
    user_id = f"web_{raw_session_id}"

    try:
        result = _process_user_message(
            user_id=user_id,
            message=message,
            source='webchat',
            user_name=None,
            platform_id='web'
        )
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
    Sends a real request to <code>POST /api/webchat/message</code> on this
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

    fetch('/api/webchat/message', {
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
