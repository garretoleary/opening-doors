"""Agent 4, Writer. Drafts each of the five touches for each top-ten account, matched to that
account's signal, never a template. Permitted: read plans, write drafts.
Not permitted: read the raw book, send anything."""
from __future__ import annotations

import json
from typing import Dict, List

from .base import Agent

TOUCHES = [
    (1, "insight email"),
    (2, "insight email"),
    (3, "LinkedIn connection request"),
    (4, "call, no voicemail, then email"),
    (5, "break-up email"),
]

TOUCH_SCHEMA = {
    "type": "object",
    "properties": {
        "touches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "touch": {"type": "integer"},
                    "kind": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "matched_to": {"type": "string"},
                },
                "required": ["touch", "kind", "subject", "body", "matched_to"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["touches"],
    "additionalProperties": False,
}

# The plan is all the Writer sees. These are the only keys it is handed.
PLAN_KEYS = ("name", "rank", "signal", "why", "business_problem", "economic_buyer",
             "first_meeting_point_of_view", "one_metric_to_agree")


class Writer(Agent):
    agent_id = "agent-4"
    name = "Writer"
    purpose = "Drafts the five touches for each top-ten account from its plan; never sees the raw book, never sends"
    colour = "#0072B2"
    rules_key = "writer"

    def run(self, plans: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        self.set_status("running")
        seen = self.act("read_plans", f"{len(plans)} plans",
                        lambda: {pid: {k: p[k] for k in PLAN_KEYS if k in p} for pid, p in plans.items()},
                        what="read plans")
        def work(plan: Dict):
            user = "Account plan, as JSON:\n" + json.dumps(plan, ensure_ascii=False)

            def draft() -> List[Dict]:
                result = self.ask(self.system_prompt, user, TOUCH_SCHEMA, 4000)
                touches = sorted(result["touches"], key=lambda t: t["touch"])
                if [t["touch"] for t in touches] != [1, 2, 3, 4, 5]:
                    raise ValueError("the Writer must return touches 1 to 5")
                for (n, kind), t in zip(TOUCHES, touches):
                    t["kind"] = kind
                return touches

            return lambda: self.act("write_drafts", plan["name"], draft, what="drafted T1 to T5")

        raw = self.each_in_parallel((pid, work(plan)) for pid, plan in seen.items())
        drafts: Dict[str, List[Dict]] = {pid: raw[pid] for pid in seen}      # plan order
        self.set_status("done")
        return drafts
