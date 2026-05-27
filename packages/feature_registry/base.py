"""Feature registry base types."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeatureGroup(Enum):
    """Feature group classification."""
    HYPE = "HYPE"           # X mentions, velocity, z-score
    SENTIMENT = "SENTIMENT" # sentiment mean, polarity skew
    DIVERGENCE = "DIVERGENCE" # bull/bear ratio, neutral ratio
    DIFFUSION = "DIFFUSION"  # cross-platform speed, peak heat time
    EXPECTATION = "EXPECTATION" # Polymarket delta, prob jump


@dataclass(frozen=True)
class FeatureSpec:
    """"Feature specification."""
    name: str
    version: str
    group: FeatureGroup
    description: str
    params: tuple[tuple[str, Any], ...] = field(default_factory=tuple)  # frozen dict
    output_dtype: str = "float64"
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "group": self.group.value,
            "description": self.description,
            "params": dict(self.params),
            "output_dtype": self.output_dtype,
            "depends_on": list(self.depends_on),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FeatureSpec":
        return cls(
            name=data["name"],
            version=data["version"],
            group=FeatureGroup(data["group"]),
            description=data.get("description", ""),
            params=tuple((k, v) for k, v in data.get("params", {}).items()),
            output_dtype=data.get("output_dtype", "float64"),
            depends_on=tuple(data.get("depends_on", [])),
            tags=tuple(data.get("tags", [])),
        )
