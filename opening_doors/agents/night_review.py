"""Agent 7, Night Review. Reads every run, the audit log and the rules folder; writes only to the
proposals and reports folders. Proposes and never applies. Registered, permitted, logged and
stoppable like the other six, through the same gate, with its own token and its own Stop.
Never: rules, the book, sending, run files, or any tool beyond the model and the file reader.
No model call yet; this step registers the agent and proves its limits.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .. import config
from ..rules import Rules, load as load_rules
from .base import Agent


class NightReview(Agent):
    agent_id = "agent-7"
    name = "Night Review"
    purpose = "Reads runs, the audit log and the rules; writes proposals and reports; proposes and never applies"
    colour = "#7F7F7F"
    rules_key = "night_review"

    # ---- reads, each through the gate ----------------------------------------------------------
    def list_runs(self) -> List[str]:
        def read() -> List[str]:
            d = config.RUNS_DIR
            return sorted(p.name for p in d.iterdir() if (p / "audit.jsonl").exists()) if d.exists() else []
        return self.act("read_runs", "runs", read, what="read runs", detail_of=lambda r: f"{len(r)} runs")

    def read_audit(self, run_id: str) -> List[Dict]:
        def read() -> List[Dict]:
            path = config.RUNS_DIR / run_id / "audit.jsonl"
            return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return self.act("read_audit", run_id, read, what="read audit log", detail_of=lambda e: f"{len(e)} lines")

    def read_run_output(self, run_id: str) -> Dict:
        def read() -> Dict:
            return json.loads((config.RUNS_DIR / run_id / "out.json").read_text(encoding="utf-8"))
        return self.act("read_runs", run_id, read, what="read run output")

    def read_rules(self) -> Dict[str, Rules]:
        from ..rules import AGENT_KEYS
        return self.act("read_rules", "rules", lambda: {k: load_rules(k) for k in AGENT_KEYS + ["night_review"]},
                        what="read rules", detail_of=lambda r: ", ".join(v.label for v in r.values()))

    # ---- writes, only here ----------------------------------------------------------------------
    def propose(self, title: str, text: str) -> Path:
        """A proposal is a file for Garret to read. Night Review never applies it."""
        return self.act("write_proposals", title, lambda: self._write(config.PROPOSALS_DIR, title, text), what="wrote proposal",
                        detail_of=lambda p: p.name)

    def report(self, title: str, text: str) -> Path:
        return self.act("write_reports", title, lambda: self._write(config.REPORTS_DIR, title, text), what="wrote report",
                        detail_of=lambda p: p.name)

    @staticmethod
    def _write(folder: Path, title: str, text: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in title.lower()).strip("-")[:60]
        path = folder / f"{stamp}-{safe}.md"
        path.write_text(f"{config.INVENTED_DATA_NOTICE}\n\n{text}\n", encoding="utf-8")
        return path
