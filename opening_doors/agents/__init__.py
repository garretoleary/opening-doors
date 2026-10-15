"""The six agents. Each acts on the AE's behalf and may only do what its permission list allows.
No agent may send. Agents 1 to 5 are built; 6 comes next."""
from .base import Agent
from .planner import Planner
from .researcher import Researcher
from .scorer import Scorer
from .writer import Writer
from .cadence import Cadence

__all__ = ["Agent", "Researcher", "Scorer", "Planner", "Writer", "Cadence"]
