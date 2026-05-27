"""Position limit rules."""
from dataclasses import dataclass
from risk_rules.base import RiskRuleABC, RiskDimension, RiskCheckResult, RiskVerdict


@dataclass(frozen=True)
class SingleSymbolLimit(RiskRuleABC):
    """Single symbol position limit."""
    max_position_pct: float = 0.2  # max 20% of portfolio in single symbol

    @property
    def dimension(self) -> RiskDimension:
        return RiskDimension.SINGLE_SYMBOL

    def check(self, state: dict) -> RiskCheckResult:
        positions = state.get("positions", {})
        for symbol, pos in positions.items():
            mkt_val = pos.get("market_value", 0.0)
            total_val = state.get("total_value", 1.0)
            if total_val <= 0:
                continue
            pct = abs(mkt_val / total_val)
            if pct > self.max_position_pct:
                return RiskCheckResult(
                    verdict=RiskVerdict.VIOLATION,
                    dimension=self.dimension,
                    rule_name="SingleSymbolLimit",
                    detail=f"{symbol} position {pct:.2%} exceeds limit {self.max_position_pct:.2%}",
                    threshold=self.max_position_pct,
                    actual=pct,
                )
        return RiskCheckResult(
            verdict=RiskVerdict.PASS,
            dimension=self.dimension,
            rule_name="SingleSymbolLimit",
        )


@dataclass(frozen=True)
class SingleNarrativeLimit(RiskRuleABC):
    """Single narrative/event narrative max exposure."""
    max_narrative_pct: float = 0.3  # max 30% in single narrative

    @property
    def dimension(self) -> RiskDimension:
        return RiskDimension.SINGLE_NARRATIVE

    def check(self, state: dict) -> RiskCheckResult:
        narratives = state.get("narrative_exposure", {})  # narrative -> usd_value
        total_val = state.get("total_value", 1.0)
        if total_val <= 0:
            return RiskCheckResult(
                verdict=RiskVerdict.PASS,
                dimension=self.dimension,
                rule_name="SingleNarrativeLimit",
            )
        for narrative, value in narratives.items():
            pct = abs(value / total_val)
            if pct > self.max_narrative_pct:
                return RiskCheckResult(
                    verdict=RiskVerdict.VIOLATION,
                    dimension=self.dimension,
                    rule_name="SingleNarrativeLimit",
                    detail=f"Narrative {narrative} exposure {pct:.2%} exceeds limit",
                    threshold=self.max_narrative_pct,
                    actual=pct,
                )
        return RiskCheckResult(
            verdict=RiskVerdict.PASS,
            dimension=self.dimension,
            rule_name="SingleNarrativeLimit",
        )
