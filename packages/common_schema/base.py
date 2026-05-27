"""Base schema classes."""
from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic
from dataclasses import dataclass, field
import json

T = TypeVar("T")


class BaseSchema(ABC):
    """Abstract base for all schema types."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseSchema":
        """Deserialize from dictionary."""
        ...

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, data: str) -> "BaseSchema":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(data))


@dataclass(frozen=True)
class ImmutableSchema:
    """Mixin that makes dataclasses immutable and serializable."""
    pass
