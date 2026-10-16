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


def test_out_appears_after_the_scorer_and_target_detail_fills_as_the_log_announces_it(tmp_path, monkeypatch):
    from opening_doors import config
    from opening_doors.desk import Desk
    from tests.test_agents import fake_ask
    desk = Desk(ask=fake_ask)
    out = desk.run()
    run = tmp_path / "runs" / "r1"; run.mkdir(parents=True)
    (run / "out.json").write_text(json.dumps(out))
    entries = [json.loads(l) for l in (desk.run_dir / "audit.jsonl").read_text().splitlines()]
    app = App()
    app._reset("replay")
    app.data = {k: out[k] for k in ("ranked", "plans", "drafts", "schedule", "qualified")}
    assert app.snapshot()["out"] == []
    first = out["ranked"][0]
    for e in entries:
        app._entry(e["time"], e["who"], e["what"], e["on_what"], e["outcome"], e["detail"])
        if e["who"] == "Scorer" and e["what"].startswith("ranked"):
            rows = app.snapshot()["out"]
            assert len(rows) == 10 and rows[0]["name"] == first["name"] and rows[0]["why"]
            assert rows[0]["ready"] == {"plan": False, "touches": False, "schedule": False, "qualified": False}
            t = app.target(first["id"])
            assert t["plan"] is None and t["touches"] is None and t["qualified"] is None
    rows = app.snapshot()["out"]
    assert all(r["ready"]["plan"] and r["ready"]["touches"] and r["ready"]["schedule"] for r in rows)
    t = app.target(first["id"])
    assert set(t["plan"]) == {"business_problem", "economic_buyer", "first_meeting_point_of_view", "one_metric_to_agree"}
    assert [x["touch"] for x in t["touches"]] == [1, 2, 3, 4, 5] and all(x["due"] for x in t["touches"])
    assert t["qualified"] and t["qualified"]["mutual_plan"]["steps"]   # the book's invented reply brought the Qualifier in
    assert app.target("acc-99") is None


def test_desk_results_fill_stage_by_stage():
    from opening_doors.desk import Desk
    from tests.test_agents import fake_ask
    desk = Desk(ask=fake_ask)
    seen = []
    desk.gov.log.subscribe(lambda e: seen.append((e.what, len(desk.results["ranked"]), len(desk.results["plans"]), len(desk.results["drafts"]))))
    desk.run(["acc-01", "acc-02", "acc-03"])
    at_read_plans = next(x for x in seen if x[0] == "read plans")
    assert at_read_plans[1] == 3 and at_read_plans[2] == 3 and at_read_plans[3] == 0   # ranked and planned, not yet drafted
    assert len(desk.results["drafts"]) == 3 and len(desk.results["schedule"]) == 3


def test_zone_tiles_count_the_book_and_move_with_the_log():
    app = App()
    app._reset("replay")
    assert [z["count"] for z in app.snapshot()["zones"]] == [0, 0, 0, 0]
    app._entry("2026-10-15T16:47:57+00:00", "desk", "run started", "25 accounts", "ok", "")
    zones = app.snapshot()["zones"]
    assert [z["zone"] for z in zones] == [4, 3, 2, 1] and [z["count"] for z in zones] == [25, 0, 0, 0]
    assert [z["name"] for z in zones] == ["Open the door", "Earn the call", "Frame the value", "Commit"]
    app._entry("2026-10-15T16:48:00+00:00", "Cadence", "T1 given", "Harrowgate Lumen", "ok", "")
    assert [z["count"] for z in app.snapshot()["zones"]] == [25, 0, 0, 0]          # T1 and T2 are Zone 4
    app._entry("2026-10-15T16:48:01+00:00", "Cadence", "T3 given", "Harrowgate Lumen", "ok", "")
    assert [z["count"] for z in app.snapshot()["zones"]] == [24, 1, 0, 0]          # T3 is Zone 3
    app._entry("2026-10-15T16:48:02+00:00", "Cadence", "reply received, invented", "Harrowgate Lumen", "ok", "at T3, to Qualifier, First call")
    assert [z["count"] for z in app.snapshot()["zones"]] == [24, 1, 0, 0]          # First call ends Zone 3
    app._entry("2026-10-15T16:48:03+00:00", "Qualifier", "mutual plan drafted", "Harrowgate Lumen", "ok", "")
    assert [z["count"] for z in app.snapshot()["zones"]] == [24, 0, 1, 0]          # Zone 2
    app._entry("2026-10-15T16:48:04+00:00", "Cadence", "T3 given", "Quillon Health", "stopped", "token revoked")
    assert [z["count"] for z in app.snapshot()["zones"]] == [24, 0, 1, 0]          # a refused move is no move
    app._entry("2026-10-15T16:48:05+00:00", "desk", "buying committee accepted the ask, invented", "Harrowgate Lumen", "ok", "Zone 1")
    assert [z["count"] for z in app.snapshot()["zones"]] == [24, 0, 0, 1]          # Zone 1


def test_dots_follow_the_log_for_the_desktop_map():
    app = App()
    app._reset("replay")
    assert app.snapshot()["dots"] == []
    app._entry("2026-10-16T08:00:00+00:00", "desk", "run started", "25 accounts", "ok", "")
    dots = app.snapshot()["dots"]
    assert len(dots) == 25 and all(d["zone"] == 4 and d["stop"] == "start" for d in dots)
    app._entry("2026-10-16T08:00:01+00:00", "Planner", "account plan", "Harrowgate Lumen", "ok", "")
    app._entry("2026-10-16T08:00:02+00:00", "Cadence", "T1 given", "Harrowgate Lumen", "ok", "")
    app._entry("2026-10-16T08:00:03+00:00", "Cadence", "no reply", "Harrowgate Lumen", "ok", "next T2")
    app._entry("2026-10-16T08:00:04+00:00", "Cadence", "T3 given", "Harrowgate Lumen", "ok", "")
    d = next(x for x in app.snapshot()["dots"] if x["name"] == "Harrowgate Lumen")
    assert d == {"name": "Harrowgate Lumen", "zone": 3, "stop": "T3 given"}
    app._entry("2026-10-16T08:00:05+00:00", "Cadence", "no reply", "Harrowgate Lumen", "ok", "resting, no sixth touch")
    assert next(x for x in app.snapshot()["dots"] if x["name"] == "Harrowgate Lumen")["stop"] == "resting"
    app._entry("2026-10-16T08:00:06+00:00", "desk", "buying committee accepted the ask, invented", "Dunwold Civil", "ok", "")
    d2 = next(x for x in app.snapshot()["dots"] if x["name"] == "Dunwold Civil")
    assert d2["zone"] == 1 and d2["stop"] == "committee"
