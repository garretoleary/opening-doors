"""Question 4, Stoppable: Stop mid-run revokes the token, the log records it, the next call is refused and logged."""
from opening_doors.desk import Desk
from tests.test_agents import fake_ask


def test_stop_on_writer_mid_run():
    desk = Desk(ask=fake_ask)
    desk.press_stop_when("agent-4", "Writer  read plans")       # the AE presses Stop as the Writer starts
    out = desk.run(["acc-01", "acc-02"])
    lines = out["log"]
    i = next(k for k, l in enumerate(lines) if "Writer  read plans" in l)
    assert "Writer  STOPPED by AE  STOPPED  token revoked" in lines[i + 1]
    after = "\n".join(lines[i + 2:])
    assert "Writer  drafted T1 to T5  Harrowgate Lumen  STOPPED  token revoked" in after    # the next call, refused
    assert "Writer  drafted T1 to T5  Veldstone Marine  STOPPED  token revoked" in after
    assert "desk  stage ended early  Writer  ok  stopped by AE, run continues" in after
    assert out["lights"]["stoppable"] is True
    assert out["stopped"] == ["agent-4"]
    assert next(a for a in out["agents"] if a["agent_id"] == "agent-4")["status"] == "stopped"
    assert out["drafts"] == {} and out["schedule"] == {}                 # nothing downstream of the Writer
    assert len(out["plans"]) == 2                                         # everything before it stands
    assert lines[-1].startswith(lines[-1][:8]) and "desk  run finished" in lines[-1]
    assert any("Planner  send email" in l and "DENIED" in l for l in lines)   # the send check still runs


def test_stop_before_any_call_refuses_everything_from_that_agent():
    desk = Desk(ask=fake_ask)
    desk.press_stop_when("agent-1", "registered  Qualifier")      # pressed right after registration
    out = desk.run(["acc-01"])
    assert "Researcher  read book  1 accounts  STOPPED  token revoked" in "\n".join(out["log"])
    assert out["notes"] == [] and out["ranked"] == [] and out["plans"] == {}
    assert "desk  run finished" in out["log"][-1]


def test_stop_is_recorded_and_the_rest_of_the_desk_keeps_going():
    desk = Desk(ask=fake_ask)
    desk.press_stop_when("agent-5", "Cadence  read drafts")
    out = desk.run(["acc-01"], simulate_reply={"acc-01": 2})
    log = "\n".join(out["log"])
    assert "Cadence  STOPPED by AE" in log
    assert "Cadence  scheduled T1 to T5  Harrowgate Lumen  STOPPED  token revoked" in log
    assert out["qualified"] == {}                                         # no hand-off ever happened
    assert len(out["drafts"]["acc-01"]) == 5                              # the Writer's work stands
    assert "desk  run finished" in out["log"][-1]


def test_stop_button_can_be_pressed_by_anyone_at_any_time():
    desk = Desk(ask=fake_ask)
    for a in desk.agents:
        a.register()
    desk.stop("agent-2")
    assert desk.gov.registry.get("agent-2").token_revoked and desk.gov.lights["stoppable"]
    assert "Scorer  STOPPED by AE  STOPPED  token revoked" in desk.gov.log.lines()[-1]
