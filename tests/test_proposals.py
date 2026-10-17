"""The Proposals panel: approve writes a new rules version and can be rolled back; reject records a reason; five cap; nothing without a tap."""
import json
import shutil
from pathlib import Path

import pytest

from opening_doors import config, proposals, rules


@pytest.fixture
def own_rules(tmp_path, monkeypatch):
    d = tmp_path / "rules"; d.mkdir()
    for f in rules.RULES_DIR.iterdir():
        shutil.copy(f, d / f.name)
    monkeypatch.setattr(rules, "RULES_DIR", d)
    return d


def write_proposal(stamp: str, pid: str, agents="Writer", family="repeated denial", runs="20261017T010000000Z: lines 2"):
    config.PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    (config.PROPOSALS_DIR / f"{stamp}-{pid.lower()}.md").write_text(
        f"All data invented.\n\n# Proposal {pid}\n\nid: {pid}\ndate: 2026-10-17\nfamily: {family}\nagents: {agents}\nevidence: {runs}\nrun count: 1\n"
        f"proposed change: Say plainly that the Writer never sends.\nrisk if applied: Small.\nrisk if ignored: Grows.\nexpiry: 2026-10-31\n\n## Reasoning in full\n\nBecause.\n\nNight Review proposes and never applies. A person decides.\n")


def test_approve_writes_a_new_numbered_version_with_who_when_and_which_proposal(own_rules):
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    assert rules.load("writer").version == 1
    result = proposals.approve("NR-2026-10-17-01")
    assert result["ok"] and result["rules_written"][0]["label"] == "writer.v2"
    v2 = rules.load("writer")
    assert v2.version == 2 and v2.path.name == "writer.v2.md" and (own_rules / "writer.v1.md").exists()
    assert v2.text.startswith("# Writer, rules v2")
    assert v2.instructions == rules.load("writer", own_rules).instructions            # the instructions are unchanged by an approval alone
    last = v2.text.strip().splitlines()[-1]
    assert last.startswith("- v2, 2026-") and "approved proposal NR-2026-10-17-01 by AE via the page at 2026-" in last and "Say plainly that the Writer never sends." in last
    assert proposals.by_id("NR-2026-10-17-01")["status"] == "approved"
    assert proposals.approve("NR-2026-10-17-01") == {"ok": False, "error": "not pending"}      # once
    log = (config.REPORTS_DIR / "page-actions").glob("*.jsonl")
    assert any("approved proposal" in p.read_text() for p in log)


def test_roll_back_restores_the_previous_version_as_a_new_number(own_rules):
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    proposals.approve("NR-2026-10-17-01")
    before = rules.load("writer", own_rules)
    result = proposals.rollback("NR-2026-10-17-01")
    assert result["ok"] and result["restored"][0] == {"label": "writer.v3", "restores": "writer.v1", "undoes": "writer.v2"}
    v3 = rules.load("writer")
    assert v3.version == 3
    assert v3.instructions == before.instructions                                        # the words of v1 are back
    assert v3.text.strip().splitlines()[-1].startswith("- v3, 2026-") and "rolled back writer.v2 to writer.v1 by AE via the page" in v3.text
    assert (own_rules / "writer.v2.md").exists()                                         # nothing deleted
    assert proposals.by_id("NR-2026-10-17-01")["status"] == "rolled back"
    assert proposals.rollback("NR-2026-10-17-01") == {"ok": False, "error": "nothing to roll back"}


def test_reject_records_a_one_line_reason(own_rules):
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    r = proposals.reject("NR-2026-10-17-01", "The send check is deliberate.\nsecond line ignored")
    assert r == {"ok": True, "reason": "The send check is deliberate."}
    assert proposals.by_id("NR-2026-10-17-01")["decision"]["reason"] == "The send check is deliberate."
    assert rules.load("writer").version == 1                                            # no rules written
    assert proposals.reject("NR-2026-10-17-01", "again") == {"ok": False, "error": "not pending"}


def test_pending_is_newest_first_and_capped_at_five(own_rules):
    for i in range(7):
        write_proposal(f"20261017T12000{i}", f"NR-2026-10-17-0{i}")
    pend = proposals.pending()
    assert len(pend) == 5 and [p["id"] for p in pend] == ["NR-2026-10-17-06", "NR-2026-10-17-05", "NR-2026-10-17-04", "NR-2026-10-17-03", "NR-2026-10-17-02"]
    proposals.reject("NR-2026-10-17-06", "no")
    assert [p["id"] for p in proposals.pending()][0] == "NR-2026-10-17-05" and len(proposals.pending()) == 5


def test_reading_changes_nothing(own_rules):
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    snapshot = {p.name: p.read_text() for p in own_rules.iterdir()}
    proposals.pending(); proposals.all_proposals(); proposals.by_id("NR-2026-10-17-01"); proposals.evidence_lines("NR-2026-10-17-01")
    assert {p.name: p.read_text() for p in own_rules.iterdir()} == snapshot
    assert not (config.PROPOSALS_DIR / "status.json").exists()


def test_approving_an_injection_report_writes_no_rules(own_rules):
    write_proposal("20261017T120000", "NR-2026-10-17-01", agents="all", family="injection")
    r = proposals.approve("NR-2026-10-17-01")
    assert r == {"ok": True, "rules_written": []}
    assert all(rules.load(k).version == 1 for k in rules.AGENT_KEYS)


def test_ask_returns_the_cited_audit_lines(own_rules):
    from opening_doors.governance.runfiles import write_once
    d = config.RUNS_DIR / "20261017T010000000Z"; d.mkdir(parents=True)
    write_once(d / "audit.jsonl", json.dumps({"time": "2026-10-17T01:00:00+00:00", "who": "desk", "what": "run started", "on_what": "25 accounts", "outcome": "ok", "detail": ""}) + "\n"
               + json.dumps({"time": "2026-10-17T01:00:01+00:00", "who": "Writer", "what": "send email", "on_what": "Dunwold Civil", "outcome": "denied", "detail": "not permitted"}) + "\n")
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    lines = proposals.evidence_lines("NR-2026-10-17-01")
    assert lines == [{"run": "20261017T010000000Z", "line": 2, "time": "01:00:01", "who": "Writer", "what": "send email", "on_what": "Dunwold Civil", "outcome": "denied", "detail": "not permitted"}]


def test_superseded_proposals_leave_the_pending_list_with_a_reason_and_a_log_line(own_rules):
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    write_proposal("20261017T120100", "NR-2026-10-17-01")                                 # a duplicate id, a different file
    assert len(proposals.pending()) == 2
    r = proposals.supersede("20261017T120100-nr-2026-10-17-01.md", "duplicate before unique-id fix")
    assert r == {"ok": True}
    pend = proposals.pending()
    assert len(pend) == 1 and pend[0]["file"] == "20261017T120000-nr-2026-10-17-01.md"
    assert proposals.counts()["superseded"] == 1 and proposals.counts()["pending"] == 1
    logs = "".join(p.read_text() for p in (config.REPORTS_DIR / "page-actions").glob("*.jsonl"))
    assert logs.count("superseded proposal") == 1 and "duplicate before unique-id fix" in logs
    assert proposals.supersede("20261017T120100-nr-2026-10-17-01.md", "again") == {"ok": False, "error": "not pending"}
    assert rules.load("writer").version == 1
