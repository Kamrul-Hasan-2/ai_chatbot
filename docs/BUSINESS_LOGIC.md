# BDStall Chatbot — Business Logic

This document describes the **business logic that is actually implemented** in the
BDStall Facebook Messenger chatbot. It is a behavioural reference (rules, flows,
decisions), not an API reference. Bangla strings are quoted where they are the
real user-facing copy.

> Source of truth: `src/services/`, `src/models/chatbot_config.py`,
> `src/repositories/state_repository.py`, `src/controllers/chat_controller.py`,
> `src/services/order_handler.py`.

---

## Table of contents

1. [What the bot is](#1-what-the-bot-is)
2. [Global rules](#2-global-rules)
3. [Request pipeline (high level)](#3-request-pipeline-high-level)
4. [Deterministic pre-Groq intercepts](#4-deterministic-pre-groq-intercepts)
5. [Intent detection (Groq + fallback)](#5-intent-detection-groq--fallback)
6. [Context & state management](#6-context--state-management)
7. [Intent handlers (per-intent behaviour)](#7-intent-handlers-per-intent-behaviour)
8. [Product search subsystem](#8-product-search-subsystem)
9. [Order placement flow](#9-order-placement-flow)
10. [Order status](#10-order-status)
11. [Knowledge / technical advice](#11-knowledge--technical-advice)
12. [Human handoff rules](#12-human-handoff-rules)
13. [Channel behaviour (Messenger webhook)](#13-channel-behaviour-messenger-webhook)
14. [External APIs](#14-external-apis)
15. [Key configuration values](#15-key-configuration-values)

---

## 1. What the bot is

A virtual assistant for **BDStall.com** (a Bangladeshi online e-commerce
marketplace). It answers product, price, delivery, order, and policy questions
over Facebook Messenger, runs a buy/order flow, and hands off to human agents for
things it should not answer. It understands **English, Bangla, and Banglish
(romanised Bangla)** equally.

The platform is **online-only** — there is no physical showroom; the bot says so
when asked.

---

## 2. Global rules

- **Bangla-only replies.** All user-facing copy is Bangla. The one generative path
  (technical advice via Groq) is explicitly forced to reply in pure Bangla even
  when the user writes in English/Banglish.
- **Facts come from the API, never invented.** Prices, specs, availability,
  warranty, and order data are always read from the BDStall API or from cached API
  product data. When a value is missing the bot redirects to the product page /
  website rather than guessing.
- **Groq's role is limited.** Groq is used for (a) intent + entity *classification*
  and (b) general knowledge/advice answers. It is **not** used to state product
  facts; the spec path constrains Groq to the product's own review text and makes
  it answer `NOT_FOUND` rather than use training knowledge.
- **Deterministic before AI.** A long chain of rule-based intercepts runs *before*
  Groq so common intents (greeting, order status, payment FAQ, etc.) never depend
  on the LLM and survive a Groq outage.
- **Loop-back.** Most informational replies end with
  `"আর কোনো প্রোডাক্ট বা বিষয়ে সাহায্য করতে পারি? 😊"`.
- **When unsure, escalate — don't guess.** Truly unclassifiable messages are handed
  to a human rather than answered speculatively.

---

## 3. Request pipeline (high level)

Entry point: `chatbot_service.process_message(user_id, message)`.

1. **Load user profile** (rolling behavioural profile) up front.
2. **STEP 1 — Load context** from the DB (`load_context`): the last saved
   `intent_content` (category/brand/title/budget) — one DB round-trip per request.
3. **Deterministic pre-Groq intercepts** (§4) — each can answer and return early.
4. **STEP 2 — Detect intent** with Groq (`detect_intent`), then apply deterministic
   post-Groq overrides and category resolution.
5. **Strict low-confidence handoff gate** (§12).
6. **STEP 3 — Merge context** (`merge_context`): category-switch reset, inheritance,
   budget follow-up, intent promotion.
7. **STEP 4 — Dispatch** to the matching intent handler.
8. **STEP 5 — Build response**: flag human-handoff intents into HUMAN mode;
   everything else stays in AI mode. Persist last intent + update the profile.
9. **Global safety net:** any exception returns a fixed Bangla apology
   (intent `system_error`) so the user is never left with a crash.

---

## 4. Deterministic pre-Groq intercepts

These run **in order**, before Groq. Each catches a specific kind of message and
returns immediately. All stay in **AI mode** unless marked **HANDOFF**.

| # | Intercept | Triggers on | Business response |
|---|-----------|-------------|-------------------|
| 1 | **Automated-template block** | The bot's own auto-reply text (≥2 of the known welcome/“thanks”/“representative will contact” phrases) | Stays silent (won't reply to its own messages). |
| 2 | **Human/agent-mode silence** | Conversation is assigned to a human agent (`responder == 'agent'`) | Empty reply, mode HUMAN — the bot stays silent while a human owns the chat. |
| 3 | **Order-flow pump** | User is mid-order (collecting name/mobile/address/etc.) | Routes the message into the order state machine (§9). |
| 4 | **Advance payment** | "অগ্রিম", "agrim", "আগে টাকা", "upfront", "advance"… | Answers the advance-payment policy (only outside-Dhaka delivery needs advance). |
| 5 | **Payment method / COD** | "cash on delivery", "bkash", "nagad", "payment", word-bounded "cod" | Fixed reply: inside Dhaka → cash on delivery; outside Dhaka → advance only. |
| 6 | **Order-status lookup** | (a) we previously asked for an order ID, or (b) an order word + an order number / status / "show-me" marker (and **not** a buy marker) | Looks up the order; if no number is present, asks for the order ID and remembers it so the next message (the bare ID) is looked up. |
| 7 | **Suggestion / "which is best"** | "সাজেশন", "কোনটা ভালো", "konta valo/kinbo", "recommend", "which is best" (phrases only) | "আমি Virtual Assistant, তাই সাজেশন নয়, তথ্যভিত্তিক সহায়তা দিতে পারি।" — refuses to pick a "best". Placed **before** the buy intercept so "konta kinbo" isn't treated as buy. |
| 8 | **Shop / showroom visit** | A shop word (shop/দোকান/showroom/office/store) **+** a physical come/go verb (eshe/asbo/jabo/visit/in person) | Explains BDStall is online-only; no physical shop to visit. (Buy/see verbs are excluded so "office er jonno laptop kinbo" is not hijacked.) |
| 9 | **Product authenticity** | "nokol", "fake", "duplicate", "vejal", "master copy", "asol na nokol" | "আমাদের এখানের সকল প্রোডাক্টই ভালো, তবে কেনার আগে অবশ্যই দেখে নিবেন।" Never hands off. |
| 10 | **Picture / image reference** | The message is just a picture word, or a picture word + a "sent" marker (দিয়েছি/পাঠিয়েছি/attach) | Bot can't read images → asks for the product name + model in text. |
| 11 | **Business / partnership (B2B)** | "leads share", "affiliate", "reseller", "dealership", "distributor", "partnership", "franchise", "b2b", "company share" | **HANDOFF** — a representative will contact you (these are unambiguous B2B asks). |
| 12 | **Greeting** | Message is exactly a greeting token (hi/hello/salam/আসসালামু আলাইকুম) | Greets and resets the session. Deterministic so a Groq outage never sends greeters to a human. |
| 13 | **URL in message** | Any `http(s)://…` | Treats it as a product link (with any budget mentioned alongside). |
| 14 | **Self-reference buy** | A self-reference word ("এইটা"/"this") + a buy word + cached products | Starts the buy flow on the cached product. |
| 15 | **Generic buy/order** | Short (≤40 char) purchase phrase ("kinbo", "order korbo", "kinte chai") | Starts the buy flow; asks which product if several are cached. |
| 16 | **Clarification selection** | Last bot turn asked "which one?" (`product_clarification`) | Resolves the numbered/named pick and answers the originally-pending question. Runs **before** the detail follow-up so "1" isn't misread. |
| 17 | **Product-detail follow-up** | A product is in focus (pinned or cached) | Answers a follow-up about that product (warranty/price/spec/condition…), or defers to the full pipeline for a new search. |

> **Note:** the ordering is load-bearing and intentional (e.g. suggestion before
> buy; clarification before detail-follow-up; word-boundary/phrase matching to
> avoid collisions like "shop" inside "shopping"). Pagination ("aro dekhan") is
> handled inside `handle_product_search` (search-pool rotation), not as a separate
> pre-Groq intercept.

---

## 5. Intent detection (Groq + fallback)

### Intents the bot recognises

| Intent | Meaning |
|--------|---------|
| `product_search` | Wants to see/find/browse products ("ase", "dekhan", "lagbe", "chai"). |
| `price_query` | Asking the price/cost of a product or category. |
| `comparison` | "which is better" / "konta valo" / "সেরা কোনটা". |
| `buy` | **How** to buy / place an order (process question: "kivabe kinbo", "cod"). |
| `exit` | Deferring — "pore kinbo", "ekhon na", "later" (beats buy when "pore" precedes "kinbo"). |
| `delivery` | Delivery time / charge / process. |
| `greeting` / `goodbye` / `thanks` | Social messages. |
| `complaint` | Refund/return/broken/wrong-item/seller-not-responding. |
| `faq` | General site/policy questions. |
| `human_request` | Wants a human agent. |
| `technical_advice` | Product capability/compatibility/upgrade/performance, or a PC-build spec list for advice. |
| `product_spec_query` | A specific spec of the product **currently on screen** ("koto gb ram"). |
| `seller_query` | Wants to **sell** / list items / open a shop / register as vendor. |
| `hate_speech` | Abuse, insults, threats. |
| `unknown` | Cannot determine. |

### How detection works

- **Groq** receives a strict JSON-extraction prompt and returns
  `{intent, entities{category,brand,title,price_max,price_min}, missing, is_followup, confidence}`
  at `temperature 0.0`, JSON-only. Spelling tolerance is built in (laptp→laptop,
  samsng→samsung, etc.), and budget words are parsed ("50k"=50000, "30 hazar"=30000,
  "under 20k"→price_max=20000).
- **Validation** forces the intent into the known set (else `unknown`), lowercases
  brand, and only accepts a price in the range `0 < n < 100,000,000`.
- **Fallback (Groq unavailable / parse error):** a keyword heuristic maps the
  message to an intent in priority order
  (greeting → goodbye → thanks → **exit** → delivery → buy → comparison →
  product_search → price_query → unknown). Exit is checked before buy so
  "pore kinbo" resolves to exit.
- **Post-Groq overrides** (deterministic corrections, each tied to a real bug):
  pure-budget messages clear a stale title; over/under budget signals are
  re-parsed and authoritative; greeting+search-word → product_search;
  greeting/unknown+comparison-word → comparison; exit phrases beat buy; explicit
  buy signals → buy.
- **Category resolution** maps a word/message to a canonical category using
  aliases (tv→television, friz→refrigerator, "hidden camera"→IP Camera…),
  exact/substring/token-overlap matching, and a fuzzy fallback with high
  thresholds (0.85–0.88) and minimum token lengths, so short tokens don't
  mis-match (e.g. "dry machine" must not become "X-Ray Machine").

---

## 6. Context & state management

- **DB is the source of truth for conversation context** (`intent_content`):
  category, brand, title, budget. Loaded once per request.
- **Context TTL:** `CONTEXT_TTL_SECONDS = 1800` (30 min). Stale context is dropped.
- **Session category memory** (`_session_category`) remembers the user's current
  category so budget-only follow-ups ("50k er modde ache?") know what to search.
- **Category switch resets state:** when the user names a *different* category,
  cached products are cleared and the old category is dropped so it can't bleed in.
- **Intent change clears cached products** (unless it's a follow-up) so a new intent
  is never answered with stale product data.
- **Product context** (`_product_context`, top-5) and the **search pool**
  (`_search_pool`, up to 15, keyed by `keywords|min|max`) back the single-vs-multiple
  product decisions and "show more" pagination.
- **Pinned product URL** (`_product_url`) focuses follow-up questions on one product.
- Local state persists to `data/chatbot_state.json` so a restart doesn't lose
  session category / cached products.

---

## 7. Intent handlers (per-intent behaviour)

- **Greeting** — clears cached products + session category, returns the welcome
  line. **Goodbye/Exit** — flag exit. **Thanks** — keeps the session open.
- **Buy** — decision ladder: no product + no category → ask what to buy
  (product/model name or link); category but no product → search first; multiple
  cached → ask which one; exactly one → fetch the buy template and, if the product
  is e-commerce ("Buy Now"), **start the order flow** (§9), otherwise show
  seller-contact instructions. Never invents how to buy.
- **Comparison** — **never asserts a single "best".** Shows the top cached product
  as "a good option" and tells the user to decide by reviews/ratings, or links to
  the category page.
- **Delivery** — advance-payment question → policy reply; tracking question → "log
  in and check My Orders"; otherwise the delivery template or fixed info: **inside
  Dhaka 60–80৳ / 1–2 working days, outside Dhaka 120–150৳ courier / 2–5 working
  days** (charges may change).
- **FAQ** — priority: AI-identity ("are you a bot?") → property/real-estate →
  warranty (deflect to website) → showroom/address (online-only reply) → FAQ search
  → "not sure, see the website". Showroom matching uses whole-word Latin matching so
  "shop" doesn't fire on "shopping".
- **Price query** — budget + category → fresh search; cached products + no budget →
  list cached prices (from API data); no category → ask which product.
- **Product spec query** — looks up the spec from the product's API details; matches
  the asked field; can use Groq **constrained to the product's review text** (under
  the daily cap); if nothing is found, redirects to the product page rather than
  guessing.
- **Product-detail follow-up** — answers warranty/price/discount/stock/colour/
  condition/spec questions about the pinned product from API data; defers to a fresh
  search on rejection / new-product / "more" / technical-advice signals.
- **Clarification selection** — resolves a numbered or named pick, pins that product,
  and answers whatever was originally asked (condition / buy / spec / product card).
- **URL handling** — BDStall product link → search by slug and pin the product;
  image/CDN URL → ask for product name; non-BDStall URL → "I only support BDStall
  links".

---

## 8. Product search subsystem

`handle_product_search` runs these branches in order:

1. **Property/real-estate** words → dedicated Apartment/Land search.
2. **Rejection / "নেই?"** → strip filler, re-search the residual keyword with the
   current budget (retry without budget if empty).
3. **Use-case / purpose** ("gaming er jonno", "for editing work") → re-search with
   the purpose added.
4. **Condition question** ("used/new") → answer about the cached product or
   re-search for the requested condition.
5. **No category** → free-text keyword fallback from the cleaned message (tries the
   full phrase, then the two longest tokens); only if that fails does it ask for the
   category.
6. **Generic category** (category only, no brand/title/budget/spec qualifier) →
   return the **category landing-page link** instead of dumping products.
7. **"More" / pagination** → if the same query has a cached pool, advance the offset
   and show the next 3; when the pool is exhausted, say so.
8. **Normal search** → search the API; if 0 results, broaden (brand+category), then
   retry without budget and show nearest-price options; if still nothing, an honest
   "out of stock, follow the website" reply.
9. **Success** → cache the pool + top-5, show the top 3 with a budget/title-aware
   header, and a numbered selection prompt ("১, ২, ৩ যেকোনো নম্বর বলুন").

Product cards show **title + price** (price straight from API data) with a numbered
"দেখুন" button each.

---

## 9. Order placement flow

A **one-shot collection** flow (not a per-field wizard). Two states: **collect** and
**confirm**.

- **Start** (from a single-product buy that is e-commerce): extract the listing id
  from the product URL (abort to "order on the product page" if absent), then ask
  for **all fields at once**: name, mobile (`017XXXXXXXX`), address, district
  (city), area (thana), quantity. "বাতিল" cancels.
- **While collecting**, several interceptors run first:
  - **Greeting** → silently restart.
  - **Cancel** → clear and confirm cancellation.
  - **Price negotiation** ("discount?", "দাম কমানো") → "our price is fixed",
    re-show the form, keep all fields.
  - **Info question** (payment / delivery / warranty / fake / return / condition,
    checked payment-before-delivery because "cash on delivery" contains "delivery")
    → answer the one line and re-show the form, keeping fields.
  - **Product-search escape** (brand+search-signal or category+search-signal) → leave
    the flow so the new query is routed normally.
  - **Smart single-field fixup:** if exactly one field is missing and the reply has
    no labels, treat the whole reply as that field's value.
- Mobile is parsed as a BD `01XXXXXXXXX` number; city/area are resolved against the
  live city/area lists (changing the city drops a now-invalid area); name/address are
  intentionally lenient (≥2 chars).
- **Confirm:** show an itemised summary; only "হ্যাঁ" places the order via the API.
  On success → confirmation with the order number + "a representative will confirm
  delivery"; on failure → apology + retry guidance. The flow is cleared either way.

---

## 10. Order status

- Triggered pre-Groq (§4 #6). The order number is extracted by translating Bangla
  digits to ASCII and taking the longest run of **≥8 digits**, **excluding BD mobile
  numbers** (11-digit `01…`, 13-digit `8801…`, 15-digit `008801…`).
- If no number is present, the bot **asks for the order ID** and remembers it, so the
  user's next message (the bare ID) is looked up directly.
- The status is fetched from the API and rendered as a **friendly Bangla sentence**
  per status (the order number + a sentence; items/totals/address are omitted):
  - `pending` → not yet confirmed, awaiting acceptance
  - `submitted` → received, in processing
  - `processing` → in progress
  - `confirmed` → confirmed, will ship soon
  - `shipped` → shipped, arriving soon
  - `delivered` → delivered, thank you
  - `cancelled` → cancelled · `returned` → returned
- An **unknown status is never echoed in English** — a generic Bangla line is used.
  A not-found order returns "order number … not found, please verify".

---

## 11. Knowledge / technical advice

- The **only** path allowed to generate free Groq text. Used for capability /
  compatibility / upgrade / performance questions and PC-build advice.
- **Rate limited to `KNOWLEDGE_DAILY_LIMIT = 5` answers per user per day.** On
  exceeding the cap the user is **handed off to a human** (`knowledge_limit_exceeded`).
- The answer is **forced to pure Bangla**, kept to 2–3 sentences, must **not** invent
  specific specs/numbers/model claims, must **not** mention prices or competitor
  brands, and is wrapped with a "verify before buying" nudge.
- The product-spec variant constrains Groq to the product's **own review text** and
  returns `NOT_FOUND` rather than fall back to training knowledge.

---

## 12. Human handoff rules

A conversation is flipped to **HUMAN** mode (a representative takes over; the bot then
stays silent) in these cases:

- **Strict low-confidence gate:** Groq returns `unknown`, **or** confidence < 0.55 with
  no usable entity and not a follow-up → handoff (`unknown_handoff`). Safe follow-up
  intents that have a known category context are exempted so e.g. "price koto?" after
  "mobile dekhan" is answered, not handed off.
- **Business/partnership (B2B)** asks (`seller_query`).
- **`seller_query`** (genuine sell/vendor intent) — but a *buyer* asking "where is your
  shop" is downgraded to the online-platform answer instead.
- **`hate_speech`**, **`human_request`** (explicit), and **`complaint`** — except a
  return/refund complaint, which is answered locally from the return policy (no
  handoff).
- **Knowledge daily-limit exceeded.**

Once in HUMAN mode, every later message is silently passed to the agent until the
conversation is reassigned to the bot.

---

## 13. Channel behaviour (Messenger webhook)

- **Webhook verify** (GET) checks the verify token; **events** (POST) process only
  `page` messaging events and ignore echoes.
- **User name** is resolved via a cascade (event → Graph API → cache → responder API →
  "User <last6>").
- **Attachments (no text):**
  - **Image** → "স্যার, আপনি কোন প্রোডাক্টটি কিনতে চাচ্ছেন? দয়া করে প্রোডাক্টটির নাম এবং মডেল বলুন।"
    (the bot can't read images).
  - **File / audio / video** → "এই ফরম্যাটে সাহায্য করা সম্ভব হচ্ছে না… টেক্সটে লিখুন।"
- **Persistence:** the visitor message (sender_type **3**) is saved before
  processing; the bot reply (sender_type **2**) is saved after. **Silent turns are
  still saved as a single space** so the conversation history has no gaps. Saves try
  JSON first, then form-data.
- **Silence:** in human mode (or the two silent intents) nothing is sent. A fallback
  apology is sent **only** for genuine AI-side errors in AI mode.
- **Sending:** a typing indicator wraps processing; replies with product links are
  sent as Messenger **button templates** (one card per product); if a template send
  fails the recipient is marked a **"lite" client** and future replies inline the
  links as text. Long text is chunked to Messenger's size limits.

---

## 14. External APIs

All under `https://www.bdstall.com/api/...` (env-overridable). Each outbound call is
logged to `logs/api_calls_YYYY-MM-DD.log`.

| Purpose | Endpoint |
|---------|----------|
| Product search | `/api/chatbot/ai_search/` |
| Delivery / condition template | `/api/chatbot/ai_template/` |
| Assign to human agent / back to bot | `/api/chatbot/chatbot_assign_agent/` · `/chatbot_assign_bot/` |
| Responder lookup (mode + name) | `/api/chatbot/chatbot_responder/` |
| Conversation history | `/api/chatbot/chatbot_history/` |
| Save message | `/api/chatbot/chatbot_save_message/` |
| Category list | `/api/chatbot/cat_list/` |
| Product spec / details | `/api/item/list_details/` |
| Knowledge answers | `/api/chatbot/knowledge/` |
| City / area lists (orders) | `/api/chatbot/city_list/` · `/area_list/` |
| Place order | `/api/chatbot/chatbot_place_order/` |
| Order status | `/api/chatbot/chatbot_order_status/` |

---

## 15. Key configuration values

| Setting | Value | Meaning |
|---------|-------|---------|
| `CONTEXT_TTL_SECONDS` | 1800 (30 min) | How long saved conversation context stays valid. |
| `KNOWLEDGE_DAILY_LIMIT` | 5 | Groq knowledge answers per user per day before handoff. |
| `CHATBOT_HISTORY_LIMIT` | 5 (1–20) | Messages of history fed to Groq. |
| Strict-handoff confidence | < 0.55 | Below this, with no entity/follow-up → human. |
| Groq classify / answer model | `llama-3.3-70b-versatile` | LLM used for intent and advice. |
| Sender types | 1 = agent, 2 = bot, 3 = visitor | Message author codes. |
| Modes | `AI` ("AI Active") · `HUMAN` ("Human Support Required") | Conversation mode. |

---

*This document reflects the behaviour implemented in the current codebase. When the
code changes (signal sets, handlers, flows), update the relevant section here.*
