"""Agent 6, Qualifier. After the first call, runs a light MEDDPICC, frames the problem and the
value, sized, and drafts the mutual plan: you will do this, I will do this, by this date, with the
explicit ask to bring the boss and the buying committee in.
Permitted: read call notes, write qualification, write value frame, write mutual plan.
Not permitted: read the raw book, send.

The value method is described generically: value identified, value framed, value realised.
Never by a vendor's name. No technical lead line.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Dict, List, Optional

from .base import Agent

QUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "qualification": {
            "type": "object",
            "properties": {
                "metrics": {"type": "string"},
                "economic_buyer": {"type": "string"},
                "decision_criteria": {"type": "string"},
                "decision_process": {"type": "string"},
                "paper_process": {"type": "string"},
                "identified_pain": {"type": "string"},
                "champion": {"type": "string"},
                "competition": {"type": "string"},
                "gaps": {"type": "string"},
            },
            "required": ["metrics", "economic_buyer", "decision_criteria", "decision_process", "paper_process",
                         "identified_pain", "champion", "competition", "gaps"],
            "additionalProperties": False,
        },
        "value_frame": {
            "type": "object",
            "properties": {
                "problem_identified": {"type": "string"},
                "value_defined": {"type": "string"},
                "value_sized": {"type": "string"},
                "how_value_is_realised": {"type": "string"},
            },
            "required": ["problem_identified", "value_defined", "value_sized", "how_value_is_realised"],
            "additionalProperties": False,
        },
        "mutual_plan": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "who": {"type": "string"},
                            "what": {"type": "string"},
                            "by": {"type": "string"},
                        },
                        "required": ["who", "what", "by"],
                        "additionalProperties": False,
                    },
                },
                "the_ask": {"type": "string"},
            },
            "required": ["goal", "steps", "the_ask"],
            "additionalProperties": False,
        },
    },
    "required": ["qualification", "value_frame", "mutual_plan"],
    "additionalProperties": False,
}

FORBIDDEN_PHRASES = ("technical lead",)


class Qualifier(Agent):
    agent_id = "agent-6"
    name = "Qualifier"
    purpose = "After the first call: light MEDDPICC, the problem and value framed and sized, the mutual plan with the ask to bring the boss and the committee in; never sees the raw book, never sends"
    colour = "#CC79A7"
    rules_key = "qualifier"

    def run(self, handoffs: List[Dict], call_notes: Dict[str, str], today: Optional[date] = None) -> Dict[str, Dict]:
        self.set_status("running")
        today = today or date.today()
        def work(h: Dict):
            return lambda: self._one(h, call_notes, today)

        raw = self.each_in_parallel((h["account_id"], work(h)) for h in handoffs)
        out = {h["account_id"]: raw[h["account_id"]] for h in handoffs}
        self.set_status("done")
        return out

    def _one(self, h: Dict, call_notes: Dict[str, str], today: date) -> Dict:
        if True:
            pid, name = h["account_id"], h["name"]
            note = self.act("read_call_notes", name, lambda p=pid: call_notes[p], what="read call notes")
            user = (f"Today: {today.isoformat()}. Account: {name}. Replied at {h['replied_at']}; first call done.\n"
                    f"First-call note, invented:\n{note}")

            def qualify(u: str = user) -> Dict:
                result = self.ask(self.system_prompt, u, QUAL_SCHEMA, 4000)
                text = json.dumps(result).lower()
                for phrase in FORBIDDEN_PHRASES:
                    if phrase in text:
                        raise ValueError(f"'{phrase}' is not allowed in the qualification")
                return result

            result = self.act("write_qualification", name, qualify, what="qualified, MEDDPICC-lite",
                              detail_of=lambda r: f"champion: {r['qualification']['champion'][:40]}")
            value = self.act("write_value_frame", name, lambda r=result: r["value_frame"], what="value framed",
                             detail_of=lambda v: v["value_sized"][:60])
            plan = self.act("write_mutual_plan", name, lambda r=result: r["mutual_plan"], what="mutual plan drafted",
                            detail_of=lambda p: f"{len(p['steps'])} steps, ask to bring the committee in")
            return {"id": pid, "name": name, "replied_at": h["replied_at"],
                    "qualification": result["qualification"], "value_frame": value, "mutual_plan": plan}
