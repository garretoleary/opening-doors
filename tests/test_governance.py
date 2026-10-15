import pytest

from opening_doors.governance import Governor, NotRegistered, PermissionDenied, Stopped


def make():
    g = Governor(owner="ae-001")
    r = g.register("agent-1", "Researcher", "reads the book and its signals")
    w = g.register("agent-4", "Writer", "drafts the five touches")
    return g, r, w


def test_nothing_runs_unless_registered():
    g = Governor(owner="ae-001")
    with pytest.raises(NotRegistered):
        g.act("agent-9", "x", "read_book", "Harrowgate Lumen", lambda: 1)


def test_registered_light_and_log():
    g, r, _ = make()
    assert g.lights["registered"] is True
    assert r.owner == "ae-001" and r.created_at and r.token
    assert "registered" in g.log.lines()[0]


def test_permitted_action_runs_and_is_logged():
    g, r, _ = make()
    out = g.act("agent-1", r.token, "read_book", "Harrowgate Lumen", lambda: "signals")
    assert out == "signals"
    assert g.lights["permitted"] and g.lights["logged"]
    assert g.log.entries[-1].outcome == "ok"
    assert "Researcher  read book  Harrowgate Lumen  ok" in g.log.lines()[-1]


def test_denied_action_is_refused_and_logged():
    g, _, w = make()
    ran = []
    with pytest.raises(PermissionDenied):
        g.act("agent-4", w.token, "send_email", "Harrowgate Lumen", lambda: ran.append(1))
    assert ran == []
    last = g.log.entries[-1]
    assert last.outcome == "denied" and last.is_red
    assert "Writer  send email  Harrowgate Lumen  DENIED  not permitted" in last.line()


def test_writer_may_not_read_the_raw_book():
    g, _, w = make()
    with pytest.raises(PermissionDenied):
        g.act("agent-4", w.token, "read_book", "", lambda: 1)


def test_stop_revokes_token_mid_run():
    g, r, _ = make()
    g.act("agent-1", r.token, "read_book", "Veldstone Marine", lambda: 1)
    g.stop("agent-1")
    assert g.lights["stoppable"] and g.registry.get("agent-1").status == "stopped"
    with pytest.raises(Stopped):
        g.act("agent-1", r.token, "read_signals", "Veldstone Marine", lambda: 1)
    assert g.log.entries[-1].outcome == "stopped"
    assert "STOPPED by AE" in g.log.lines()[-2]


def test_wrong_token_is_refused():
    g, r, _ = make()
    with pytest.raises(Stopped):
        g.act("agent-1", "not-the-token", "read_book", "", lambda: 1)


def test_log_file_and_live_listener(tmp_path):
    g = Governor(owner="ae-001", log_path=tmp_path / "audit.jsonl")
    seen = []
    g.log.subscribe(lambda e: seen.append(e.what))
    g.register("agent-2", "Scorer", "ranks the 25")
    assert seen == ["registered"]
    assert (tmp_path / "audit.jsonl").read_text().count("\n") == 1


def test_registry_rows_never_show_token():
    g, r, _ = make()
    for row in g.registry.as_rows():
        assert "token" not in row
