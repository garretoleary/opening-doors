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
from opening_doors.claude import SpendCapReached

UK = ZoneInfo("Europe/London")
HERE = Path(__file__).parent
AGENT_NAMES = ["Researcher", "Scorer", "Planner", "Writer", "Cadence", "Qualifier"]
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

    # ---- what the page reads ---------------------------------------------------------------
    def snapshot(self) -> Dict:
        with self.lock:
            now = time.time()
            elapsed = int(((self.finished or now) - self.started)) if self.started else 0
            return {
                "notice": config.INVENTED_DATA_NOTICE,
                "running": self.running, "mode": self.mode, "elapsed": elapsed,
                "lights": dict(self.lights), "agents": dict(self.agents),
                "log": list(self.log), "spend_gbp": round(self.spend_gbp, 2), "limit": self.limit,
            }

    def _entry(self, time_iso: str, who: str, what: str, on_what: str, outcome: str, detail: str) -> None:
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

    def _reset(self, mode: str) -> None:
        with self.lock:
            self.running, self.mode = True, mode
            self.started, self.finished = time.time(), None
            self.lights = {k: False for k in self.lights}
            self.log, self.agents, self.spend_gbp, self.limit = [], {n: "waiting" for n in AGENT_NAMES}, 0.0, None

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
        desk = self.desk
        if not desk or not self.running:
            return False
        ids = {a.name: a.agent_id for a in desk.agents}
        if name not in ids:
            return False
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

    def _replay(self, path: Path) -> None:
        entries = [json.loads(l) for l in (path / "audit.jsonl").read_text().splitlines() if l.strip()]
        try:
            prev = None
            for e in entries:
                t = datetime.fromisoformat(e["time"]).timestamp()
                if prev is not None:
                    time.sleep(max(0.0, (t - prev) / REPLAY_SPEED))
                prev = t
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
