"""Risk rules base types."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class RiskDimension(Enum):
    """Risk dimension classification."""
    SINGLE_SYMBOL = "SINGLE_SYMBOL"
    SINGLE_NARRATIVE = "SINGLE_NARRATIVE"
    VENUE_EXPOSURE = "VENUE_EXPOSURE"
    PORTFOLIO_VAR = "PORTFOLIO_VAR"
    DRAWDOWN = "DRAWDOWN"
    REJECT_RATE = "REJECT_RATE"
    DATA_SOURCE = "DATA_SOURCE"
    LATENCY = "LATENCY"


class RiskVerdict(Enum):
    """Risk check verdict."""
    PASS = "PASS"
    VIOLATION = "VIOLATION"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RiskCheckResult:
    """Result of a risk rule check."""
    verdict: RiskVerdict
    dimension: RiskDimension
    rule_name: str
    detail: str = ""
    threshold: float = 0.0
    actual: float = 0.0

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "dimension": self.dimension.value,
            "rule_name": self.rule_name,
            "detail": self.detail,
            "threshold": self.threshold,
            "actual": self.actual,
        }


class RiskRuleABC(ABC):
    """Abstract base for all risk rules."""

    @property
    @abstractmethod
    def dimension(self) -> RiskDimension:
        """The risk dimension this rule checks."""
        ...

    @abstractmethod
    def check(self, state: dict) -> RiskCheckResult:
        """Evaluate rule against current state."""
        ...
