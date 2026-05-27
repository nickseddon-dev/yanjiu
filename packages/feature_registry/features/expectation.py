"""Expectation group features."""
from feature_registry.base import FeatureGroup, FeatureSpec


POLYMARKET_DELTA = FeatureSpec(
    name="polymarket_delta",
    version="1.0",
    group=FeatureGroup.EXPECTATION,
    description="Change in Polymarket probability over window",
    params=(("window_hours", 24),),
    output_dtype="float64",
    depends_on=("polymarket.probability",),
    tags=("polymarket", "expectation"),
)

PROB_JUMP_MAGNITUDE = FeatureSpec(
    name="prob_jump_magnitude",
    version="1.0",
    group=FeatureGroup.EXPECTATION,
    description="Absolute probability jump size",
    params=(("threshold", 0.1),),
    output_dtype="float64",
    depends_on=("polymarket.probability",),
    tags=("polymarket", "expectation"),
)
