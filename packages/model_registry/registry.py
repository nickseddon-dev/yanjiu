"""Model registry - register, promote, archive models."""
from typing import Dict, List, Optional
from model_registry.base import ModelType, ModelSpec


class ModelRegistry:
    """Central registry for all models."""
    _models: Dict[str, ModelSpec] = {}

    @classmethod
    def register(cls, spec: ModelSpec) -> None:
        key = f"{spec.model_id}:{spec.version}"
        cls._models[key] = spec

    @classmethod
    def resolve(cls, model_id: str, version: Optional[str] = None) -> ModelSpec:
        if version:
            key = f"{model_id}:{version}"
            if key not in cls._models:
                raise KeyError(f"Model not found: {key}")
            return cls._models[key]
        matches = {k: v for k, v in cls._models.items() if v.model_id == model_id}
        if not matches:
            raise KeyError(f"No model found with id: {model_id}")
        latest = sorted(matches.keys())[-1]
        return matches[latest]

    @classmethod
    def promote(cls, model_id: str, version: str) -> ModelSpec:
        spec = cls.resolve(model_id, version)
        # Archive all other versions
        for k, v in cls._models.items():
            if v.model_id == model_id and v.status == "production":
                cls._models[k] = ModelSpec(
                    model_id=v.model_id,
                    model_type=v.model_type,
                    version=v.version,
                    features=v.features,
                    hyperparams=v.hyperparams,
                    metrics=v.metrics,
                    status="archived",
                    created_at=v.created_at,
                    description=v.description,
                )
        # Promote this one
        promoted = ModelSpec(
            model_id=spec.model_id,
            model_type=spec.model_type,
            version=spec.version,
            features=spec.features,
            hyperparams=spec.hyperparams,
            metrics=spec.metrics,
            status="production",
            created_at=spec.created_at,
            description=spec.description,
        )
        cls._models[f"{model_id}:{version}"] = promoted
        return promoted

    @classmethod
    def list_by_status(cls, status: str) -> List[ModelSpec]:
        return [m for m in cls._models.values() if m.status == status]

    @classmethod
    def clear(cls) -> None:
        cls._models.clear()
