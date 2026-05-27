"""Fee models."""
from cost_models.base import CostModelABC
from cost_models.types import CostEstimate


class FixedFeeModel(CostModelABC):
    """Fixed fee per trade."""
    def __init__(self, fee_rate: float = 0.0004):  # 4bp
        self.fee_rate = fee_rate

    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        fee = quantity * price * self.fee_rate
        return CostEstimate(fee=fee, total=fee)


class TieredFeeModel(CostModelABC):
    """Tiered fee based on 30d volume."""
    def __init__(self, tiers: tuple = None):
        if tiers is None:
            tiers = (
                (50000, 0.0004),
                (100000, 0.00035),
                (500000, 0.0003),
                (1000000, 0.0002),
            )
        self.tiers = tiers  # (volume_threshold, fee_rate)

    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        # Use cumulative volume for fee tier lookup
        # For stub, use 4bp
        fee_rate = 0.0004
        fee = quantity * price * fee_rate
        return CostEstimate(fee=fee, total=fee)
