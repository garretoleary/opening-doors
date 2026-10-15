"""Question 4, Stoppable. How do I respond?

A Stop per agent revokes that agent's token mid-run. The next thing the agent tries is
refused, the log records it, the agent's line goes dark, the red light shows.
"""
from __future__ import annotations

from .registry import Registry


class Stopped(Exception):
    """The agent's token was revoked by the AE. It may not continue."""


class StopSwitch:
    def __init__(self, registry: Registry):
        self.registry = registry

    def stop(self, agent_id: str) -> None:
        """The AE presses Stop. The token is revoked at once."""
        record = self.registry.get(agent_id)
        record.token_revoked = True
        record.status = "stopped"

    def is_stopped(self, agent_id: str) -> bool:
        return self.registry.get(agent_id).token_revoked

    def check_token(self, agent_id: str, token: str) -> None:
        """Raise Stopped if the token is revoked or does not match the registry."""
        record = self.registry.get(agent_id)
        if record.token_revoked or token != record.token:
            raise Stopped(f"{agent_id} token revoked")
