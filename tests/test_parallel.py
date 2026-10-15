"""The timing fix: per-account calls run a few at a time, every one through the gate, the log in time order."""
import threading
import time

import pytest

from opening_doors.desk import Desk
from opening_doors.governance import Stopped
from tests.test_agents import fake_ask


def slow_ask_factory(delay=0.05):
    """A stand-in model that takes a moment and counts how many calls are in flight at once."""
    state = {"in_flight": 0, "peak": 0, "lock": threading.Lock()}

    def slow(system, user, schema, max_tokens=0):
        with state["lock"]:
            state["in_flight"] += 1
            state["peak"] = max(state["peak"], state["in_flight"])
        time.sleep(delay)
        try:
            return fake_ask(system, user, schema, max_tokens)
        finally:
            with state["lock"]:
                state["in_flight"] -= 1
    return slow, state


def test_planner_and_writer_calls_overlap_and_results_keep_rank_order():
    slow, state = slow_ask_factory()
    desk = Desk(ask=slow)
    out = desk.run()
    assert state["peak"] > 1                                           # calls really ran side by side
    assert list(out["plans"]) == [s["id"] for s in out["ranked"][:10]]  # plans back in rank order
    assert list(out["drafts"]) == list(out["plans"])
    assert len(out["drafts"]) == 10 and all(len(t) == 5 for t in out["drafts"].values())


def test_every_parallel_call_is_logged_once_and_in_time_order():
    slow, _ = slow_ask_factory()
    desk = Desk(ask=slow)
    out = desk.run()
    entries = desk.gov.log.entries
    times = [e.time for e in entries]
    assert times == sorted(times)                                       # the log is in the order things happened
    assert sum(e.what == "account plan" and e.outcome == "ok" for e in entries) == 10
    assert sum(e.what == "drafted T1 to T5" and e.outcome == "ok" for e in entries) == 10
    assert (desk.run_dir / "audit.jsonl").read_text().count("\n") == len(entries)


def test_stop_during_parallel_writer_refuses_the_rest_and_discards_results():
    slow, _ = slow_ask_factory(delay=0.1)
    desk = Desk(ask=slow)
    desk.press_stop_when("agent-4", "Writer  read plans")
    out = desk.run()
    log = out["log"]
    assert any("Writer  STOPPED by AE" in l for l in log)
    stopped_lines = [l for l in log if "Writer  drafted T1 to T5" in l and "STOPPED" in l]
    assert len(stopped_lines) == 10                                     # every piece refused or discarded, none silently kept
    assert out["drafts"] == {} and out["schedule"] == {}
    assert any("desk  stage ended early  Writer" in l for l in log)
    assert "desk  run finished" in log[-1]


def test_a_stop_pressed_during_a_call_discards_that_call():
    from opening_doors.governance import Governor
    gov = Governor(owner="ae-001")
    rec = gov.register("agent-4", "Writer", "drafts")

    def work():
        gov.stop("agent-4")                                             # the AE presses Stop while the model is working
        return "a draft"

    with pytest.raises(Stopped):
        gov.act("agent-4", rec.token, "write_drafts", "Harrowgate Lumen", work)
    assert "token revoked during the call, result discarded" in gov.log.lines()[-1]


def test_parallel_setting_of_one_still_works(monkeypatch):
    from opening_doors import config
    monkeypatch.setattr(config, "PARALLEL_CALLS", 1)
    slow, state = slow_ask_factory(delay=0.01)
    out = Desk(ask=slow).run(["acc-01", "acc-02", "acc-03"])
    assert state["peak"] == 1 and len(out["drafts"]) == 3
