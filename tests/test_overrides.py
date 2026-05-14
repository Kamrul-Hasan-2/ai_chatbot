"""
Tests for apply_post_groq_overrides() — the deterministic correction rules
that fire after Groq returns an intent. Each rule below has a paired
positive (rule fires) and negative (rule does NOT fire) case so that
future regex/keyword tweaks don't silently widen or narrow the rule.
"""
from services.intent_service import apply_post_groq_overrides


def _make_groq_result(intent="unknown", title="", price_max=None, price_min=None,
                     category="", brand=""):
    return {
        "intent": intent,
        "entities": {
            "category": category,
            "brand": brand,
            "title": title,
            "price_max": price_max,
            "price_min": price_min,
        },
        "missing": [],
        "is_followup": False,
        "confidence": 0.5,
    }


# ── Rule 1: pure budget refinement clears stale title ─────────────────────────

class TestPureBudgetRefinement:
    def test_pure_budget_message_clears_title(self):
        groq = _make_groq_result(intent="product_search", title="samsung phone",
                                 price_max=20000)
        prev = {"title": "samsung phone", "prev_title": "iphone"}
        result = apply_post_groq_overrides(groq, "20000 takar modde", prev)

        assert result["is_pure_budget_msg"] is True
        assert result["groq_result"]["entities"]["title"] == ""
        assert result["prev_ctx"]["title"] == ""
        assert result["prev_ctx"]["prev_title"] == ""

    def test_pure_budget_banglish_upore(self):
        groq = _make_groq_result(title="laptop")
        result = apply_post_groq_overrides(groq, "30k upore", {"title": "laptop"})
        assert result["is_pure_budget_msg"] is True
        assert result["groq_result"]["entities"]["title"] == ""

    def test_message_with_product_keyword_is_not_pure_budget(self):
        groq = _make_groq_result(title="samsung phone")
        result = apply_post_groq_overrides(
            groq, "samsung phone 20000 takar modde", {"title": "samsung phone"}
        )
        assert result["is_pure_budget_msg"] is False
        assert result["groq_result"]["entities"]["title"] == "samsung phone"


# ── Rule 2: over/under signal corrects Groq's min/max swap ────────────────────

class TestBudgetOverUnderCorrection:
    def test_over_signal_forces_min_only(self):
        # Groq incorrectly returned price_max for an "above" query.
        groq = _make_groq_result(price_max=50000, price_min=None)
        result = apply_post_groq_overrides(groq, "50k upore phone", {})

        ent = result["groq_result"]["entities"]
        assert ent["price_min"] == 50000
        assert ent["price_max"] is None

    def test_under_signal_forces_max_only(self):
        groq = _make_groq_result(price_max=None, price_min=30000)
        result = apply_post_groq_overrides(groq, "30k er modde laptop", {})

        ent = result["groq_result"]["entities"]
        assert ent["price_max"] == 30000
        assert ent["price_min"] is None

    def test_no_signal_leaves_prices_alone(self):
        groq = _make_groq_result(price_max=20000, price_min=10000)
        result = apply_post_groq_overrides(groq, "samsung phone", {})

        ent = result["groq_result"]["entities"]
        assert ent["price_max"] == 20000
        assert ent["price_min"] == 10000


# ── Rule 3: search words promote greeting → product_search ────────────────────

class TestSearchOverride:
    def test_greeting_with_dekhao_becomes_product_search(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "hello phone dekhao", {})
        assert result["groq_result"]["intent"] == "product_search"

    def test_greeting_with_chai_becomes_product_search(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "laptop chai", {})
        assert result["groq_result"]["intent"] == "product_search"

    def test_pure_greeting_unaffected(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "hello", {})
        assert result["groq_result"]["intent"] == "greeting"


# ── Rule 4: comparison words override greeting/unknown ────────────────────────

class TestComparisonOverride:
    def test_konti_valo_becomes_comparison(self):
        groq = _make_groq_result(intent="unknown")
        result = apply_post_groq_overrides(groq, "konti valo hobe", {})
        assert result["groq_result"]["intent"] == "comparison"

    def test_which_one_becomes_comparison_from_greeting(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "which one is better", {})
        assert result["groq_result"]["intent"] == "comparison"

    def test_existing_product_search_not_downgraded_to_comparison(self):
        # Rule only applies when intent is greeting/unknown.
        groq = _make_groq_result(intent="product_search")
        result = apply_post_groq_overrides(groq, "konti valo phone", {})
        assert result["groq_result"]["intent"] == "product_search"


# ── Rule 5: buy signal always wins ────────────────────────────────────────────

class TestBuyOverride:
    def test_kibhabe_kinbo_overrides_anything(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "kibhabe kinbo", {})
        assert result["groq_result"]["intent"] == "buy"

    def test_payment_method_phrase_becomes_buy(self):
        groq = _make_groq_result(intent="faq")
        result = apply_post_groq_overrides(groq, "what is the payment method", {})
        assert result["groq_result"]["intent"] == "buy"

    def test_unrelated_message_keeps_original_intent(self):
        groq = _make_groq_result(intent="product_search")
        result = apply_post_groq_overrides(groq, "samsung phone dekhao", {})
        # Note: this hits the search override (Rule 3 doesn't apply because
        # intent isn't greeting), so it stays as product_search.
        assert result["groq_result"]["intent"] == "product_search"


# ── Defensive: None / odd prev_ctx ────────────────────────────────────────────

class TestEdgeCases:
    def test_none_prev_ctx_does_not_crash(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "hello", None)
        assert isinstance(result["prev_ctx"], dict)

    def test_empty_message_does_nothing(self):
        groq = _make_groq_result(intent="greeting")
        result = apply_post_groq_overrides(groq, "", {})
        assert result["groq_result"]["intent"] == "greeting"
        assert result["is_pure_budget_msg"] is False
