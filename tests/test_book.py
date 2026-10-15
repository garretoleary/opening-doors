import pytest

from opening_doors.book import BookError, accounts, icp, load_book, validate


def test_book_loads_with_25_invented_accounts():
    book = load_book()
    assert len(book["accounts"]) == 25
    assert "invented" in book["notice"].lower()
    assert all(a["invented"] for a in book["accounts"])


def test_every_account_in_size_range_with_signal_and_person():
    for a in accounts():
        assert 4000 <= a["employees"] <= 20000
        assert a["signals"] and a["people"]
        assert a["relationship"] == "none"


def test_signals_are_recent():
    for a in accounts():
        for s in a["signals"]:
            assert "2026-08-01" <= s["date"] <= "2026-10-15"


def test_icp_present():
    assert "fit" in icp() and icp()["size"].startswith("4,000")


def test_validation_catches_bad_size():
    book = load_book()
    book["accounts"][0]["employees"] = 900
    with pytest.raises(BookError):
        validate(book)


def test_access_setup_today_present_and_holds_no_credentials():
    for a in accounts():
        assert a["access_setup_today"] and "identity_today" not in a
        low = a["access_setup_today"].lower()
        assert "password:" not in low and "token" not in low and "@" not in low
