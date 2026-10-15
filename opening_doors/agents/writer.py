"""Agent 4, Writer. Drafts each of the five touches for each top-ten account, matched to that
account's signal, never a template. Permitted: read plans, write drafts.
Not permitted: read the raw book, send anything."""
from __future__ import annotations

import json
from typing import Dict, List

from .base import INVENTED, Agent

TOUCHES = [
    (1, "insight email"),
    (2, "insight email"),
    (3, "LinkedIn connection note"),
    (4, "email or call script"),
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
    system_prompt = (
        f"{INVENTED}\nYou are the Writer on a sales desk. You draft the five touches of the seller's "
        "sequence for one account, from its account plan only. Each touch must be built on this account's "
        "own signal and plan; never a template, never a line that could be sent to a different company. "
        "Touch 1, insight email: give something useful about their situation, ask for nothing. "
        "Touch 2, insight email, a week later: a second, different piece of value, ask for nothing. "
        "Touch 3, LinkedIn connection note: under 280 characters, no subject, one reason to connect. "
        "Touch 4, email or call script: the one small ask, a fifteen-minute call, named around the one "
        "metric to agree. Touch 5, break-up email: close the loop politely, leave the door open, no guilt. "
        "Address the economic buyer by first name. Plain English, short sentences, no jargon, no product "
        "names, no exclamation marks. Emails under 110 words with a subject line; the LinkedIn note has an "
        "empty subject. matched_to: the signal or plan line this touch is built on, in a few words. "
        "Return exactly five touches, numbered 1 to 5, in order."
    )

    def run(self, plans: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        self.set_status("running")
        seen = self.act("read_plans", f"{len(plans)} plans",
                        lambda: {pid: {k: p[k] for k in PLAN_KEYS if k in p} for pid, p in plans.items()},
                        what="read plans")
        drafts: Dict[str, List[Dict]] = {}
        for pid, plan in seen.items():
            user = "Account plan, as JSON:\n" + json.dumps(plan, ensure_ascii=False)

            def draft(u: str = user) -> List[Dict]:
                result = self.ask(self.system_prompt, u, TOUCH_SCHEMA, 4000)
                touches = sorted(result["touches"], key=lambda t: t["touch"])
                if [t["touch"] for t in touches] != [1, 2, 3, 4, 5]:
                    raise ValueError("the Writer must return touches 1 to 5")
                for (n, kind), t in zip(TOUCHES, touches):
                    t["kind"] = kind
                return touches

            drafts[pid] = self.act("write_drafts", plan["name"], draft, what="drafted T1 to T5")
        self.set_status("done")
        return drafts
