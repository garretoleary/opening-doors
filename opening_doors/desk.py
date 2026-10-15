"""The desk. Not an agent. A plain controller that hands work between the agents,
holds each account's state and reports to the page.

Run one account:  python -m opening_doors.desk --only acc-01
Run the book:     python -m opening_doors.desk
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .agents import Cadence, Planner, Qualifier, Researcher, Scorer, Writer
from .book import call_notes, load_book
from .claude import AskFn, Spend, SpendCapReached, make_ask
from .governance import Governor, PermissionDenied, Stopped

ZONES = {4: "Open the door", 3: "Earn the call", 2: "Frame the value", 1: "Commit"}


class Desk:
    def __init__(self, ask: Optional[AskFn] = None, run_dir: Optional[Path] = None):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = run_dir or (config.RUNS_DIR / self.run_id)
        self.spend = Spend(ledger_path=config.STATE_DIR / "spend.json")
        self.gov = Governor(owner=config.AE["id"], log_path=self.run_dir / "audit.jsonl")
        self.ask = ask or make_ask(self.spend)
        self.researcher = Researcher(self.gov, self.ask)
        self.scorer = Scorer(self.gov, self.ask)
        self.planner = Planner(self.gov, self.ask)
        self.writer = Writer(self.gov, self.ask)
        self.cadence = Cadence(self.gov, self.ask)
        self.qualifier = Qualifier(self.gov, self.ask)
        self.agents = [self.researcher, self.scorer, self.planner, self.writer, self.cadence, self.qualifier]
        self.state: Dict[str, Dict] = {}     # account id -> zone, stop
        self.out: Dict = {}
        self.stopped: List[str] = []         # agents the AE stopped this run
        self.results: Dict = {"ranked": [], "plans": {}, "drafts": {}, "schedule": {}, "qualified": {}}   # filled stage by stage

    # ---- Question 4. The Stop button. Callable from the page, a thread, or a test, at any moment. ----
    def stop(self, agent_id: str) -> None:
        """The AE presses Stop. The token is revoked now; the agent's next action is refused and logged."""
        self.gov.stop(agent_id)
        if agent_id not in self.stopped:
            self.stopped.append(agent_id)

    def press_stop_when(self, agent_id: str, log_phrase: str) -> None:
        """Demo helper: press Stop on agent_id the moment a log line contains log_phrase.
        This is the AE's finger on the button at a chosen point mid-run."""
        def listener(entry):
            if log_phrase in entry.line() and agent_id not in self.stopped:
                self.stop(agent_id)
        self.gov.log.subscribe(listener)

    def _stage(self, agent, fn, empty):
        """Run one agent's stage. If the AE has stopped that agent, the stage ends there,
        the desk notes it, and the run carries on with whatever came before."""
        try:
            return fn()
        except Stopped:
            self.gov.log.record("desk", "stage ended early", agent.name, "ok", "stopped by AE, run continues")
            return empty

    def run(self, only_ids: Optional[List[str]] = None, simulate_reply: Optional[Dict[str, int]] = None) -> Dict:
        """Take the book, or a chosen few accounts, through the six agents.

        simulate_reply: {account id: touch} to play out, for the demo, the AE giving touches up to that
        one and the buyer replying, so the account reaches First call and the Qualifier.
        """
        self.spend.start_run()                                  # daily run limit, monthly cap
        book = load_book()
        if only_ids:
            book = dict(book, accounts=[a for a in book["accounts"] if a["id"] in only_ids])
        for a in book["accounts"]:
            self.state[a["id"]] = {"name": a["name"], "zone": 4, "stop": "start"}

        for agent in self.agents:                               # Question 1: registered first
            agent.register()
        self.gov.log.record("desk", "run started", f"{len(book['accounts'])} accounts", "ok", config.INVENTED_DATA_NOTICE)

        notes = self._stage(self.researcher, lambda: self.researcher.run(book), [])
        ranked = self._stage(self.scorer, lambda: self.scorer.run(notes, book["icp"]), []) if notes else []
        self.results["ranked"] = ranked
        plans = self._stage(self.planner, lambda: self.planner.run(ranked, notes, book), {}) if ranked else {}
        self.results["plans"] = plans
        for pid in plans:
            self.state[pid]["stop"] = "planned"
        drafts = self._stage(self.writer, lambda: self.writer.run(plans), {}) if plans else {}
        self.results["drafts"] = drafts
        for pid in drafts:
            self.state[pid]["stop"] = "drafted"
        schedule = self._stage(self.cadence, lambda: self.cadence.run(drafts, {pid: p["name"] for pid, p in plans.items()}), {}) if drafts else {}
        self.results["schedule"] = schedule
        for pid in schedule:
            self.state[pid]["stop"] = "T1 scheduled"

        # The demo's simulated replies: the AE gives touches, the buyer answers, the account moves on.
        for pid, touch in (simulate_reply or {}).items():
            if pid not in schedule:
                continue
            def play(pid=pid, touch=touch):
                for n in range(1, touch + 1):
                    self.cadence.given_by_ae(pid, n)
                    if n < touch:
                        self.cadence.no_reply(pid)
                self.cadence.reply(pid, touch)
                self.state[pid].update(zone=2, stop="First call")
            self._stage(self.cadence, play, None)
        qualified = (self._stage(self.qualifier, lambda: self.qualifier.run(self.cadence.handoffs, call_notes()), {})
                     if self.cadence.handoffs else {})
        self.results["qualified"] = qualified
        for pid in qualified:
            self.state[pid]["stop"] = "Problem identified, value defined"

        # The governance check every run makes: no agent may send. Refused and logged, never skipped.
        checker = self.writer if "agent-4" not in self.stopped else self.planner
        target = ranked[0]["name"] if ranked else ""
        try:
            checker.act("send_email", target, lambda: None, what="send email")
        except (PermissionDenied, Stopped):
            pass

        self.gov.log.record("desk", "run finished", "", "ok",
                            f"£{self.spend.gbp_this_run:.2f} this run, {self.spend.calls} model calls")
        self.out = {
            "run_id": self.run_id, "notice": config.INVENTED_DATA_NOTICE,
            "notes": notes, "ranked": ranked, "plans": plans, "drafts": drafts, "schedule": schedule, "qualified": qualified, "stopped": self.stopped, "state": self.state,
            "lights": self.gov.lights, "agents": self.gov.registry.as_rows(),
            "spend": {"gbp": round(self.spend.gbp_this_run, 4), "calls": self.spend.calls,
                      "input_tokens": self.spend.input_tokens, "output_tokens": self.spend.output_tokens},
            "log": [e.line() for e in self.gov.log.entries],
        }
        self.gov.write_run_file(self.run_dir / "out.json", json.dumps(self.out, indent=2, ensure_ascii=False))
        return self.out


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Opening Doors desk")
    p.add_argument("--only", nargs="*", help="account ids, e.g. acc-01")
    p.add_argument("--simulate-reply", nargs="*", default=[], metavar="ID:TOUCH",
                   help="play a reply at that touch, e.g. acc-01:3, so the account reaches the Qualifier")
    p.add_argument("--stop", nargs=2, metavar=("AGENT", "WHEN"), default=None,
                   help="press Stop on an agent when a log line contains WHEN, e.g. --stop agent-4 'read plans'")
    args = p.parse_args(argv)
    sim = {x.split(":")[0]: int(x.split(":")[1]) for x in args.simulate_reply}
    desk = Desk()
    if args.stop:
        desk.press_stop_when(args.stop[0], args.stop[1])
    try:
        out = desk.run(args.only, sim)
    except SpendCapReached as e:
        print(f"{e}. Here is the video instead.")
        return 2
    print(config.INVENTED_DATA_NOTICE)
    print("\nLOG")
    for line in out["log"]:
        print(" ", line)
    print("\nLIGHTS", {k: ("on" if v else "off") for k, v in out["lights"].items()})
    print("AGENTS", "  ".join(f"{a['name']}: {a['status']}" for a in out["agents"]))
    print("\nSPEND", f"£{out['spend']['gbp']:.4f}", out["spend"]["calls"], "calls",
          out["spend"]["input_tokens"], "in,", out["spend"]["output_tokens"], "out")
    print("\nOUT")
    for s in out["ranked"]:
        print(f"  {s['rank']}. {s['name']}  {s['score']}  {s['why_selected']}  [{s['how_found']}]")
    for pid, plan in out["plans"].items():
        print(f"\nPLAN  {plan['name']}")
        for k in ("business_problem", "economic_buyer", "first_meeting_point_of_view", "one_metric_to_agree"):
            print(f"  {k.replace('_', ' ')}: {plan[k]}")
    for pid, touches in out["drafts"].items():
        print(f"\nTOUCHES  {out['plans'][pid]['name']}")
        for t in touches:
            head = f"T{t['touch']} {t['kind']}"
            if t["subject"]:
                head += f"  subject: {t['subject']}"
            print(f"  {head}  [{t['matched_to']}]")
            print("     " + t["body"].replace("\n", "\n     "))
    for pid, sch in out["schedule"].items():
        print(f"\nSCHEDULE  {sch['name']}  " + "  ".join(f"T{t['touch']} {t['due']}" for t in sch["touches"]))
    for pid, q in out["qualified"].items():
        print(f"\nQUALIFICATION  {q['name']}  (replied at {q['replied_at']})")
        for k, v in q["qualification"].items():
            print(f"  {k.replace('_', ' ')}: {v}")
        print(f"\nVALUE FRAME  {q['name']}")
        for k, v in q["value_frame"].items():
            print(f"  {k.replace('_', ' ')}: {v}")
        mp = q["mutual_plan"]
        print(f"\nMUTUAL PLAN  {q['name']}")
        print(f"  goal: {mp['goal']}")
        for st in mp["steps"]:
            print(f"  {st['who']} will {st['what']}  by {st['by']}")
        print(f"  the ask: {mp['the_ask']}")
    print(f"\nsaved to {desk.run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
