"""Question 2, Permitted. What can they do?

A permission list per agent, enforced in code. A denied call is refused and logged.
No agent may send. The AE reviews and sends.
"""
from __future__ import annotations

from typing import Dict, FrozenSet


class PermissionDenied(Exception):
    """The agent asked to do something its permission list does not allow."""


# Actions that no agent may ever take. Listed so the denial is explicit, not an accident.
NEVER_PERMITTED: FrozenSet[str] = frozenset({"send_email", "send_linkedin", "send", "place_call"})

PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "agent-1": frozenset({"read_book", "read_signals"}),                       # Researcher
    "agent-2": frozenset({"read_research", "write_scores"}),                   # Scorer
    "agent-3": frozenset({"read_scores", "write_plans"}),                      # Planner
    "agent-4": frozenset({"read_plans", "write_drafts"}),                      # Writer: not read_book, not send
    "agent-5": frozenset({"read_drafts", "write_schedule", "write_log"}),      # Cadence: not send
    "agent-6": frozenset({"read_call_notes", "write_qualification",           # Qualifier
                          "write_value_frame", "write_mutual_plan"}),
}


def is_permitted(agent_id: str, action: str) -> bool:
    if action in NEVER_PERMITTED:
        return False
    return action in PERMISSIONS.get(agent_id, frozenset())


def check(agent_id: str, action: str) -> None:
    """Raise PermissionDenied unless the action is on the agent's list."""
    if not is_permitted(agent_id, action):
        raise PermissionDenied(f"{agent_id} may not {action}")


def permissions_for(agent_id: str) -> list:
    return sorted(PERMISSIONS.get(agent_id, frozenset()))
