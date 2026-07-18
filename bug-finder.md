# Bug Finder Report

**Project:** BDStall AI Chatbot
**Date:** 2026-07-15
**Method:** Full-code review by 5 parallel review agents (one per subsystem), with the highest-severity findings independently re-verified against the source.
**Scope reviewed:** `src/controllers/`, `src/services/`, `src/repositories/`, `src/models/`, `src/utils/`, `run.py`, `config/gunicorn_config.py`
**Note:** The intent layer (`intent_handlers_service.py`, `intent_service.py`) review was still running when this report was written — its findings will be appended in a follow-up section.

**Total findings: 50** — 12 High, 17 Medium, 21 Low.

---

## 🔴 HIGH severity

### H1. `'no'` cue substring-matches inside "note"/"nokia"/"lenovo" — hijacks product questions as selections ✅ verified
- **File:** `src/utils/flow_helpers.py:273-275`
- The cue check `any(c in nl for c in cues)` substring-matches the short Latin token `'no'`. Any message containing "note", "nokia", "lenovo" etc. plus a single digit 1–5 is treated as a product selection. The `len(nl.split()) <= 3` shortcut also fires with no cue at all.
- **Scenario:** After a product list is shown, user asks "redmi note 5 er dam koto" → `'no'` matches inside "note", the lone `5` is picked → bot treats it as "selected product #5" instead of answering the price question. This is the known signal-set collision pattern — Latin tokens must be word-bounded.

### H2. Advance-payment intercept uses raw substring match — `'advance'`⊂"advanced", `'ogram'`⊂"program", `'আগাম'`⊂"আগামী" ✅ verified
- **File:** `src/services/chatbot_service.py:695` (signals at lines 79–84)
- `any(s in message.lower() for s in _ADVANCE_SIGNALS)` — plain substring, unlike the hate-speech path which uses the word-bounding `_msg_has_any`.
- **Scenario:** "advanced gaming laptop chai" or "programming er jonno laptop lagbe" → intercepted before Groq and answered with the advance-payment/delivery FAQ instead of running a product search. "আগামী মাসে kinbo" gets the same wrong reply.

### H3. Hate-speech signal `'গুদ'` substring-fires inside `'গুদাম'` (warehouse) ✅ verified
- **File:** `src/services/chatbot_service.py:679` (signal at line 97)
- Bangla tokens are intentionally substring-matched in `_msg_has_any`, but `'গুদ'` is a substring of the common word 'গুদাম'.
- **Scenario:** Customer asks "আপনাদের গুদাম কোথায়?" (where is your warehouse?) → bot scolds them for abusive language and escalates to a human agent.

### H4. Order-status detection: `'order'`⊂"recorder"/"preorder" hijacks browsing messages ✅ verified
- **File:** `src/services/chatbot_service.py:765-771` (`_ORDER_WORDS` at line 220)
- `any(w in _msg_l_os for w in _ORDER_WORDS)` is raw substring.
- **Scenario:** "voice recorder dekhte chai" → `'order'` matches inside "recorder" + view-marker 'dekhte chai', no buy marker → bot replies "আপনার অর্ডার আইডিটি দিন" and sets `awaiting_order_id` instead of showing recorders.

### H5. Human-mode sell-back check: `'sell'`⊂"seller" yanks conversations away from human agents ✅ verified
- **File:** `src/services/chatbot_service.py:626-631`
- `any(s in _msg_l_sell for s in _SELL_SIGNALS)` with bare `'sell'` in the tuple.
- **Scenario:** A user already handed to a human agent messages "seller call dhore na" (complaint about a seller) → `assign_bot(user_id)` re-assigns the conversation to the bot mid-support.

### H6. Dashed phone number becomes the shipping address in freeform order parsing
- **File:** `src/services/order_handler.py:494`
- `_parse_freeform`'s mobile-line exclusion only strips spaces (`.replace(' ', '')`) while `_parse_mobile` strips `[\s\-()]`, so a dashed number is parsed as mobile *and* also survives into the leftover lines.
- **Scenario:** User sends "Karim\n01712-345678" (common BD format) → mobile parses fine, but the dashed line is stored as `address='01712-345678'`; the address now passes validation (≥2 chars) so the user is never asked for a real address and the order ships to a phone number.

### H7. Multi-missing-field replies overwrite the collected name and loop the prompt
- **File:** `src/services/order_handler.py:573` (smart follow-up at line 954 handles only exactly one missing field)
- With ≥2 fields missing, an unlabelled reply goes to `_parse_freeform`, which guesses any letters-only line as `'name'` (lines 499–503), and `_validate_and_resolve` lets that overwrite the already-collected name while never filling the missing city.
- **Scenario:** Missing = ['জেলা', 'এলাকা']; the prompt suggests "(যেমন: Dhaka, Chittagong…)"; user replies "Dhaka" → `{'name': 'Dhaka'}` overwrites the real name, city stays unset, identical re-prompt loops; the order can end up placed under the name "Dhaka".

### H8. Webhook returns HTTP 500 on any escaped exception → Facebook redelivers the batch, can deactivate the webhook ✅ verified
- **File:** `src/controllers/chat_controller.py:1500-1502`
- Any exception in the entry loop (e.g. lazy `get_chatbot()` init failure — this repo's historical deploy failure) returns 500 to Facebook.
- **Scenario:** An error on the 2nd event of a batch → events already replied to get redelivered and re-answered (duplicate replies/history rows); sustained 5xx causes Facebook to throttle and eventually deactivate the webhook subscription (silent bot).

### H9. Fully synchronous webhook processing with no `message.mid` dedup → duplicate replies on slow requests ✅ verified
- **File:** `src/controllers/chat_controller.py:1463`
- One incoming text can trigger, inline before the 200 is returned: multiple name-lookup HTTP calls (10s+8s timeouts), visitor save (2×10s), Groq + product-search calls, bot save (2×10s), and per-button Send API calls. Nothing anywhere checks `mid`.
- **Scenario:** BDStall save API or Groq is slow → total time exceeds Facebook's ~20s webhook timeout → FB redelivers the same event → user receives the same answer twice, history gets duplicate rows. `config/gunicorn_config.py` (workers=1, sync, timeout=120) additionally head-of-line-blocks all other users behind the slow request.

### H10. `_save_local_state` dumps the whole in-memory state over `chatbot_state.json` — cross-process clobbering ✅ verified
- **File:** `src/repositories/state_repository.py:79-97`
- Every save rewrites the entire file from this process's memory; only `seller_flow` re-reads the file before use (`get_order_flow` at line 296 does not).
- **Scenario:** With more than one worker process (the code's own comment at lines 316–319 anticipates this), an order started on worker A is invisible to worker B; worker B's next save (triggered by `save_last_intent` on every reply) rewrites the file without the order, permanently erasing the collected name/mobile/address mid-order. Currently mitigated only by `workers=1` in gunicorn config — raising the worker count makes this live.

### H11. Pre-reply conversation context cached for 60s across requests → follow-ups lose their category
- **File:** `src/services/api_client_service.py:241` (`_HISTORY_TTL`)
- The docstring says the cache exists to avoid a second call "in the same request cycle", but the TTL spans requests, and saving a new `intent_content` does not invalidate it (`invalidate_user_cache` fires only on explicit category switch, `chatbot_service.py:1281`).
- **Scenario:** Fresh user sends "laptop dekhan" (empty context cached at T0, bot saves `{cat: laptop}`); user follows up "30k er modde" at T0+30s → `load_context` returns the stale empty context → the follow-up loses the category and the bot re-asks the category prompt instead of searching laptops under 30k.

### H12. `_HISTORY_TTL` companion: search failures cached as "no products" for 5 minutes
- **File:** `src/services/api_client_service.py:127`
- `search_products` caches `_do_search`'s failure result (timeout/HTTP error returns the same `{'products_found': 0, 'products': []}` shape as a genuine empty result) for the full 300s `_SEARCH_TTL`.
- **Scenario:** The ai_search API times out once for a query → for the next 5 minutes every user with the same query gets "no products found" even though the API recovered seconds later.

---

## 🟠 MEDIUM severity

### M1. Hyphenated model numbers parsed as price ranges
- **File:** `src/utils/flow_helpers.py:48`
- The price-range regex has no boundaries around the `-` separator.
- **Scenario:** "hp core i5-8250u laptop ache?" matches "5-8250" → `{'min_price': 5000, 'max_price': 8250}` — a budget the user never gave silently filters results.

### M2. "Above N" budget requests inverted to "under N"
- **File:** `src/utils/flow_helpers.py:64`
- The generic fallback maps any "NUMBER unit" mention to `max_price`; there is no 'upore/over/above' handling.
- **Scenario:** "50 hazar er upore laptop dekhan" (above 50k) → `{'max_price': 50000}` — the exact opposite bound.

### M3. Language-switch guard is vacuous — one English-looking message flips the profile
- **File:** `src/utils/user_profile.py:145-149`
- Both the `if` and `else` branches execute `self.language = observed`, so the documented "don't downgrade to english unless seen twice" guard does nothing.
- **Scenario:** A user chatting in Bangla for 10 turns sends "ok" → profile flips to `english`; `to_prompt_block` then pushes the Groq prompt toward English replies (violates the Bangla-only rule).

### M4. URL regex swallows trailing Bangla danda (।) and punctuation into product IDs
- **File:** `src/utils/product_link_handler.py:30`
- `[^\s<>"\']+` includes `।`, commas, and closing parens in the extracted URL, polluting `product_id`.
- **Scenario:** "https://www.bdstall.com/details/hp-laptop-123।" (standard Bangla sentence end) → product_id `hp-laptop-123।` → API lookup fails → user gets the English "No products found" fallback and a broken button URL.

### M5. Link-only messages generate a button template with empty text — Facebook rejects it, user gets nothing
- **File:** `src/utils/product_link_handler.py:230`
- The single-button template uses `formatted['description'][:640]` as text, which is `""` when the message is only a link. Facebook rejects button templates with empty text (error 100).
- **Scenario:** User sends just a bdstall details link → Send API rejects the payload → no reply delivered.

### M6. English fallback "No products found" sent to users
- **File:** `src/utils/product_details_handler.py:299` (same defect at line 114)
- **Scenario:** User sends only a bdstall link whose API lookup fails → the bot replies "No products found" in English (Bangla-only rule violation).

### M7. Default product-template text is English ("Price: N/A", "Price:")
- **File:** `src/utils/product_details_handler.py:178` (also lines 123/147)
- **Scenario:** A bare product link that resolves → user sees "HP Laptop …\nPrice: 45,000" — English reply text.

### M8. Buy intercepts have no negation guard — refusals trigger the buy flow
- **File:** `src/services/chatbot_service.py:1050` (also self-reference intercept at 1023)
- **Scenario:** After the bot shows a product, user replies "na vai eta kinbo na" (won't buy) → 'kinbo' matches → bot starts buy/clarification handling on a refusal.

### M9. `'eta'`⊂"details", `'order'`⊂"recorder" in the self-reference buy path
- **File:** `src/services/chatbot_service.py:1021`
- `_BUY_SELF_REF`/`_BUY_ORDER_WORDS` are substring-matched.
- **Scenario:** With cached search results, "recorder er details den" → treated as a buy of the cached product instead of a details request.

### M10. Payment intercept fires before order-status — paid-but-undelivered complaints get the COD FAQ
- **File:** `src/services/chatbot_service.py:709`
- **Scenario:** "বিকাশে পেমেন্ট করেছি কিন্তু অর্ডার আসেনি" → answered with the canned cash-on-delivery FAQ instead of the order-status/complaint path.

### M11. Digits anywhere in the area reply are treated as an area_id lookup
- **File:** `src/services/order_handler.py:383`
- `_match_area` gives digits priority as an ID lookup; area IDs are small numeric strings (e.g. `'10'` per tests).
- **Scenario:** "এলাকা: Mirpur 10" → digit `10` matches whatever Dhaka area has `area_id='10'` — an arbitrary different area — instead of name-matching "Mirpur".

### M12. `_word_match` uses only spaces as boundaries — "cancel," and "ase?" missed
- **File:** `src/services/order_handler.py:289`
- **Scenario:** Mid-order "cancel, please" → `_is_cancel` returns False → stored as `name='cancel, please'` instead of cancelling; "hp laptop ase?" fails the search-escape and is swallowed as a form value.

### M13. Read-modify-write on shared state dicts without the lock — saves silently lost
- **File:** `src/repositories/state_repository.py:96` (mutators at 157, 191, 224–227, 242 write without `_state_lock`)
- `json.dump` iterates the shared dicts under `_state_lock`, but mutators don't take it → "dictionary changed size during iteration", swallowed at line 102, save silently lost.
- **Scenario:** Two users message simultaneously in a threaded worker → one user's order/intent update never reaches disk.

### M14. Live API secrets logged in plaintext
- **Files:** `src/services/api_client_service.py:102` (ASSIGN_AGENT_KEY payload), lines 71/78 (RESPONDER_KEY in URL), 495–497 (SAVE_MESSAGE_KEY); `src/controllers/chat_controller.py:284` (SAVE_MESSAGE_API_KEY in every message-save log — confirmed present in `logs/api_calls_2026-05-24.log`)
- Other call sites deliberately mask with `'***'` (e.g. `fetch_city_list:663`, `place_order:742-744`), but these do not.
- **Scenario:** Anyone with access to `logs/api_calls_*.log` harvests production API keys.

### M15. PAGE_ACCESS_TOKEN leaks into logs via exception messages
- **File:** `src/controllers/chat_controller.py:388` (token embedded in URL at line 374; same pattern at 403)
- **Scenario:** graph.facebook.com connection error → the exception message contains "…/me/messages?access_token=EAA…" → written to logs by `logger.warning`.

### M16. One transient send failure permanently marks a user as an FB Lite client
- **File:** `src/controllers/chat_controller.py:654`
- `_send_facebook_payload` returns False for *every* non-2xx and network exception; a False triggers `mark_lite_client`, persisted to `data/lite_clients.json` with no un-mark path.
- **Scenario:** A one-off Send API timeout/5xx/rate-limit → that user never receives product cards or buttons again, forever, across restarts.

### M17. Followup: `user_profile` language flip feeds the (currently disabled) humanizer's English instruction
- **Files:** `src/services/humanizer_service.py:69` + `src/utils/user_profile.py:145`
- The humanizer's language map contains `'english'` → "Reply in English…", violating the Bangla-only rule. Latent today (humanizer intentionally disabled at `chatbot_service.py:471`) but armed by bug M3.
- **Scenario:** If the humanizer is re-enabled as designed, any profile flipped to 'english' (which one "ok" message causes) gets fully English replies.

---

## 🟡 LOW severity

### L1. Bangla postposition budget phrases can never match
- **File:** `src/utils/flow_helpers.py:58` — the "under" regex requires the keyword *before* the number, but 'modde/মধ্যে/vitor/er modde' always follow the number in natural Bangla. "60000 er modde laptop" gets no budget filter at all.

### L2. English field labels in an otherwise-Bangla order prompt
- **File:** `src/utils/flow_helpers.py:130` — "Name:", "Phone Number:", "Address:" rendered inside a Bangla reply (Bangla labels exist in `extract_order_detail_fields` but are unused here).

### L3. `_detect_style`'s "formal" branch is dead
- **File:** `src/utils/user_profile.py:85` — both returns after the formal-marker check return `'casual'`; the has_emoji/length computation at 79/83 has no effect.

### L4. `product_cache` grows without bound
- **File:** `src/utils/product_link_handler.py:367` — timestamp-unique keys inserted per link message; `clean_cache()` is never called anywhere in the repo. Memory leak in a long-running worker.

### L5. Details-page URL used as image fallback
- **File:** `src/utils/product_details_handler.py:83` — when `ImagePath` is absent, the card's `image_url` is the product's HTML page → broken/rejected image in Messenger.

### L6. Bangla category interpolated raw into URL without percent-encoding
- **File:** `src/utils/category_product_handler.py:158` — `f"https://www.bdstall.com/{category}/"` with a Bangla token produces an invalid unencoded URL in a web_url button.

### L7. English default texts in category templates
- **File:** `src/utils/category_product_handler.py:212` (also 166) — "Popular {category} products" / "Check out {category} products" sent to users in English.

### L8. Responder-API failure cached as 'bot' for 30s
- **File:** `src/services/api_client_service.py:88` — a transient 500 caches `'bot'`, so the bot talks over a live human agent for up to 30s with no re-check (only confirmed 'bot' results were meant to be cached per comments at 51–52, 66).

### L9. Unbounded per-user caches
- **File:** `src/services/api_client_service.py:43` — `_history_cache`, `_intent_cache`, `_responder_cache` entries are TTL-checked on read but never evicted (only `_search_cache` has a size cap). Slow memory leak per Messenger PSID.

### L10. `shutil.move` is not an atomic replace on Windows
- **File:** `src/repositories/state_repository.py:97` — on Windows the rename falls back to copy2 (truncate + rewrite in place); a crash/concurrent read mid-copy corrupts `chatbot_state.json`. `os.replace` is atomic on both platforms.

### L11. `KNOWLEDGE_DAILY_LIMIT` env parse unguarded
- **File:** `src/models/chatbot_config.py:40` — `int(os.getenv(...))` raises at import time on a bad value and the whole app fails to boot (the identical pattern for `HISTORY_LIMIT` at 77–80 is wrapped in try/except).

### L12. Humanizer contains an explicit "Reply in English" instruction
- **File:** `src/services/humanizer_service.py:69` — see M17; violates the Bangla-only rule if ever enabled.

### L13. Category validator re-fetches with no failure backoff, blocking up to 8s per message
- **File:** `src/services/category_validator_service.py:105` — `refresh()` only updates `_last_loaded` on success; every call retries a blocking HTTP request serialized through `_lock`. (Class currently unused — latent.)

### L14. Set-iteration order makes category resolution nondeterministic
- **File:** `src/services/category_validator_service.py:213` — the token-index fallback iterates a set; multi-category messages resolve differently across restarts. (Latent — class unused.)

### L15. Placeholder name "User <last6>" permanently poisons name resolution
- **File:** `src/controllers/chat_controller.py:1359` — a single failed Graph profile lookup persists the synthetic name via `remember_user_name` into cache + `data/user_names.json`; every later lookup short-circuits on it (lines 200, 672, 748–755), so the real name is never fetched again.

### L16. Misspelled honorific "স্য়ার" in the user-facing error fallback ✅ verified
- **File:** `src/controllers/chat_controller.py:1489` — spurious য়-form (U+09AF U+09BC) instead of "স্যার" used everywhere else in the repo.

### L17. Send API hardcodes Graph v25.0, ignoring `FACEBOOK_GRAPH_API_VERSION`
- **File:** `src/controllers/chat_controller.py:374` (also 403) — the profile lookup at 680 honors the env var but outbound sends don't.

### L18. Attachment turns never saved to chat history
- **File:** `src/controllers/chat_controller.py:1386-1447` — image/sticker/file branches bypass `save_chat_message` for both the user's turn and the bot's reply; human agents taking over see a gap.

### L19. Seller-flow mobile regex drops Bangla-digit phone numbers
- **File:** `src/services/chatbot_service.py:523` — `_BD_MOB_PAT` compiled with `re.ASCII` and input never passed through `_to_en_digits` (unlike the order handler); "০১৭১২৩৪৫৬৭৮" is silently dropped → `mobile=''` submitted.

### L20. Seller submission failure reported to the user as success
- **File:** `src/services/chatbot_service.py:558` — `_continue_seller_flow` returns the fixed thank-you regardless of `submit_seller_request`'s result, and flow state was already cleared at 518; a failed submission is silently lost with no retry path.

### L21. Whole-state save on every reply amplifies H10/M13
- **File:** `src/repositories/state_repository.py:79` — `save_last_intent` on every reply triggers a full-file rewrite, maximizing the window for the clobber/race bugs above.

---

## Pattern summary

1. **Signal-set substring collisions (recurring, known pattern):** H1, H2, H3, H4, H5, M8, M9 — raw `in` checks on short tokens. The repo already has the correct helper (`_msg_has_any` in `intent_service.py:331` word-bounds Latin tokens) but most intercepts in `chatbot_service.py` and `flow_helpers.py` don't use it.
2. **Order-flow data corruption:** H6, H7, M11, M12 — freeform parsing overwrites good data and misses cancel/escape commands.
3. **Webhook reliability (silent-bot / duplicate-reply risk):** H8, H9, M16, L15.
4. **State persistence races:** H10, M13, L10, L21.
5. **Stale caches:** H11, H12, L8, L9.
6. **Secrets in logs:** M14, M15.
7. **English leaking to users (Bangla-only rule):** M6, M7, L2, L7, L12, and M3/M17 (language-flip chain).

---

*Pending: findings from the intent-layer review (`intent_handlers_service.py`, `intent_service.py`) will be appended below when that review completes.*
