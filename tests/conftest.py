"""Tests lock files under their temporary folders. Unlock them afterwards so pytest can tidy up."""
import os
import stat

import pytest


@pytest.fixture(autouse=True)
def _tests_never_touch_real_runs_or_ledger(tmp_path, monkeypatch):
    """Every test writes run files and the spend ledger under its own temporary folder."""
    from opening_doors import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    yield
    for f in tmp_path.rglob("*"):
        if f.is_file():
            try:
                if hasattr(os, "chflags"):
                    os.chflags(f, 0)
                os.chmod(f, stat.S_IWUSR | stat.S_IRUSR)
            except OSError:
                pass
