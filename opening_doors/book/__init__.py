"""The book: 25 invented accounts and their invented signals.

Loaded once, validated, read-only. Agents reach it only through the governance gate.
"""
from __future__ import annotations

import json
from typing import Dict, List

from ..config import BOOK_PATH

NOTICE = "All data invented."


class BookError(Exception):
    pass


def load_book() -> dict:
    data = json.loads(BOOK_PATH.read_text(encoding="utf-8"))
    validate(data)
    return data


def validate(data: dict) -> None:
    accounts = data.get("accounts", [])
    if len(accounts) != 25:
        raise BookError(f"expected 25 accounts, found {len(accounts)}")
    names = [a["name"] for a in accounts]
    if len(set(names)) != 25:
        raise BookError("account names must be unique")
    for a in accounts:
        if not (4000 <= a["employees"] <= 20000):
            raise BookError(f"{a['name']}: employees {a['employees']} outside 4,000 to 20,000")
        if a.get("relationship") != "none":
            raise BookError(f"{a['name']}: the book is named accounts with no relationship yet")
        if not a.get("signals"):
            raise BookError(f"{a['name']}: no signals")
        if not a.get("access_setup_today"):
            raise BookError(f"{a['name']}: missing access_setup_today")
        if a.get("invented") is not True:
            raise BookError(f"{a['name']}: every account must be marked invented")
    if "invented" not in data.get("notice", "").lower():
        raise BookError("the book must carry the invented-data notice")


def accounts() -> List[Dict]:
    return load_book()["accounts"]


def icp() -> dict:
    return load_book()["icp"]
