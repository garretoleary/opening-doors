"""Agent 2, Scorer. Ranks the 25 against the ideal client profile and states, for each,
why it was selected and how it was found. Permitted: read Researcher output, write scores."""
from __future__ import annotations

import json
from typing import Dict, List

from .base import INVENTED, Agent

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "integer"},
                    "why_selected": {"type": "string"},
                    "how_found": {"type": "string"},
                },
                "required": ["id", "score", "why_selected", "how_found"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scores"],
    "additionalProperties": False,
}


class Scorer(Agent):
    agent_id = "agent-2"
    name = "Scorer"
    purpose = "Ranks the 25 against the ideal client profile; says why each was selected and how it was found"
    colour = "#56B4E9"
    system_prompt = (
        f"{INVENTED}\nYou are the Scorer on a sales desk. Score every account from 0 to 100 against the ideal "
        "client profile. Higher means a stronger reason to open the door this quarter. why_selected: one plain "
        "sentence a sales leader would accept, naming the trigger and the gap. how_found: which signal surfaced "
        "it, in a few words, e.g. 'new COO, 1 September' or 'three identity roles posted'. Use the whole range; "
        "do not bunch scores. Return a score for every account id, in the same order."
    )

    def run(self, notes: List[Dict], icp: dict) -> List[Dict]:
        self.set_status("running")
        research = self.act("read_research", f"{len(notes)} notes", lambda: notes, what="read research")
        user = ("Ideal client profile:\n" + json.dumps(icp, ensure_ascii=False)
                + "\n\nResearch notes, as JSON:\n" + json.dumps(research, ensure_ascii=False))

        def score() -> List[Dict]:
            result = self.ask(self.system_prompt, user, SCORE_SCHEMA, 8000)
            by_id = {s["id"]: s for s in result["scores"]}
            names = {n["id"]: n["name"] for n in notes}
            scored = [dict(by_id[n["id"]], name=names[n["id"]]) for n in notes if n["id"] in by_id]
            scored.sort(key=lambda s: -s["score"])
            for rank, s in enumerate(scored, start=1):
                s["rank"] = rank
            return scored

        ranked = self.act("write_scores", "", score, what=f"ranked {len(notes)}",
                          detail_of=lambda r: f"top: {r[0]['name']}" if r else "")
        self.set_status("done")
        return ranked
