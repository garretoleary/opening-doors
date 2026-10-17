"""Agent 7, Night Review: registered like the other six, reads what it may, writes only proposals and reports."""
import pytest

from opening_doors import config
from opening_doors.agents import NightReview
from opening_doors.desk import Desk
from opening_doors.governance import Governor, PermissionDenied, Stopped
from opening_doors.governance.permissions import PERMISSIONS, is_permitted
from tests.test_agents import fake_ask


def night(tmp_path):
    gov = Governor(owner="ae-001", log_path=tmp_path / "night" / "audit.jsonl")
    nr = NightReview(gov, fake_ask)
    nr.register()
    return gov, nr


def test_registered_like_the_other_six(tmp_path):
    gov, nr = night(tmp_path)
    row = next(r for r in gov.registry.as_rows() if r["agent_id"] == "agent-7")
    assert row["name"] == "Night Review" and row["owner"] == "ae-001" and row["created_at"] and "token" not in row
    assert gov.registry.get("agent-7").token                          # its own token, never shown
    assert "desk  registered  Night Review  ok  owner ae-001, rules night_review.v1" in gov.log.lines()[0]
    assert PERMISSIONS["agent-7"] == frozenset({"read_runs", "read_audit", "read_rules", "write_proposals", "write_reports"})


def test_reads_runs_audit_and_rules_and_writes_only_proposals_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROPOSALS_DIR", tmp_path / "proposals")
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path / "reports")
    desk = Desk(ask=fake_ask); desk.run(["acc-04"])                   # one run to read
    gov, nr = night(tmp_path)
    runs = nr.list_runs()
    assert runs and nr.read_audit(runs[-1]) and nr.read_run_output(runs[-1])["state"]
    assert set(nr.read_rules()) >= {"researcher", "night_review"}
    p = nr.propose("Scorer v2", "Proposal text."); r = nr.report("Night report", "Report text.")
    assert p.parent == tmp_path / "proposals" and r.parent == tmp_path / "reports"
    assert "All data invented" in p.read_text()
    assert all(e.outcome == "ok" for e in gov.log.entries[1:])
    assert any("Night Review  wrote proposal  Scorer v2  ok" in l for l in gov.log.lines())


def test_attempt_to_write_rules_is_refused_and_logged_red(tmp_path):
    gov, nr = night(tmp_path)
    ran = []
    for action in ("write_rules", "edit_rules", "delete_rules"):
        with pytest.raises(PermissionDenied):
            nr.act(action, "scorer.v2.md", lambda: ran.append(1))
        e = gov.log.entries[-1]
        assert ran == [] and e.who == "Night Review" and e.outcome == "denied" and e.is_red
    assert "Night Review  write rules  scorer.v2.md  DENIED  not permitted" in gov.log.lines()[-3]


def test_attempt_to_edit_a_file_under_runs_is_refused_and_logged(tmp_path):
    desk = Desk(ask=fake_ask); desk.run(["acc-04"])
    gov, nr = night(tmp_path)
    for action in ("edit_run_file", "rewrite_log", "delete_run_file"):
        with pytest.raises(PermissionDenied):
            nr.act(action, "audit.jsonl", lambda: 1)
        assert gov.log.entries[-1].outcome == "denied" and gov.log.entries[-1].is_red
    assert "Night Review  edit run file  audit.jsonl  DENIED  not permitted" in gov.log.lines()[-3]
    with pytest.raises(PermissionError):                              # and the file itself is locked, rule zero
        (desk.run_dir / "audit.jsonl").open("w")


def test_stop_on_night_review_refuses_its_next_action(tmp_path):
    gov, nr = night(tmp_path)
    nr.list_runs()
    gov.stop("agent-7")
    assert "Night Review  STOPPED by AE  STOPPED  token revoked" in gov.log.lines()[-1]
    with pytest.raises(Stopped):
        nr.list_runs()
    assert "Night Review  read runs  runs  STOPPED  token revoked" in gov.log.lines()[-1]
    assert gov.registry.get("agent-7").status == "stopped"


def test_never_book_send_or_anything_else():
    for action in ("read_book", "read_signals", "write_book", "send", "send_email", "send_linkedin", "place_call",
                   "write_plans", "write_drafts", "write_scores", "use_tool", "run_shell"):
        assert not is_permitted("agent-7", action)
