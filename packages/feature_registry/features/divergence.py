"""Divergence group features."""
from feature_registry.base import FeatureGroup, FeatureSpec


BULL_BEAR_RATIO = FeatureSpec(
    name="bull_bear_ratio",
    version="1.0",
    group=FeatureGroup.DIVERGENCE,
    description="Ratio of bullish comments to bearish comments",
    params=(),
    output_dtype="float64",
    depends_on=("social.comment_sentiments",),
    tags=("social", "divergence"),
)

NEUTRAL_RATIO = FeatureSpec(
    name="neutral_ratio",
    version="1.0",
    group=FeatureGroup.DIVERGENCE,
    description="Fraction of neutral (sentiment near 0) comments",
    params=(("threshold", 0.1),),
    output_dtype="float64",
    depends_on=("social.comment_sentiments",),
    tags=("social", "divergence"),
)
