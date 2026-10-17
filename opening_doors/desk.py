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
from .book import call_notes, journey, load_book
from .claude import AskFn, Spend, SpendCapReached, make_ask
from .governance import Governor, PermissionDenied, Stopped
from .rules import keep_copies, load_all

ZONES = {4: "Open the door", 3: "Earn the call", 2: "Frame the value", 1: "Commit"}


class Desk:
    def __init__(self, ask: Optional[AskFn] = None, run_dir: Optional[Path] = None):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")[:-3] + "Z"   # unique to the millisecond
        self.run_dir = run_dir or (config.RUNS_DIR / self.run_id)
        self.rules = load_all()                 # all six rules files, or RulesMissing: the run refuses to start
        self.spend = Spend(ledger_path=config.STATE_DIR / "spend.json")
        self.gov = Governor(owner=config.AE["id"], log_path=self.run_dir / "audit.jsonl")
        # Each agent asks its own model (config.model_for); a stand-in ask serves every agent in tests.
        asks = {}
        def ask_for(agent_id: str):
            if ask:
                return ask
            m = config.model_for(agent_id)
            if m not in asks:
                asks[m] = make_ask(self.spend, m)
            return asks[m]
        self.ask = ask
        r = self.rules
        self.researcher = Researcher(self.gov, ask_for("agent-1"), r["researcher"])
        self.scorer = Scorer(self.gov, ask_for("agent-2"), r["scorer"])
        self.planner = Planner(self.gov, ask_for("agent-3"), r["planner"])
        self.writer = Writer(self.gov, ask_for("agent-4"), r["writer"])
        self.cadence = Cadence(self.gov, ask_for("agent-5"), r["cadence"])
        self.qualifier = Qualifier(self.gov, ask_for("agent-6"), r["qualifier"])
        self.models = {a.agent_id: config.model_for(a.agent_id) for a in (self.researcher, self.scorer, self.planner, self.writer, self.cadence, self.qualifier)}
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

    def run(self, only_ids: Optional[List[str]] = None) -> Dict:
        """Take the book, or a chosen few accounts, through the six agents.

        The run depicts a book a few weeks in. The book says where each account stands (days into the
        sequence) and how it answers; all invented data, so every run is repeatable. For the accounts
        this run drafts, the AE gives each touch due by that day and the book answers: a reply moves
        the account to First call and the Qualifier; a touch out with no reply yet waits; no reply by
        touch 5 rests it. After the mutual plan a buyer who accepts the ask brings the committee in,
        Zone 1. Accounts worked in an earlier wave but outside this run's top ten keep the position the
        book gives them, logged by the desk.
        """
        self.spend.start_run()                                  # daily run limit, monthly cap
        book = load_book()
        if only_ids:
            book = dict(book, accounts=[a for a in book["accounts"] if a["id"] in only_ids])
        for a in book["accounts"]:
            self.state[a["id"]] = {"name": a["name"], "zone": 4, "stop": "start"}

        for agent in self.agents:                               # Question 1: registered first
            agent.register()
        keep_copies(self.rules, self.run_dir)                   # the rules this run used, locked with the run
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

        # The sequence plays out to today: the AE gives each touch due; the book answers.
        positions = journey()
        def play_out():
            for pid in schedule:
                pos = positions.get(pid, {"days_in": 0, "at_touch": None, "committee": False})
                schedule[pid]["day"] = pos["days_in"]
                for n in range(1, 6):
                    if config.CADENCE_DAY[n] > pos["days_in"]:          # not due yet
                        if n > 1:
                            self.cadence.awaiting(pid)
                            self.state[pid]["stop"] = f"T{n - 1} given, awaiting reply"
                        break
                    self.cadence.given_by_ae(pid, n)
                    self.state[pid]["stop"] = f"T{n} given"
                    if n >= 3:
                        self.state[pid]["zone"] = 3
                    if pos["at_touch"] == n:
                        self.cadence.reply(pid, n)
                        self.state[pid].update(zone=3, stop="First call")
                        break
                    if n < 5 and config.CADENCE_DAY[n + 1] > pos["days_in"]:   # reply day not reached
                        self.cadence.awaiting(pid)
                        self.state[pid]["stop"] = f"T{n} given, awaiting reply"
                        break
                    self.cadence.no_reply(pid)
                else:
                    self.state[pid]["stop"] = "resting after T5"
        if schedule:
            self._stage(self.cadence, play_out, None)
        # Accounts worked in an earlier wave, outside this run's top ten: the book says where they stand.
        for pid, pos in positions.items():
            if pid in schedule or pid not in self.state or pos["days_in"] <= 0:
                continue
            given = max((n for n in range(1, 6) if config.CADENCE_DAY[n] <= pos["days_in"]), default=0)
            if pos["at_touch"] and pos["at_touch"] <= given:
                detail, zone, stop = f"replied at T{pos['at_touch']}, First call", 3, "First call"
            elif given >= 5:
                detail, zone, stop = "resting after T5", 3, "resting after T5"
            else:
                detail, zone, stop = f"T{given} given, awaiting reply", (3 if given >= 3 else 4), f"T{given} given, awaiting reply"
            self.gov.log.record("desk", "book position, invented", self.state[pid]["name"], "ok", detail)
            self.state[pid].update(zone=zone, stop=stop)
        # As each account's mutual plan lands, it moves to Zone 2; if the book says the buyer accepts the
        # ask, the committee line follows at once and it moves to Zone 1. Live, account by account.
        name_to_pid = {v["name"]: k for k, v in self.state.items()}
        def on_entry(e):
            if e.who == "Qualifier" and e.what == "mutual plan drafted" and e.outcome == "ok":
                pid = name_to_pid.get(e.on_what)
                if pid is None:
                    return
                self.state[pid].update(zone=2, stop="Problem identified, value defined")
                if positions.get(pid, {}).get("committee"):
                    self.gov.log.record("desk", "buying committee accepted the ask, invented", e.on_what, "ok",
                                        "boss and committee booked, Zone 1")
                    self.state[pid].update(zone=1, stop="Buying committee")
        self.gov.log.subscribe(on_entry)
        qualified = (self._stage(self.qualifier, lambda: self.qualifier.run(self.cadence.handoffs, call_notes()), {})
                     if self.cadence.handoffs else {})
        self.results["qualified"] = qualified

        # The governance check every run makes: no agent may send. Refused and logged, never skipped.
        checker = self.writer if "agent-4" not in self.stopped else self.planner
        target = ranked[0]["name"] if ranked else ""
        try:
            checker.act("send_email", target, lambda: None, what="send email", tag="deliberate_check")
        except (PermissionDenied, Stopped):
            pass

        self.gov.log.record("desk", "run finished", "", "ok",
                            f"£{self.spend.gbp_this_run:.2f} this run, {self.spend.calls} model calls")
        self.out = {
            "run_id": self.run_id, "notice": config.INVENTED_DATA_NOTICE, "models": self.models,
            "rules": {k: v.label for k, v in self.rules.items()},
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
    p.add_argument("--stop", nargs=2, metavar=("AGENT", "WHEN"), default=None,
                   help="press Stop on an agent when a log line contains WHEN, e.g. --stop agent-4 'read plans'")
    args = p.parse_args(argv)
    desk = Desk()
    if args.stop:
        desk.press_stop_when(args.stop[0], args.stop[1])
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
    print("AGENTS", "  ".join(f"{a['name']}: {a['status']}" for a in out["agents"]))
    zones = {z: sum(1 for v in out["state"].values() if v["zone"] == z) for z in (4, 3, 2, 1)}
    print("ZONES", "  ".join(f"Zone {z}: {n}" for z, n in zones.items()))
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
