# BDStall AI Chatbot — Project Documentation

A Flask-based Bangla/Banglish/English AI chatbot for BDStall.com (Bangladeshi e-commerce marketplace).
Handles product search, ordering, delivery, FAQ, technical advice, and human handoff
across Facebook Messenger, web, and direct API channels.

---

## 1. What this project does

The chatbot answers customer questions in Bangla on BDStall.com's Facebook page and
website. It understands three input forms equally well:

- **Bangla** — "আমাকে ২০ হাজার টাকার মধ্যে মোবাইল দেখান"
- **Banglish** (romanised Bangla) — "amake 20k er modde mobile dekhao"
- **English** — "show me mobiles under 20k"

For every user message, the bot:

1. Loads the user's recent conversation context from the BDStall history API. -- conflict
2. Sends the message to **Groq LLM** (`llama-3.3-70b-versatile`) to classify intent
   and extract entities (category, brand, title, price range).
3. Dispatches the message to a per-intent handler that builds a **formatted Bangla
   reply** — no LLM is used for the visible answer, except for the `technical_advice`
   (knowledge) intent which is rate-limited.
4. Searches BDStall product APIs when the intent is product-related.
5. Persists the conversation turn via the BDStall save-message API and returns
   the reply (with optional Facebook Messenger button card payload).

When the bot is uncertain or the user is abusive/asks for a human, the conversation
is handed off to a human agent via the BDStall responder API.

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          External clients                               │
│      Facebook Messenger    Web chat UI    Direct API (Postman)          │
└────────┬─────────────────────┬──────────────────┬──────────────────────┘
         │                     │                  │
         ▼                     ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  src/controllers/chat_controller.py        (Flask app + routes)         │
│  ─ /webhook       Facebook Messenger webhook                            │
│  ─ /chat          Web/Postman chat endpoint                             │
│  ─ /agent/reply   Manual human agent message                            │
│  ─ /mode/<uid>    Read / switch AI ↔ HUMAN mode                         │
│  ─ /health        Liveness                                              │
└────────┬────────────────────────────────────────────────────────────────┘
         │ process_message(user_id, message)
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  src/services/chatbot_service.py            (orchestrator)              │
│                                                                         │
│  STEP 1  load_context (DB)                                              │
│  STEP 2  detect_intent (Groq)                                           │
│  STEP 3  merge_context + category/intent reset                          │
│  STEP 4  dispatch to a handler in intent_handlers_service               │
│  STEP 5  build response (mode = ai | human)                             │
└────────┬────────────────────────────────────────────────────────────────┘
         │
   ┌─────┼─────────────────────────────────────────────────────┐
   │     │                                                     │
   ▼     ▼                                                     ▼
┌──────────────┐                                       ┌─────────────────┐
│ services/    │                                       │ repositories/   │
│  intent_     │                                       │  state_         │
│  service     │   Groq client, intent merging         │  repository     │
│  intent_     │   per-intent business logic           │   in-memory +   │
│  handlers_   │   (handle_buy, handle_product_search) │   chatbot_      │
│  service     │                                       │   state.json    │
│  api_client_ │   BDStall REST API client             │                 │
│  service     │   (search, save_message, history…)    └─────────────────┘
└──────────────┘
```

Key principles:

- **The BDStall history API is the source of truth for `intent_content`.** Local
  state holds only in-session data (last cached product list, last intent string,
  per-user knowledge counter).
- **One LLM call per user turn at most.** Intent detection uses Groq. Almost all
  replies are formatted Bangla strings; only `technical_advice` calls Groq again
  to generate an answer, and that call is rate-limited to 5/user/day.
- **Single Gunicorn worker by default** (`config/gunicorn_config.py`). Multiple
  workers would split per-user in-memory state across processes; if you scale
  horizontally, move state to Redis first.

---

## 3. Repository layout

```
ai_chatbot/
├── run.py                          # Local dev launcher (Flask dev server)
├── start_gunicorn.sh               # Production launcher (Gunicorn)
├── deploy_production.sh            # Full server deploy (systemd + nginx)
├── Dockerfile + docker-compose.yml # Container build
├── requirements.txt                # Python dependencies (Flask, Groq, …)
├── .env                            # Secrets — never commit
├── .env.example                    # Template for required vars
│
├── config/
│   ├── gunicorn_config.py          # Worker count, logs, bind address
│   ├── chatbot.service             # systemd unit file template
│   ├── nginx.conf                  # Reverse-proxy config (HTTPS)
│   └── nginx_no_ssl.conf           # Reverse-proxy config (plain HTTP)
│
├── src/
│   ├── api/
│   │   └── app_simple.py           # Compat shim → controllers/chat_controller
│   │
│   ├── controllers/
│   │   └── chat_controller.py      # Flask routes + Facebook webhook handling
│   │
│   ├── services/
│   │   ├── chatbot_service.py      # process_message orchestrator
│   │   ├── intent_service.py       # Groq call + intent validation + merge
│   │   ├── intent_handlers_service.py  # One function per intent
│   │   ├── api_client_service.py   # BDStall REST API calls + caches
│   │   ├── humanizer_service.py    # (disabled — formatted answers only)
│   │   └── category_validator_service.py
│   │
│   ├── repositories/
│   │   └── state_repository.py     # In-memory + JSON-persisted state
│   │
│   ├── models/
│   │   └── chatbot_config.py       # Constants, API URLs, Groq prompt template
│   │
│   └── utils/
│       ├── user_profile.py         # Rolling per-user behavioural profile
│       ├── conversation_context.py
│       ├── product_link_handler.py
│       └── product_details_handler.py
│
├── data/                           # Runtime state (gitignored)
│   ├── chatbot_state.json          # Per-user in-session state
│   ├── lite_clients.json           # Facebook Lite sender IDs
│   └── user_names.json             # Cached Messenger display names
│
├── logs/                           # Daily rotating logs
│   ├── api_calls_YYYY-MM-DD.log    # Outbound BDStall API calls
│   ├── access.log                  # Gunicorn HTTP access log
│   └── error.log                   # Gunicorn error log
│
└── tests/                          # pytest suite (45 tests)
    ├── test_humanizer.py
    ├── test_overrides.py
    └── test_user_profile.py
```

---

## 4. Conversation flow (one turn end-to-end)

### Step 0 — Inbound request

- **Facebook**  → `/webhook` POST receives a Messenger payload. The controller
  extracts `sender_id` + `message.text`, then calls `_process_user_message()`.
- **Web / API** → `/chat` POST with `{user_id, message}`.

Either route lands in the same orchestrator: `chatbot_service.process_message()`.

### Step 1 — Pre-Groq intercepts

Before calling Groq, the orchestrator checks several fast deterministic rules:

| Check | What it does |
|---|---|
| **Automated-template guard** | If the message looks like the auto-reply template BDStall sends ("Thank you for your message…"), it's ignored. |
| **Human mode check** | `check_responder_type(user_id)` — if the user is already assigned to a human agent, AI is skipped and the bot stays silent. |
| **URL in message** | If the message contains a BDStall product URL, it goes straight to `handle_url_message`. |
| **Self-reference buy** | "এইটা অর্ডার দিতে চাই" + cached products → `handle_buy` directly. |
| **Generic buy phrase** | Short messages like "ami order korte chai", "kinte chai" → `handle_buy` directly. |
| **Product detail follow-up** | If a product URL is pinned (or just shown), questions like "ki ki color", "ram koto" → `handle_product_detail_followup`. |
| **Clarification selection** | If the last bot reply asked "which one?", the user's number selection routes to `handle_clarification_selection`. |

If none of the intercepts match, we proceed to Groq.

### Step 2 — Intent detection via Groq

`intent_service.detect_intent()` calls Groq with:

- **System prompt** (`GROQ_SYSTEM_PROMPT_TEMPLATE` in `models/chatbot_config.py`) —
  describes 18 valid intents, gives spelling-tolerance hints (e.g., "laptp → laptop"),
  budget parsing rules, and 15 few-shot examples.
- **User prompt** — the last few history lines (limit 5, configurable via
  `CHATBOT_HISTORY_LIMIT`) plus the current message.
- **Required JSON schema** — `{intent, entities, missing, is_followup, confidence}`.

Groq returns one of these intents:
`product_search | price_query | comparison | buy | exit | delivery | greeting |
goodbye | thanks | complaint | faq | human_request | technical_advice |
hate_speech | product_link | seller_query | product_spec_query | unknown`.

### Step 3 — Strict intent guard

After Groq returns, the orchestrator enforces the strict policy:

```
if intent == 'unknown'
   OR (confidence < 0.55 AND no entities AND not a followup):
       assign_agent(user_id, 'unknown_intent')
       reply: "স্যার, আপনার মেসেজটি আমি ঠিকমতো বুঝতে পারিনি।
                আমাদের একজন প্রতিনিধি শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"
       mode  : HUMAN
       return
```

### Step 4 — Context merge and resets

`intent_service.merge_context()` combines Groq's extracted entities with the
previous turn's saved `intent_content`. Several deterministic resets run here:

- **Greeting** ("hi", "hello", "salam") → clear category and product cache.
- **Category switch** — if Groq returned a different category than the saved
  session category, clear product cache and category fields.
- **Intent change** — if the new intent differs from the last bot intent and
  isn't a follow-up, clear cached products so a new intent never gets answered
  using stale product state.
- **Pure budget refinement** ("20k modde") — inherit previous category, drop
  any stale title.

### Step 5 — Dispatch to handler

`_dispatch()` maps the intent to a handler in
`intent_handlers_service.py`. Each handler returns:

```python
{
  'response':       str,           # Bangla reply text
  'intent':         str,           # outgoing intent name (may differ from input)
  'intent_content': dict,          # gets persisted to BDStall as JSON
  'products':       list,          # cached for the next turn
  'link_buttons':   list,          # Messenger button card payload
}
```

### Step 6 — Mode selection and response build

```
HANDOFF_INTENTS = {unknown_handoff, knowledge_limit_exceeded,
                   seller_query, hate_speech, explicit_human_request,
                   complaint_handoff}

if handler returned a HANDOFF intent → ChatMode.HUMAN  +  HUMAN_SUPPORT_REQUIRED_STATUS
else                                  → ChatMode.AI    +  AI_ACTIVE_STATUS
```

The controller then **persists both messages** (visitor + bot) to BDStall via
`save_chat_message()` and (for Facebook) sends the reply to Messenger via the
Graph API. Facebook Lite clients get plain-text + URL instead of button cards.

---

## 5. Intent catalogue

| Intent | Handler | Channel of answer |
|---|---|---|
| `greeting` | `handle_greeting` | Static Bangla template + session reset |
| `goodbye` | `handle_goodbye` | Static template |
| `thanks` | `handle_thanks` | Static template |
| `exit` | `handle_exit` | Static template ("পরে কিনব") |
| `buy` / `ordering` | `handle_buy` | 3-step purchase instructions + "প্রোডাক্ট দেখুন" button |
| `comparison` | `handle_comparison` | Top cached product as recommendation |
| `delivery` | `handle_delivery` | `fetch_delivery_template()` API or FAQ row |
| `faq` | `handle_faq` | FAQ DB lookup (Bangla + English question fields) |
| `human_request` | handoff | `assign_agent()` + Bangla notice |
| `seller_query` | handoff | `assign_agent()` + Bangla notice |
| `hate_speech` | handoff | `assign_agent()` + polite warning |
| `complaint` | inline | Trimmed return-policy excerpt (no Groq summary) |
| `product_search` | `handle_product_search` | `search_products()` BDStall API → top 3 cards |
| `price_query` | `handle_price_query` | Cached products price list OR fresh search |
| `product_spec_query` | `handle_product_spec_query` | Structured `fetch_product_spec()` keyword match. Falls back to rate-limited Groq if no structured match. |
| `technical_advice` | `handle_technical_advice` | **Groq-backed** (knowledge intent). Rate-limited to 5/user/day. |
| `product_link` | `handle_product_link` | Parses URL, returns title + price + buttons |
| `unknown` | strict handoff | `assign_agent()` + Bangla notice |

### Knowledge intent — the only Groq-backed answer

`handle_technical_advice` is the only handler that asks Groq to generate the
user-facing answer. To prevent abuse:

1. On every call, check `get_knowledge_count(user_id)` from
   `repositories/state_repository.py`.
2. If `>= KNOWLEDGE_DAILY_LIMIT` (default 5) → `assign_agent(user_id,
   'knowledge_limit_exceeded')` and reply with a Bangla "limit reached" notice.
3. Otherwise call Groq, and on success call `increment_knowledge_count(user_id)`.

The counter is keyed by `(user_id, YYYY-MM-DD)` and persists in
`data/chatbot_state.json` so it survives restarts. It auto-resets at midnight.

---

## 6. State, caches, and persistence

### In-memory (per process) — `repositories/state_repository.py`

| Dict | Purpose |
|---|---|
| `_product_context[uid]` | Last 5 products shown to the user. |
| `_product_url[uid]` | URL pinned for follow-up questions ("eta", "atar"). |
| `_last_intent[uid]` | Last intent string the bot replied with. |
| `_session_category[uid]` | The category for the active conversation. |
| `_pending_question[uid]` | The message that triggered a clarification prompt. |
| `_search_pool[uid]` / `_search_offset[uid]` | 15-product pool + offset for "show more". |
| `_user_profile[uid]` | Rolling behavioural profile (language, style, recent intents). |
| `_knowledge_count[uid]` | Knowledge calls today (date + count). |

### On disk — `data/chatbot_state.json`

Atomically written on every state change. Loaded at startup. Holds:

```json
{
  "user_product_context":  { "<uid>": [ ... ] },
  "user_last_intent":      { "<uid>": "product_search" },
  "user_session_category": { "<uid>": "laptop" },
  "user_profile":          { "<uid>": { ... } },
  "user_knowledge_count":  { "<uid>": {"date":"2026-05-21","count":3} }
}
```

This file is **gitignored** — never commit it, it's pure runtime data.

### External — BDStall APIs

| API | Used for |
|---|---|
| `…/api/chatbot/chatbot_history/` | Read last N messages + last `intent_content` (source of truth). |
| `…/api/chatbot/chatbot_save_message/` | Persist visitor + bot messages. |
| `…/api/chatbot/ai_search/` | Product search (term + min/max price). |
| `…/api/chatbot/cat_list/` | Canonical category list (cached). |
| `…/api/chatbot/ai_template/` | Delivery + condition templates. |
| `…/api/chatbot/chatbot_responder/` | Check / set AI vs human mode. |
| `…/api/chatbot/chatbot_assign_agent/` | Hand a user off to a human agent. |
| `…/api/chatbot/chatbot_assign_bot/` | Hand a user back to the AI. |
| `…/api/item/list_details/` | Structured product spec features. |
| `…/api/chatbot/knowledge/` | Buying terms / refund policy text. |

Outbound calls are logged to `logs/api_calls_YYYY-MM-DD.log` (one JSON line per call).

---

## 7. Configuration

Copy `.env.example` to `.env` and fill in:

```env
# Groq (intent detection + knowledge answers)
GROQ_API_KEY=gsk_xxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_ANSWER_MODEL=llama-3.3-70b-versatile

# BDStall APIs (defaults baked in — only override for staging)
BDSTALL_API_KEY=...
SEARCH_API_URL=https://www.bdstall.com/api/chatbot/ai_search/
CHATBOT_HISTORY_API_URL=https://www.bdstall.com/api/chatbot/chatbot_history/
CHATBOT_HISTORY_LIMIT=5

# Knowledge rate limit
KNOWLEDGE_DAILY_LIMIT=5

# Context expiry (seconds) — how stale a category/budget can be
# (set in models/chatbot_config.py as CONTEXT_TTL_SECONDS=1800)

# Facebook Messenger
PAGE_ACCESS_TOKEN=EAAxxxx
VERIFY_TOKEN=my_verify_token_12345
FACEBOOK_GRAPH_API_VERSION=v25.0

# Server
PORT=5000
GUNICORN_WORKERS=1            # keep at 1 — see config/gunicorn_config.py note
```

All config lives in `src/models/chatbot_config.py`. Nothing else reads
`os.getenv` directly — this is intentional, so you have one place to audit
secrets.

---

## 8. Running locally (Windows / dev)

```powershell
# 1. install deps
pip install -r requirements.txt

# 2. populate .env (see section 7)

# 3. run the dev server
python run.py
```

The server boots at `http://localhost:5000`. Quick smoke tests:

```powershell
# health
curl http://localhost:5000/health

# send a chat
$body = @{ user_id="test_user"; message="amake 30k er laptop dekhao" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:5000/chat -Method POST -Body $body -ContentType application/json
```

For Facebook Messenger testing, expose the local server with ngrok:

```powershell
ngrok http 5000
# In Facebook App → Messenger → Webhook, set:
#   Callback URL : https://<ngrok-id>.ngrok.io/webhook
#   Verify Token : my_verify_token_12345
#   Events       : messages, messaging_postbacks
```

---

## 9. Running tests

```powershell
python -m pytest tests/ -q
```

The suite has 45 tests covering Groq override logic, humanizer guards, and the
user profile. Tests run in under a second and never hit the network.

---

## 10. Production deployment

The production target is a Linux VM (Ubuntu/Debian) at
`/root/ai_services/ai_chatbot`, served by Gunicorn behind Nginx, managed by
systemd.

### 10.1 First-time deploy

```bash
# on the server, as root
cd /root/ai_services && git clone <repo-url> ai_chatbot
cd ai_chatbot
pip install -r requirements.txt
cp .env.example .env && nano .env       # fill in real keys
bash deploy_production.sh               # creates systemd unit + nginx site
```

### 10.2 Updating code

```bash
cd ~/ai_services/ai_chatbot
git stash push -- data/chatbot_state.json   # in case runtime state diverged
git pull
git stash drop
sudo systemctl restart chatbot
sudo journalctl -u chatbot -n 50 --no-pager
```

`data/chatbot_state.json` and `data/lite_clients.json` are gitignored — runtime
state should never block a pull. If it does, stash + drop as above.

### 10.3 Useful commands on the server

```bash
sudo systemctl status chatbot        # check it's running
sudo systemctl restart chatbot       # apply code change
sudo journalctl -u chatbot -f        # follow logs
tail -f logs/api_calls_*.log         # outbound API trace
tail -f logs/error.log               # Gunicorn errors
```

### 10.4 Docker

```bash
docker-compose up -d
```

The container runs `gunicorn -c config/gunicorn_config.py src.api.app_simple:app`
on port 5000.

---

## 11. HTTP API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Service info + endpoint list |
| `/health` | GET | Liveness probe |
| `/chat` | POST | Send a message and get a reply |
| `/agent/reply` | POST | Save a manual human-agent reply |
| `/save-message` | POST | Persist any sender_type (1=agent, 2=bot, 3=visitor) |
| `/webhook` | GET | Facebook webhook verification |
| `/webhook` | POST | Facebook webhook delivery |
| `/chatbot/webhook` | GET/POST | Same as `/webhook` (proxy-safe path) |
| `/mode/<user_id>` | GET | Read AI/HUMAN mode |
| `/mode/<user_id>/human` | POST | Switch to human |
| `/mode/<user_id>/ai` | POST | Switch back to AI |
| `/debug/messenger` | GET | Show env / FB config (no secrets logged) |
| `/test` | GET | Built-in browser chat UI (loads `static/index.html`) |
| `/test` | POST | Same as `/chat` (legacy) |

### Sample `/chat` request

```json
POST /chat
{
  "user_id": "fb_id_8123456789",
  "message": "ami 30k er modde laptop dekhao"
}
```

### Sample reply

```json
{
  "success": true,
  "user_id": "fb_id_8123456789",
  "user_name": "User 456789",
  "message": "ami 30k er modde laptop dekhao",
  "response": "স্যার, ৳30,000 এর মধ্যে এই প্রোডাক্টগুলো দেখতে পারেন:\n\n1. ...",
  "mode": "ai",
  "intent": "product_search",
  "intent_content": { "cat": "laptop", "brand": "", "price_max": 30000, ... },
  "products": [ { "title": "...", "price": "...", "url": "..." }, ... ],
  "link_buttons": [ { "text": "1. দেখুন", "url": "..." }, ... ],
  "processing_time": 0.92
}
```

`mode` is either `"ai"` or `"human"`. When it is `"human"`, the client should
stop showing AI replies for this user until a human agent posts via
`/agent/reply` and the user is switched back.

---

## 12. Language policy

**All bot-generated text must be Bangla.** This is enforced everywhere:

- Every static template in `intent_handlers_service.py` is Bangla.
- Every button label (`'প্রোডাক্ট দেখুন'`, `'বিডিস্টলে দেখুন'`, `'1. দেখুন'`).
- The humanizer is intentionally disabled in `chatbot_service._build_response`
  so no Groq-generated English ever leaks into a reply.
- The Groq prompt for `technical_advice` instructs: "reply in the SAME language
  the user used" — combined with the rate limit, this stays in Bangla because
  customer messages are in Bangla.

If you find an English string in a user-facing response, that's a bug — fix
the template directly.

---

## 13. Common troubleshooting

### `git pull` fails on `data/chatbot_state.json`

The file is tracked-and-modified on the server. Either:

```bash
git stash push -- data/chatbot_state.json && git pull && git stash drop
```

…or untrack it once and for all:

```bash
git rm --cached data/chatbot_state.json
# .gitignore already lists it — commit and push
```

### "Same products keep showing for a new question"

The product cache wasn't cleared. Check that:

1. The new intent isn't being detected as `is_followup=true` by Groq.
2. The category change reset is firing — look for `"intent change … —
   clearing product context"` in the logs.
3. If a user keeps getting old products, send them "hi" — greeting handler
   explicitly clears all state.

### "Bot is silent on Facebook"

The user is in HUMAN mode. Check:

```bash
curl http://localhost:5000/mode/<sender_id>
```

If it returns `{"mode":"human"}`, either a human agent should reply, or you
can flip back to AI:

```bash
curl -X POST http://localhost:5000/mode/<sender_id>/ai
```

### "Knowledge questions stopped working"

The user hit their 5/day limit. They've been handed off to a human. To reset
for testing, edit `data/chatbot_state.json` and remove their entry from
`user_knowledge_count`, then restart the service.

### "Buttons say 'unavailable' in Facebook Lite"

FB Lite doesn't render button templates. The first failure is detected, the
sender ID is recorded in `data/lite_clients.json`, and from then on the bot
sends plain text with URLs to that user.

### "Groq is rate-limiting us"

Set a lower `KNOWLEDGE_DAILY_LIMIT` and add a cache layer for the
`detect_intent` call (the conversation history rarely changes turn-to-turn).
Today there is **no** intent-detection cache — every visitor turn calls Groq
once.

---

## 14. How to extend the bot

### Add a new intent

1. Add the intent name to `VALID_INTENTS` in
   `src/models/chatbot_config.py`.
2. Add an `INTENT DEFINITION` block + a few-shot example in
   `GROQ_SYSTEM_PROMPT_TEMPLATE` (same file).
3. Write a `handle_<intent>` function in
   `src/services/intent_handlers_service.py` returning
   `{response, intent, intent_content, products, link_buttons}`.
4. Wire it into `_dispatch()` in `src/services/chatbot_service.py`.
5. Add a test in `tests/`.

### Add a new template phrase

Edit the relevant string in `intent_handlers_service.py`. Bangla only. No
emoji unless the existing template uses one. Keep the `LOOP_BACK` suffix
appended to informational answers so the user is invited to continue.

### Add a new BDStall API call

1. Add the URL constant in `src/models/chatbot_config.py` (with `os.getenv`
   override).
2. Add a thin wrapper in `src/services/api_client_service.py` that calls
   `requests.get/post`, logs via `_log_api_call`, and returns a parsed dict.
3. Call it from the relevant handler.

---

## 15. Key files at a glance

| File | What lives here |
|---|---|
| `src/models/chatbot_config.py` | All constants, API URLs, Groq prompt template, knowledge daily limit. |
| `src/services/chatbot_service.py` | `process_message()` orchestrator, dispatch table, handoff intents. |
| `src/services/intent_service.py` | `detect_intent()` Groq call, `merge_context()`, post-Groq overrides. |
| `src/services/intent_handlers_service.py` | One function per intent — the answer templates. |
| `src/services/api_client_service.py` | All HTTP to BDStall + history/intent caches. |
| `src/repositories/state_repository.py` | In-memory dicts + JSON persistence + knowledge counter. |
| `src/controllers/chat_controller.py` | Flask routes, Facebook webhook, Messenger send/payload helpers, FB Lite detection. |
| `config/gunicorn_config.py` | Worker count = 1 (state lives in-process). |
| `data/chatbot_state.json` | Runtime state — gitignored. |
| `logs/api_calls_*.log` | One JSON line per outbound API call. |

---

## 16. Glossary

- **Banglish** — Bangla written in Latin letters (e.g., "ami laptop dekhi").
- **Intent** — The kind of thing the user wants (search a product, ask a
  delivery question, complain, etc.).
- **Entities** — Structured fields extracted from the message (category,
  brand, title, price range).
- **intent_content** — The JSON we save to BDStall per turn. The next turn's
  `load_context()` reads it back to remember what the user was talking about.
- **Follow-up (`is_followup`)** — A turn that depends on the previous turn's
  topic ("আরও দেখান", "ram koto"). Follow-ups don't reset cached products.
- **FB Lite** — Facebook's lightweight client. Doesn't support button cards;
  needs plain-text + URL fallback.
- **Handoff** — Switching the conversation to a human agent via
  `assign_agent()`.

---

Last updated: 2026-05-21
