"""Market impact models."""
from cost_models.base import CostModelABC
from cost_models.types import CostEstimate


class LinearImpactModel(CostModelABC):
    """Linear market impact: impact = gamma * order_value / ADV."""
    def __init__(self, gamma: float = 0.1):
        self.gamma = gamma

    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        # If pre-computed market_impact is passed, use it
        if market_impact > 0:
            return CostEstimate(impact=market_impact, total=market_impact)
        # Otherwise estimate
        order_value = quantity * price
        impact = order_value * self.gamma * 0.0001
        return CostEstimate(impact=impact, total=impact)
