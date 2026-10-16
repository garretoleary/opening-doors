"""The book: 25 invented accounts and their invented signals.

Loaded once, validated, read-only. Agents reach it only through the governance gate.
"""
from __future__ import annotations

import json
from typing import Dict, List

from ..config import BOOK_PATH, CALL_NOTES_PATH, REPLIES_PATH

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


def call_notes() -> dict:
    """Invented first-call notes, one per account, keyed by account id. Separate from the book."""
    data = json.loads(CALL_NOTES_PATH.read_text(encoding="utf-8"))
    if "invented" not in data.get("notice", "").lower():
        raise BookError("call notes must carry the invented-data notice")
    notes = {n["id"]: n["note"] for n in data["notes"] if n.get("invented") is True}
    if len(notes) != 25:
        raise BookError(f"expected 25 invented call notes, found {len(notes)}")
    return notes


def replies() -> Dict[str, Dict]:
    """Invented replies, keyed by account id: at_touch 1 to 4, committee True or False."""
    data = json.loads(REPLIES_PATH.read_text(encoding="utf-8"))
    if "invented" not in data.get("notice", "").lower():
        raise BookError("replies must carry the invented-data notice")
    out = {}
    for r in data["replies"]:
        if r.get("invented") is not True or not (1 <= int(r["at_touch"]) <= 4):
            raise BookError(f"{r.get('id')}: a reply is invented and arrives at touch 1 to 4")
        out[r["id"]] = {"at_touch": int(r["at_touch"]), "committee": bool(r["committee"])}
    return out
