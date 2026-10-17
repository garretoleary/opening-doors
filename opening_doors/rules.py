"""Rules as versioned files. Each agent's instructions live in rules/<agent>.v<N>.md, never in code.

A run reads the current version (the highest N) for every agent before it starts, logs the version
it used, and keeps a locked copy of each file it used under the run's folder. No agent may write
to rules: the permission does not exist and the attempt is refused and logged like any other.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from . import config

AGENT_KEYS = ["researcher", "scorer", "planner", "writer", "cadence", "qualifier"]
RULES_DIR = config.ROOT / "rules"
_NAME = re.compile(r"^(?P<key>[a-z_]+)\.v(?P<n>\d+)\.md$")


class RulesMissing(Exception):
    """A rules file is missing. A run refuses to start without all six."""


@dataclass(frozen=True)
class Rules:
    key: str
    version: int
    path: Path
    text: str            # the whole file
    instructions: str    # the Instructions section, what the agent is told

    @property
    def label(self) -> str:
        return f"{self.key}.v{self.version}"


def current_path(key: str, rules_dir: Optional[Path] = None) -> Optional[Path]:
    """The highest-numbered rules file for an agent, or None."""
    rules_dir = rules_dir or RULES_DIR                 # resolved now, so a test can point elsewhere
    best, best_n = None, -1
    if rules_dir.exists():
        for p in rules_dir.iterdir():
            m = _NAME.match(p.name)
            if m and m.group("key") == key and int(m.group("n")) > best_n:
                best, best_n = p, int(m.group("n"))
    return best


def load(key: str, rules_dir: Optional[Path] = None) -> Rules:
    rules_dir = rules_dir or RULES_DIR
    path = current_path(key, rules_dir)
    if path is None:
        raise RulesMissing(f"no rules file for {key} under {rules_dir}")
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## Instructions\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m or not m.group(1).strip():
        raise RulesMissing(f"{path.name} has no Instructions section")
    n = int(_NAME.match(path.name).group("n"))
    return Rules(key=key, version=n, path=path, text=text, instructions=m.group(1).strip())


def load_all(rules_dir: Optional[Path] = None) -> Dict[str, Rules]:
    """All six, or RulesMissing naming the first one absent. Called before a run starts."""
    rules_dir = rules_dir or RULES_DIR
    out = {}
    for key in AGENT_KEYS:
        out[key] = load(key, rules_dir)
    return out


def keep_copies(rules: Dict[str, Rules], run_dir: Path) -> List[Path]:
    """Write a locked copy of every rules file the run used under runs/<id>/rules/. Rule zero applies."""
    from .governance.runfiles import write_once
    kept = []
    for r in rules.values():
        dest = run_dir / "rules" / r.path.name
        write_once(dest, r.text)
        kept.append(dest)
    return kept
