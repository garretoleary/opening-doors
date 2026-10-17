"""Agent 1, Researcher. Reads the book of 25 accounts and their invented signals.
Permitted: read book, read signals. Not permitted: write, send."""
from __future__ import annotations

import json
from typing import Dict, List

from .base import Agent

NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "strongest_signal": {"type": "string"},
                    "why_now": {"type": "string"},
                    "identity_gap": {"type": "string"},
                    "likely_buyer": {"type": "string"},
                },
                "required": ["id", "strongest_signal", "why_now", "identity_gap", "likely_buyer"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["notes"],
    "additionalProperties": False,
}


class Researcher(Agent):
    agent_id = "agent-1"
    name = "Researcher"
    purpose = "Reads the book of 25 accounts and their signals; writes nothing, sends nothing"
    colour = "#E69F00"
    rules_key = "researcher"

    def run(self, book: dict) -> List[Dict]:
        self.set_status("running")
        n = f"{len(book['accounts'])} accounts"
        accounts = self.act("read_book", n, lambda: book["accounts"], what="read book")
        signals = self.act(
            "read_signals", n,
            lambda: [{"id": a["id"], "name": a["name"], "sector": a["sector"], "employees": a["employees"],
                      "people": a["people"], "signals": a["signals"], "access_setup_today": a["access_setup_today"]}
                     for a in accounts],
            what="read signals",
        )
        user = "Accounts, as JSON:\n" + json.dumps(signals, ensure_ascii=False)
        result = self.ask(self.system_prompt, user, NOTE_SCHEMA, 8000)
        by_id = {n["id"]: n for n in result["notes"]}
        names = {a["id"]: a["name"] for a in accounts}
        notes = [dict(by_id[a["id"]], name=names[a["id"]]) for a in accounts if a["id"] in by_id]
        self.set_status("done")
        return notes
