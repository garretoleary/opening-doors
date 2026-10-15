"""Question 3, Logged. What are they doing?

A plain-English audit log, live. Fields modelled on OCSF: who (actor), what (activity),
when (time), on what (target), outcome (status). Every line is also written as JSON so
the page can replay it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .runfiles import protect_append_only


class LogTampered(Exception):
    """The log file on disk is shorter than what was written. Someone rewrote it."""


@dataclass
class Entry:
    time: str        # ISO 8601, UTC
    who: str         # agent name, "desk", or "AE"
    what: str        # the action, in plain words
    on_what: str     # the account or thing acted on, "" if none
    outcome: str     # ok, denied, stopped, error
    detail: str = ""  # one short clause, e.g. "not permitted" or "token revoked"

    def line(self) -> str:
        """One plain-English line in the order who, what, on which account, outcome."""
        parts = [self.time[11:19], self.who, self.what]
        if self.on_what:
            parts.append(self.on_what)
        outcome = self.outcome.upper() if self.outcome != "ok" else "ok"
        parts.append(outcome)
        if self.detail:
            parts.append(self.detail)
        return "  ".join(parts)

    @property
    def is_red(self) -> bool:
        """Denials and stops show in red on the page."""
        return self.outcome in ("denied", "stopped")


class AuditLog:
    def __init__(self, path: Optional[Path] = None):
        self.entries: List[Entry] = []
        self.path = path
        self.listeners: List[Callable[[Entry], None]] = []
        self._bytes_written = 0
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                raise LogTampered(f"{self.path.name} already exists; a run never reuses a log file")

    def record(self, who: str, what: str, on_what: str = "", outcome: str = "ok", detail: str = "") -> Entry:
        entry = Entry(
            time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            who=who, what=what, on_what=on_what, outcome=outcome, detail=detail,
        )
        self.entries.append(entry)
        if self.path:
            if self.path.exists() and self.path.stat().st_size < self._bytes_written:
                raise LogTampered(f"{self.path.name} is shorter than what was written")
            line = json.dumps(asdict(entry)) + "\n"
            first = not self.path.exists()
            with self.path.open("a", encoding="utf-8") as f:   # append is the only mode ever used
                f.write(line)
            self._bytes_written += len(line.encode("utf-8"))
            if first:
                protect_append_only(self.path)
        for listener in self.listeners:
            listener(entry)
        return entry

    def subscribe(self, listener: Callable[[Entry], None]) -> None:
        """The page subscribes here so the log fills live."""
        self.listeners.append(listener)

    def lines(self, last: Optional[int] = None) -> List[str]:
        entries = self.entries[-last:] if last else self.entries
        return [e.line() for e in entries]
