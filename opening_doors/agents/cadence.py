"""Agent 5, Cadence. Owns the five-touch sequence in Zones 4 and 3.

Garret's sequence: touch 1 email, day 1. Touch 2 email, day 5. Touch 3 LinkedIn connection request,
day 8. Touch 4 call, no voicemail if unanswered, then email, day 11. Touch 5 break-up email, day 18.
After touch 5 the account rests; no sixth touch, ever. Tracks what was given to whom so nothing
repeats. A reply at any touch moves the account to First call and hands it to Agent 6.
Permitted: read drafts, write schedule, write log. Not permitted: send.

Cadence makes no model call. Scheduling is rules, and rules are enforced in code.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .. import config
from ..governance import RuleDenied
from .base import Agent

LAST_TOUCH = 5
KINDS = {1: "insight email", 2: "insight email", 3: "LinkedIn connection request",
         4: "call, no voicemail, then email", 5: "break-up email"}


class Cadence(Agent):
    agent_id = "agent-5"
    name = "Cadence"
    purpose = "Schedules the five touches, enforces the rest rule and the no-repeat rule, hands replies to the Qualifier; never sends"
    colour = "#D55E00"
    rules_key = "cadence"

    def __init__(self, gov, ask, rules=None):
        super().__init__(gov, ask, rules)
        self.schedule: Dict[str, Dict] = {}            # account id -> stage, next touch, touches
        self.given: Set[Tuple[str, int]] = set()       # (account id, touch) already given
        self.given_content: Set[Tuple[str, str]] = set()   # (account id, hash of body) already given
        self.handoffs: List[Dict] = []                 # replies handed to Agent 6

    # ---- building the schedule from the Writer's drafts ------------------------------------
    def run(self, drafts: Dict[str, List[Dict]], names: Dict[str, str], start: Optional[date] = None) -> Dict[str, Dict]:
        self.set_status("running")
        start = start or date.today()
        seen = self.act("read_drafts", f"{len(drafts)} accounts", lambda: drafts, what="read drafts")
        for pid, touches in seen.items():
            name = names[pid]
            self.act("write_schedule", name, lambda t=touches, p=pid, n=name: self._build(p, n, t, start),
                     what="scheduled T1 to T5")
        self.set_status("done")
        return self.schedule

    def _build(self, pid: str, name: str, touches: List[Dict], start: date) -> None:
        self.schedule[pid] = {
            "name": name, "stage": "T1", "next_touch": 1,
            "touches": [
                {"touch": t["touch"], "kind": KINDS[t["touch"]], "day": config.CADENCE_DAY[t["touch"]],
                 "due": (start + timedelta(days=config.CADENCE_DAY[t["touch"]] - 1)).isoformat(),
                 "status": "scheduled", "body_hash": self._hash(t["body"])}
                for t in sorted(touches, key=lambda t: t["touch"])
            ],
        }

    # ---- what happens as the AE works the sequence ------------------------------------------
    def given_by_ae(self, pid: str, touch: int) -> None:
        """The AE reviewed and sent a touch. Cadence records it; Cadence itself sends nothing."""
        self.act("write_log", self._name(pid), lambda: self._record_given(pid, touch), what=f"T{touch} given")

    def no_reply(self, pid: str) -> None:
        """No reply by the due date: move to the next touch, or rest after touch 5."""
        self.act("write_schedule", self._name(pid), lambda: self._advance(pid), what="no reply",
                 detail_of=lambda s: f"next T{s['next_touch']}" if s["stage"] != "resting" else "resting, no sixth touch")

    def awaiting(self, pid: str) -> None:
        """The last touch is out and its reply day has not come: the account waits where it is."""
        self.act("write_log", self._name(pid), lambda: self._state(pid), what="awaiting reply",
                 detail_of=lambda s: f"T{(s['next_touch'] or 1) - 1} given, day {self._day(pid)} of the sequence" if s["next_touch"] else "")

    def _day(self, pid: str) -> int:
        return self._state(pid).get("day", 0)

    def reply(self, pid: str, touch: int) -> Dict:
        """A reply at any touch: the account moves to First call and goes to the Qualifier."""
        return self.act("write_log", self._name(pid), lambda: self._handoff(pid, touch), what="reply received, invented",
                        detail_of=lambda h: f"at T{touch}, to Qualifier, First call")

    # ---- the rules ----------------------------------------------------------------------------
    def _record_given(self, pid: str, touch: int) -> None:
        s = self._state(pid)
        if s["stage"] == "resting":
            raise RuleDenied("rest rule: account is resting after T5, no sixth touch")
        if s["stage"] == "first_call":
            raise RuleDenied("account already replied; sequence closed, with the Qualifier")
        if touch > LAST_TOUCH or touch < 1:
            raise RuleDenied(f"rest rule: there is no T{touch}")
        if (pid, touch) in self.given:
            raise RuleDenied(f"no repeat: T{touch} already given")
        if touch != s["next_touch"]:
            raise RuleDenied(f"out of sequence: next is T{s['next_touch']}")
        entry = s["touches"][touch - 1]
        if (pid, entry["body_hash"]) in self.given_content:
            raise RuleDenied("no repeat: this wording was already given to this account")
        self.given.add((pid, touch))
        self.given_content.add((pid, entry["body_hash"]))
        entry["status"] = "given"
        s["stage"] = f"T{touch}"

    def _advance(self, pid: str) -> Dict:
        s = self._state(pid)
        if s["stage"] == "resting":
            raise RuleDenied("rest rule: account is resting after T5, no sixth touch")
        if s["stage"] == "first_call":
            raise RuleDenied("account already replied; sequence closed")
        current = s["next_touch"]
        if (pid, current) not in self.given:
            raise RuleDenied(f"T{current} has not been given yet")
        if current == LAST_TOUCH:
            s["stage"] = "resting"
            s["next_touch"] = None
        else:
            s["next_touch"] = current + 1
        return s

    def _handoff(self, pid: str, touch: int) -> Dict:
        s = self._state(pid)
        if s["stage"] == "first_call":
            raise RuleDenied("already handed to the Qualifier")
        if (pid, touch) not in self.given:
            raise RuleDenied(f"T{touch} was not given, so it cannot have been replied to")
        for entry in s["touches"]:
            if entry["status"] == "scheduled":
                entry["status"] = "cancelled, replied"
        s["stage"] = "first_call"
        s["next_touch"] = None
        handoff = {"account_id": pid, "name": s["name"], "replied_at": f"T{touch}",
                   "to": "agent-6", "stage": "First call"}
        self.handoffs.append(handoff)
        return handoff

    # ---- helpers ------------------------------------------------------------------------------
    def _state(self, pid: str) -> Dict:
        if pid not in self.schedule:
            raise RuleDenied("no schedule for this account")
        return self.schedule[pid]

    def _name(self, pid: str) -> str:
        return self.schedule.get(pid, {}).get("name", pid)

    @staticmethod
    def _hash(body: str) -> str:
        return hashlib.sha256(" ".join(body.split()).lower().encode("utf-8")).hexdigest()[:16]
