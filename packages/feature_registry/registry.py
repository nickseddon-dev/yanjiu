"""Feature registry - registers and resolves features."""
from typing import Dict, List, Optional
from feature_registry.base import FeatureGroup, FeatureSpec


class FeatureRegistry:
    """Central registry for all features."""
    _features: Dict[str, FeatureSpec] = {}  # key: name (versioned)

    @classmethod
    def register(cls, spec: FeatureSpec) -> None:
        key = f"{spec.name}:{spec.version}"
        cls._features[key] = spec

    @classmethod
    def resolve(cls, name: str, version: Optional[str] = None) -> FeatureSpec:
        if version:
            key = f"{name}:{version}"
            if key not in cls._features:
                raise KeyError(f"Feature not found: {key}")
            return cls._features[key]
        # latest version
        matches = {k: v for k, v in cls._features.items() if v.name == name}
        if not matches:
            raise KeyError(f"No feature found with name: {name}")
        # return latest
        latest = sorted(matches.keys())[-1]
        return matches[latest]

    @classmethod
    def list_by_group(cls, group: FeatureGroup) -> List[FeatureSpec]:
        return [f for f in cls._features.values() if f.group == group]

    @classmethod
    def list_all(cls) -> List[FeatureSpec]:
        return list(cls._features.values())

    @classmethod
    def clear(cls) -> None:
        cls._features.clear()
