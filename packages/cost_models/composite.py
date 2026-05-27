"""Composite cost model - combines all cost components."""
from cost_models.base import CostModelABC
from cost_models.types import CostEstimate
from cost_models.slippage import LinearSlippageModel
from cost_models.fee import FixedFeeModel
from cost_models.impact import LinearImpactModel


class CompositeCostModel(CostModelABC):
    """Combines fee + slippage + market impact into total cost."""

    def __init__(
        self,
        fee_model: CostModelABC = None,
        slippage_model: CostModelABC = None,
        impact_model: CostModelABC = None,
    ):
        self.fee_model = fee_model or FixedFeeModel()
        self.slippage_model = slippage_model or LinearSlippageModel()
        self.impact_model = impact_model or LinearImpactModel()

    def estimate_cost(
        self,
        side: str,
        quantity: float,
        price: float,
        market_impact: float = 0.0,
    ) -> CostEstimate:
        fee_est = self.fee_model.estimate_cost(side, quantity, price, market_impact)
        slip_est = self.slippage_model.estimate_cost(side, quantity, price, market_impact)
        imp_est = self.impact_model.estimate_cost(side, quantity, price, market_impact)

        total = fee_est.fee + slip_est.slippage + imp_est.impact
        return CostEstimate(
            fee=fee_est.fee,
            slippage=slip_est.slippage,
            impact=imp_est.impact,
            total=total,
            currency=fee_est.currency,
        )
