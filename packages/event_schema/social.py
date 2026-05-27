"""Social media event types."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from event_schema.base import EventType, EventSnapshot, EventABC


@dataclass(frozen=True)
class SocialSurgeEvent(EventABC):
    """Social media surge event (X/Reddit mention spike)."""
    event_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    mention_count: int = 0
    mention_velocity: float = 0.0
    z_score: float = 0.0
    top_keywords: tuple = field(default_factory=tuple)
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 6

    def to_snapshot(self) -> EventSnapshot:
        return EventSnapshot(
            event_id=self.event_id,
            event_type=EventType.SOCIAL_SURGE,
            source=self.source,
            symbol=self.symbol,
            timestamp=self.timestamp,
            confidence=self.confidence,
            intensity=self.intensity,
            decay_window_h=self.decay_window_h,
            raw_payload=tuple({
                "mention_count": self.mention_count,
                "mention_velocity": self.mention_velocity,
                "z_score": self.z_score,
                "top_keywords": list(self.top_keywords),
            }.items()),
        )

    @classmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "SocialSurgeEvent":
        raw = dict(snapshot.raw_payload)
        return cls(
            event_id=snapshot.event_id,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            source=snapshot.source,
            mention_count=int(raw.get("mention_count", 0)),
            mention_velocity=float(raw.get("mention_velocity", 0.0)),
            z_score=float(raw.get("z_score", 0.0)),
            top_keywords=tuple(raw.get("top_keywords", [])),
            confidence=snapshot.confidence,
            intensity=snapshot.intensity,
            decay_window_h=snapshot.decay_window_h,
        )


@dataclass(frozen=True)
class SentimentShiftEvent(EventABC):
    """Sentiment shift event (positive/negative sentiment change)."""
    event_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    sentiment_mean: float = 0.0
    sentiment_delta: float = 0.0
    polarity_skew: float = 0.0
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 4

    def to_snapshot(self) -> EventSnapshot:
        return EventSnapshot(
            event_id=self.event_id,
            event_type=EventType.SENTIMENT_SHIFT,
            source=self.source,
            symbol=self.symbol,
            timestamp=self.timestamp,
            confidence=self.confidence,
            intensity=self.intensity,
            decay_window_h=self.decay_window_h,
            raw_payload=tuple({
                "sentiment_mean": self.sentiment_mean,
                "sentiment_delta": self.sentiment_delta,
                "polarity_skew": self.polarity_skew,
            }.items()),
        )

    @classmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "SentimentShiftEvent":
        raw = dict(snapshot.raw_payload)
        return cls(
            event_id=snapshot.event_id,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            source=snapshot.source,
            sentiment_mean=float(raw.get("sentiment_mean", 0.0)),
            sentiment_delta=float(raw.get("sentiment_delta", 0.0)),
            polarity_skew=float(raw.get("polarity_skew", 0.0)),
            confidence=snapshot.confidence,
            intensity=snapshot.intensity,
            decay_window_h=snapshot.decay_window_h,
        )
