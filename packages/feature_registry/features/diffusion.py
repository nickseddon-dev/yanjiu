"""Diffusion group features."""
from feature_registry.base import FeatureGroup, FeatureSpec


CROSS_PLATFORM_SPEED = FeatureSpec(
    name="cross_platform_speed",
    version="1.0",
    group=FeatureGroup.DIFFUSION,
    description="Speed of topic propagation across X and Reddit",
    params=(("platforms", ["X", "REDDIT"]),),
    output_dtype="float64",
    depends_on=("social.mention_count",),
    tags=("social", "diffusion"),
)

PEAK_HEAT_TIME = FeatureSpec(
    name="peak_heat_time",
    version="1.0",
    group=FeatureGroup.DIFFUSION,
    description="Hours since topic reached peak mention velocity",
    params=(),
    output_dtype="float64",
    depends_on=("social.mention_velocity",),
    tags=("social", "diffusion"),
)
