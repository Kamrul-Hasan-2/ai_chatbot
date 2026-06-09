"""
Regression tests for three routing/state bugs:

1. Category switch must drop a carried-over budget (mobile after "laptop under
   50k" should not stay capped at 50k).
2. A safe follow-up intent (price_query/product_search/comparison/technical_advice)
   with an existing category context must NOT hit the strict low-confidence
   handoff — it should inherit context and be handled.
3. "aro dekhan" / "show more" after products were shown must paginate the cached
   pool (or repeat cached products), never hand off.

Bugs 1 & 2 are integration tests that drive process_message with the Groq call,
responder check, history fetch and _dispatch stubbed out, capturing the merged
context that reaches _dispatch. Bug 3 is covered both directly (handle_show_more)
and end-to-end (the pre-Groq intercept must run before Groq).
"""
import pytest

import services.chatbot_service as cs
import services.intent_handlers_service as ih
import repositories.state_repository as sr


def _groq(intent, category="", price_max=None, price_min=None,
          conf=0.9, followup=False, brand="", title=""):
    return {
        "intent": intent,
        "entities": {"category": category, "brand": brand, "title": title,
                     "price_max": price_max, "price_min": price_min},
        "missing": [], "is_followup": followup, "confidence": conf,
    }


@pytest.fixture
def temp_state(tmp_path, monkeypatch):
    """Isolate the JSON state file and start from empty in-memory dicts."""
    monkeypatch.setattr(sr, "_STATE_FILE", str(tmp_path / "state.json"))
    for _k, d in sr._MEM_MAP:
        d.clear()
    yield
    for _k, d in sr._MEM_MAP:
        d.clear()


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Bypass responder/history/category-resolution and capture what reaches
    _dispatch. detect_intent/load_context are set per-test."""
    captured = {}
    monkeypatch.setattr(cs, "check_responder_type", lambda uid: "bot")
    monkeypatch.setattr(cs, "fetch_history", lambda uid: "")
    monkeypatch.setattr(cs, "resolve_category", lambda raw, cats: raw)          # identity
    monkeypatch.setattr(cs, "resolve_category_from_message", lambda msg, cats: "")

    def _fake_dispatch(intent, ctx, user_id, message, prev_ctx=None):
        captured["intent"] = intent
        captured["ctx"] = dict(ctx)
        return {"response": "ok", "intent": intent, "intent_content": {}, "products": []}

    monkeypatch.setattr(cs, "_dispatch", _fake_dispatch)
    return captured


# ── Bug 1: category switch clears carried-over budget ─────────────────────────

class TestCategorySwitchClearsBudget:
    def test_mobile_after_laptop_50k_drops_budget(self, temp_state, stub_pipeline, monkeypatch):
        uid = "u_bug1"
        sr.set_session_category(uid, "laptop")
        monkeypatch.setattr(cs, "load_context", lambda u: {
            "category": "laptop", "cat": "laptop", "prev_cat": "laptop",
            "price_max": 50000, "prev_price_max": 50000,
        })
        monkeypatch.setattr(cs, "detect_intent",
                            lambda *a, **k: _groq("product_search", category="mobile"))

        cs.process_message(uid, "mobile dekhan")

        ctx = stub_pipeline["ctx"]
        assert ctx.get("category", "").lower().startswith("mobile")
        assert ctx.get("price_max") is None      # the bug: this used to stay 50000
        assert ctx.get("price_min") is None

    def test_budget_stated_in_switch_message_survives(self, temp_state, stub_pipeline, monkeypatch):
        uid = "u_bug1b"
        sr.set_session_category(uid, "laptop")
        monkeypatch.setattr(cs, "load_context", lambda u: {
            "category": "laptop", "cat": "laptop", "prev_cat": "laptop",
            "price_max": 50000, "prev_price_max": 50000,
        })
        # New budget IS stated in the same message → must survive the switch.
        monkeypatch.setattr(cs, "detect_intent",
                            lambda *a, **k: _groq("product_search", category="mobile",
                                                  price_max=30000))

        cs.process_message(uid, "mobile under 30k")

        ctx = stub_pipeline["ctx"]
        assert ctx.get("category", "").lower().startswith("mobile")
        assert ctx.get("price_max") == 30000     # new budget kept, old 50000 dropped


# ── Bug 2: safe follow-up inherits context instead of handing off ─────────────

class TestSafeFollowupNoHandoff:
    def test_price_query_after_category_inherits(self, temp_state, stub_pipeline, monkeypatch):
        uid = "u_bug2"
        sr.set_session_category(uid, "Mobile")
        monkeypatch.setattr(cs, "load_context", lambda u: {})
        # Low confidence, no entities, not a follow-up — would previously hand off.
        monkeypatch.setattr(cs, "detect_intent",
                            lambda *a, **k: _groq("price_query", conf=0.3, followup=False))

        res = cs.process_message(uid, "price koto?")

        assert res["intent"] != "unknown_handoff"
        assert res.get("mode") != "human"
        assert stub_pipeline.get("intent") == "price_query"        # reached dispatch
        assert stub_pipeline["ctx"].get("category", "").lower() == "mobile"

    def test_unknown_random_message_still_hands_off(self, temp_state, stub_pipeline, monkeypatch):
        uid = "u_bug2b"
        sr.set_session_category(uid, "Mobile")           # context exists
        monkeypatch.setattr(cs, "load_context", lambda u: {})
        # 'unknown' is deliberately excluded from safe-inherit → must still hand off.
        monkeypatch.setattr(cs, "detect_intent",
                            lambda *a, **k: _groq("unknown", conf=0.2, followup=False))

        res = cs.process_message(uid, "asdfgh qwerty")

        assert res["intent"] == "unknown_handoff"
        assert "intent" not in stub_pipeline               # never reached dispatch


# ── Bug 3: "aro dekhan" paginates instead of handing off ──────────────────────

class TestShowMore:
    def _pool(self, n):
        return [{"title": f"P{i}", "price": "100", "url": f"u{i}"} for i in range(n)]

    def test_is_more_request_detection(self):
        assert ih._is_more_request("aro dekhan") is True
        assert ih._is_more_request("aro dekhao") is True
        assert ih._is_more_request("show more") is True
        assert ih._is_more_request("ac lagbe") is False
        assert ih._is_more_request("laptop dekhan") is False

    def test_show_more_returns_next_page(self, temp_state):
        uid = "u_more"
        pool = self._pool(6)
        sr.set_search_pool(uid, "ac||", pool)
        sr.set_product_context(uid, pool[:3])

        res = ih.handle_show_more({}, uid)

        assert res is not None
        assert [p["title"] for p in res["products"]] == ["P3", "P4", "P5"]
        assert res["intent"] == "product_search"

    def test_show_more_exhausted_repeats_cache(self, temp_state):
        uid = "u_more2"
        pool = self._pool(2)
        sr.set_search_pool(uid, "k||", pool)
        sr.set_product_context(uid, pool[:2])

        res = ih.handle_show_more({}, uid)   # next slice empty → repeat cached

        assert res is not None               # NOT a handoff/None
        assert res["intent"] in ("product_search", "no_more_products")

    def test_show_more_no_pool_no_cache_returns_none(self, temp_state):
        assert ih.handle_show_more({}, "u_empty") is None

    def test_aro_dekhan_intercepted_before_groq(self, temp_state, monkeypatch):
        uid = "u_more_int"
        pool = self._pool(6)
        sr.set_search_pool(uid, "ac||", pool)
        sr.set_product_context(uid, pool[:3])

        monkeypatch.setattr(cs, "check_responder_type", lambda u: "bot")
        monkeypatch.setattr(cs, "fetch_history", lambda u: "")
        monkeypatch.setattr(cs, "load_context", lambda u: {})

        groq_called = {"hit": False}

        def _no_groq(*a, **k):
            groq_called["hit"] = True
            return _groq("unknown", conf=0.1)

        monkeypatch.setattr(cs, "detect_intent", _no_groq)

        res = cs.process_message(uid, "aro dekhan")

        assert res["intent"] == "product_search"
        assert res["intent"] != "unknown_handoff"
        assert groq_called["hit"] is False        # handled pre-Groq
