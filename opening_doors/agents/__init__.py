"""The six agents. Each acts on the AE's behalf and may only do what its permission list allows.
No agent may send. Agents 1 to 4 are built; 5 and 6 come next."""
from .base import Agent
from .planner import Planner
from .researcher import Researcher
from .scorer import Scorer
from .writer import Writer

__all__ = ["Agent", "Researcher", "Scorer", "Planner", "Writer"]
