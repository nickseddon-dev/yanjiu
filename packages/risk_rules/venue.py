"""Venue exposure limit rule."""
from dataclasses import dataclass
from risk_rules.base import RiskRuleABC, RiskDimension, RiskCheckResult, RiskVerdict


@dataclass(frozen=True)
class VenueExposureLimit(RiskRuleABC):
    """Single venue max exposure."""
    max_venue_pct: float = 0.4  # max 40% in single venue

    @property
    def dimension(self) -> RiskDimension:
        return RiskDimension.VENUE_EXPOSURE

    def check(self, state: dict) -> RiskCheckResult:
        venue_exposure = state.get("venue_exposure", {})  # venue_id -> usd_value
        total_val = state.get("total_value", 1.0)
        if total_val <= 0:
            return RiskCheckResult(
                verdict=RiskVerdict.PASS,
                dimension=self.dimension,
                rule_name="VenueExposureLimit",
            )
        for venue_id, value in venue_exposure.items():
            pct = abs(value / total_val)
            if pct > self.max_venue_pct:
                return RiskCheckResult(
                    verdict=RiskVerdict.VIOLATION,
                    dimension=self.dimension,
                    rule_name="VenueExposureLimit",
                    detail=f"Venue {venue_id} exposure {pct:.2%} exceeds limit",
                    threshold=self.max_venue_pct,
                    actual=pct,
                )
        return RiskCheckResult(
            verdict=RiskVerdict.PASS,
            dimension=self.dimension,
            rule_name="VenueExposureLimit",
        )
