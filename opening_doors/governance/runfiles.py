"""Rule zero. The audit log is append-only. No file under runs/ is ever edited after a run.

Two layers. The operating system: every file a run writes gets the append-only flag, so a
rewrite, delete or rename fails even for the owner. The governance gate: any request to change
a run file, from an agent or the desk, is denied and logged. A run's record is what happened.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


class RunFileLocked(PermissionError):
    """Something tried to rewrite, delete or rename a file under runs/."""


def protect_append_only(path: Path) -> bool:
    """Mark a file append-only at the operating-system level. Returns True if the flag was set."""
    if hasattr(os, "chflags") and hasattr(stat, "UF_APPEND"):
        os.chflags(path, stat.UF_APPEND)
        return True
    return False


def write_once(path: Path, text: str) -> None:
    """Write a run file exactly once, then lock it: read-only and append-only flagged."""
    if path.exists():
        raise RunFileLocked(f"{path.name} already exists; run files are written once")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o444)
    protect_append_only(path)


def is_locked(path: Path) -> bool:
    """True if the file cannot be rewritten by a normal write."""
    try:
        with path.open("r+"):
            return False
    except PermissionError:
        return True
