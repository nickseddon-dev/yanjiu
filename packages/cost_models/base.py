"""Cost model base."""
from abc import ABC, abstractmethod
from cost_models.types import CostEstimate


class CostModelABC(ABC):
    """Abstract base for cost models."""

    @abstractmethod
    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        """"Estimate cost for a given order."""
        ...
