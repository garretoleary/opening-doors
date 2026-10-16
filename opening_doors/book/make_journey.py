"""Writes journey.json: where each account stands in the five-touch sequence when a run begins,
and how it will answer. The run depicts a book a few weeks in. All invented, all data, so every
run is repeatable.

Per account: days_in, the day of the sequence reached (0 = not yet touched); at_touch, the touch
the buyer replies at, 1 to 4, or null for never; committee, whether after the mutual plan the
buyer brings the boss and the buying committee in. Touch days are Garret's: 1, 5, 8, 11, 18.
Accounts not listed have not been touched.
Run: python -m opening_doors.book.make_journey
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("journey.json")

JOURNEY = {
    # the ten the Scorer usually puts top: this run drafts and plays them to their day
    "acc-01": {"days_in": 10, "at_touch": 3, "committee": True},    # Harrowgate Lumen: replied at T3, committee in
    "acc-10": {"days_in": 10, "at_touch": 1, "committee": True},    # Dunwold Civil
    "acc-03": {"days_in": 10, "at_touch": 2, "committee": True},    # Quillon Health
    "acc-06": {"days_in": 10, "at_touch": 2, "committee": False},   # Pellmoor Rail Services: qualified
    "acc-02": {"days_in": 12, "at_touch": 4, "committee": False},   # Veldstone Marine
    "acc-07": {"days_in": 10, "at_touch": 1, "committee": False},   # Caskellon Energy
    "acc-19": {"days_in": 10, "at_touch": 3, "committee": False},   # Morrowick Care Homes
    "acc-12": {"days_in": 9,  "at_touch": None, "committee": False},  # Lantergate Retail: T3 given, awaiting a reply
    "acc-16": {"days_in": 12, "at_touch": None, "committee": False},  # Ashcombe Dental Partners: T4 given, awaiting
    "acc-24": {"days_in": 20, "at_touch": None, "committee": False},  # Ravensholt Engineering Group: resting after T5
    # worked in an earlier wave, outside this run's top ten: their position is read from the book
    "acc-11": {"days_in": 9,  "at_touch": None, "committee": False},  # Sablefern Pharma Services: T3, awaiting
    "acc-17": {"days_in": 12, "at_touch": None, "committee": False},  # Stornbridge Capital Partners: T4, awaiting
    "acc-04": {"days_in": 20, "at_touch": None, "committee": False},  # Brackwater Foods: resting
    "acc-08": {"days_in": 20, "at_touch": None, "committee": False},  # Tarnbeck Logistics: resting
}

def build() -> dict:
    return {
        "notice": "All data invented. Each account's place in the sequence and its reply are made up so the demonstration is repeatable; they are data, not a model's choice.",
        "as_of": "2026-10-16",
        "journey": [{"id": k, **v, "invented": True} for k, v in JOURNEY.items()],
    }

if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} with {len(JOURNEY)} positions")
