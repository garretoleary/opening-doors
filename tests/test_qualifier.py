"""Agent 6 Qualifier: call notes in; MEDDPICC-lite, value frame and mutual plan out; raw book never seen; nothing sent."""
import pytest

from opening_doors.agents import Qualifier
from opening_doors.book import call_notes
from opening_doors.desk import Desk
from opening_doors.governance import Governor, PermissionDenied
from tests.test_agents import fake_ask


def qualifier_after_reply():
    desk = Desk(ask=fake_ask)
    out = desk.run(["acc-01", "acc-04"])          # Harrowgate Lumen replies at T3; Brackwater Foods never replies, day 20
    return desk, out


def test_reply_reaches_qualifier_and_produces_three_things():
    desk, out = qualifier_after_reply()
    assert list(out["qualified"]) == ["acc-01"]
    q = out["qualified"]["acc-01"]
    assert q["replied_at"] == "T3"
    assert set(q["qualification"]) >= {"metrics", "economic_buyer", "champion", "gaps"}
    assert q["value_frame"]["value_sized"]
    assert q["mutual_plan"]["steps"] and "committee" in q["mutual_plan"]["the_ask"].lower()
    assert out["state"]["acc-01"]["stop"] == "Buying committee" and out["state"]["acc-01"]["zone"] == 1
    assert out["state"]["acc-04"]["stop"] == "resting after T5" and out["state"]["acc-04"]["zone"] == 3
    lines = desk.gov.log.lines()
    for phrase in ("Qualifier  read call notes  Harrowgate Lumen  ok", "Qualifier  qualified, MEDDPICC-lite  Harrowgate Lumen  ok",
                   "Qualifier  value framed  Harrowgate Lumen  ok", "Qualifier  mutual plan drafted  Harrowgate Lumen  ok"):
        assert any(phrase in l for l in lines), phrase


def test_no_reply_means_no_qualifier_work():
    desk = Desk(ask=fake_ask)
    out = desk.run(["acc-04"])
    assert out["qualified"] == {}
    assert not any("Qualifier  read call notes" in l for l in desk.gov.log.lines())


def test_qualifier_denied_raw_book_plans_drafts_scores_logged():
    gov = Governor(owner="ae-001")
    q = Qualifier(gov, fake_ask); q.register()
    for action in ("read_book", "read_signals", "read_plans", "read_drafts", "read_scores", "read_research"):
        with pytest.raises(PermissionDenied):
            q.act(action, "Harrowgate Lumen", lambda: 1)
        e = gov.log.entries[-1]
        assert e.who == "Qualifier" and e.outcome == "denied" and e.is_red
    assert "Qualifier  read book  Harrowgate Lumen  DENIED  not permitted" in gov.log.lines()[-6]


def test_qualifier_denied_send_logged_and_nothing_runs():
    gov = Governor(owner="ae-001")
    q = Qualifier(gov, fake_ask); q.register()
    ran = []
    for action in ("send_email", "send_linkedin", "send", "place_call"):
        with pytest.raises(PermissionDenied):
            q.act(action, "Harrowgate Lumen", lambda: ran.append(1))
    assert ran == []
    assert all(e.outcome == "denied" for e in gov.log.entries[-4:])
    assert "Qualifier  send email  Harrowgate Lumen  DENIED  not permitted" in gov.log.lines()[-4]


def test_qualifier_is_handed_the_call_note_only():
    seen = []
    def spy(system, user, schema, max_tokens=0):
        seen.append(user); return fake_ask(system, user, schema, max_tokens)
    gov = Governor(owner="ae-001")
    q = Qualifier(gov, spy); q.register()
    q.run([{"account_id": "acc-01", "name": "Harrowgate Lumen", "replied_at": "T2", "to": "agent-6", "stage": "First call"}], call_notes())
    assert len(seen) == 1 and "First-call note, invented" in seen[0]
    for book_only in ("access_setup_today", '"signals"', '"employees"', "business_problem", "touches"):
        assert book_only not in seen[0]


def test_technical_lead_line_is_refused_and_logged():
    def bad(system, user, schema, max_tokens=0):
        r = fake_ask(system, user, schema, max_tokens)
        r["qualification"]["champion"] = "Technical lead: someone"
        return r
    gov = Governor(owner="ae-001")
    q = Qualifier(gov, bad); q.register()
    with pytest.raises(ValueError):
        q.run([{"account_id": "acc-01", "name": "Harrowgate Lumen", "replied_at": "T1", "to": "agent-6", "stage": "First call"}], call_notes())
    assert gov.log.entries[-1].outcome == "error"


def test_call_notes_are_invented_and_separate_from_the_book():
    notes = call_notes()
    assert len(notes) == 25 and all(notes.values())
