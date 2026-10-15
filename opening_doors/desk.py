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
from .agents import Cadence, Planner, Researcher, Scorer, Writer
from .book import load_book
from .claude import AskFn, Spend, SpendCapReached, make_ask
from .governance import Governor, PermissionDenied

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
        self.agents = [self.researcher, self.scorer, self.planner, self.writer, self.cadence]
        self.state: Dict[str, Dict] = {}     # account id -> zone, stop
        self.out: Dict = {}

    def run(self, only_ids: Optional[List[str]] = None) -> Dict:
        """Take the book, or a chosen few accounts, through Agents 1 to 3."""
        self.spend.start_run()                                  # daily run limit, monthly cap
        book = load_book()
        if only_ids:
            book = dict(book, accounts=[a for a in book["accounts"] if a["id"] in only_ids])
        for a in book["accounts"]:
            self.state[a["id"]] = {"name": a["name"], "zone": 4, "stop": "start"}

        for agent in self.agents:                               # Question 1: registered first
            agent.register()
        self.gov.log.record("desk", "run started", f"{len(book['accounts'])} accounts", "ok", config.INVENTED_DATA_NOTICE)

        notes = self.researcher.run(book)
        ranked = self.scorer.run(notes, book["icp"])
        plans = self.planner.run(ranked, notes, book)
        for pid in plans:
            self.state[pid]["stop"] = "planned"
        drafts = self.writer.run(plans)
        for pid in drafts:
            self.state[pid]["stop"] = "drafted"
        schedule = self.cadence.run(drafts, {pid: p["name"] for pid, p in plans.items()})
        for pid in schedule:
            self.state[pid]["stop"] = "T1 scheduled"

        # The governance check every run makes: no agent may send. Refused and logged, never skipped.
        try:
            self.writer.act("send_email", ranked[0]["name"], lambda: None, what="send email")
        except PermissionDenied:
            pass

        self.gov.log.record("desk", "run finished", "", "ok",
                            f"£{self.spend.gbp_this_run:.2f} this run, {self.spend.calls} model calls")
        self.out = {
            "run_id": self.run_id, "notice": config.INVENTED_DATA_NOTICE,
            "notes": notes, "ranked": ranked, "plans": plans, "drafts": drafts, "schedule": schedule, "state": self.state,
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
    args = p.parse_args(argv)
    desk = Desk()
    try:
        out = desk.run(args.only)
    except SpendCapReached as e:
        print(f"{e}. Here is the video instead.")
        return 2
    print(config.INVENTED_DATA_NOTICE)
    print("\nLOG")
    for line in out["log"]:
        print(" ", line)
    print("\nLIGHTS", {k: ("on" if v else "off") for k, v in out["lights"].items()})
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
    print(f"\nsaved to {desk.run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
