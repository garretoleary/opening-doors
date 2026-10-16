"""The book says where each account stands and how it answers, so every run depicts the same book a few weeks in."""
from opening_doors.book import journey
from opening_doors.desk import Desk
from tests.test_agents import fake_ask


def test_journey_is_invented_data():
    j = journey()
    assert j and all(v["days_in"] >= 0 for v in j.values())
    assert all(v["at_touch"] is None or 1 <= v["at_touch"] <= 4 for v in j.values())
    assert j["acc-10"] == {"days_in": 10, "at_touch": 1, "committee": True}


def test_a_full_run_depicts_a_book_in_progress_repeatably():
    counts = []
    for _ in range(2):
        out = Desk(ask=fake_ask).run()
        zones = {z: sum(1 for v in out["state"].values() if v["zone"] == z) for z in (4, 3, 2, 1)}
        counts.append(zones)
        log = "\n".join(out["log"])
        assert "Cadence  reply received, invented" in log
        assert "awaiting reply" in log                                            # some wait at T3 or T4
        assert "resting, no sixth touch" in log or "resting after T5" in log       # some rest
        assert "desk  book position, invented" in log                              # earlier waves, outside the top ten
        assert "desk  buying committee accepted the ask, invented" in log
        assert sum(zones.values()) == 25
        assert zones[2] + zones[1] == len(out["qualified"])
    assert counts[0] == counts[1]                                                  # same book, same picture
    # with the stand-in Scorer the top ten are acc-01 to acc-10, so Morrowick (acc-19) sits outside them and
    # waits at First call instead of being qualified; the real Scorer ranks it in, giving 11, 7, 4, 3
    assert counts[0] == {4: 11, 3: 8, 2: 3, 1: 3}


def test_positions_awaiting_resting_and_handing_off():
    out = Desk(ask=fake_ask).run(["acc-04", "acc-10", "acc-12", "acc-16"])
    s = out["state"]
    assert s["acc-04"]["stop"] == "resting after T5" and s["acc-04"]["zone"] == 3        # day 20, never replied
    assert s["acc-10"]["stop"] == "Buying committee" and s["acc-10"]["zone"] == 1        # replied at T1, committee in
    assert s["acc-12"]["stop"] == "T3 given, awaiting reply" and s["acc-12"]["zone"] == 3  # day 9
    assert s["acc-16"]["stop"] == "T4 given, awaiting reply" and s["acc-16"]["zone"] == 3  # day 12
    assert "acc-10" in out["qualified"] and len(out["qualified"]) == 1


def test_untouched_accounts_stay_in_zone_four():
    out = Desk(ask=fake_ask).run(["acc-05", "acc-09"])
    assert all(v["zone"] == 4 for v in out["state"].values())
    assert "awaiting reply" not in "\n".join(out["log"]) or "T1 given" in "\n".join(out["log"])


def test_committee_line_follows_each_mutual_plan_at_once():
    out = Desk(ask=fake_ask).run()
    log = out["log"]
    for i, line in enumerate(log):
        if "Qualifier  mutual plan drafted" in line and " ok" in line:
            name = line.split("mutual plan drafted  ")[1].split("  ok")[0]
            pid = next(k for k, v in out["state"].items() if v["name"] == name)
            if out["state"][pid]["zone"] == 1:                   # the book says the committee is in
                assert "buying committee accepted the ask, invented  " + name in log[i + 1], name
    assert sum("buying committee accepted" in l for l in log) == 3
