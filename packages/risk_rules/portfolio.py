"""Portfolio-level risk rules."""
from dataclasses import dataclass
from risk_rules.base import RiskRuleABC, RiskDimension, RiskCheckResult, RiskVerdict


@dataclass(frozen=True)
class PortfolioVaRLimit(RiskRuleABC):
    """Portfolio Value-at-Risk limit."""
    max_var_pct: float = 0.02  # max 2% VaR

    @property
    def dimension(self) -> RiskDimension:
        return RiskDimension.PORTFOLIO_VAR

    def check(self, state: dict) -> RiskCheckResult:
        var_pct = state.get("portfolio_var_pct", 0.0)
        if var_pct > self.max_var_pct:
            return RiskCheckResult(
                verdict=RiskVerdict.VIOLATION,
                dimension=self.dimension,
                rule_name="PortfolioVaRLimit",
                detail=f"Portfolio VaR {var_pct:.2%} exceeds limit {self.max_var_pct:.2%}",
                threshold=self.max_var_pct,
                actual=var_pct,
            )
        return RiskCheckResult(
            verdict=RiskVerdict.PASS,
            dimension=self.dimension,
            rule_name="PortfolioVaRLimit",
        )


@dataclass(frozen=True)
class MaxDrawdownLimit(RiskRuleABC):
    """Maximum drawdown limit."""
    max_drawdown_pct: float = 0.05  # max 5% drawdown

    @property
    def dimension(self) -> RiskDimension:
        return RiskDimension.DRAWDOWN

    def check(self, state: dict) -> RiskCheckResult:
        drawdown_pct = state.get("current_drawdown_pct", 0.0)
        if drawdown_pct > self.max_drawdown_pct:
            return RiskCheckResult(
                verdict=RiskVerdict.VIOLATION,
                dimension=self.dimension,
                rule_name="MaxDrawdownLimit",
                detail=f"Drawdown {drawdown_pct:.2%} exceeds limit {self.max_drawdown_pct:.2%}",
                threshold=self.max_drawdown_pct,
                actual=drawdown_pct,
            )
        return RiskCheckResult(
            verdict=RiskVerdict.PASS,
            dimension=self.dimension,
            rule_name="MaxDrawdownLimit",
        )
