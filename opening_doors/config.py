"""Settings for Opening Doors. Values are estimates until the first real run is measured."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK_PATH = ROOT / "opening_doors" / "book" / "accounts.json"
CALL_NOTES_PATH = ROOT / "opening_doors" / "book" / "call_notes.json"
REPLIES_PATH = ROOT / "opening_doors" / "book" / "replies.json"
RUNS_DIR = ROOT / "runs"            # per-run audit logs and outputs, git-ignored, never edited after a run
STATE_DIR = ROOT / "state"          # the spend ledger, git-ignored, updated on every call

# The Claude model the agents use, and per-agent overrides. One line to change an agent's model.
MODEL = os.environ.get("OPENING_DOORS_MODEL", "claude-opus-5-5")
AGENT_MODELS = {
    # "agent-1": "claude-haiku-5-5",   # Researcher
    # "agent-2": "claude-haiku-5-5",   # Scorer
}
for _k, _v in os.environ.items():                 # OPENING_DOORS_MODEL_AGENT_1=claude-haiku-5-5 overrides agent-1
    if _k.startswith("OPENING_DOORS_MODEL_AGENT_"):
        AGENT_MODELS["agent-" + _k.rsplit("_", 1)[1]] = _v
EFFORT = os.environ.get("OPENING_DOORS_EFFORT", "low")   # demo runs must finish in under 3 minutes
MAX_TOKENS = 4096


def model_for(agent_id: str) -> str:
    return AGENT_MODELS.get(agent_id, MODEL)
PARALLEL_CALLS = int(os.environ.get("OPENING_DOORS_PARALLEL_CALLS", "5"))   # per-account calls at once; estimate

# Caps. Garret's API key pays. Both are estimates until measured.
SPEND_CAP_GBP = float(os.environ.get("OPENING_DOORS_SPEND_CAP_GBP", "20"))
RUNS_PER_DAY = int(os.environ.get("OPENING_DOORS_RUNS_PER_DAY", "20"))
USD_PER_GBP = 1.30                  # estimate, used only to show spend in pounds

# Price per million tokens, US dollars, from the Claude API price list 2026-10-06.
PRICES_USD_PER_MTOK = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
}
PRICE_USD_PER_MTOK = PRICES_USD_PER_MTOK[MODEL]

# The human every agent acts for. Invented, like everything else.
AE = {"id": "ae-001", "name": "The AE", "role": "Strategic Account Executive"}

# Garret's five-touch sequence. His method, set 15 October 2026, not an estimate.
# Day 1 is the day the sequence starts. After touch 5 the account rests; no sixth touch.
CADENCE_DAY = {
    1: 1,    # email, insight
    2: 5,    # email, second insight
    3: 8,    # LinkedIn connection request
    4: 11,   # call, no voicemail if unanswered, then email: the one small ask
    5: 18,   # break-up email
}

INVENTED_DATA_NOTICE = "All data invented. Every company, person, signal and number is made up."
