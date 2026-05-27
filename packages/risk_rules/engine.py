"""Risk engine - runs all active rules."""
from typing import List
from risk_rules.base import RiskRuleABC, RiskCheckResult, RiskVerdict
from risk_rules.position import SingleSymbolLimit, SingleNarrativeLimit
from risk_rules.venue import VenueExposureLimit
from risk_rules.portfolio import PortfolioVaRLimit, MaxDrawdownLimit


class RiskEngine:
    """Aggregates all risk rules and evaluates portfolio state."""

    def __init__(self):
        self._rules: List[RiskRuleABC] = []

    def add_rule(self, rule: RiskRuleABC) -> None:
        self._rules.append(rule)

    def add_default_rules(self) -> None:
        self._rules.extend([
            SingleSymbolLimit(max_position_pct=0.2),
            SingleNarrativeLimit(max_narrative_pct=0.3),
            VenueExposureLimit(max_venue_pct=0.4),
            PortfolioVaRLimit(max_var_pct=0.02),
            MaxDrawdownLimit(max_drawdown_pct=0.05),
        ])

    def evaluate(self, state: dict) -> List[RiskCheckResult]:
        """Run all rules, return results."""
        results = []
        for rule in self._rules:
            results.append(rule.check(state))
        return results

    def has_violations(self, results: List[RiskCheckResult]) -> bool:
        return any(r.verdict == RiskVerdict.VIOLATION for r in results)

    def violations_only(self, results: List[RiskCheckResult]) -> List[RiskCheckResult]:
        return [r for r in results if r.verdict == RiskVerdict.VIOLATION]
