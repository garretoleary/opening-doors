"""Proposals on the page. Pending proposals, newest first, at most five. A person taps Approve, Reject or Ask.
Approve writes a new numbered version of the agent's rules file naming who, when and which proposal, and can be
rolled back, which writes the previous version again as a new number. Nothing changes without a tap, and every
tap is logged in an append-only page log. No Approve all.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config, rules as rules_mod
from .governance.audit import AuditLog

LIMIT = 5
FIELDS = ["id", "date", "family", "key", "agents", "evidence", "run count", "proposed change", "risk if applied", "risk if ignored", "expiry"]


def _status_path() -> Path:
    return config.PROPOSALS_DIR / "status.json"


def _status() -> Dict[str, Dict]:
    p = _status_path()
    return json.loads(p.read_text()) if p.exists() else {}


def _set_status(key: str, record: Dict) -> None:
    """Keyed by the proposal's file name, which is unique even where two reviews wrote the same id."""
    s = _status(); s[key] = record
    _status_path().parent.mkdir(parents=True, exist_ok=True)
    _status_path().write_text(json.dumps(s, indent=2))


def _page_log() -> AuditLog:
    """The page's own append-only log of human decisions. A new file per day; never rewritten."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = config.REPORTS_DIR / "page-actions" / f"{day}.jsonl"
    log = AuditLog.__new__(AuditLog)
    log.entries, log.path, log.listeners, log._bytes_written = [], path, [], (path.stat().st_size if path.exists() else 0)
    import threading
    log._lock = threading.RLock()
    path.parent.mkdir(parents=True, exist_ok=True)
    return log


def parse(path: Path) -> Dict:
    text = path.read_text(encoding="utf-8")
    out: Dict = {"file": path.name, "path": str(path)}
    for f in FIELDS:
        m = re.search(rf"^{re.escape(f)}: (.*)$", text, re.M)
        out[f.replace(" ", "_")] = m.group(1).strip() if m else ""
    m = re.search(r"^## Reasoning in full\s*\n(.*?)(?=^Night Review proposes|\Z)", text, re.S | re.M)
    out["reasoning"] = m.group(1).strip() if m else ""
    out["agents_list"] = [a.strip() for a in out["agents"].split(",") if a.strip()]
    out["evidence_map"] = {}
    for part in out["evidence"].split(";"):
        if ":" in part:
            run, lines = part.split(":", 1)
            nums = [int(x) for x in re.findall(r"\d+", lines)]
            out["evidence_map"][run.strip()] = nums
    return out


def all_proposals() -> List[Dict]:
    d = config.PROPOSALS_DIR
    if not d.exists():
        return []
    items = [parse(p) for p in sorted(d.glob("*.md"), reverse=True)]        # newest first by file stamp
    status = _status()
    for it in items:
        rec = status.get(it["file"]) or status.get(it["id"]) or {}
        it["status"] = rec.get("status", "pending")
        it["decision"] = rec
    return items


def pending(limit: int = LIMIT) -> List[Dict]:
    return [p for p in all_proposals() if p["status"] == "pending"][:limit]


def by_id(pid: str) -> Optional[Dict]:
    """The proposal with this id; if two files share it, the pending one, else the newest."""
    matches = [p for p in all_proposals() if p["id"] == pid]
    return next((p for p in matches if p["status"] == "pending"), matches[0] if matches else None)


def supersede(file_name: str, reason: str, who: str = "AE via the page") -> Dict:
    """Take a proposal off the pending list without deciding it, with a reason. One log line."""
    p = next((x for x in all_proposals() if x["file"] == file_name), None)
    if not p or p["status"] != "pending":
        return {"ok": False, "error": "not pending"}
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _set_status(file_name, {"status": "superseded", "by": who, "when": when, "reason": reason})
    _page_log().record(who, "superseded proposal", f"{p['id']} ({file_name})", "ok", reason)
    return {"ok": True}


def counts() -> Dict[str, int]:
    out = {"pending": 0, "approved": 0, "rejected": 0, "superseded": 0, "rolled back": 0}
    for p in all_proposals():
        out[p["status"]] = out.get(p["status"], 0) + 1
    return out


def evidence_lines(pid: str) -> List[Dict]:
    """Ask: the text of every audit line the proposal cites."""
    p = by_id(pid)
    if not p:
        return []
    out = []
    for run_id, nums in p["evidence_map"].items():
        path = config.RUNS_DIR / run_id / "audit.jsonl"
        if not path.exists():
            continue
        entries = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for n in nums:
            if 1 <= n <= len(entries):
                e = entries[n - 1]
                out.append({"run": run_id, "line": n, "time": e.get("time", "")[11:19], "who": e.get("who"), "what": e.get("what"),
                            "on_what": e.get("on_what"), "outcome": e.get("outcome"), "detail": e.get("detail")})
    return out


def _next_version(key: str) -> int:
    cur = rules_mod.current_path(key)
    return (int(re.search(r"\.v(\d+)\.md$", cur.name).group(1)) + 1) if cur else 1


def _write_version(key: str, text: str, changelog_line: str) -> str:
    n = _next_version(key)
    text = re.sub(r"^(# .*?, rules )v\d+", rf"\g<1>v{n}", text, count=1, flags=re.M)
    text = text.rstrip("\n") + "\n" + changelog_line + "\n"
    path = rules_mod.rules_dir() / f"{key}.v{n}.md"
    path.write_text(text, encoding="utf-8")
    return f"{key}.v{n}"


def approve(pid: str, who: str = "AE via the page") -> Dict:
    """Approve: a new numbered rules version for each agent the proposal concerns, naming who, when and which proposal."""
    p = by_id(pid)
    if not p or p["status"] != "pending":
        return {"ok": False, "error": "not pending"}
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = []
    for name in p["agents_list"]:
        key = name.lower().replace(" ", "_")
        if rules_mod.current_path(key) is None:
            continue                                               # 'all', or an agent with no rules file: nothing to write
        cur = rules_mod.load(key)
        label = _write_version(key, cur.text, f"- v{_next_version(key)}, {when[:10]}: approved proposal {pid} by {who} at {when}. Change: {p['proposed_change']}")
        written.append({"label": label, "previous": cur.label})
    _set_status(p["file"], {"status": "approved", "by": who, "when": when, "rules_written": written})
    _page_log().record(who, "approved proposal", pid, "ok", ", ".join(w["label"] for w in written) or "no rules file to write")
    return {"ok": True, "rules_written": written}


def rollback(pid: str, who: str = "AE via the page") -> Dict:
    """Roll back: the version before the approval is written again as a new number. Nothing is deleted."""
    p = by_id(pid)
    s = _status().get(p["file"]) if p else None
    if not s or s.get("status") != "approved":
        return {"ok": False, "error": "nothing to roll back"}
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    restored = []
    for w in s.get("rules_written", []):
        key = w["label"].rsplit(".v", 1)[0]
        prev = rules_mod.rules_dir() / f"{w['previous']}.md"
        if not prev.exists():
            continue
        label = _write_version(key, prev.read_text(encoding="utf-8"), f"- v{_next_version(key)}, {when[:10]}: rolled back {w['label']} to {w['previous']} by {who} at {when}; proposal {pid}.")
        restored.append({"label": label, "restores": w["previous"], "undoes": w["label"]})
    _set_status(p["file"], {**s, "status": "rolled back", "rolled_back_by": who, "rolled_back_at": when, "restored": restored})
    _page_log().record(who, "rolled back proposal", pid, "ok", ", ".join(r["label"] for r in restored) or "nothing to restore")
    return {"ok": True, "restored": restored}


def reject(pid: str, reason: str, who: str = "AE via the page") -> Dict:
    p = by_id(pid)
    if not p or p["status"] != "pending":
        return {"ok": False, "error": "not pending"}
    reason = (reason or "").strip().splitlines()[0][:200] if reason and reason.strip() else "no reason given"
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _set_status(p["file"], {"status": "rejected", "by": who, "when": when, "reason": reason})
    _page_log().record(who, "rejected proposal", pid, "ok", reason)
    return {"ok": True, "reason": reason}
