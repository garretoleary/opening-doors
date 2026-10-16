"""The page's server. Standard library only. Serves one page, reports the desk's state, starts a run.

  python -m web.server                 serve on http://127.0.0.1:8765
  POST /run                            start a real run (one at a time; the caps apply)
  POST /replay                         play the latest saved run from its audit log, no spend
  GET  /state                          what the page shows, log times in UK time
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from opening_doors import config
from opening_doors.book import load_book
from opening_doors.claude import SpendCapReached

UK = ZoneInfo("Europe/London")
HERE = Path(__file__).parent
AGENT_NAMES = ["Researcher", "Scorer", "Planner", "Writer", "Cadence", "Qualifier"]
# Colours from the visual (Okabe and Ito). Planner's yellow carries a black edge on the page.
AGENT_COLOURS = {"Researcher": "#E69F00", "Scorer": "#56B4E9", "Planner": "#F0E442",
                 "Writer": "#0072B2", "Cadence": "#D55E00", "Qualifier": "#CC79A7"}
REPLAY_SPEED = 8.0          # saved runs play back this many times faster than they happened


def uk_time(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(UK).strftime("%H:%M:%S")


class App:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.mode = ""                      # "run" or "replay"
        self.started: Optional[float] = None
        self.finished: Optional[float] = None
        self.lights = {"registered": False, "permitted": False, "logged": False, "stoppable": False}
        self.log: List[Dict] = []
        self.agents = {n: "waiting" for n in AGENT_NAMES}
        self.spend_gbp = 0.0
        self.limit: Optional[str] = None
        self.desk = None
        self.replay_stopped: set = set()     # agents stopped by the AE during a replay
        self.data: Dict = {}                 # the run's results: ranked, plans, drafts, schedule, qualified
        self.zones: Dict[str, int] = {}      # account name -> zone 4..1, moved by the log as the run goes
        self.stops: Dict[str, str] = {}      # account name -> last stop reached, for the map's dots
        self.book_size = 0
        self.book_names: List[str] = [a["name"] for a in load_book()["accounts"]]
        self.revealed: set = set()           # (kind, account name) pairs the log has announced

    # ---- what the page reads ---------------------------------------------------------------
    def _out(self) -> List[Dict]:
        """The ten targets, once the Scorer has ranked. Each with its reason and what is ready to tap."""
        if ("ranked", "") not in self.revealed:
            return []
        rows = []
        for s_ in self.data.get("ranked", [])[:10]:
            n = s_["name"]
            rows.append({"id": s_["id"], "rank": s_["rank"], "name": n, "score": s_["score"],
                         "why": s_["why_selected"], "how_found": s_["how_found"],
                         "ready": {"plan": ("plan", n) in self.revealed, "touches": ("touches", n) in self.revealed,
                                   "schedule": ("schedule", n) in self.revealed, "qualified": ("qualified", n) in self.revealed}})
        return rows

    def target(self, pid: str) -> Optional[Dict]:
        """One target's plan, five touches with dates, MEDDPICC-lite and mutual plan, as far as the run has got."""
        with self.lock:
            row = next((r for r in self._out() if r["id"] == pid), None)
            if not row:
                return None
            n, ready = row["name"], row["ready"]
            plan = self.data.get("plans", {}).get(pid) if ready["plan"] else None
            touches = self.data.get("drafts", {}).get(pid) if ready["touches"] else None
            sched = self.data.get("schedule", {}).get(pid) if ready["schedule"] else None
            qual = self.data.get("qualified", {}).get(pid) if ready["qualified"] else None
            if touches and sched:
                due = {t["touch"]: t["due"] for t in sched["touches"]}
                touches = [dict(t, due=due.get(t["touch"], "")) for t in touches]
            return {"id": pid, "name": n, "rank": row["rank"], "why": row["why"], "how_found": row["how_found"],
                    "plan": {k: plan[k] for k in ("business_problem", "economic_buyer", "first_meeting_point_of_view", "one_metric_to_agree")} if plan else None,
                    "touches": touches, "qualified": qual}

    def _zone_counts(self) -> List[Dict]:
        """Four tiles, Zone 4 to Zone 1. Accounts not yet moved by the log sit in Zone 4."""
        moved = {z: sum(1 for v in self.zones.values() if v == z) for z in (3, 2, 1)}
        z4 = max(0, self.book_size - sum(moved.values()))
        names = {4: "Open the door", 3: "Earn the call", 2: "Frame the value", 1: "Commit"}
        counts = {4: z4, 3: moved[3], 2: moved[2], 1: moved[1]}
        return [{"zone": z, "name": names[z], "count": counts[z] if self.book_size else 0} for z in (4, 3, 2, 1)]

    def snapshot(self) -> Dict:
        with self.lock:
            now = time.time()
            elapsed = int(((self.finished or now) - self.started)) if self.started else 0
            return {
                "zones": self._zone_counts(),
                "dots": [{"name": n, "zone": self.zones.get(n, 4), "stop": self.stops.get(n, "start")} for n in self.book_names] if self.book_size else [],
                "out": self._out(),
                "notice": config.INVENTED_DATA_NOTICE,
                "running": self.running, "mode": self.mode, "elapsed": elapsed,
                "lights": dict(self.lights),
                "agents": [{"n": i + 1, "name": n, "status": self.agents[n], "colour": AGENT_COLOURS[n]} for i, n in enumerate(AGENT_NAMES)],
                "log": list(self.log), "spend_gbp": round(self.spend_gbp, 2), "limit": self.limit,
            }

    def _entry(self, time_iso: str, who: str, what: str, on_what: str, outcome: str, detail: str) -> None:
        if who in self.replay_stopped and outcome == "ok":      # in a replay, the gate's refusal is played for them
            outcome, detail = "stopped", "token revoked"
        parts = [who, what] + ([on_what] if on_what else []) + [outcome.upper() if outcome != "ok" else "ok"] + ([detail] if detail else [])
        with self.lock:
            self.log.append({"time": uk_time(time_iso), "who": who, "what": what, "on_what": on_what,
                             "outcome": outcome, "detail": detail, "line": "  ".join(parts),
                             "red": outcome in ("denied", "stopped")})
            if what == "registered":
                self.lights["registered"] = True
            if who in self.agents and outcome == "ok":
                self.lights["permitted"] = True
                self.lights["logged"] = True
                self.lights["stoppable"] = True            # armed; it stays on. A Stop reddens the agent's row.
                if self.agents[who] == "waiting":
                    self.agents[who] = "running"
            if outcome == "stopped":
                self.lights["stoppable"] = True
                if who in self.agents:
                    self.agents[who] = "stopped"
            if what == "stage ended early" and on_what in self.agents:
                self.agents[on_what] = "stopped"
            if what == "run finished":
                for name, status in self.agents.items():
                    if status == "running":
                        self.agents[name] = "done"
            if what == "run started":                             # every account starts in Zone 4, Open the door
                try:
                    self.book_size = int(on_what.split()[0])
                except (ValueError, IndexError):
                    self.book_size = 0
            if outcome == "ok" and on_what:                       # the journey: where each account sits
                if who == "Planner" and what == "account plan":
                    self.stops[on_what] = "planned"
                elif who == "Cadence" and what in ("T1 given", "T2 given"):
                    self.stops[on_what] = what
                elif who == "Cadence" and what == "T3 given":
                    self.zones[on_what] = 3                       # Zone 3, Earn the call
                    self.stops[on_what] = what
                elif who == "Cadence" and what in ("T4 given", "T5 given"):
                    self.stops[on_what] = what
                elif who == "Cadence" and what == "no reply" and detail.startswith("resting"):
                    self.stops[on_what] = "resting"
                elif who == "Cadence" and what == "awaiting reply":
                    self.stops[on_what] = "awaiting " + (self.stops.get(on_what, "T1 given"))
                elif who == "desk" and what == "book position, invented":
                    given = next((n for n in (5, 4, 3, 2, 1) if f"T{n}" in detail), 0)
                    if "resting" in detail:
                        self.zones[on_what], self.stops[on_what] = 3, "resting"
                    elif "replied" in detail:
                        self.zones[on_what], self.stops[on_what] = 3, "first call"
                    else:
                        self.zones[on_what] = 3 if given >= 3 else 4
                        self.stops[on_what] = f"awaiting T{given} given"
                elif who == "Cadence" and what.startswith("reply received"):
                    self.zones[on_what] = 3                       # First call, still Zone 3
                    self.stops[on_what] = "first call"
                elif who == "Qualifier" and what == "mutual plan drafted":
                    self.zones[on_what] = 2                       # Zone 2, Frame the value
                    self.stops[on_what] = "qualified"
                elif who == "desk" and what.startswith("buying committee accepted"):
                    self.zones[on_what] = 1                       # Zone 1, Commit
                    self.stops[on_what] = "committee"
            if outcome == "ok":                                   # what OUT may now show
                if who == "Scorer" and what.startswith("ranked"):
                    self.revealed.add(("ranked", ""))
                elif who == "Planner" and what == "account plan":
                    self.revealed.add(("plan", on_what))
                elif who == "Writer" and what == "drafted T1 to T5":
                    self.revealed.add(("touches", on_what))
                elif who == "Cadence" and what == "scheduled T1 to T5":
                    self.revealed.add(("schedule", on_what))
                elif who == "Qualifier" and what == "mutual plan drafted":
                    self.revealed.add(("qualified", on_what))

    def _reset(self, mode: str) -> None:
        with self.lock:
            self.running, self.mode = True, mode
            self.started, self.finished = time.time(), None
            self.lights = {k: False for k in self.lights}
            self.log, self.agents, self.spend_gbp, self.limit = [], {n: "waiting" for n in AGENT_NAMES}, 0.0, None
            self.replay_stopped = set()
            self.data, self.revealed = {}, set()
            self.zones, self.stops, self.book_size = {}, {}, 0

    # ---- a real run ----------------------------------------------------------------------------
    def start_run(self) -> bool:
        with self.lock:
            if self.running:
                return False
        self._reset("run")
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self) -> None:
        from opening_doors.desk import Desk
        try:
            desk = Desk()
            self.desk = desk
            with self.lock:
                self.data = desk.results                  # fills stage by stage as the desk works
            desk.gov.log.subscribe(lambda e: self._entry(e.time, e.who, e.what, e.on_what, e.outcome, e.detail))
            desk.run()
            with self.lock:
                self.spend_gbp = desk.spend.gbp_this_run
        except SpendCapReached as exc:
            with self.lock:
                self.limit = f"{exc}. Here is the video instead."
        except Exception as exc:                      # the page must never hang on an error
            self._entry(datetime.now(timezone.utc).isoformat(), "desk", "run failed", "", "error", type(exc).__name__)
        finally:
            with self.lock:
                self.running, self.finished = False, time.time()

    def stop_agent(self, name: str) -> bool:
        """The Stop button on the page. A real run: the desk's Stop, token revoked, next call refused.
        A replay: the press is logged, the row goes red, and that agent's later lines play as refused."""
        if name not in AGENT_NAMES or not self.running:
            return False
        if self.mode == "replay":
            with self.lock:
                already = name in self.replay_stopped
                self.replay_stopped.add(name)
            if not already:
                self._entry(datetime.now(timezone.utc).isoformat(), name, "STOPPED by AE", "", "stopped", "token revoked (replay)")
            return True
        desk = self.desk
        if not desk:
            return False
        ids = {a.name: a.agent_id for a in desk.agents}
        desk.stop(ids[name])
        return True

    # ---- replay of a saved run, for the demo and for testing the page without spend ------------
    def start_replay(self, run_id: Optional[str] = None) -> bool:
        with self.lock:
            if self.running:
                return False
        runs = sorted(p for p in config.RUNS_DIR.iterdir() if (p / "audit.jsonl").exists()) if config.RUNS_DIR.exists() else []
        if not runs:
            return False
        path = (config.RUNS_DIR / run_id) if run_id else runs[-1]
        self._reset("replay")
        threading.Thread(target=self._replay, args=(path,), daemon=True).start()
        return True

    def _downstream_of_a_stop(self, who: str) -> bool:
        with self.lock:
            if who not in AGENT_NAMES or not self.replay_stopped:
                return False
            return AGENT_NAMES.index(who) > min(AGENT_NAMES.index(n) for n in self.replay_stopped)

    def _replay(self, path: Path) -> None:
        entries = [json.loads(l) for l in (path / "audit.jsonl").read_text().splitlines() if l.strip()]
        out = path / "out.json"
        if out.exists():
            saved = json.load(out.open())
            with self.lock:
                self.data = {k: saved.get(k, {} if k != "ranked" else []) for k in ("ranked", "plans", "drafts", "schedule", "qualified")}
        try:
            prev = None
            for e in entries:
                t = datetime.fromisoformat(e["time"]).timestamp()
                if prev is not None:
                    time.sleep(max(0.0, (t - prev) / REPLAY_SPEED))
                prev = t
                if self._downstream_of_a_stop(e["who"]):       # as in a real run, nothing after a stopped agent runs
                    continue
                self._entry(e["time"], e["who"], e["what"], e["on_what"], e["outcome"], e["detail"])
            out = path / "out.json"
            if out.exists():
                with self.lock:
                    self.spend_gbp = json.load(out.open()).get("spend", {}).get("gbp", 0.0)
        finally:
            with self.lock:
                self.running, self.finished = False, time.time()


APP = App()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/state":
            self._send(200, json.dumps(APP.snapshot()).encode(), "application/json")
        elif self.path.startswith("/target/"):
            t = APP.target(self.path.split("/target/", 1)[1])
            self._send(200 if t else 404, json.dumps(t or {"error": "not ready"}).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path == "/run":
            ok = APP.start_run()
        elif self.path.startswith("/replay"):
            run_id = self.path.split("/replay/", 1)[1] if "/replay/" in self.path else None
            ok = APP.start_replay(run_id)
        elif self.path.startswith("/stop/"):
            ok = APP.stop_agent(self.path.split("/stop/", 1)[1])
        else:
            self._send(404, b"not found", "text/plain"); return
        self._send(200 if ok else 409, json.dumps({"ok": ok}).encode(), "application/json")

    def log_message(self, *args) -> None:      # keep the terminal quiet
        pass


def main(argv: Optional[List[str]] = None) -> None:
    port = int((argv or sys.argv[1:] or ["8765"])[0])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Opening Doors page on http://127.0.0.1:{port}  ({config.INVENTED_DATA_NOTICE})")
    server.serve_forever()


if __name__ == "__main__":
    main()
