"""What every agent shares: a registration, a token, and one way to act, through the gate."""
from __future__ import annotations

from typing import Any, Callable, Optional

from ..claude import AskFn
from ..governance import Governor


class Agent:
    agent_id: str = ""
    name: str = ""
    purpose: str = ""
    colour: str = ""        # Okabe-Ito hex, as on the visual
    system_prompt: str = ""

    def __init__(self, gov: Governor, ask: AskFn):
        self.gov = gov
        self.ask = ask
        self.record = None

    def register(self) -> None:
        self.record = self.gov.register(self.agent_id, self.name, self.purpose, self.colour)

    @property
    def token(self) -> str:
        if self.record is None:
            raise RuntimeError(f"{self.name} is not registered")
        return self.record.token

    def act(self, action: str, on_what: str, fn: Callable[[], Any], what: Optional[str] = None,
            detail_of: Optional[Callable[[Any], str]] = None) -> Any:
        """Do one thing on the AE's behalf. Refused and logged if governance says no."""
        return self.gov.act(self.agent_id, self.token, action, on_what, fn, what, detail_of)

    def set_status(self, status: str) -> None:
        self.gov.set_status(self.agent_id, status)


INVENTED = "All data in this task is invented for a demonstration. Treat every company, person and number as fictional."
