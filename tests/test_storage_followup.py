from repositories.state_repository import clear_product_state, set_product_context
from services.intent_handlers_service import handle_product_detail_followup


UID = "storage-followup-user"
PRODUCT = {
    "title": "HP ProBook 440 G3 Core i3 6th Gen 16GB RAM 256GB SSD",
    "price": "18,500",
    "url": "https://www.bdstall.com/details/hp-probook-440-g3-12345/",
}


def setup_function():
    clear_product_state(UID)


def teardown_function():
    clear_product_state(UID)


def test_ssd_ase_with_single_product_answers_storage_spec(monkeypatch):
    set_product_context(UID, [PRODUCT])
    monkeypatch.setattr(
        "services.intent_handlers_service.load_context",
        lambda user_id: {},
    )
    monkeypatch.setattr(
        "services.intent_handlers_service.fetch_product_spec",
        lambda listing_id: {
            "title": PRODUCT["title"],
            "features": {"Hard Disk": "256GB SSD"},
            "review": "",
        },
    )

    result = handle_product_detail_followup({}, UID, "Ssd ase", PRODUCT["url"])

    assert result["intent"] == "product_spec_query"
    assert "256GB SSD" in result["response"]


def test_ssd_ase_with_multiple_products_asks_which_product(monkeypatch):
    set_product_context(UID, [
        PRODUCT,
        {
            "title": "HP Elitebook 840 G3 Core i5 16GB RAM 256GB SSD",
            "price": "23,999",
            "url": "https://www.bdstall.com/details/hp-elitebook-840-g3-67890/",
        },
    ])
    monkeypatch.setattr(
        "services.intent_handlers_service.load_context",
        lambda user_id: {},
    )

    result = handle_product_detail_followup({}, UID, "Ssd ase", PRODUCT["url"])

    assert result["intent"] == "product_clarification"


# ── _is_storage_drive_search: intended hits + collision guards ────────────────

from services.chatbot_service import _is_storage_drive_search


def test_storage_search_signals_detected():
    assert _is_storage_drive_search("ssd lagbe")
    assert _is_storage_drive_search("external hdd dekhao")
    assert _is_storage_drive_search("ssd price koto")
    assert _is_storage_drive_search("portable ssd chai")


def test_storage_spec_question_is_not_a_search():
    # availability/spec wording about a cached drive must NOT trigger a new search
    assert not _is_storage_drive_search("ei laptop e ssd ache")
    assert not _is_storage_drive_search("ssd ache ki")


def test_storage_complaint_is_not_a_search():
    # damaged-drive / refund complaints must reach the complaint flow, not search
    assert not _is_storage_drive_search("amar ssd damage hoyeche")
    assert not _is_storage_drive_search("ssd ta nosto, refund chai")


def test_storage_signal_word_boundaries():
    # 'show' must not match inside 'showroom', 'dam' not inside 'damage'
    assert not _is_storage_drive_search("hdd showroom e ache")
