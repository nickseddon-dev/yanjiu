"""Base event types."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class EventType(Enum):
    """Event type classification."""
    SOCIAL_SURGE = "SOCIAL_SURGE"
    SENTIMENT_SHIFT = "SENTIMENT_SHIFT"
    POLYMARKET_JUMP = "POLYMARKET_JUMP"
    POLYMARKET_RESOLUTION = "POLYMARKET_RESOLUTION"
    ONCHAIN_INFLOW = "ONCHAIN_INFLOW"
    WHALE_ALERT = "WHALE_ALERT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EventSnapshot:
    """Canonical event snapshot - from dev doc Section 4.1.3."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.UNKNOWN
    source: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 24
    raw_payload: tuple = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "intensity": self.intensity,
            "decay_window_h": self.decay_window_h,
            "raw_payload": dict(self.raw_payload),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EventSnapshot":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        raw = data.get("raw_payload", {})
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=EventType(data.get("event_type", "UNKNOWN")),
            source=data.get("source", ""),
            symbol=data.get("symbol", ""),
            timestamp=ts,
            confidence=float(data.get("confidence", 0.0)),
            intensity=float(data.get("intensity", 0.0)),
            decay_window_h=int(data.get("decay_window_h", 24)),
            raw_payload=tuple(raw.items()) if isinstance(raw, dict) else tuple(),
        )


class EventABC(ABC):
    """Abstract base for all event types."""

    @abstractmethod
    def to_snapshot(self) -> EventSnapshot:
        """Convert to canonical EventSnapshot."""
        ...

    @classmethod
    @abstractmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "EventABC":
        """Reconstruct from EventSnapshot."""
        ...
