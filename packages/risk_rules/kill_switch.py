"""Kill switch implementation - from dev doc Section 4.5.2."""
from dataclasses import dataclass, field
from risk_rules.base import RiskRuleABC, RiskDimension, RiskCheckResult, RiskVerdict


@dataclass(frozen=True)
class KillSwitch:
    """Hard kill switch - triggers halt on critical conditions."""
    triggers: tuple[tuple[str, str, float], ...] = field(default_factory=lambda: (
        ("daily_drawdown", ">", 0.05),      # 5% daily drawdown
        ("data_source_failure", ">=", 2),     # 2+ data sources down
        ("order_reject_rate", ">", 0.3),     # 30% reject rate
        ("exchange_latency_ms", ">", 2000),  # 2s+ latency
    ))

    def check(self, state: dict) -> tuple[bool, str]:
        """Returns (should_kill, reason)."""
        for metric, op, threshold in self.triggers:
            if metric not in state:
                continue
            actual = state[metric]
            # Evaluate comparison
            triggered = False
            if op == ">":
                triggered = actual > threshold
            elif op == ">=":
                triggered = actual >= threshold
            elif op == "<":
                triggered = actual < threshold
            elif op == "<=":
                triggered = actual <= threshold
            elif op == "==":
                triggered = actual == threshold
            if triggered:
                return True, f"KillSwitch: {metric} {op} {threshold} (actual={actual})"
        return False, ""

    def get_trigger_states(self, state: dict) -> list[str]:
        """List all currently triggered conditions."""
        triggered = []
        for metric, op, threshold in self.triggers:
            if metric not in state:
                continue
            actual = state[metric]
            if op == ">" and actual > threshold:
                triggered.append(f"{metric}={actual} {op} {threshold}")
            elif op == ">=" and actual >= threshold:
                triggered.append(f"{metric}={actual} {op} {threshold}")
        return triggered
