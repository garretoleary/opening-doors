"""Agent 5 Cadence: the five-touch schedule, the rest rule, the no-repeat rule, the reply hand-off, no sending."""
from datetime import date

import pytest

from opening_doors.agents import Cadence, Planner, Researcher, Scorer, Writer
from opening_doors.book import load_book
from opening_doors.governance import Governor, PermissionDenied, RuleDenied
from tests.test_agents import fake_ask

START = date(2026, 10, 16)


def desk_with_cadence():
    gov = Governor(owner="ae-001")
    agents = [Researcher(gov, fake_ask), Scorer(gov, fake_ask), Planner(gov, fake_ask), Writer(gov, fake_ask), Cadence(gov, fake_ask)]
    for a in agents:
        a.register()
    r, s, p, w, c = agents
    book = load_book()
    notes = r.run(book)
    plans = p.run(s.run(notes, book["icp"]), notes, book)
    drafts = w.run(plans)
    c.run(drafts, {pid: pl["name"] for pid, pl in plans.items()}, start=START)
    return gov, c


def last_line(gov):
    return gov.log.lines()[-1]


def test_schedule_has_five_dated_touches_per_account():
    gov, c = desk_with_cadence()
    assert len(c.schedule) == 10
    s = c.schedule["acc-01"]
    assert s["stage"] == "T1" and s["next_touch"] == 1
    assert [t["touch"] for t in s["touches"]] == [1, 2, 3, 4, 5]
    assert [t["day"] for t in s["touches"]] == [1, 5, 8, 11, 18]       # Garret's sequence
    assert [t["due"] for t in s["touches"]] == ["2026-10-16", "2026-10-20", "2026-10-23", "2026-10-26", "2026-11-02"]
    assert s["touches"][3]["kind"] == "call, no voicemail, then email"
    assert [t["due"] for t in s["touches"]] == sorted(t["due"] for t in s["touches"])
    assert sum("Cadence  scheduled T1 to T5" in l for l in gov.log.lines()) == 10


def test_rest_rule_after_t5_no_sixth_touch_ever():
    gov, c = desk_with_cadence()
    for n in (1, 2, 3, 4, 5):
        c.given_by_ae("acc-01", n)
        c.no_reply("acc-01")
    assert c.schedule["acc-01"]["stage"] == "resting" and c.schedule["acc-01"]["next_touch"] is None
    assert last_line(gov).endswith("Cadence  no reply  Harrowgate Lumen  ok  resting, no sixth touch")
    with pytest.raises(RuleDenied):
        c.given_by_ae("acc-01", 6)
    assert "Cadence  T6 given  Harrowgate Lumen  DENIED  rest rule" in last_line(gov)
    with pytest.raises(RuleDenied):
        c.given_by_ae("acc-01", 1)
    assert "DENIED  rest rule" in last_line(gov)
    with pytest.raises(RuleDenied):
        c.no_reply("acc-01")
    assert "DENIED  rest rule" in last_line(gov)


def test_no_repeat_rule_same_touch_and_same_wording():
    gov, c = desk_with_cadence()
    c.given_by_ae("acc-01", 1)
    with pytest.raises(RuleDenied):
        c.given_by_ae("acc-01", 1)
    assert "Cadence  T1 given  Harrowgate Lumen  DENIED  no repeat: T1 already given" in last_line(gov)
    # same wording, different slot: refused too
    c.no_reply("acc-01")
    c.schedule["acc-01"]["touches"][1]["body_hash"] = c.schedule["acc-01"]["touches"][0]["body_hash"]
    with pytest.raises(RuleDenied):
        c.given_by_ae("acc-01", 2)
    assert "DENIED  no repeat: this wording was already given" in last_line(gov)


def test_out_of_sequence_is_refused_and_logged():
    gov, c = desk_with_cadence()
    with pytest.raises(RuleDenied):
        c.given_by_ae("acc-01", 3)
    assert "Cadence  T3 given  Harrowgate Lumen  DENIED  out of sequence: next is T1" in last_line(gov)


def test_reply_at_any_touch_hands_off_to_qualifier():
    gov, c = desk_with_cadence()
    c.given_by_ae("acc-01", 1); c.no_reply("acc-01")
    c.given_by_ae("acc-01", 2); c.no_reply("acc-01")
    c.given_by_ae("acc-01", 3)
    handoff = c.reply("acc-01", 3)
    assert handoff == {"account_id": "acc-01", "name": "Harrowgate Lumen", "replied_at": "T3", "to": "agent-6", "stage": "First call"}
    assert c.handoffs == [handoff]
    s = c.schedule["acc-01"]
    assert s["stage"] == "first_call" and s["next_touch"] is None
    assert [t["status"] for t in s["touches"]] == ["given", "given", "given", "cancelled, replied", "cancelled, replied"]
    assert last_line(gov).endswith("Cadence  reply received, invented  Harrowgate Lumen  ok  at T3, to Qualifier, First call")
    with pytest.raises(RuleDenied):                        # no further touches after a reply
        c.given_by_ae("acc-01", 4)
    assert "DENIED  account already replied" in last_line(gov)


def test_reply_at_t5_still_hands_off_and_reply_needs_a_given_touch():
    gov, c = desk_with_cadence()
    for n in (1, 2, 3, 4):
        c.given_by_ae("acc-02", n); c.no_reply("acc-02")
    c.given_by_ae("acc-02", 5)
    assert c.reply("acc-02", 5)["replied_at"] == "T5"
    with pytest.raises(RuleDenied):
        c.reply("acc-03", 2)
    assert "DENIED  T2 was not given" in last_line(gov)


def test_cadence_may_not_send_and_denial_is_logged():
    gov, c = desk_with_cadence()
    ran = []
    for action in ("send_email", "send_linkedin", "send", "place_call"):
        with pytest.raises(PermissionDenied):
            c.act(action, "Harrowgate Lumen", lambda: ran.append(1))
        e = gov.log.entries[-1]
        assert e.who == "Cadence" and e.outcome == "denied" and e.is_red
    assert ran == []
    assert "Cadence  send email  Harrowgate Lumen  DENIED  not permitted" in gov.log.lines()[-4]


def test_cadence_may_not_read_book_plans_or_scores():
    gov, c = desk_with_cadence()
    for action in ("read_book", "read_signals", "read_plans", "read_scores"):
        with pytest.raises(PermissionDenied):
            c.act(action, "", lambda: 1)
        assert gov.log.entries[-1].outcome == "denied"


def test_every_cadence_denial_is_in_the_log_never_skipped():
    gov, c = desk_with_cadence()
    before = len(gov.log.entries)
    attempts = 0
    for fn in (lambda: c.given_by_ae("acc-01", 2), lambda: c.no_reply("acc-01"), lambda: c.reply("acc-01", 1),
               lambda: c.act("send_email", "x", lambda: 1)):
        attempts += 1
        with pytest.raises((RuleDenied, PermissionDenied)):
            fn()
    denied = [e for e in gov.log.entries[before:] if e.outcome == "denied"]
    assert len(denied) == attempts
