"""The page's server: state in UK time, lights in order, replay without spend."""
import json
import time

from web import server
from web.server import App, uk_time


def test_uk_time_conversion():
    assert uk_time("2026-10-15T16:47:57.553+00:00") == "17:47:57"      # BST in October
    assert uk_time("2026-12-15T16:47:57+00:00") == "16:47:57"          # GMT in December


def test_lights_come_on_in_order_and_denials_are_red():
    app = App()
    app._reset("replay")
    snap = app.snapshot()
    assert not any(snap["lights"].values())
    app._entry("2026-10-15T16:47:57+00:00", "desk", "registered", "Researcher", "ok", "owner ae-001")
    assert app.snapshot()["lights"] == {"registered": True, "permitted": False, "logged": False, "stoppable": False}
    app._entry("2026-10-15T16:47:58+00:00", "Researcher", "read book", "25 accounts", "ok", "")
    l = app.snapshot()["lights"]
    assert l["permitted"] and l["logged"] and l["stoppable"]            # all four on; Stop is armed
    app._entry("2026-10-15T16:47:59+00:00", "Writer", "send email", "Dunwold Civil", "denied", "not permitted")
    app._entry("2026-10-15T16:48:00+00:00", "Writer", "STOPPED by AE", "", "stopped", "token revoked")
    snap = app.snapshot()
    writer = next(a for a in snap["agents"] if a["name"] == "Writer")
    assert snap["lights"]["stoppable"] and writer["status"] == "stopped" and writer["colour"] == "#0072B2" and writer["n"] == 4
    assert [e["red"] for e in snap["log"]] == [False, False, True, True]
    assert snap["log"][2]["line"] == "Writer  send email  Dunwold Civil  DENIED  not permitted"
    assert snap["log"][0]["time"] == "17:47:57"


def test_replay_of_a_saved_run_needs_no_model(tmp_path, monkeypatch):
    from opening_doors import config
    from web import server
    run = tmp_path / "runs" / "r1"; run.mkdir(parents=True)
    lines = [{"time": "2026-10-15T16:47:57+00:00", "who": "desk", "what": "registered", "on_what": "Scorer", "outcome": "ok", "detail": ""},
             {"time": "2026-10-15T16:47:57.100+00:00", "who": "Scorer", "what": "ranked 25", "on_what": "", "outcome": "ok", "detail": "top: X"},
             {"time": "2026-10-15T16:47:57.200+00:00", "who": "desk", "what": "run finished", "on_what": "", "outcome": "ok", "detail": ""}]
    (run / "audit.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    app = App()
    assert app.start_replay()
    for _ in range(50):
        if not app.snapshot()["running"]:
            break
        time.sleep(0.05)
    snap = app.snapshot()
    assert not snap["running"] and len(snap["log"]) == 3 and next(a for a in snap["agents"] if a["name"] == "Scorer")["status"] == "done"
    assert snap["lights"]["registered"] and snap["lights"]["logged"]


def test_stop_pressed_during_replay_reddens_row_logs_it_and_refuses_later_lines(tmp_path, monkeypatch):
    from opening_doors import config
    run = tmp_path / "runs" / "r1"; run.mkdir(parents=True)
    lines = [{"time": "2026-10-15T16:47:57+00:00", "who": "desk", "what": "registered", "on_what": "Writer", "outcome": "ok", "detail": ""},
             {"time": "2026-10-15T16:47:58+00:00", "who": "Writer", "what": "read plans", "on_what": "10 plans", "outcome": "ok", "detail": ""},
             {"time": "2026-10-15T16:48:06+00:00", "who": "Writer", "what": "drafted T1 to T5", "on_what": "Dunwold Civil", "outcome": "ok", "detail": ""},
             {"time": "2026-10-15T16:48:06.500+00:00", "who": "Cadence", "what": "scheduled T1 to T5", "on_what": "Dunwold Civil", "outcome": "ok", "detail": ""},
             {"time": "2026-10-15T16:48:07+00:00", "who": "desk", "what": "run finished", "on_what": "", "outcome": "ok", "detail": ""}]
    (run / "audit.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(server, "REPLAY_SPEED", 8.0)
    app = App()
    assert app.start_replay()
    for _ in range(100):                                   # wait until the Writer has read the plans
        if any(e["what"] == "read plans" for e in app.snapshot()["log"]):
            break
        time.sleep(0.02)
    assert app.stop_agent("Writer")                        # the AE presses Stop on the page
    assert not app.stop_agent("Nobody")
    for _ in range(100):
        if not app.snapshot()["running"]:
            break
        time.sleep(0.05)
    snap = app.snapshot()
    writer = next(a for a in snap["agents"] if a["name"] == "Writer")
    assert writer["status"] == "stopped"
    whats = [(e["who"], e["what"], e["outcome"]) for e in snap["log"]]
    assert ("Writer", "STOPPED by AE", "stopped") in whats
    assert ("Writer", "drafted T1 to T5", "stopped") in whats              # played as refused, not as ok
    assert snap["lights"]["stoppable"]                                     # light 4 stays on
    assert [e["red"] for e in snap["log"]].count(True) == 2
    assert next(a for a in snap["agents"] if a["name"] == "Cadence")["status"] == "waiting"   # nothing downstream ran
    assert ("Cadence", "scheduled T1 to T5", "ok") not in whats
