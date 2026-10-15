"""Agent 4 Writer: plans in, five touches out, raw book never seen, nothing sent."""
import pytest

from opening_doors.agents import Planner, Researcher, Scorer, Writer
from opening_doors.book import load_book
from opening_doors.governance import Governor, PermissionDenied
from tests.test_agents import fake_ask


def desk_with_plans(ask=fake_ask):
    gov = Governor(owner="ae-001")
    r, s, p, w = Researcher(gov, ask), Scorer(gov, ask), Planner(gov, ask), Writer(gov, ask)
    for a in (r, s, p, w):
        a.register()
    book = load_book()
    notes = r.run(book)
    plans = p.run(s.run(notes, book["icp"]), notes, book)
    return gov, w, plans


def test_writer_drafts_five_touches_for_each_of_the_top_ten():
    gov, w, plans = desk_with_plans()
    drafts = w.run(plans)
    assert len(drafts) == 10
    kinds = ["insight email", "insight email", "LinkedIn connection note", "email or call script", "break-up email"]
    for pid, touches in drafts.items():
        assert [t["touch"] for t in touches] == [1, 2, 3, 4, 5]
        assert [t["kind"] for t in touches] == kinds
        assert touches[2]["subject"] == ""                       # a LinkedIn note has no subject
        assert all(t["matched_to"] for t in touches)
    assert sum("Writer  drafted T1 to T5" in l and l.endswith("ok") for l in gov.log.lines()) == 10
    assert gov.registry.get("agent-4").status == "done"


def test_touches_are_not_a_template_across_accounts():
    _, w, plans = desk_with_plans()
    drafts = w.run(plans)
    bodies = [t["body"] for touches in drafts.values() for t in touches]
    assert len(set(bodies)) == len(bodies)                      # no body repeats across accounts or touches


def test_writer_is_handed_plans_only_never_the_book():
    seen = []

    def spy(system, user, schema, max_tokens=0):
        seen.append(user)
        return fake_ask(system, user, schema, max_tokens)

    gov, w, plans = desk_with_plans(spy)
    seen.clear()
    w.run(plans)
    assert len(seen) == 10
    for user in seen:
        for book_only in ("access_setup_today", '"people"', '"signals"', '"employees"', '"hq"', '"sector"'):
            assert book_only not in user


def test_writer_denied_raw_book_and_signals_logged():
    gov, w, _ = desk_with_plans()
    for action in ("read_book", "read_signals", "read_research", "read_scores"):
        with pytest.raises(PermissionDenied):
            w.act(action, "", lambda: 1)
        last = gov.log.entries[-1]
        assert last.who == "Writer" and last.outcome == "denied" and last.is_red
    assert "Writer  read book  DENIED  not permitted" in gov.log.lines()[-4]


def test_writer_denied_send_logged_and_nothing_runs():
    gov, w, _ = desk_with_plans()
    ran = []
    for action in ("send_email", "send_linkedin", "send", "place_call"):
        with pytest.raises(PermissionDenied):
            w.act(action, "Harrowgate Lumen", lambda: ran.append(1))
    assert ran == []
    denied = [e for e in gov.log.entries[-4:]]
    assert all(e.outcome == "denied" and e.who == "Writer" for e in denied)
    assert "Writer  send email  Harrowgate Lumen  DENIED  not permitted" in gov.log.lines()[-4]


def test_writer_rejects_wrong_touch_count():
    def bad(system, user, schema, max_tokens=0):
        return {"touches": [{"touch": 1, "kind": "", "subject": "s", "body": "b", "matched_to": "m"}]}
    gov, w, plans = desk_with_plans()
    w.ask = bad
    with pytest.raises(ValueError):
        w.run(plans)
    assert gov.log.entries[-1].outcome == "error"
