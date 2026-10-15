"""Rule zero: the audit log is append-only and no file under runs/ is ever changed after a run."""
import os

import pytest

from opening_doors.agents import Researcher
from opening_doors.desk import Desk
from opening_doors.governance import Governor, PermissionDenied, RunFileLocked
from opening_doors.governance.audit import LogTampered
from opening_doors.governance.runfiles import is_locked
from tests.test_agents import fake_ask


@pytest.fixture
def run(tmp_path, monkeypatch):
    from opening_doors import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    desk = Desk(ask=fake_ask, run_dir=tmp_path / "runs" / "r1")
    desk.run(["acc-01"])
    return desk


def test_audit_log_cannot_be_rewritten_deleted_or_renamed(run):
    log = run.run_dir / "audit.jsonl"
    with pytest.raises(PermissionError):
        log.open("w")
    with pytest.raises(PermissionError):
        os.remove(log)
    with pytest.raises(PermissionError):
        os.rename(log, log.with_name("other"))
    assert is_locked(log)


def test_out_json_cannot_be_rewritten_deleted_or_written_twice(run):
    out = run.run_dir / "out.json"
    with pytest.raises(PermissionError):
        out.open("w")
    with pytest.raises(PermissionError):
        os.remove(out)
    with pytest.raises(RunFileLocked):
        run.gov.write_run_file(out, "{}")
    assert is_locked(out)


def test_existing_log_lines_unchanged_after_more_entries(run):
    log = run.run_dir / "audit.jsonl"
    before = log.read_text()
    run.gov.log.record("desk", "note", "", "ok")
    after = log.read_text()
    assert after.startswith(before) and after.count("\n") == before.count("\n") + 1


def test_agent_rewrite_attempt_is_denied_and_logged(run):
    r = run.researcher
    for action in ("rewrite_log", "edit_run_file", "delete_run_file"):
        with pytest.raises(PermissionDenied):
            r.act(action, "audit.jsonl", lambda: None)
        last = run.gov.log.entries[-1]
        assert last.outcome == "denied" and last.is_red and last.who == "Researcher"


def test_desk_rewrite_attempt_is_denied_and_logged(run):
    log = run.run_dir / "audit.jsonl"
    for change in ("rewrite", "edit", "delete"):
        with pytest.raises(PermissionDenied):
            run.gov.request_run_file_change("desk", log, change)
        last = run.gov.log.entries[-1]
        assert last.who == "desk" and last.outcome == "denied" and "rule zero" in last.detail
    assert "desk  delete run file  audit.jsonl  DENIED  rule zero" in run.gov.log.lines()[-1]


def test_log_file_is_never_reused(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text("old\n")
    with pytest.raises(LogTampered):
        Governor(owner="ae-001", log_path=path)


def test_shortened_log_is_detected(tmp_path):
    from opening_doors.governance.audit import AuditLog
    from opening_doors.governance.runfiles import protect_append_only
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("desk", "one", "", "ok")
    log.record("desk", "two", "", "ok")
    os.chflags(log.path, 0)                       # a deliberate attacker clears the flag first
    log.path.write_text("short\n")
    with pytest.raises(LogTampered):
        log.record("desk", "three", "", "ok")


def test_no_agent_is_permitted_to_change_run_files():
    from opening_doors.governance.permissions import PERMISSIONS, is_permitted
    for agent_id in list(PERMISSIONS) + ["desk", "anyone"]:
        for action in ("rewrite_log", "edit_run_file", "delete_run_file"):
            assert not is_permitted(agent_id, action)


def test_spend_ledger_lives_outside_runs(run):
    assert run.spend.ledger_path.parent.name == "state"
    assert not (run.run_dir.parent / "spend.json").exists()
