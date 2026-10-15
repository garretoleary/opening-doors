"""The six agents. Each acts on the AE's behalf and may only do what its permission list allows.
No agent may send. Agents 1 to 3 are built; 4 to 6 come on Friday."""
from .base import Agent
from .planner import Planner
from .researcher import Researcher
from .scorer import Scorer

__all__ = ["Agent", "Researcher", "Scorer", "Planner"]
