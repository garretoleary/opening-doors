"""Writes replies.json: the invented replies the book gives during a run, so every run is repeatable.

A reply is data, never a model choice. For each account that replies: the touch it replies at
(1 to 4) and whether, after the mutual plan, the buyer accepts the ask and brings the buying
committee in. Accounts not listed never reply; after touch 5 they rest.
Run: python -m opening_doors.book.make_replies
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("replies.json")

REPLIES = {
    "acc-10": {"at_touch": 1, "committee": True},    # Dunwold Civil
    "acc-03": {"at_touch": 2, "committee": True},    # Quillon Health
    "acc-01": {"at_touch": 3, "committee": True},    # Harrowgate Lumen
    "acc-06": {"at_touch": 2, "committee": False},   # Pellmoor Rail Services
    "acc-02": {"at_touch": 4, "committee": False},   # Veldstone Marine
    "acc-07": {"at_touch": 1, "committee": False},   # Caskellon Energy
    "acc-11": {"at_touch": 3, "committee": False},   # Sablefern Pharma Services
    "acc-17": {"at_touch": 4, "committee": True},    # Stornbridge Capital Partners
}

def build() -> dict:
    return {
        "notice": "All data invented. These replies are made up so the demonstration is repeatable; they are data, not a model's choice.",
        "as_of": "2026-10-16",
        "replies": [{"id": k, **v, "invented": True} for k, v in REPLIES.items()],
    }

if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} with {len(REPLIES)} replies")
