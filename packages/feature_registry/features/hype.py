"""Hype group features."""
from feature_registry.base import FeatureGroup, FeatureSpec


# X mention count z-score
X_MENTION_ZSCORE = FeatureSpec(
    name="x_mention_zscore",
    version="1.0",
    group=FeatureGroup.HYPE,
    description="Z-score of X mention count vs 30d rolling window",
    params=(("window_days", 30), ("min_mentions", 10)),
    output_dtype="float64",
    depends_on=("social.mention_count",),
    tags=("social", "hype", "cross-sectional"),
)

# Reddit post velocity (posts per hour)
REDDIT_POST_VELOCITY = FeatureSpec(
    name="reddit_post_velocity",
    version="1.0",
    group=FeatureGroup.HYPE,
    description="Rate of new Reddit posts per hour",
    params=(("window_hours", 6),),
    output_dtype="float64",
    depends_on=("social.post_count",),
    tags=("social", "hype"),
)
