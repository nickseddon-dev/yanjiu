"""Prediction market event types."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from event_schema.base import EventType, EventSnapshot, EventABC


@dataclass(frozen=True)
class PolymarketJumpEvent(EventABC):
    """Polymarket probability jump event."""
    event_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    market_question: str = ""
    prior_probability: float = 0.0
    current_probability: float = 0.0
    probability_delta: float = 0.0
    volume: float = 0.0
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 12

    def to_snapshot(self) -> EventSnapshot:
        return EventSnapshot(
            event_id=self.event_id,
            event_type=EventType.POLYMARKET_JUMP,
            source="POLYMARKET",
            symbol=self.symbol,
            timestamp=self.timestamp,
            confidence=self.confidence,
            intensity=self.intensity,
            decay_window_h=self.decay_window_h,
            raw_payload=tuple({
                "market_question": self.market_question,
                "prior_probability": self.prior_probability,
                "current_probability": self.current_probability,
                "probability_delta": self.probability_delta,
                "volume": self.volume,
            }.items()),
        )

    @classmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "PolymarketJumpEvent":
        raw = dict(snapshot.raw_payload)
        return cls(
            event_id=snapshot.event_id,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            market_question=str(raw.get("market_question", "")),
            prior_probability=float(raw.get("prior_probability", 0.0)),
            current_probability=float(raw.get("current_probability", 0.0)),
            probability_delta=float(raw.get("probability_delta", 0.0)),
            volume=float(raw.get("volume", 0.0)),
            confidence=snapshot.confidence,
            intensity=snapshot.intensity,
            decay_window_h=snapshot.decay_window_h,
        )


@dataclass(frozen=True)
class PolymarketResolutionEvent(EventABC):
    """Polymarket market resolution event."""
    event_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    market_question: str = ""
    outcome: str = ""
    resolution_price: float = 0.0
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 1

    def to_snapshot(self) -> EventSnapshot:
        return EventSnapshot(
            event_id=self.event_id,
            event_type=EventType.POLYMARKET_RESOLUTION,
            source="POLYMARKET",
            symbol=self.symbol,
            timestamp=self.timestamp,
            confidence=self.confidence,
            intensity=self.intensity,
            decay_window_h=self.decay_window_h,
            raw_payload=tuple({
                "market_question": self.market_question,
                "outcome": self.outcome,
                "resolution_price": self.resolution_price,
            }.items()),
        )

    @classmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "PolymarketResolutionEvent":
        raw = dict(snapshot.raw_payload)
        return cls(
            event_id=snapshot.event_id,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            market_question=str(raw.get("market_question", "")),
            outcome=str(raw.get("outcome", "")),
            resolution_price=float(raw.get("resolution_price", 0.0)),
            confidence=snapshot.confidence,
            intensity=snapshot.intensity,
            decay_window_h=snapshot.decay_window_h,
        )
