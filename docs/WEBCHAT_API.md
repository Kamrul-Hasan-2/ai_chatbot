# BDStall Chatbot — Website Webchat API

This document is the **integration contract for the frontend team** building
live chat into the BDStall website. It describes the new backend endpoint
only — there is no bundled UI/widget to embed; the frontend builds its own
chat interface against this API.

> Source of truth: `src/api/webchat_routes.py`.

---

## Table of contents

1. [What this is](#1-what-this-is)
2. [Design constraint: the Messenger code is frozen](#2-design-constraint-the-messenger-code-is-frozen)
3. [Base URL](#3-base-url)
4. [Endpoint: POST /api/webchat/message](#4-endpoint-post-apiwebchatmessage)
5. [Session id: frontend responsibilities](#5-session-id-frontend-responsibilities)
6. [Rendering the response](#6-rendering-the-response)
7. [Errors](#7-errors)
8. [Rate limiting](#8-rate-limiting)
9. [CORS](#9-cors)
10. [Optional: persisting a frontend-rendered welcome message](#10-optional-persisting-a-frontend-rendered-welcome-message)
11. [Examples](#11-examples)

---

## 1. What this is

A single new endpoint, `POST /api/webchat/message`, that runs a website chat
message through the **exact same AI pipeline** the Facebook Messenger bot
uses: same intent detection, same product search, same order flow, same
Bangla-only reply rule, same BDStall message-history persistence. The
frontend team is free to build whatever chat UI they want (bubble, sidebar,
full page) — this doc only covers the request/response contract.

---

## 2. Design constraint: the Messenger code is frozen

All Facebook Messenger logic — webhook verification, HMAC signature checks,
Send API calls, FB Lite fallback, message dedup — lives in
`src/controllers/chat_controller.py`. Per project instructions in
`CLAUDE.md`, that file must not be edited without explicit permission, and a
`.claude/settings.json` `permissions.ask` rule enforces this at the tool
level.

The webchat endpoint honours this by construction: `src/api/webchat_routes.py`
**imports** (never edits) the existing platform-agnostic pipeline function
`_process_user_message(...)` from `chat_controller.py`. `git diff
src/controllers/chat_controller.py` is empty — verified as part of building
this feature.

Registration is a 3-line addition to `src/api/app_simple.py` (the production
entrypoint used by both `run.py` and Gunicorn/Docker), not to
`chat_controller.py`.

---

## 3. Base URL

| Environment | Base URL |
|---|---|
| Local dev | `http://localhost:5000` |
| Production | `https://ai.bdstall.com/chatbot` |

Production is reverse-proxied by nginx under a `/chatbot` prefix — the same
box also serves an unrelated app at the domain root. **Every route in this
document must include that prefix in production**, e.g. the message endpoint
is:

```
https://ai.bdstall.com/chatbot/api/webchat/message
```

Calling `https://ai.bdstall.com/api/webchat/message` (without `/chatbot`)
hits the other service instead and returns a 404 — this has bitten us during
testing, so it's worth double-checking whenever a request 404s unexpectedly.

Because the frontend (`www.bdstall.com` or wherever it's hosted) is a
different origin than `ai.bdstall.com`, **use the full base URL above**, not
a relative path like `/api/webchat/message` — a relative path only works
when the calling page is itself served from `ai.bdstall.com/chatbot/...`,
which the real frontend won't be. CORS is already open (§9), so the
cross-origin call itself is not a problem.

---

## 4. Endpoint: POST /api/webchat/message

**Request**

```json
{
  "session_id": "a1b2c3d4e5f6...",
  "message": "১০ হাজার টাকার মধ্যে ল্যাপটপ দেখান"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string | yes | Frontend-generated. `[A-Za-z0-9_-]`, 1–64 chars. See §5. |
| `message` | string | yes | The user's message. Max 2000 characters. |

**Response — 200**

```json
{
  "response": "১০ হাজার টাকার মধ্যে এই ল্যাপটপগুলো দেখতে পারেন...",
  "mode": "ai",
  "intent": "product_search",
  "intent_content": { "cat": "laptop", "price_max": 10000, "...": "..." },
  "conversation_status": "AI Active",
  "products": [ { "title": "...", "url": "...", "...": "..." } ],
  "link_buttons": [ { "text": "View this link", "url": "https://www.bdstall.com/..." } ],
  "processing_time": 1.235,
  "user_name": "User 567890",
  "platform_id": "web"
}
```

| Field | Always present? | Notes |
|---|---|---|
| `response` | yes | Bot reply text, always in Bangla. Can be `""` on a silent turn (e.g. human-mode handoff) — render nothing in that case. |
| `mode` | yes | `"ai"` or `"human"`. |
| `intent` | yes | Internal intent label (e.g. `product_search`, `greeting`, `order_status`). |
| `intent_content` | yes | Normalized context (category/brand/title/budget). Mostly for debugging/analytics. |
| `conversation_status` | yes | Human-readable status string. |
| `products` | yes | List of matched products; often `[]`. |
| `link_buttons` | only if present | `{text, url}` pairs to render as clickable links/buttons when the reply references a product/category page. |
| `processing_time` | yes | Seconds, server-side. |
| `user_name` | yes | Best-known display name for this session (falls back to a generated placeholder). |
| `platform_id` | yes | Always `"web"` for this endpoint. |

This response shape matches exactly what the shared pipeline actually
returns today (see `_build_response()` in `src/services/chatbot_service.py`)
— no extra keys are invented, so treat any field not listed above as
undefined/absent rather than assuming it exists.

---

## 5. Session id: frontend responsibilities

The frontend must generate a random id per visitor (e.g.
`crypto.randomUUID()`) and persist it (e.g. `localStorage`) so a returning
visitor's conversation continues. Send the **same raw id** on every request
in `session_id` — do not add any prefix.

The server never trusts this id verbatim: it validates the format and
**always** namespaces it internally as `web_<session_id>` before using it as
the conversation's user id. This guarantees a webchat session can never
collide with a Facebook Messenger user id (Messenger PSIDs are purely
numeric), so it can never read or pollute another channel's conversation
state, mode, or history — regardless of what a client sends.

If you also need to reference this same conversation elsewhere (e.g. calling
`/save-message`, see §10), use `web_<session_id>` — the same prefix the server
applies internally — so both write to the same underlying conversation.

---

## 6. Rendering the response

- Render `response` as plain text (it may contain literal `\n` line breaks).
  Do **not** render it as HTML — it is untrusted user-visible text end to
  end, so use a text-only rendering path (e.g. React's default text
  interpolation, `textContent`), never `innerHTML`/`dangerouslySetInnerHTML`.
- When `link_buttons` is present and non-empty, render each `{text, url}` as
  a link/button opening `url` (e.g. `target="_blank" rel="noopener
  noreferrer"` on web).
- When `response` is `""`, show nothing for that turn (this represents a
  silent bot turn, e.g. while a human agent has taken over — see `mode`).

---

## 7. Errors

| Status | Cause | Body |
|---|---|---|
| `400` | Missing/empty `message`, message over 2000 chars, or missing/invalid `session_id` | `{"success": false, "error": "..."}` |
| `429` | Per-IP rate limit exceeded (§8) | `{"success": false, "error": "Too many messages — please slow down and try again shortly."}` |
| `500` | Unexpected server error | `{"success": false, "error": "...", "response": "দুঃখিত, এই মুহূর্তে উত্তর দিতে সমস্যা হচ্ছে। অনুগ্রহ করে আবার চেষ্টা করুন।", "mode": "human"}` — safe to render `response` directly to the user as a fallback bubble. |

---

## 8. Rate limiting

The endpoint enforces an in-memory per-IP limit of **20 requests/minute**,
returning `429` beyond that. Design the frontend to disable the send
button/input while a request is in flight rather than allowing rapid
re-sends, and surface a friendly message on `429` (e.g. "please wait a
moment").

---

## 9. CORS

CORS is open on the whole Flask app (`CORS(app)`, no origin allowlist), so
this endpoint can be called from the BDStall website domain or any other
origin without additional configuration.

---

## 10. Optional: persisting a frontend-rendered welcome message

If the frontend renders a static greeting bubble on chat open *without*
calling `/api/webchat/message` (common — no need to spend an AI call on a
canned greeting), persist it to BDStall's message history so the
conversation looks complete in any admin/agent dashboard that reads that
history, using the existing (unmodified) endpoint:

```
POST /save-message
{ "user_id": "web_<session_id>", "sender_type": 2, "message": "<greeting text>" }
```

`sender_type: 2` means "Bot". Use the same `web_<session_id>` id described
in §5 so this message lands in the same conversation the AI-pipeline
messages use.

---

## 11. Examples

**curl — local dev**

```bash
curl -X POST http://localhost:5000/api/webchat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id":"a1b2c3d4e5f6","message":"Hi"}'
```

**curl — production**

```bash
curl -X POST https://ai.bdstall.com/chatbot/api/webchat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id":"a1b2c3d4e5f6","message":"Hp g3 laptop ase"}'
```

Verified working — this exact request (session id, product-search message,
and the full `/chatbot/...` production URL from §3) returned a real 200 with
matching HP laptop results and prices.

**Frontend fetch**

Always call the full production base URL from §3 — the frontend runs on a
different origin than `ai.bdstall.com`, so a relative path like
`/api/webchat/message` will not resolve correctly from the real site.

```js
const WEBCHAT_BASE_URL = 'https://ai.bdstall.com/chatbot';

async function sendWebchatMessage(sessionId, message) {
  const res = await fetch(`${WEBCHAT_BASE_URL}/api/webchat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Request failed (${res.status})`);
  }
  return res.json();
}
```

---

*This document reflects the behaviour implemented in the current codebase.
When the code changes, update the relevant section here.*
