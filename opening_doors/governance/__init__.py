"""Governance layer, modelled on the Blueprint Alliance's four questions, asked in order:
registered, permitted, logged, stoppable.

Every agent action goes through Governor.act(). That one gate checks the agent is
registered, that its token is still live, that the action is on its permission list,
then runs the action and logs the outcome. There is no other way for an agent to act.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .audit import AuditLog, Entry
from .permissions import PermissionDenied, check as check_permission, permissions_for
from .registry import AgentRecord, NotRegistered, Registry
from .runfiles import RunFileLocked, is_locked, write_once
from .stop import StopSwitch, Stopped

__all__ = [
    "Governor", "Registry", "AgentRecord", "AuditLog", "Entry", "StopSwitch",
    "NotRegistered", "PermissionDenied", "Stopped", "RunFileLocked", "permissions_for",
]


class Governor:
    def __init__(self, owner: str, log_path: Optional[Path] = None):
        self.owner = owner
        self.registry = Registry()
        self.log = AuditLog(log_path)
        self.stop_switch = StopSwitch(self.registry)
        # The four lights, in order. Each comes on the first time its question is answered.
        self.lights: Dict[str, bool] = {"registered": False, "permitted": False, "logged": False, "stoppable": False}

    # Question 1
    def register(self, agent_id: str, name: str, purpose: str, colour: str = "") -> AgentRecord:
        record = self.registry.register(agent_id, name, self.owner, purpose, colour)
        self.lights["registered"] = True
        self.log.record("desk", "registered", name, "ok", f"owner {self.owner}")
        return record

    # Question 4
    def stop(self, agent_id: str) -> None:
        record = self.registry.get(agent_id)
        self.stop_switch.stop(agent_id)
        self.lights["stoppable"] = True
        self.log.record(record.name, "STOPPED by AE", "", "stopped", "token revoked")

    # The gate. Questions 1 to 4, in order, on every action.
    def act(self, agent_id: str, token: str, action: str, on_what: str, fn: Callable[[], Any],
            what: Optional[str] = None, detail_of: Optional[Callable[[Any], str]] = None) -> Any:
        """Run fn on the agent's behalf if, and only if, governance allows it.

        agent_id: who is acting. token: the credential it was issued at registration.
        action: the permission name, e.g. "read_book". on_what: the account or thing.
        what: the plain-English phrase for the log; defaults to the action with spaces.
        detail_of: optional, turns the result into a short clause for the log line.
        """
        phrase = what or action.replace("_", " ")
        record = self.registry.get(agent_id)               # Registered, or NotRegistered
        try:
            self.stop_switch.check_token(agent_id, token)   # Stoppable
        except Stopped:
            self.log.record(record.name, phrase, on_what, "stopped", "token revoked")
            raise
        try:
            check_permission(agent_id, action)              # Permitted
            self.lights["permitted"] = True
        except PermissionDenied:
            self.log.record(record.name, phrase, on_what, "denied", "not permitted")
            raise
        try:
            result = fn()
        except Exception as exc:                            # Logged, even when it fails
            self.log.record(record.name, phrase, on_what, "error", type(exc).__name__)
            raise
        detail = detail_of(result) if detail_of else ""
        self.log.record(record.name, phrase, on_what, "ok", detail)   # Logged
        self.lights["logged"] = True
        return result

    # Rule zero. The desk is not an agent and has no token, so it asks here. The answer is always no.
    def request_run_file_change(self, who: str, path: Path, change: str) -> None:
        """Any request to rewrite, edit or delete a file under runs/ is denied and logged."""
        self.log.record(who, f"{change} run file", path.name, "denied", "rule zero: run files are never changed")
        raise PermissionDenied(f"{who} may not {change} {path.name}")

    def write_run_file(self, path: Path, text: str) -> None:
        """The one way a run file is written: once, then locked."""
        write_once(path, text)

    def set_status(self, agent_id: str, status: str) -> None:
        self.registry.get(agent_id).status = status
