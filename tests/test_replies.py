"""Invented replies are data in the book, so every run moves the same accounts the same way."""
from opening_doors.book import replies
from opening_doors.desk import Desk
from tests.test_agents import fake_ask


def test_replies_are_invented_data_at_touches_one_to_four():
    r = replies()
    assert r and all(1 <= v["at_touch"] <= 4 for v in r.values())
    assert r["acc-10"] == {"at_touch": 1, "committee": True}


def test_a_full_run_moves_accounts_through_the_zones_repeatably():
    counts = []
    for _ in range(2):
        out = Desk(ask=fake_ask).run()
        zones = {z: sum(1 for v in out["state"].values() if v["zone"] == z) for z in (4, 3, 2, 1)}
        counts.append(zones)
        log = "\n".join(out["log"])
        assert "Cadence  reply received, invented" in log
        assert "resting, no sixth touch" in log
        assert "desk  buying committee accepted the ask, invented" in log
        assert sum(zones.values()) == 25 and zones[4] >= 15                 # the 15 not in the top ten never move
        assert zones[2] + zones[1] == len(out["qualified"])
    assert counts[0] == counts[1]                                           # same book, same moves


def test_non_repliers_rest_and_repliers_hand_off():
    out = Desk(ask=fake_ask).run(["acc-04", "acc-10"])
    s = out["state"]
    assert s["acc-04"]["stop"] == "resting after T5" and s["acc-04"]["zone"] == 3
    assert s["acc-10"]["stop"] == "Buying committee" and s["acc-10"]["zone"] == 1
    assert "acc-10" in out["qualified"] and "acc-04" not in out["qualified"]
