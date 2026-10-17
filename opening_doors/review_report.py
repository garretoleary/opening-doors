"""The nightly dashboard. Every number carries its receipts: the run ids and audit line numbers it was
counted from. No number without a receipt; a zero carries an empty receipt and says so. If the evidence
is thin, the dashboard says: not enough runs yet to judge. Built from the latest review's folder and the
runs it read; written also as a dated file under reports by Night Review at the end of each nightly run.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import config, proposals
from .governance.permissions import PERMISSIONS
from .rules import AGENT_KEYS

AGENTS = [("agent-1", "Researcher"), ("agent-2", "Scorer"), ("agent-3", "Planner"), ("agent-4", "Writer"),
          ("agent-5", "Cadence"), ("agent-6", "Qualifier"), ("agent-7", "Night Review")]
THIN = 3


def _num(value, receipts: List[Dict], note: str = "") -> Dict:
    """A number with its receipts. A zero carries an empty receipt list and says why."""
    receipts = receipts or []
    if not receipts and not note:
        note = "nothing to count" if value == 0 else "no receipt"
    return {"value": value, "receipts": receipts, "note": note}


def latest_review_dir() -> Optional[Path]:
    d = config.REPORTS_DIR
    if not d.exists():
        return None
    dirs = sorted((p for p in d.iterdir() if p.is_dir() and p.name.startswith("review-") and (p / "summary.json").exists()), reverse=True)
    return dirs[0] if dirs else None


def _audit(run_id: str) -> List[Dict]:
    path = config.RUNS_DIR / run_id / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _review_audit(review_dir: Path) -> List[Dict]:
    path = review_dir / "audit.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def build(review_dir: Optional[Path] = None) -> Dict:
    review_dir = review_dir or latest_review_dir()
    if review_dir is None:
        return {"ready": False, "message": "No night review yet. Press Run night review."}
    summary = json.loads((review_dir / "summary.json").read_text())
    findings = json.loads((review_dir / "findings.json").read_text()) if (review_dir / "findings.json").exists() else []
    runs = summary.get("runs_read", [])
    audits = {r: _audit(r) for r in runs}
    thin = len(runs) < THIN

    # tiles: every count is a list of receipts first, then its length
    run_receipts = [{"run": r, "line": next((n for n, e in enumerate(audits[r], 1) if e.get("what") == "run started"), 1)} for r in runs]
    call_receipts, cost_receipts, cost_total, calls_total = [], [], 0.0, 0
    for r in runs:
        for n, e in enumerate(audits[r], 1):
            if e.get("what") == "run finished":
                call_receipts.append({"run": r, "line": n}); cost_receipts.append({"run": r, "line": n})
                out_path = config.RUNS_DIR / r / "out.json"
                spend = json.loads(out_path.read_text()).get("spend", {}) if out_path.exists() else {}
                cost_total += float(spend.get("gbp", 0) or 0); calls_total += int(spend.get("calls", 0) or 0)
    denial_receipts = [{"run": r, "line": n} for r in runs for n, e in enumerate(audits[r], 1) if e.get("outcome") == "denied"]
    stop_receipts = [{"run": r, "line": n} for r in runs for n, e in enumerate(audits[r], 1) if e.get("outcome") == "stopped"]
    tiles = {
        "runs": _num(len(runs), run_receipts),
        "model_calls": _num(calls_total, call_receipts),
        "cost_gbp": _num(round(cost_total, 2), cost_receipts),
        "denials": _num(len(denial_receipts), denial_receipts),
        "stops": _num(len(stop_receipts), stop_receipts),
    }

    # one line per agent, seven agents, plain words with counts
    agents = []
    review_audit = _review_audit(review_dir)
    for agent_id, name in AGENTS:
        if name == "Night Review":
            src = {"review": review_audit}
        else:
            src = audits
        acts = [{"run": r, "line": n} for r, es in src.items() for n, e in enumerate(es, 1) if e.get("who") == name and e.get("outcome") == "ok"]
        den = [{"run": r, "line": n} for r, es in src.items() for n, e in enumerate(es, 1) if e.get("who") == name and e.get("outcome") == "denied"]
        stp = [{"run": r, "line": n} for r, es in src.items() for n, e in enumerate(es, 1) if e.get("who") == name and e.get("outcome") == "stopped"]
        ran_in = sorted({a["run"] for a in acts})
        stop_state = "stopped" if stp else "armed"
        words = (f"{name} acted {len(acts)} times in {len(ran_in)} run{'s' if len(ran_in) != 1 else ''}, "
                 f"{len(den)} refused, {len(stp)} stopped." if acts or den or stp else f"{name} did nothing in these runs.")
        agents.append({"agent_id": agent_id, "name": name, "words": words, "permitted": sorted(PERMISSIONS.get(agent_id, [])),
                       "actions": _num(len(acts), acts), "denials": _num(len(den), den), "stops": _num(len(stp), stp), "stop_state": stop_state})

    # findings and proposals
    finding_rows = [{"family": f["family"], "summary": f["summary"], "receipts": [{"run": r, "line": n} for r, ls in f["evidence"].items() for n in (ls or [None])],
                     "runs": len(f["evidence"])} for f in findings]
    checks = summary.get("checks_passed") or {}
    check_receipts = [{"run": r, "line": n} for r, ls in checks.items() for n in ls]
    counts = proposals.counts()

    # Night Review's own run
    nr_den = [{"run": "review", "line": n} for n, e in enumerate(review_audit, 1) if e.get("outcome") == "denied"]
    own = {"seconds": summary.get("seconds"), "cost_gbp": summary.get("gbp"), "model_calls": summary.get("model_calls"),
           "denials": _num(len(nr_den), nr_den), "review": summary.get("review"),
           "words": f"Night Review's own run: {summary.get('seconds')} s, £{float(summary.get('gbp') or 0):.2f} over {summary.get('model_calls')} model calls, {len(nr_den)} refused."}

    alliance = [
        {"question": "Where are my agents?", "answer": f"{len(AGENTS)} registered: " + ", ".join(n for _, n in AGENTS), "receipts": [{"run": r, "line": n} for r in runs[:1] for n, e in enumerate(audits[r], 1) if e.get("what") == "registered"]},
        {"question": "What can they do?", "answer": "A permission list per agent, enforced in code; shown on each agent's line.", "receipts": []},
        {"question": "What are they doing?", "answer": f"This report: {len(runs)} runs read, every number with its audit lines.", "receipts": run_receipts},
        {"question": "How do I stop one?", "answer": "A Stop per agent revokes its token mid-run. " + ", ".join(f"{a['name']} {a['stop_state']}" for a in agents), "receipts": stop_receipts},
    ]
    return {
        "ready": True, "review": summary.get("review"), "review_dir": review_dir.name, "runs_read": runs,
        "thin": thin, "thin_message": "Not enough runs yet to judge." if thin else "",
        "reread": bool(summary.get("reread")), "reread_message": "No new runs since the last review; the latest were read again." if summary.get("reread") else "",
        "tiles": tiles, "agents": agents, "findings": finding_rows,
        "checks_passed": _num(len(check_receipts), check_receipts, "" if check_receipts else "no deliberate check seen"),
        "proposals": counts, "alliance": alliance, "night_review": own,
        "notice": config.INVENTED_DATA_NOTICE,
    }


def receipts_ok(dash: Dict) -> List[str]:
    """The receipts rule: every number has receipts, or is zero with a note. Returns the breaches, so [] is a pass."""
    breaches = []
    def check(label: str, num: Dict):
        if not isinstance(num, dict) or "value" not in num:
            breaches.append(f"{label}: not a receipted number"); return
        if num["value"] not in (0, 0.0) and not num["receipts"]:
            breaches.append(f"{label}: {num['value']} without a receipt")
        if num["value"] in (0, 0.0) and not num["receipts"] and not num.get("note"):
            breaches.append(f"{label}: zero without a note")
    for k, v in dash.get("tiles", {}).items():
        check(f"tile {k}", v)
    for a in dash.get("agents", []):
        for k in ("actions", "denials", "stops"):
            check(f"{a['name']} {k}", a[k])
    check("checks_passed", dash.get("checks_passed", {}))
    check("night review denials", dash.get("night_review", {}).get("denials", {}))
    for f in dash.get("findings", []):
        if f["runs"] and not f["receipts"]:
            breaches.append(f"finding {f['summary']}: no receipt")
    return breaches


def as_text(dash: Dict) -> str:
    """The same dashboard as a dated file under reports."""
    if not dash.get("ready"):
        return dash.get("message", "")
    t = dash["tiles"]
    lines = [f"{dash['notice']}", "", f"# Night review dashboard {dash['review']}", "",
             f"Runs {t['runs']['value']} · model calls {t['model_calls']['value']} · cost £{t['cost_gbp']['value']:.2f} · denials {t['denials']['value']} · stops {t['stops']['value']}"]
    if dash["thin"]:
        lines.append(dash["thin_message"])
    lines += ["", "## Agents"] + [f"- {a['words']} Permitted: {', '.join(a['permitted'])}. Stop: {a['stop_state']}." for a in dash["agents"]]
    lines += ["", "## Findings"] + ([f"- {f['family']}: {f['summary']} ({f['runs']} runs)" for f in dash["findings"]] or ["- none"])
    lines += ["", f"Governance check passed: {dash['checks_passed']['value']} lines.", "",
              "## Proposals", "- " + ", ".join(f"{k} {v}" for k, v in dash["proposals"].items()), "", "## The four questions"]
    lines += [f"- {q['question']} {q['answer']}" for q in dash["alliance"]]
    lines += ["", dash["night_review"]["words"], "", "Every number above has its audit lines behind it on the page."]
    return "\n".join(lines) + "\n"
