"""Settings for Opening Doors. Values are estimates until the first real run is measured."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK_PATH = ROOT / "opening_doors" / "book" / "accounts.json"
RUNS_DIR = ROOT / "runs"            # per-run audit logs and outputs, git-ignored

# The Claude model every agent uses. One model, one cache namespace.
MODEL = os.environ.get("OPENING_DOORS_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("OPENING_DOORS_EFFORT", "low")   # demo runs must finish in under 3 minutes
MAX_TOKENS = 4096

# Caps. Garret's API key pays. Both are estimates until measured.
SPEND_CAP_GBP = float(os.environ.get("OPENING_DOORS_SPEND_CAP_GBP", "20"))
RUNS_PER_DAY = int(os.environ.get("OPENING_DOORS_RUNS_PER_DAY", "20"))
USD_PER_GBP = 1.30                  # estimate, used only to show spend in pounds

# Price per million tokens for MODEL, US dollars, taken from the Claude API price list 2026-10-06.
PRICE_USD_PER_MTOK = {"input": 4.00, "output": 20.00}

# The human every agent acts for. Invented, like everything else.
AE = {"id": "ae-001", "name": "The AE", "role": "Strategic Account Executive"}

INVENTED_DATA_NOTICE = "All data invented. Every company, person, signal and number is made up."
