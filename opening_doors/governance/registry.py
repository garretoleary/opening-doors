"""Question 1, Registered. Where are my agents?

A registry of every agent: identity, owner (the AE), purpose, creation time, and the token
it acts with. Nothing runs unless it is registered. Register before you restrict.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


class NotRegistered(Exception):
    """The agent is not in the registry, so it may not run."""


@dataclass
class AgentRecord:
    agent_id: str          # e.g. "agent-1"
    name: str              # e.g. "Researcher"
    owner: str             # the AE every agent acts on behalf of
    purpose: str
    created_at: str        # ISO 8601, UTC
    token: str             # the credential the agent acts with; revoked by Stop
    token_revoked: bool = False
    status: str = "waiting"   # waiting, running, done, stopped
    colour: str = ""       # Okabe-Ito hex for the page


@dataclass
class Registry:
    agents: Dict[str, AgentRecord] = field(default_factory=dict)

    def register(self, agent_id: str, name: str, owner: str, purpose: str, colour: str = "") -> AgentRecord:
        record = AgentRecord(
            agent_id=agent_id,
            name=name,
            owner=owner,
            purpose=purpose,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            token=secrets.token_urlsafe(16),
            colour=colour,
        )
        self.agents[agent_id] = record
        return record

    def get(self, agent_id: str) -> AgentRecord:
        try:
            return self.agents[agent_id]
        except KeyError:
            raise NotRegistered(f"{agent_id} is not registered") from None

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self.agents

    def as_rows(self) -> list:
        """What the page shows: identity, owner, purpose, when, status. Never the token."""
        return [
            {
                "agent_id": a.agent_id, "name": a.name, "owner": a.owner, "purpose": a.purpose,
                "created_at": a.created_at, "status": a.status, "colour": a.colour,
            }
            for a in self.agents.values()
        ]
