"""Cost estimate types."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    """Total cost breakdown."""
    fee: float = 0.0
    slippage: float = 0.0
    impact: float = 0.0
    total: float = 0.0
    currency: str = "USDT"

    def to_dict(self) -> dict:
        return {
            "fee": self.fee,
            "slippage": self.slippage,
            "impact": self.impact,
            "total": self.total,
            "currency": self.currency,
        }
