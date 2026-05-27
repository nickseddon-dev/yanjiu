"""Model registry base types."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelType(Enum):
    """Model type classification."""
    CLASSIFIER = "CLASSIFIER"
    REGRESSOR = "REGRESSOR"
    ENSEMBLE = "ENSEMBLE"


@dataclass(frozen=True)
class ModelSpec:
    """Model specification."""
    model_id: str
    model_type: ModelType
    version: str
    features: tuple[str, ...]
    hyperparams: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
    metrics: tuple[tuple[str, float], ...] = field(default_factory=tuple)  # name -> value
    status: str = "development"  # development / production / archived
    created_at: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "model_type": self.model_type.value,
            "version": self.version,
            "features": list(self.features),
            "hyperparams": dict(self.hyperparams),
            "metrics": dict(self.metrics),
            "status": self.status,
            "created_at": self.created_at,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelSpec":
        return cls(
            model_id=data["model_id"],
            model_type=ModelType(data["model_type"]),
            version=data["version"],
            features=tuple(data.get("features", [])),
            hyperparams=tuple((k, v) for k, v in data.get("hyperparams", {}).items()),
            metrics=tuple((k, v) for k, v in data.get("metrics", {}).items()),
            status=data.get("status", "development"),
            created_at=data.get("created_at", ""),
            description=data.get("description", ""),
        )
