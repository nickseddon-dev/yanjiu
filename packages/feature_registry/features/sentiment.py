"""Sentiment group features."""
from feature_registry.base import FeatureGroup, FeatureSpec


SENTIMENT_MEAN = FeatureSpec(
    name="sentiment_mean",
    version="1.0",
    group=FeatureGroup.SENTIMENT,
    description="Mean sentiment score (-1 to 1) across posts",
    params=(("source", "X"),),
    output_dtype="float64",
    depends_on=("social.sentiment_scores",),
    tags=("social", "sentiment"),
)

POLARITY_SKEW = FeatureSpec(
    name="polarity_skew",
    version="1.0",
    group=FeatureGroup.SENTIMENT,
    description="Skewness of sentiment distribution toward pos/neg",
    params=(),
    output_dtype="float64",
    depends_on=("social.sentiment_scores",),
    tags=("social", "sentiment"),
)

SENTIMENT_VELOCITY = FeatureSpec(
    name="sentiment_velocity",
    version="1.0",
    group=FeatureGroup.SENTIMENT,
    description="Rate of sentiment change per hour",
    params=(("window_hours", 2),),
    output_dtype="float64",
    depends_on=("social.sentiment_scores",),
    tags=("social", "sentiment"),
)
