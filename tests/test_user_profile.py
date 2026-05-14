"""
Tests for the UserProfile dataclass and observe_message logic.

These cover the "remembers across turns" feature: language detection,
brand tracking, budget rolling window, and the prompt-block summary
that gets injected into the Groq system prompt.
"""
from utils.user_profile import UserProfile, detect_language


class TestLanguageDetection:
    def test_pure_bangla_script(self):
        assert detect_language("আমি একটা ফোন চাই") == 'bangla'

    def test_banglish_with_markers(self):
        assert detect_language("phone dekhao 20k modde") == 'banglish'

    def test_english_only(self):
        assert detect_language("show me phones under 20000") == 'english'

    def test_empty_message(self):
        assert detect_language("") == 'english'

    def test_mixed_bangla_dominates(self):
        # Any Bangla script means we call it bangla.
        assert detect_language("hi স্যার, phone ase ki?") == 'bangla'


class TestProfileObservation:
    def test_brand_is_remembered(self):
        p = UserProfile()
        p.observe_message("samsung phone dekhao")
        assert 'samsung' in p.preferred_brands

    def test_brand_recency_order(self):
        p = UserProfile()
        p.observe_message("samsung phone dekhao")
        p.observe_message("apple iphone chai")
        # Most recent first.
        assert p.preferred_brands[0] == 'apple'
        assert 'samsung' in p.preferred_brands

    def test_category_observed_explicitly(self):
        p = UserProfile()
        p.observe_message("phone dekhao", category="mobile")
        assert 'mobile' in p.interested_categories

    def test_budget_widens_to_observed_range(self):
        p = UserProfile()
        p.observe_message("phone 20k modde", price_max=20000)
        p.observe_message("ekta 30k er upore dekhao", price_min=30000)
        assert p.budget_min == 30000
        assert p.budget_max == 20000

    def test_language_picked_up_from_message(self):
        p = UserProfile()
        p.observe_message("আমি একটা ল্যাপটপ চাই")
        assert p.language == 'bangla'

    def test_message_count_increments(self):
        p = UserProfile()
        p.observe_message("hi")
        p.observe_message("phone dekhao")
        assert p.message_count == 2


class TestPromptBlock:
    def test_new_user_returns_no_context_marker(self):
        p = UserProfile()
        block = p.to_prompt_block()
        assert 'new user' in block.lower()

    def test_block_includes_brand_after_observation(self):
        p = UserProfile()
        p.observe_message("samsung phone dekhao", category="mobile")
        block = p.to_prompt_block()
        assert 'samsung' in block
        assert 'mobile' in block

    def test_block_includes_budget_when_known(self):
        p = UserProfile()
        p.observe_message("20000 modde phone", price_max=20000)
        block = p.to_prompt_block()
        assert '20,000' in block


class TestSerialization:
    def test_roundtrip_through_dict(self):
        p1 = UserProfile()
        p1.observe_message("samsung phone dekhao 20k modde",
                           category="mobile", price_max=20000)
        d = p1.to_dict()
        p2 = UserProfile.from_dict(d)
        assert p2.preferred_brands == p1.preferred_brands
        assert p2.interested_categories == p1.interested_categories
        assert p2.budget_max == p1.budget_max
        assert p2.language == p1.language
        assert p2.message_count == p1.message_count

    def test_from_dict_handles_none_gracefully(self):
        p = UserProfile.from_dict(None)
        assert p.message_count == 0
        assert p.preferred_brands == []

    def test_from_dict_handles_partial_data(self):
        p = UserProfile.from_dict({'language': 'bangla'})
        assert p.language == 'bangla'
        assert p.preferred_brands == []
        assert p.budget_min is None
