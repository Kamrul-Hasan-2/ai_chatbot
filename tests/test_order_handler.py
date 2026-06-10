"""
tests/test_order_handler.py — unit tests for the order placement flow.

Covers:
  - Greeting reset mid-order
  - Price negotiation mid-order
  - Cancel
  - Field parsing (labelled, freeform, smart single-missing follow-up)
  - Address validator accepts short inputs
  - Full happy-path flow (collect → confirm → place)
  - Order flow not entered for unknown user
"""
import pytest
from unittest.mock import patch, MagicMock

# ── import the module under test ──────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.order_handler import (
    start_order_flow, continue_order_flow, is_in_order_flow,
    _is_greeting_reset, _is_price_negotiation, _is_cancel, _is_confirm,
    _is_product_search_escape,
    _extract_fields, _parse_labelled_lines, _parse_freeform,
    _validate_and_resolve, _match_city, _match_area,
    STEP_COLLECT, STEP_CONFIRM,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CITIES = [
    {'city_id': '1',  'city_name': 'Dhaka'},
    {'city_id': '2',  'city_name': 'Chittagong'},
    {'city_id': '3',  'city_name': 'Sylhet'},
    {'city_id': '4',  'city_name': 'Khulna'},
]

SAMPLE_AREAS = [
    {'area_id': '10', 'area_name': 'Mirpur',     'city_id': '1'},
    {'area_id': '11', 'area_name': 'Dhanmondi',  'city_id': '1'},
    {'area_id': '12', 'area_name': 'Gulshan',    'city_id': '1'},
    {'area_id': '20', 'area_name': 'Agrabad',    'city_id': '2'},
    {'area_id': '21', 'area_name': 'Patenga',    'city_id': '2'},
]

SAMPLE_PRODUCT = {
    'title': 'DZ09 Smart Watch',
    'url':   'https://www.bdstall.com/details/dz09-smart-watch-27344/',
}

UID = 'test_user_001'


def _clear_state():
    from repositories.state_repository import clear_order_flow
    clear_order_flow(UID)


# ── Helpers ───────────────────────────────────────────────────────────────────

class TestIsGreetingReset:
    def test_hi(self):
        assert _is_greeting_reset('hi') is True

    def test_hii(self):
        assert _is_greeting_reset('Hii') is True

    def test_hello(self):
        assert _is_greeting_reset('HELLO') is True

    def test_salam(self):
        assert _is_greeting_reset('salam') is True

    def test_assalamualaikum(self):
        assert _is_greeting_reset('assalamualaikum') is True

    def test_bangla_hai(self):
        assert _is_greeting_reset('হাই') is True

    def test_bangla_salam(self):
        assert _is_greeting_reset('সালাম') is True

    def test_good_morning(self):
        assert _is_greeting_reset('good morning') is True

    def test_hi_i_want_to_order_is_not_reset(self):
        # Contains content beyond the greeting word
        assert _is_greeting_reset('hi i want to order') is False

    def test_product_message_is_not_reset(self):
        assert _is_greeting_reset('laptop lagbe') is False

    def test_empty_is_not_reset(self):
        assert _is_greeting_reset('') is False

    def test_too_long_is_not_reset(self):
        assert _is_greeting_reset('hi ' * 10) is False


class TestIsProductSearchEscape:
    def test_brand_plus_ase(self):
        assert _is_product_search_escape('hp laptop ase') is True

    def test_brand_plus_lagbe(self):
        assert _is_product_search_escape('samsung phone lagbe') is True

    def test_category_plus_dekhao(self):
        assert _is_product_search_escape('laptop dekhao') is True

    def test_category_plus_chai(self):
        assert _is_product_search_escape('AC chai') is True

    def test_bare_brand_not_escape(self):
        # Just "hp" alone could be a name in the form
        assert _is_product_search_escape('hp') is False

    def test_bare_search_signal_not_escape(self):
        # "ase" alone is too ambiguous
        assert _is_product_search_escape('ase') is False

    def test_order_form_value_not_escape(self):
        # A name reply should not escape
        assert _is_product_search_escape('Rahim Ahmed') is False

    def test_address_not_escape(self):
        assert _is_product_search_escape('House 5, Road 3, Mirpur') is False

    def test_empty_not_escape(self):
        assert _is_product_search_escape('') is False


class TestIsPriceNegotiation:
    def test_discount(self):
        assert _is_price_negotiation('discount daben?') is True

    def test_dam_komano(self):
        assert _is_price_negotiation('dam komano jabe?') is True

    def test_bangla_chad(self):
        assert _is_price_negotiation('ছাড় দিন') is True

    def test_fixed_naki(self):
        assert _is_price_negotiation('fixed naki price?') is True

    def test_normal_message_not_price(self):
        assert _is_price_negotiation('Dhaka') is False

    def test_name_not_price(self):
        assert _is_price_negotiation('Karim') is False


class TestIsCancel:
    def test_cancel(self):
        assert _is_cancel('cancel') is True

    def test_batil(self):
        assert _is_cancel('বাতিল') is True

    def test_stop(self):
        assert _is_cancel('stop') is True

    def test_order_message_not_cancel(self):
        assert _is_cancel('Karim, 01711111111') is False


class TestIsConfirm:
    def test_haa(self):
        assert _is_confirm('হ্যাঁ') is True

    def test_yes(self):
        assert _is_confirm('yes') is True

    def test_ok(self):
        assert _is_confirm('ok') is True

    def test_ji(self):
        assert _is_confirm('ji') is True

    def test_confirm(self):
        assert _is_confirm('confirm') is True

    def test_no_is_not_confirm(self):
        assert _is_confirm('না') is False

    def test_empty_not_confirm(self):
        assert _is_confirm('') is False


# ── Parser ────────────────────────────────────────────────────────────────────

class TestParseLabelledLines:
    def test_all_six_fields(self):
        text = (
            "নাম: Karim\n"
            "মোবাইল: 01711111111\n"
            "ঠিকানা: Road 5, House 10\n"
            "জেলা: Dhaka\n"
            "এলাকা: Mirpur\n"
            "পরিমাণ: 2\n"
        )
        out = _parse_labelled_lines(text)
        assert out['name'] == 'Karim'
        assert out['mobile'] == '01711111111'
        assert out['address'] == 'Road 5, House 10'
        assert out['city'] == 'Dhaka'
        assert out['area'] == 'Mirpur'
        assert out['qty'] == '2'

    def test_english_labels(self):
        out = _parse_labelled_lines("name: Rahim\nphone: 01811111111\naddress: Sylhet")
        assert out['name'] == 'Rahim'
        assert out['mobile'] == '01811111111'
        assert out['address'] == 'Sylhet'

    def test_equals_separator(self):
        out = _parse_labelled_lines("name = Salam\nqty = 3")
        assert out['name'] == 'Salam'
        assert out['qty'] == '3'

    def test_unlabelled_line_ignored(self):
        out = _parse_labelled_lines("Rahim Ahmed\n01711111111")
        assert out == {}


class TestParseFreeform:
    def test_name_and_mobile(self):
        out = _parse_freeform("Karim\n01711111111")
        assert out.get('name') == 'Karim'
        assert out.get('mobile') == '01711111111'

    def test_mobile_embedded_in_text(self):
        out = _parse_freeform("call me at 01711111111")
        assert out.get('mobile') == '01711111111'

    def test_qty_last_number(self):
        out = _parse_freeform("Karim\n01711111111\nDhaka\n2")
        assert out.get('qty') == '2'

    def test_address_is_longest_line(self):
        out = _parse_freeform("Rahim\n01811111111\nHouse 12, Road 5, Banani, Dhaka 1213")
        assert 'Banani' in (out.get('address') or '')


class TestExtractFields:
    def test_labelled_overrides_freeform(self):
        # Mobile appears in freeform position but also as a label — label wins
        text = "নাম: Karim\nমোবাইল: 01711111111\nঠিকানা: House 5 Road 3\nজেলা: Dhaka\nএলাকা: Mirpur\nপরিমাণ: 1"
        out = _extract_fields(text)
        assert out['name'] == 'Karim'
        assert out['mobile'] == '01711111111'


# ── Validator / resolver ──────────────────────────────────────────────────────

class TestValidateAndResolve:
    def test_all_fields_valid(self):
        state = {}
        extracted = {
            'name': 'Rahim',
            'mobile': '01711111111',
            'address': 'House 5',
            'city': 'Dhaka',
            'area': 'Mirpur',
            'qty': '1',
        }
        state, missing = _validate_and_resolve(state, extracted, SAMPLE_CITIES, SAMPLE_AREAS)
        assert missing == []
        assert state['name'] == 'Rahim'
        assert state['mobile'] == '01711111111'
        assert state['city_id'] == '1'
        assert state['area_id'] == '10'
        assert state['qty'] == 1

    def test_short_address_accepted(self):
        state = {}
        extracted = {'address': 'ab', 'name': 'X', 'mobile': '01711111111',
                     'city': 'Dhaka', 'area': 'Mirpur', 'qty': '1'}
        _, missing = _validate_and_resolve(state, extracted, SAMPLE_CITIES, SAMPLE_AREAS)
        assert 'ঠিকানা' not in missing

    def test_address_four_chars_accepted(self):
        state = {}
        extracted = {'address': 'Ulon', 'name': 'X', 'mobile': '01711111111',
                     'city': 'Dhaka', 'area': 'Mirpur', 'qty': '1'}
        _, missing = _validate_and_resolve(state, extracted, SAMPLE_CITIES, SAMPLE_AREAS)
        assert 'ঠিকানা' not in missing

    def test_missing_all_fields_reported(self):
        state = {}
        _, missing = _validate_and_resolve(state, {}, SAMPLE_CITIES, SAMPLE_AREAS)
        assert len(missing) == 6

    def test_unknown_city_not_resolved(self):
        state = {}
        extracted = {'city': 'Narnia'}
        state, _ = _validate_and_resolve(state, extracted, SAMPLE_CITIES, SAMPLE_AREAS)
        assert 'city_id' not in state

    def test_area_filtered_by_city(self):
        state = {'city_id': '2', 'city_name': 'Chittagong'}
        extracted = {'area': 'Agrabad'}
        state, missing = _validate_and_resolve(state, extracted, SAMPLE_CITIES, SAMPLE_AREAS)
        assert state.get('area_id') == '20'


class TestMatchCity:
    def test_exact_name(self):
        c = _match_city('Dhaka', SAMPLE_CITIES)
        assert c['city_id'] == '1'

    def test_substring_match(self):
        c = _match_city('live in Chittagong city', SAMPLE_CITIES)
        assert c['city_id'] == '2'

    def test_no_match_returns_none(self):
        assert _match_city('Narnia', SAMPLE_CITIES) is None


class TestMatchArea:
    def test_exact_area(self):
        a = _match_area('Mirpur', SAMPLE_AREAS, '1')
        assert a['area_id'] == '10'

    def test_area_from_wrong_city_not_returned(self):
        # Agrabad is in city_id=2, not 1
        a = _match_area('Agrabad', SAMPLE_AREAS, '1')
        assert a is None

    def test_no_city_returns_none(self):
        assert _match_area('Mirpur', SAMPLE_AREAS, '') is None


# ── Flow (mocked state + API) ─────────────────────────────────────────────────

@patch('services.order_handler.fetch_city_list', return_value=SAMPLE_CITIES)
@patch('services.order_handler.fetch_area_list', return_value=SAMPLE_AREAS)
class TestOrderFlow:

    def setup_method(self):
        _clear_state()

    def test_start_flow_returns_collect_prompt(self, mock_areas, mock_cities):
        result = start_order_flow(UID, SAMPLE_PRODUCT)
        assert result['intent'] == 'order_collect'
        assert 'নাম' in result['response']
        assert is_in_order_flow(UID)

    def test_start_flow_missing_listing_id(self, mock_areas, mock_cities):
        bad_product = {'title': 'Test', 'url': 'https://www.bdstall.com/details/no-id/'}
        result = start_order_flow(UID, bad_product)
        assert result['intent'] == 'order_no_listing_id'

    def test_greeting_reset_clears_flow(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        assert is_in_order_flow(UID)
        result = continue_order_flow(UID, 'Hi')
        assert result is None
        assert not is_in_order_flow(UID)

    def test_salam_reset_clears_flow(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        result = continue_order_flow(UID, 'সালাম')
        assert result is None
        assert not is_in_order_flow(UID)

    def test_cancel_clears_flow(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        result = continue_order_flow(UID, 'বাতিল')
        assert result['intent'] == 'order_cancelled'
        assert not is_in_order_flow(UID)

    def test_price_negotiation_returns_fixed_and_preserves_state(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        # Provide a valid name first
        continue_order_flow(UID, 'নাম: Rahim')
        result = continue_order_flow(UID, 'discount daben?')
        assert result['intent'] == 'order_price_fixed'
        assert 'ফিক্সড' in result['response']
        # Flow still active (price message re-shows form, keeps state)
        assert is_in_order_flow(UID)

    def test_missing_fields_reported(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        result = continue_order_flow(UID, 'Rahim')  # only name, everything else missing
        assert result['intent'] == 'order_collect'
        # At least one missing field bullet expected
        assert '•' in result['response']

    def test_smart_followup_single_missing_assigns_whole_reply(self, mock_areas, mock_cities):
        # Pre-fill all fields except city
        from repositories.state_repository import set_order_flow
        set_order_flow(UID, {
            'step': STEP_COLLECT,
            'product_title': 'Watch',
            'product_url': SAMPLE_PRODUCT['url'],
            'listing_id': '27344',
            'name': 'Rahim',
            'mobile': '01711111111',
            'address': 'House 5',
            'qty': 1,
        })
        result = continue_order_flow(UID, 'Dhaka')  # unlabelled, only city missing
        # Should resolve Dhaka as city and move to confirm or ask for area
        assert result is not None
        # Response should NOT treat "Dhaka" as a name
        response = result['response']
        assert 'Dhaka' not in response or 'নাম' not in response

    def test_all_fields_moves_to_confirm(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        full_reply = (
            "নাম: Rahim Ahmed\n"
            "মোবাইল: 01711111111\n"
            "ঠিকানা: House 5 Road 3\n"
            "জেলা: Dhaka\n"
            "এলাকা: Mirpur\n"
            "পরিমাণ: 1"
        )
        result = continue_order_flow(UID, full_reply)
        assert result['intent'] == 'order_confirm'
        assert 'নিশ্চিত' in result['response'] or 'হ্যাঁ' in result['response']

    @patch('services.order_handler.place_order')
    def test_confirm_yes_places_order(self, mock_place, mock_areas, mock_cities):
        mock_place.return_value = {
            'success': True,
            'message': 'Order placed',
            'order_no': '17805661821',
            'order_id': '99',
        }
        start_order_flow(UID, SAMPLE_PRODUCT)
        full_reply = (
            "নাম: Rahim Ahmed\n"
            "মোবাইল: 01711111111\n"
            "ঠিকানা: House 5 Road 3\n"
            "জেলা: Dhaka\n"
            "এলাকা: Mirpur\n"
            "পরিমাণ: 1"
        )
        continue_order_flow(UID, full_reply)   # → confirm step
        result = continue_order_flow(UID, 'হ্যাঁ')
        assert result['intent'] == 'order_placed'
        assert '17805661821' in result['response']
        assert 'প্রতিনিধি' in result['response']
        assert not is_in_order_flow(UID)

    @patch('services.order_handler.place_order')
    def test_confirm_no_asks_again(self, mock_place, mock_areas, mock_cities):
        mock_place.return_value = {'success': True, 'order_no': '123', 'order_id': '1'}
        start_order_flow(UID, SAMPLE_PRODUCT)
        full_reply = (
            "নাম: Rahim Ahmed\n"
            "মোবাইল: 01711111111\n"
            "ঠিকানা: House 5\n"
            "জেলা: Dhaka\n"
            "এলাকা: Mirpur\n"
            "পরিমাণ: 1"
        )
        continue_order_flow(UID, full_reply)   # → confirm step
        result = continue_order_flow(UID, 'not now')
        assert result['intent'] == 'order_confirm'
        # Flow still active awaiting proper confirm
        assert is_in_order_flow(UID)

    @patch('services.order_handler.place_order')
    def test_api_failure_returns_error(self, mock_place, mock_areas, mock_cities):
        mock_place.return_value = {'success': False, 'message': 'Server error'}
        start_order_flow(UID, SAMPLE_PRODUCT)
        full_reply = (
            "নাম: Rahim Ahmed\n"
            "মোবাইল: 01711111111\n"
            "ঠিকানা: House 5\n"
            "জেলা: Dhaka\n"
            "এলাকা: Mirpur\n"
            "পরিমাণ: 1"
        )
        continue_order_flow(UID, full_reply)
        result = continue_order_flow(UID, 'হ্যাঁ')
        assert result['intent'] == 'order_failed'
        # On a transient API failure the flow is PRESERVED at STEP_CONFIRM so the
        # user can retry with "হ্যাঁ" without re-entering everything. (fix #1)
        assert is_in_order_flow(UID)

    def test_product_search_mid_order_clears_flow(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        assert is_in_order_flow(UID)
        result = continue_order_flow(UID, 'hp laptop ase')
        assert result is None
        assert not is_in_order_flow(UID)

    def test_samsung_phone_lagbe_clears_flow(self, mock_areas, mock_cities):
        start_order_flow(UID, SAMPLE_PRODUCT)
        result = continue_order_flow(UID, 'samsung phone lagbe')
        assert result is None
        assert not is_in_order_flow(UID)

    def test_not_in_flow_returns_none(self, mock_areas, mock_cities):
        _clear_state()
        result = continue_order_flow(UID, 'hello')
        assert result is None

    def test_success_message_has_protinidhi_not_bikreta(self, mock_areas, mock_cities):
        with patch('services.order_handler.place_order') as mock_place:
            mock_place.return_value = {'success': True, 'order_no': '12345', 'order_id': '1'}
            start_order_flow(UID, SAMPLE_PRODUCT)
            full_reply = (
                "নাম: Rahim\nমোবাইল: 01711111111\nঠিকানা: House 5\n"
                "জেলা: Dhaka\nএলাকা: Mirpur\nপরিমাণ: 1"
            )
            continue_order_flow(UID, full_reply)
            result = continue_order_flow(UID, 'হ্যাঁ')
            assert 'বিক্রেতা' not in result['response']
            assert 'প্রতিনিধি' in result['response']


# ── Order status helper ───────────────────────────────────────────────────────

class TestExtractOrderNo:
    def test_extract_plain_order_no(self):
        from services.intent_handlers_service import _extract_order_no
        assert _extract_order_no('order status 17805661821') == '17805661821'

    def test_mobile_number_not_extracted(self):
        from services.intent_handlers_service import _extract_order_no
        # A mobile (01XXXXXXXXX) should not be treated as an order number
        result = _extract_order_no('call me at 01711111111')
        assert result == '' or result is None

    def test_short_number_not_extracted(self):
        from services.intent_handlers_service import _extract_order_no
        result = _extract_order_no('order 1234567')  # 7 digits — too short
        assert result == '' or result is None
