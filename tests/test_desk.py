from opening_doors.desk import Desk
from tests.test_agents import fake_ask


def test_desk_runs_one_account_end_to_end(tmp_path, monkeypatch):
    from opening_doors import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    desk = Desk(ask=fake_ask, run_dir=tmp_path / "run")
    out = desk.run(["acc-01"])
    assert out["ranked"][0]["name"] == "Harrowgate Lumen" and len(out["plans"]) == 1
    assert all(out["lights"].values())                     # all four on, in order, as the run starts; Stop is armed
    assert any("Writer  send email  Harrowgate Lumen  DENIED  not permitted" in l for l in out["log"])
    assert (tmp_path / "run" / "out.json").exists() and (tmp_path / "run" / "audit.jsonl").exists()
    assert out["state"]["acc-01"]["stop"] == "Buying committee" and len(out["drafts"]["acc-01"]) == 5   # replies at T3, accepts the ask
    assert len(out["schedule"]["acc-01"]["touches"]) == 5
