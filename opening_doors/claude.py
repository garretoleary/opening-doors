"""The one place Opening Doors calls the Claude API.

Every agent asks through ask_json(): one model, structured JSON back, usage counted
against the spend cap. Agents never hold a client of their own.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import config

AskFn = Callable[[str, str, Dict[str, Any], int], Dict[str, Any]]


class SpendCapReached(Exception):
    """The monthly cap or the daily run limit is hit. The page shows the video instead."""


@dataclass
class Spend:
    """Counts tokens and pounds for this run and keeps a small ledger across runs."""
    ledger_path: Optional[Path] = None
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    usd: float = 0.0
    ledger: Dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.ledger_path and self.ledger_path.exists():
            self.ledger = json.loads(self.ledger_path.read_text())
        self.ledger.setdefault("month", date.today().strftime("%Y-%m"))
        self.ledger.setdefault("gbp_this_month", 0.0)
        self.ledger.setdefault("runs", {})
        if self.ledger["month"] != date.today().strftime("%Y-%m"):
            self.ledger = {"month": date.today().strftime("%Y-%m"), "gbp_this_month": 0.0, "runs": {}}

    @property
    def gbp_this_run(self) -> float:
        return self.usd / config.USD_PER_GBP

    def start_run(self) -> None:
        today = date.today().isoformat()
        runs_today = self.ledger["runs"].get(today, 0)
        if runs_today >= config.RUNS_PER_DAY:
            raise SpendCapReached(f"limit reached: {runs_today} runs today")
        if self.ledger["gbp_this_month"] >= config.SPEND_CAP_GBP:
            raise SpendCapReached(f"limit reached: £{self.ledger['gbp_this_month']:.2f} this month")
        self.ledger["runs"][today] = runs_today + 1
        self._save()

    def add(self, input_tokens: int, output_tokens: int, model: str = config.MODEL) -> None:
        price = config.PRICES_USD_PER_MTOK.get(model, config.PRICE_USD_PER_MTOK)
        with self._lock:
            before = self.gbp_this_run
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.usd += (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
            self.calls += 1
            self.ledger["gbp_this_month"] += self.gbp_this_run - before
            self._save()
            over = self.ledger["gbp_this_month"] >= config.SPEND_CAP_GBP
        if over:
            raise SpendCapReached(f"limit reached: £{self.ledger['gbp_this_month']:.2f} this month")

    def _save(self) -> None:
        if self.ledger_path:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            self.ledger_path.write_text(json.dumps(self.ledger, indent=2))


def make_ask(spend: Spend, model: str = config.MODEL) -> AskFn:
    """Build the real ask function for one model. Imports the SDK here so tests need no key."""
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(config.ROOT / ".env")
    client = anthropic.Anthropic()
    # A declined request retries on a backup model, where the API offers that (not for Haiku).
    extra = {} if model.startswith("claude-haiku") else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    def ask_json(system: str, user: str, schema: Dict[str, Any], max_tokens: int = config.MAX_TOKENS) -> Dict[str, Any]:
        response = client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": config.EFFORT, "format": {"type": "json_schema", "schema": schema}},
            **extra,
        )
        spend.add(response.usage.input_tokens, response.usage.output_tokens, model)
        if response.stop_reason == "refusal":
            raise RuntimeError("the model declined this request")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("the answer was cut off; raise max_tokens")
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)

    return ask_json
