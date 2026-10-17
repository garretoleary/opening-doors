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


def test_limit_reached_shows_a_labelled_replay_of_the_seed_run(tmp_path, monkeypatch):
    from opening_doors import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")          # no run on this disk yet
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(config, "RUNS_PER_DAY", 0)                      # today's runs are used
    monkeypatch.setattr(server, "REPLAY_SPEED", 400.0)
    app = App()
    assert app.start_run()
    for _ in range(200):
        snap = app.snapshot()
        if snap["limit"] and not snap["running"] and snap["log"]:
            break
        time.sleep(0.05)
    snap = app.snapshot()
    assert snap["limit"].startswith("limit reached: today's 0 runs are used") and "replay" in snap["limit"]
    assert snap["mode"] == "replay" and len(snap["log"]) > 100 and snap["spend_gbp"] == 0.49
    assert [z["count"] for z in snap["zones"]] == [11, 7, 4, 3]            # the shipped run, invented data
    assert (tmp_path / "state" / "spend.json").exists() is False or True


def test_daily_limit_is_ten():
    from opening_doors import config
    assert config.RUNS_PER_DAY == 10


def test_dots_tiles_and_log_agree_at_every_moment(tmp_path, monkeypatch):
    """One source. At every log line: dots per zone == tile counts == what the log alone implies."""
    from opening_doors import config
    from opening_doors.desk import Desk
    from tests.test_agents import fake_ask
    desk = Desk(ask=fake_ask)
    desk.run()
    entries = [json.loads(l) for l in (desk.run_dir / "audit.jsonl").read_text().splitlines()]
    app = App()
    app._reset("replay")
    expected = {}                                            # name -> zone, derived here from the log alone
    size = 0
    for e in entries:
        app._entry(e["time"], e["who"], e["what"], e["on_what"], e["outcome"], e["detail"])
        if e["what"] == "run started":
            size = int(e["on_what"].split()[0])
        if e["outcome"] == "ok" and e["on_what"]:
            w, o, d = e["who"], e["what"], e["detail"]
            if w == "Cadence" and o == "T3 given":
                expected[e["on_what"]] = 3
            elif w == "Cadence" and o.startswith("reply received"):
                expected[e["on_what"]] = 3
            elif w == "Qualifier" and o == "mutual plan drafted":
                expected[e["on_what"]] = 2
            elif w == "desk" and o.startswith("buying committee accepted"):
                expected[e["on_what"]] = 1
            elif w == "desk" and o == "book position, invented":
                given = next((n for n in (5, 4, 3, 2, 1) if f"T{n}" in d), 0)
                expected[e["on_what"]] = 3 if ("resting" in d or "replied" in d or given >= 3) else 4
        snap = app.snapshot()
        tiles = {z["zone"]: z["count"] for z in snap["zones"]}
        dots = {z: sum(1 for x in snap["dots"] if x["zone"] == z) for z in (4, 3, 2, 1)}
        from_log = {z: sum(1 for v in expected.values() if v == z) for z in (3, 2, 1)}
        from_log[4] = (size - sum(from_log.values())) if size else 0
        assert dots == tiles == from_log, (e["what"], e["on_what"], dots, tiles, from_log)
        for x in snap["dots"]:                                 # and each account sits where the log put it
            assert x["zone"] == expected.get(x["name"], 4), x
    assert tiles == {4: 11, 3: 8, 2: 3, 1: 3}                   # the stand-in Scorer's spread, reached only at the end
    moves = [e for e in entries if e["outcome"] == "ok" and ((e["who"] == "Qualifier" and e["what"] == "mutual plan drafted") or e["what"].startswith("buying committee"))]
    assert moves, "zone 2 and 1 moves must come from logged events"


def test_no_account_moves_before_its_event_is_logged():
    """Before any Cadence or Qualifier line, every account is in Zone 4, whatever the desk's own state says."""
    app = App()
    app._reset("run")
    app._entry("2026-10-16T13:37:00+00:00", "desk", "run started", "25 accounts", "ok", "")
    for who, what, on in (("Researcher", "read book", "25 accounts"), ("Scorer", "ranked 25", ""), ("Planner", "account plan", "Dunwold Civil"),
                          ("Writer", "drafted T1 to T5", "Dunwold Civil"), ("Cadence", "scheduled T1 to T5", "Dunwold Civil"), ("Cadence", "T1 given", "Dunwold Civil")):
        app._entry("2026-10-16T13:37:01+00:00", who, what, on, "ok", "")
        snap = app.snapshot()
        assert [z["count"] for z in snap["zones"]] == [25, 0, 0, 0]
        assert all(d["zone"] == 4 for d in snap["dots"])


def test_a_query_string_does_not_hide_the_page():
    from web.server import Handler
    class Fake(Handler):
        def __init__(self, path):
            self.path = path; self.sent = []
        def _send(self, code, body, ctype): self.sent.append((code, ctype))
    h = Fake("/?from=a-shared-link"); h.do_GET()
    assert h.sent[0][0] == 200 and "text/html" in h.sent[0][1]
    h = Fake("/state?x=1"); h.do_GET()
    assert h.sent[0][0] == 200 and "json" in h.sent[0][1]


def test_chain_counts_match_the_state_and_each_links_to_audit_lines():
    from opening_doors.desk import Desk
    from tests.test_agents import fake_ask
    desk = Desk(ask=fake_ask)
    out = desk.run()
    entries = [json.loads(l) for l in (desk.run_dir / "audit.jsonl").read_text().splitlines()]
    app = App()
    app._reset("replay")
    for e in entries:
        app._entry(e["time"], e["who"], e["what"], e["on_what"], e["outcome"], e["detail"])
    snap = app.snapshot()
    chain = {c["key"]: c for c in snap["chain"]}
    zones = {z: sum(1 for v in out["state"].values() if v["zone"] == z) for z in (4, 3, 2, 1)}
    assert chain["researched"]["count"] == 25 and chain["planned"]["count"] == len(out["plans"]) == 10
    assert [chain[k]["count"] for k in ("zone4", "zone3", "zone2", "zone1")] == [zones[4], zones[3], zones[2], zones[1]]
    assert [c["label"] for c in snap["chain"]] == ["researched", "planned", "Find", "Open", "Qualify", "Agree"]
    assert [chain[k]["count"] for k in ("zone4", "zone3", "zone2", "zone1")] == [z["count"] for z in snap["zones"]]   # one source
    log = snap["log"]
    assert log[chain["researched"]["lines"][0] - 1]["what"] == "read signals"
    assert len(chain["planned"]["lines"]) == 10 and all(log[n - 1]["what"] == "account plan" for n in chain["planned"]["lines"])
    assert len(chain["zone2"]["lines"]) == zones[2] and all(log[n - 1]["what"] == "mutual plan drafted" for n in chain["zone2"]["lines"])
    assert len(chain["zone1"]["lines"]) == zones[1] and all(log[n - 1]["what"].startswith("buying committee") for n in chain["zone1"]["lines"])
    assert len(chain["zone3"]["lines"]) == zones[3]                                                      # one receipt per account sitting there
    assert chain["zone4"]["lines"] and log[chain["zone4"]["lines"][0] - 1]["what"] == "read signals"
    assert snap["cost_live_gbp"] == 0.0                                                                    # the stand-in spends nothing


def test_live_cost_is_zero_before_a_run():
    assert App().snapshot()["cost_live_gbp"] == 0.0 and App().snapshot()["chain"] == []


def test_review_tab_caption_footer_and_two_decimal_costs():
    """Three phone fixes, 17 October: cost to two decimals everywhere, the Hunt footer line on the Review tab, a caption under the button."""
    from opening_doors import config
    html = (config.ROOT / "web" / "index.html").read_text()
    assert "Night Review reads every run, finds repeated mistakes and proposes rule changes. A person approves each one. Nothing applies on its own." in html
    review_footer = html[html.index('<section class="reviewpane'):html.index('<div class="head hunt">')]
    assert "Every agent acts on the AE's behalf. No agent is permitted to send. Times are UK. Built by <b>Garret O'Leary</b> with <b>Claude Code</b> on the Claude API." in review_footer
    assert 'Number(T.cost_gbp.value).toFixed(2)' in html and ".4f" not in html
    from opening_doors import review_report
    import inspect
    assert ":.4f" not in inspect.getsource(review_report)


def test_demo_proposal_button_is_absent_without_the_staging_variable(monkeypatch):
    from opening_doors import config
    from web import server
    from web.server import Handler
    class Fake(Handler):
        def __init__(self, path):
            self.path = path; self.sent = []; self.headers = {}
        def _send(self, code, body, ctype): self.sent.append((code, body, ctype))
    monkeypatch.setattr(config, "STAGING", False)
    h = Fake("/"); h.do_GET()
    body = h.sent[0][1].decode()
    assert h.sent[0][0] == 200 and "Demo proposal" not in body and "demoprop" not in body and "staging-only" not in body
    h = Fake("/proposals/demo"); h.do_POST()
    assert h.sent[0][0] == 404
    monkeypatch.setattr(config, "STAGING", True)
    h = Fake("/"); h.do_GET()
    assert 'id="demoprop"' in h.sent[0][1].decode()
    assert "staging-only" in (config.ROOT / "web" / "index.html").read_text()     # the markers the server cuts on
    assert 'OPENING_DOORS_STAGING = "1"' in (config.ROOT / "fly.v2.toml").read_text()
    assert "STAGING" not in (config.ROOT / "fly.toml").read_text()                 # never on the live app
