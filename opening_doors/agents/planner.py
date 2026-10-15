"""Agent 3, Planner. For the top ten, drafts the account plan: the business problem, the likely
economic buyer, the first-meeting point of view, the one metric to agree.
Permitted: read scores, write plans."""
from __future__ import annotations

import json
from typing import Dict, List

from .base import INVENTED, Agent

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "business_problem": {"type": "string"},
        "economic_buyer": {"type": "string"},
        "first_meeting_point_of_view": {"type": "string"},
        "one_metric_to_agree": {"type": "string"},
    },
    "required": ["business_problem", "economic_buyer", "first_meeting_point_of_view", "one_metric_to_agree"],
    "additionalProperties": False,
}

TOP_N = 10


class Planner(Agent):
    agent_id = "agent-3"
    name = "Planner"
    purpose = "Drafts the account plan for each of the top ten"
    colour = "#F0E442"
    system_prompt = (
        f"{INVENTED}\nYou are the Planner on a sales desk. Write a one-page account plan for one account, "
        "in plain English a busy sales leader reads in a minute. business_problem: the cost or risk the trigger "
        "creates, in two sentences. economic_buyer: the named person with role and why they own the budget. "
        "first_meeting_point_of_view: the one insight to open with, two sentences, no product names. "
        "one_metric_to_agree: a single number the buyer and seller would agree to move, with a plausible "
        "starting value and target. Under 120 words in all."
    )

    def run(self, ranked: List[Dict], notes: List[Dict], book: dict) -> Dict[str, Dict]:
        self.set_status("running")
        top = self.act("read_scores", f"top {TOP_N}", lambda: ranked[:TOP_N], what="read scores")
        note_by_id = {n["id"]: n for n in notes}
        acct_by_id = {a["id"]: a for a in book["accounts"]}
        plans: Dict[str, Dict] = {}
        for s in top:
            acct = acct_by_id[s["id"]]
            user = ("Account:\n" + json.dumps({k: acct[k] for k in ("name", "sector", "hq", "employees", "people", "signals", "access_setup_today")}, ensure_ascii=False)
                    + "\n\nResearch note:\n" + json.dumps(note_by_id.get(s["id"], {}), ensure_ascii=False)
                    + "\n\nScore and reason:\n" + json.dumps({k: s[k] for k in ("score", "why_selected", "how_found")}, ensure_ascii=False))
            plan = self.act("write_plans", acct["name"],
                            lambda u=user: self.ask(self.system_prompt, u, PLAN_SCHEMA, 2000),
                            what="account plan")
            plans[s["id"]] = dict(plan, id=s["id"], name=acct["name"], rank=s["rank"])
        self.set_status("done")
        return plans
