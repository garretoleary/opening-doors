"""Agents 1 to 3 run against a stand-in for the model, so no key is needed here."""
import pytest

from opening_doors.agents import Planner, Researcher, Scorer
from opening_doors.book import load_book
from opening_doors.claude import Spend, SpendCapReached
from opening_doors.governance import Governor, NotRegistered, PermissionDenied


def fake_ask(system, user, schema, max_tokens=0):
    """Returns the shape each agent asks for, with made-up words."""
    import json
    props = schema["properties"]
    if "notes" in props:
        ids = [a["id"] for a in json.loads(user.split("as JSON:\n", 1)[1])]
        return {"notes": [{"id": i, "strongest_signal": "s", "why_now": "w", "identity_gap": "g", "likely_buyer": "b"} for i in ids]}
    if "scores" in props:
        ids = [n["id"] for n in json.loads(user.split("as JSON:\n", 1)[1])]
        return {"scores": [{"id": i, "score": 100 - k, "why_selected": "why", "how_found": "how"} for k, i in enumerate(ids)]}
    if "mutual_plan" in props:
        name = user.split("Account: ", 1)[1].split(".", 1)[0]
        q = {k: f"{k} for {name}" for k in ("metrics", "economic_buyer", "decision_criteria", "decision_process",
                                           "paper_process", "identified_pain", "champion", "competition", "gaps")}
        return {"qualification": q,
                "value_frame": {"problem_identified": "p", "value_defined": "v", "value_sized": "£1 estimate", "how_value_is_realised": "h"},
                "mutual_plan": {"goal": "g", "steps": [{"who": "You", "what": "w", "by": "2026-11-01"}, {"who": "I", "what": "x", "by": "2026-11-02"}],
                                "the_ask": f"Bring the boss and the buying committee at {name}."}}
    if "touches" in props:
        plan = json.loads(user.split("as JSON:\n", 1)[1])
        return {"touches": [{"touch": n, "kind": "", "subject": "" if n == 3 else f"T{n} for {plan['name']}",
                             "body": f"T{n} body about {plan['signal']} at {plan['name']}", "matched_to": plan["signal"]}
                            for n in (1, 2, 3, 4, 5)]}
    return {"business_problem": "p", "economic_buyer": "e", "first_meeting_point_of_view": "v", "one_metric_to_agree": "m"}


def desk():
    gov = Governor(owner="ae-001")
    r, s, p = Researcher(gov, fake_ask), Scorer(gov, fake_ask), Planner(gov, fake_ask)
    for a in (r, s, p):
        a.register()
    return gov, r, s, p, load_book()


def test_researcher_reads_book_and_signals_and_returns_25_notes():
    gov, r, _, _, book = desk()
    notes = r.run(book)
    assert len(notes) == 25 and notes[0]["name"] == "Harrowgate Lumen"
    lines = gov.log.lines()
    assert any("Researcher  read book  25 accounts  ok" in l for l in lines)
    assert any("Researcher  read signals  25 accounts  ok" in l for l in lines)
    assert gov.registry.get("agent-1").status == "done"


def test_researcher_may_not_write_or_send():
    gov, r, _, _, _ = desk()
    for action in ("write_scores", "write_plans", "send_email"):
        with pytest.raises(PermissionDenied):
            r.act(action, "Harrowgate Lumen", lambda: 1)
    denied = [e for e in gov.log.entries if e.outcome == "denied"]
    assert len(denied) == 3 and all(e.is_red for e in denied)


def test_scorer_ranks_25_with_reason_and_source():
    gov, r, s, _, book = desk()
    ranked = s.run(r.run(book), book["icp"])
    assert [x["rank"] for x in ranked] == list(range(1, 26))
    assert all(x["why_selected"] and x["how_found"] for x in ranked)
    assert any("Scorer  ranked 25  ok  top: Harrowgate Lumen" in l for l in gov.log.lines())


def test_scorer_may_not_read_the_raw_book():
    gov, _, s, _, _ = desk()
    with pytest.raises(PermissionDenied):
        s.act("read_book", "", lambda: 1)
    assert gov.log.entries[-1].outcome == "denied"


def test_planner_writes_ten_plans_only():
    gov, r, s, p, book = desk()
    notes = r.run(book)
    plans = p.run(s.run(notes, book["icp"]), notes, book)
    assert len(plans) == 10
    assert all(v["business_problem"] and v["one_metric_to_agree"] for v in plans.values())
    assert sum("Planner  account plan" in l and l.endswith("ok") for l in gov.log.lines()) == 10


def test_planner_may_not_send_and_denial_is_logged_not_skipped():
    gov, _, _, p, _ = desk()
    ran = []
    with pytest.raises(PermissionDenied):
        p.act("send", "Harrowgate Lumen", lambda: ran.append(1))
    assert ran == []
    assert "Planner  send  Harrowgate Lumen  DENIED  not permitted" in gov.log.lines()[-1]


def test_unregistered_agent_cannot_act():
    gov = Governor(owner="ae-001")
    r = Researcher(gov, fake_ask)
    with pytest.raises(NotRegistered):
        r.run(load_book())


def test_spend_counts_pounds_and_stops_at_cap(tmp_path, monkeypatch):
    from opening_doors import config
    spend = Spend(ledger_path=tmp_path / "spend.json")
    spend.start_run()
    spend.add(1_000_000, 0)                       # one million input tokens
    assert round(spend.gbp_this_run, 2) == round(4.00 / config.USD_PER_GBP, 2)
    monkeypatch.setattr(config, "SPEND_CAP_GBP", 1.0)
    with pytest.raises(SpendCapReached):
        spend.start_run()
