"""On-chain event types."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from event_schema.base import EventType, EventSnapshot, EventABC


@dataclass(frozen=True)
class OnchainInflowEvent(EventABC):
    """On-chain inflow event (funds flowing into exchange)."""
    event_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    inflow_amount: float = 0.0
    inflow_usd: float = 0.0
    inflow_velocity: float = 0.0
    source_chain: str = ""
    wallet_count: int = 0
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 8

    def to_snapshot(self) -> EventSnapshot:
        return EventSnapshot(
            event_id=self.event_id,
            event_type=EventType.ONCHAIN_INFLOW,
            source="ONCHAIN",
            symbol=self.symbol,
            timestamp=self.timestamp,
            confidence=self.confidence,
            intensity=self.intensity,
            decay_window_h=self.decay_window_h,
            raw_payload=tuple({
                "inflow_amount": self.inflow_amount,
                "inflow_usd": self.inflow_usd,
                "inflow_velocity": self.inflow_velocity,
                "source_chain": self.source_chain,
                "wallet_count": self.wallet_count,
            }.items()),
        )

    @classmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "OnchainInflowEvent":
        raw = dict(snapshot.raw_payload)
        return cls(
            event_id=snapshot.event_id,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            inflow_amount=float(raw.get("inflow_amount", 0.0)),
            inflow_usd=float(raw.get("inflow_usd", 0.0)),
            inflow_velocity=float(raw.get("inflow_velocity", 0.0)),
            source_chain=str(raw.get("source_chain", "")),
            wallet_count=int(raw.get("wallet_count", 0)),
            confidence=snapshot.confidence,
            intensity=snapshot.intensity,
            decay_window_h=snapshot.decay_window_h,
        )


@dataclass(frozen=True)
class WhaleAlertEvent(EventABC):
    """Large whale transfer alert."""
    event_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transaction_hash: str = ""
    from_address: str = ""
    to_address: str = ""
    amount: float = 0.0
    amount_usd: float = 0.0
    transaction_type: str = ""
    confidence: float = 0.0
    intensity: float = 0.0
    decay_window_h: int = 4

    def to_snapshot(self) -> EventSnapshot:
        return EventSnapshot(
            event_id=self.event_id,
            event_type=EventType.WHALE_ALERT,
            source="ONCHAIN",
            symbol=self.symbol,
            timestamp=self.timestamp,
            confidence=self.confidence,
            intensity=self.intensity,
            decay_window_h=self.decay_window_h,
            raw_payload=tuple({
                "transaction_hash": self.transaction_hash,
                "from_address": self.from_address,
                "to_address": self.to_address,
                "amount": self.amount,
                "amount_usd": self.amount_usd,
                "transaction_type": self.transaction_type,
            }.items()),
        )

    @classmethod
    def from_snapshot(cls, snapshot: EventSnapshot) -> "WhaleAlertEvent":
        raw = dict(snapshot.raw_payload)
        return cls(
            event_id=snapshot.event_id,
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            transaction_hash=str(raw.get("transaction_hash", "")),
            from_address=str(raw.get("from_address", "")),
            to_address=str(raw.get("to_address", "")),
            amount=float(raw.get("amount", 0.0)),
            amount_usd=float(raw.get("amount_usd", 0.0)),
            transaction_type=str(raw.get("transaction_type", "")),
            confidence=snapshot.confidence,
            intensity=snapshot.intensity,
            decay_window_h=snapshot.decay_window_h,
        )
