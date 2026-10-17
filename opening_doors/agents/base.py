"""What every agent shares: a registration, a token, and one way to act, through the gate."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from .. import config
from ..claude import AskFn
from ..governance import Governor, Stopped
from ..rules import Rules, load as load_rules


class Agent:
    agent_id: str = ""
    name: str = ""
    purpose: str = ""
    colour: str = ""        # Okabe-Ito hex, as on the visual
    rules_key: str = ""     # rules/<rules_key>.v<N>.md holds this agent's instructions

    def __init__(self, gov: Governor, ask: AskFn, rules: Optional[Rules] = None):
        self.gov = gov
        self.ask = ask
        self.record = None
        self.rules = rules or load_rules(self.rules_key)       # RulesMissing if the file is absent

    @property
    def system_prompt(self) -> str:
        return self.rules.instructions

    def register(self) -> None:
        self.record = self.gov.register(self.agent_id, self.name, self.purpose, self.colour, rules=self.rules.label)

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

    def each_in_parallel(self, items: Iterable[Tuple[str, Callable[[], Any]]]) -> Dict[str, Any]:
        """Run one piece of work per key, a few at a time. Each piece goes through the gate on its own,
        so each is checked, refused or logged separately. If the AE stops this agent while pieces
        are running, the remaining pieces are refused by the gate and the whole stage ends as stopped."""
        items = list(items)
        results: Dict[str, Any] = {}
        stopped: Optional[Stopped] = None
        with ThreadPoolExecutor(max_workers=max(1, config.PARALLEL_CALLS)) as pool:
            futures = {key: pool.submit(fn) for key, fn in items}
            for key, fut in futures.items():
                try:
                    results[key] = fut.result()
                except Stopped as exc:
                    stopped = exc
        if stopped:
            raise stopped
        return results


INVENTED = "All data in this task is invented for a demonstration. Treat every company, person and number as fictional."
