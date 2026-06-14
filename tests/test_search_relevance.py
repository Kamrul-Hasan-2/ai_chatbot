"""
tests/test_search_relevance.py — Bangla search-term translation and the
irrelevant-result guard for the no-category free-text search.

Covers the production bug where "ডাবল ইলেক্ট্রিক চুলা আছে?" (double electric
stove) returned a flat, a fishing bait, and a land share: the Bangla keywords
were sent verbatim to the English-only search API, whose fallback returns
unrelated listings, and the bot displayed them without any relevance check.
"""
import pytest
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.intent_handlers_service import (
    _translate_bn_search_terms, _results_match_query,
    _search_without_category, _clean_product_keywords,
)

UID = 'test_user_search'

# The exact junk the API returned in production for the stove query
GARBAGE_PRODUCTS = [
    {'title': '1550 Sqft Ready Flat Sale at Khulshi Residential Area, Chittagong',
     'price': '৳ 14,500,000', 'url': 'https://www.bdstall.com/details/flat-1/'},
    {'title': 'Artificial Frog Fishing Bait', 'price': '৳ 130',
     'url': 'https://www.bdstall.com/details/bait-2/'},
    {'title': 'Land Share Sale at Khilkhet, Dhaka', 'price': '৳ 1,800,000',
     'url': 'https://www.bdstall.com/details/land-3/'},
]

STOVE_PRODUCTS = [
    {'title': 'Double Burner Electric Hot Plate Stove', 'price': '৳ 2,500',
     'url': 'https://www.bdstall.com/details/stove-9/'},
]


class TestTranslateBnSearchTerms:
    def test_stove_query_translated(self):
        assert _translate_bn_search_terms('ডাবল ইলেক্ট্রিক চুলা') == 'double electric stove'

    def test_suffix_survives_as_droppable_fragment(self):
        # "চুলার" = চুলা + র — the stray 'র' is later dropped by the token filter
        out = _translate_bn_search_terms('চুলার')
        assert 'stove' in out

    def test_banglish_chula(self):
        assert _translate_bn_search_terms('electric chula') == 'electric stove'

    def test_phrase_wins_over_subword(self):
        assert _translate_bn_search_terms('রাইস কুকার') == 'rice cooker'

    def test_english_untouched(self):
        assert _translate_bn_search_terms('hp laptop') == 'hp laptop'

    def test_empty(self):
        assert _translate_bn_search_terms('') == ''

    # ── Boundary-awareness: collisions confirmed by adversarial review ────────

    def test_khati_genuine_not_bed(self):
        # 'খাট' (bed) must not fire inside 'খাটি' (genuine/pure)
        out = _translate_bn_search_terms('খাটি মধু')
        assert 'bed' not in out
        assert 'খাটি' in out

    def test_khato_short_not_bed(self):
        out = _translate_bn_search_terms('খাটো টেবিল')
        assert 'bed' not in out
        assert 'table' in out

    def test_batil_cancel_not_light(self):
        # 'বাতি' (light) must not fire inside 'বাতিল' (cancel)
        out = _translate_bn_search_terms('অর্ডার বাতিল করেন')
        assert 'light' not in out

    def test_lighter_not_light(self):
        assert _translate_bn_search_terms('লাইটার') == 'lighter'

    def test_satellite_not_light(self):
        out = _translate_bn_search_terms('স্যাটেলাইট ডিশ')
        assert 'satellite' in out
        assert 'light' not in out

    def test_flight_not_light(self):
        assert 'light' not in _translate_bn_search_terms('ফ্লাইট')

    def test_batting_not_light(self):
        # Latin keys are word-bounded: 'batti' must not fire inside 'batting'
        assert _translate_bn_search_terms('batting gloves') == 'batting gloves'

    def test_mistiri_not_iron(self):
        assert 'iron' not in _translate_bn_search_terms('mistiri lagbe')

    def test_fancy_light_conjunct_safe(self):
        # 'ফ্যান' must not split the conjunct in 'ফ্যান্সি' — explicit key wins
        assert _translate_bn_search_terms('ফ্যান্সি লাইট') == 'fancy light'

    def test_gastric_not_gas(self):
        assert 'gas' not in _translate_bn_search_terms('গ্যাস্ট্রিক')

    def test_motorcycle_whole_word(self):
        assert _translate_bn_search_terms('মোটরসাইকেল') == 'motorcycle'

    def test_common_suffixes_consumed(self):
        assert _translate_bn_search_terms('খাটটা') == 'bed'
        assert _translate_bn_search_terms('টেবিলের দাম') .startswith('table')
        assert _translate_bn_search_terms('ব্যাটারির দাম').startswith('battery')

    # ── New entries: TV box, photostat, crimping ──────────────────────────────

    def test_smart_tv_box_phrase(self):
        out = _translate_bn_search_terms('স্মার্ট টিভি বক্স')
        assert 'smart tv box' in out

    def test_tv_box_phrase(self):
        out = _translate_bn_search_terms('টিভি বক্স')
        assert 'tv box' in out

    def test_smart_tv_phrase(self):
        out = _translate_bn_search_terms('স্মার্ট টিভি')
        assert 'smart tv' in out

    def test_tivi_standalone(self):
        assert 'tv' in _translate_bn_search_terms('টিভি')

    def test_box_standalone(self):
        assert 'box' in _translate_bn_search_terms('বক্স')

    def test_smartphone_not_smart_box(self):
        # 'স্মার্টফোন' must translate to smartphone, not trigger 'স্মার্ট টিভি' etc.
        out = _translate_bn_search_terms('স্মার্টফোন')
        assert 'smartphone' in out
        assert 'tv' not in out

    def test_photostat_translated(self):
        out = _translate_bn_search_terms('ফটোস্ট্যাট')
        assert 'photocopier' in out

    def test_photostat_misspelling(self):
        out = _translate_bn_search_terms('ফেটোস্ট্যাট')
        assert 'photocopier' in out

    def test_copy_machine_phrase(self):
        out = _translate_bn_search_terms('কপি মেশিন')
        assert 'photocopier' in out

    def test_photostat_copy_machine_full(self):
        out = _translate_bn_search_terms('ফেটোস্ট্যাট কপি মেশিন')
        assert 'photocopier' in out

    def test_climpting_misspelling(self):
        # 'climpting' (misspelling of crimping) should be mapped to 'crimping'
        out = _translate_bn_search_terms('climpting tools')
        assert 'crimping' in out
        assert 'climpting' not in out

    def test_crimping_search_not_regression(self):
        # 'crimping' itself (correctly spelled) must survive unchanged
        out = _translate_bn_search_terms('crimping tools')
        assert 'crimping' in out


class TestResultsMatchQuery:
    def test_garbage_results_rejected(self):
        assert _results_match_query('double electric stove', GARBAGE_PRODUCTS) is False

    def test_matching_results_accepted(self):
        assert _results_match_query('double electric stove', STOVE_PRODUCTS) is True

    def test_partial_token_match_accepted(self):
        # One matching token in one top title is enough
        assert _results_match_query('voltage protector', [
            {'title': 'TPoa Voltage Protector 3 Pin'},
        ]) is True

    def test_pure_bangla_query_trusted(self):
        # No Latin tokens → can't compare against English titles → trust
        assert _results_match_query('ডাবল চুলা', GARBAGE_PRODUCTS) is True


class TestSearchWithoutCategory:
    def setup_method(self):
        from repositories.state_repository import clear_product_state
        clear_product_state(UID)

    @patch('services.intent_handlers_service.search_products')
    def test_stove_query_garbage_results_fall_through(self, mock_search):
        # API returns unrelated fallback listings for every attempt →
        # _search_without_category must return None (caller asks the category)
        mock_search.return_value = {'products_found': 3, 'products': GARBAGE_PRODUCTS}
        ctx = {'category': '', 'brand': '', 'title': '',
               'price_max': None, 'price_min': None}
        result = _search_without_category(ctx, UID, 'ডাবল ইলেক্ট্রিক চুলা আছে?')
        assert result is None

    @patch('services.intent_handlers_service.search_products')
    def test_stove_query_translated_and_listed(self, mock_search):
        # API understands the translated English term → real stove listing
        mock_search.return_value = {'products_found': 1, 'products': STOVE_PRODUCTS}
        ctx = {'category': '', 'brand': '', 'title': '',
               'price_max': None, 'price_min': None}
        result = _search_without_category(ctx, UID, 'ডাবল ইলেক্ট্রিক চুলা আছে?')
        assert result is not None
        assert result['intent'] == 'product_search'
        assert 'Double Burner Electric Hot Plate Stove' in result['response']
        # The term actually sent to the API must be the translated English one
        sent_term = mock_search.call_args_list[0].args[0]
        assert 'stove' in sent_term
        assert 'চুলা' not in sent_term

    @patch('services.intent_handlers_service.search_products')
    def test_untranslatable_bangla_never_searched(self, mock_search):
        # Out-of-table pure-Bangla word: the English-only index can only return
        # junk and the guard can't compare Bangla to English titles — so don't
        # search at all; fall through to the category clarification.
        mock_search.return_value = {'products_found': 3, 'products': GARBAGE_PRODUCTS}
        ctx = {'category': '', 'brand': '', 'title': '',
               'price_max': None, 'price_min': None}
        result = _search_without_category(ctx, UID, 'ঝুড়ি আছে?')
        assert result is None
        mock_search.assert_not_called()

    @patch('services.intent_handlers_service.search_products')
    def test_rejection_path_garbage_blocked(self, mock_search):
        # "X নেই?" routes through the rejection branch — it must not display
        # the junk fallback either (review-confirmed exposure).
        from services.intent_handlers_service import handle_product_search
        mock_search.return_value = {'products_found': 3, 'products': GARBAGE_PRODUCTS}
        ctx = {'category': '', 'brand': '', 'title': '',
               'price_max': None, 'price_min': None}
        result = handle_product_search(ctx, UID, 'ডাবল ইলেক্ট্রিক চুলা নেই?')
        assert result['intent'] == 'no_products_found'
        assert 'Flat' not in result['response']

    @patch('services.intent_handlers_service.search_products')
    def test_rejection_path_pure_bangla_not_searched(self, mock_search):
        from services.intent_handlers_service import handle_product_search
        mock_search.return_value = {'products_found': 3, 'products': GARBAGE_PRODUCTS}
        ctx = {'category': '', 'brand': '', 'title': '',
               'price_max': None, 'price_min': None}
        result = handle_product_search(ctx, UID, 'ঝুড়ি নেই?')
        assert result['intent'] == 'no_products_found'
        mock_search.assert_not_called()

    @patch('services.intent_handlers_service.search_products')
    def test_english_query_unaffected(self, mock_search):
        mock_search.return_value = {'products_found': 1, 'products': [
            {'title': 'TPoa Voltage Protector 3 Pin', 'price': '৳ 450',
             'url': 'https://www.bdstall.com/details/vp-5/'},
        ]}
        ctx = {'category': '', 'brand': '', 'title': '',
               'price_max': None, 'price_min': None}
        result = _search_without_category(ctx, UID, 'voltage protector ase?')
        assert result is not None
        assert 'Voltage Protector' in result['response']
