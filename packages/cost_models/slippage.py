"""Slippage models."""
from cost_models.base import CostModelABC
from cost_models.types import CostEstimate


class LinearSlippageModel(CostModelABC):
    """Linear slippage: slippage_bps = beta * (order_value / market_volume)."""
    def __init__(self, beta: float = 0.1):
        self.beta = beta

    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        order_value = quantity * price
        # Simplified linear slippage: 1bp per 1% ADV participation
        slippage = order_value * self.beta * 0.0001
        return CostEstimate(slippage=slippage, total=slippage)


class SquareRootSlippageModel(CostModelABC):
    """Square-root slippage: more realistic for liquid markets."""
    def __init__(self, eta: float = 0.5):
        self.eta = eta

    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        order_value = quantity * price
        slippage = order_value * self.eta * 0.001  # simplified
        return CostEstimate(slippage=slippage, total=slippage)
