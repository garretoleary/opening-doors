from opening_doors.desk import Desk
from tests.test_agents import fake_ask


def test_desk_runs_one_account_end_to_end(tmp_path, monkeypatch):
    from opening_doors import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    desk = Desk(ask=fake_ask, run_dir=tmp_path / "run")
    out = desk.run(["acc-01"])
    assert out["ranked"][0]["name"] == "Harrowgate Lumen" and len(out["plans"]) == 1
    assert all(out["lights"].values()) is False            # stoppable light stays off until Stop is pressed
    assert out["lights"]["registered"] and out["lights"]["permitted"] and out["lights"]["logged"]
    assert any("Writer  send email  Harrowgate Lumen  DENIED  not permitted" in l for l in out["log"])
    assert (tmp_path / "run" / "out.json").exists() and (tmp_path / "run" / "audit.jsonl").exists()
    assert out["state"]["acc-01"]["stop"] == "drafted" and len(out["drafts"]["acc-01"]) == 5
