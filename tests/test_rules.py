"""Rules as versioned files: read before a run, logged, kept locked with the run, never written by an agent."""
import os
from pathlib import Path

import pytest

from opening_doors import rules
from opening_doors.agents import Cadence, Planner, Qualifier, Researcher, Scorer, Writer
from opening_doors.desk import Desk
from opening_doors.governance import Governor, PermissionDenied
from opening_doors.governance.runfiles import is_locked
from tests.test_agents import fake_ask


def test_six_rules_files_exist_with_instructions_and_a_changelog():
    all_rules = rules.load_all()
    assert list(all_rules) == ["researcher", "scorer", "planner", "writer", "cadence", "qualifier"]
    for r in all_rules.values():
        assert r.version == 1 and r.path.name == f"{r.key}.v1.md"
        assert r.instructions and "invented" in r.instructions.lower()
        assert "## Changelog" in r.text and "- v1, " in r.text


def test_agents_take_their_instructions_from_the_rules_file():
    gov = Governor(owner="ae-001")
    for cls in (Researcher, Scorer, Planner, Writer, Qualifier):
        a = cls(gov, fake_ask)
        assert a.system_prompt == rules.load(cls.rules_key).instructions
        assert not hasattr(cls, "__dict__") or "system_prompt" not in cls.__dict__      # nothing left in code


def test_the_current_version_is_the_highest_number(tmp_path):
    for n in (1, 3, 2):
        (tmp_path / f"scorer.v{n}.md").write_text(f"# Scorer v{n}\n\n## Instructions\nversion {n}\n\n## Changelog\n- v{n}\n")
    r = rules.load("scorer", tmp_path)
    assert r.version == 3 and r.instructions == "version 3"


def test_a_run_refuses_to_start_if_a_rules_file_is_missing(tmp_path, monkeypatch):
    for f in rules.RULES_DIR.iterdir():
        if f.name != "writer.v1.md":
            (tmp_path / f.name).write_text(f.read_text())
    monkeypatch.setattr(rules, "RULES_DIR", tmp_path)
    with pytest.raises(rules.RulesMissing, match="writer"):
        Desk(ask=fake_ask)                                        # nothing registered, nothing logged, nothing spent


def test_the_audit_line_names_the_rules_version_used():
    desk = Desk(ask=fake_ask)
    out = desk.run(["acc-04"])
    lines = out["log"]
    for name, key in (("Researcher", "researcher"), ("Scorer", "scorer"), ("Planner", "planner"),
                      ("Writer", "writer"), ("Cadence", "cadence"), ("Qualifier", "qualifier")):
        assert any(f"desk  registered  {name}  ok  owner ae-001, rules {key}.v1" in l for l in lines), name
    assert out["rules"] == {k: f"{k}.v1" for k in rules.AGENT_KEYS}


def test_rules_copies_under_runs_are_locked_rule_zero_unchanged():
    desk = Desk(ask=fake_ask)
    desk.run(["acc-04"])
    kept = sorted((desk.run_dir / "rules").iterdir())
    assert [p.name for p in kept] == sorted(f"{k}.v1.md" for k in rules.AGENT_KEYS)
    for p in kept:
        assert p.read_text() == (rules.RULES_DIR / p.name).read_text()
        assert is_locked(p)
        with pytest.raises(PermissionError):
            p.open("w")
        with pytest.raises(PermissionError):
            os.remove(p)
    assert is_locked(desk.run_dir / "audit.jsonl")               # the log is as it was


def test_no_agent_may_write_edit_or_delete_rules():
    gov = Governor(owner="ae-001")
    agents = [cls(gov, fake_ask) for cls in (Researcher, Scorer, Planner, Writer, Cadence, Qualifier)]
    for a in agents:
        a.register()
    for a in agents:
        for action in ("write_rules", "edit_rules", "delete_rules"):
            with pytest.raises(PermissionDenied):
                a.act(action, "researcher.v2.md", lambda: 1)
            e = gov.log.entries[-1]
            assert e.who == a.name and e.outcome == "denied" and e.is_red
    from opening_doors.governance.permissions import PERMISSIONS
    assert not any(p in ("write_rules", "edit_rules", "delete_rules") for perms in PERMISSIONS.values() for p in perms)
    assert not any(p.startswith(("write_", "edit_", "delete_")) and "rules" in p for perms in PERMISSIONS.values() for p in perms)


def test_the_registry_is_the_only_source_of_permissions_rules_files_are_display_copies(tmp_path, monkeypatch):
    """A rules file that claims the Writer may send changes nothing: the gate asks the governance registry only."""
    for f in rules.RULES_DIR.iterdir():
        text = f.read_text()
        if f.name == "writer.v1.md":
            text = text.replace("## Permitted\n", "## Permitted\nsend_email, read_book, write_rules\n").replace("## Not permitted\n", "## Not permitted\nnothing\n")
        (tmp_path / f.name).write_text(text)
    monkeypatch.setattr(rules, "RULES_DIR", tmp_path)
    r = rules.load("writer")
    assert "send_email" in r.text                                 # the file says so
    assert not hasattr(r, "permissions") and not hasattr(r, "permitted")   # the loader exposes no such thing
    gov = Governor(owner="ae-001")
    w = Writer(gov, fake_ask, r); w.register()
    for action in ("send_email", "read_book", "write_rules"):
        with pytest.raises(PermissionDenied):                     # the registry still says no
            w.act(action, "Harrowgate Lumen", lambda: 1)
        assert gov.log.entries[-1].outcome == "denied"
    w.act("write_drafts", "Harrowgate Lumen", lambda: 1)           # and still yes to what the registry allows
    assert gov.log.entries[-1].outcome == "ok"


def test_rules_live_on_the_data_volume_and_survive_a_simulated_redeploy(tmp_path, monkeypatch):
    """The image copy is the seed, read once onto an empty volume. Approve and Roll back write only the volume copy.
    A redeploy (new image, same volume) keeps writer.v2 and v3."""
    from opening_doors import proposals
    from tests.test_proposals import write_proposal
    volume = tmp_path / "data" / "rules"                                   # empty, as on a first start
    monkeypatch.setattr(rules, "RULES_DIR", volume)
    assert rules.RULES_DIR != rules.SEED_RULES_DIR
    copied = rules.seed_if_absent()
    assert sorted(p.name for p in copied) == sorted(p.name for p in rules.SEED_RULES_DIR.iterdir() if p.name.endswith(".md"))
    assert rules.load("writer").version == 1 and rules.load("writer").path.parent == volume
    write_proposal("20261017T120000", "NR-2026-10-17-01")
    assert proposals.approve("NR-2026-10-17-01")["rules_written"][0]["label"] == "writer.v2"
    assert proposals.rollback("NR-2026-10-17-01")["ok"]
    assert sorted(p.name for p in volume.glob("writer.*")) == ["writer.v1.md", "writer.v2.md", "writer.v3.md"]
    assert not (rules.SEED_RULES_DIR / "writer.v2.md").exists()           # the image copy is untouched
    # a redeploy: the code (and its seed) arrive fresh, the volume stays; nothing is overwritten
    assert rules.seed_if_absent() == []
    assert rules.load("writer").version == 3 and sorted(p.name for p in volume.glob("writer.*")) == ["writer.v1.md", "writer.v2.md", "writer.v3.md"]
    assert rules.load_all()["writer"].label == "writer.v3"
    # tamper check: a seed file with the same name is never copied over a volume file
    (volume / "scorer.v1.md").write_text((volume / "scorer.v1.md").read_text() + "\n- kept\n")
    rules.seed_if_absent()
    assert (volume / "scorer.v1.md").read_text().endswith("- kept\n")
