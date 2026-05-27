"""Signal and execution schemas."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
import pydantic
import uuid


class SignalStatus(Enum):
    """Signal lifecycle status."""
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class EntryDecision(Enum):
    """Pre-trade gate decision."""
    NO_TRADE = "NO_TRADE"
    SMALL_TEST = "SMALL_TEST"
    PARTIAL_ENTER = "PARTIAL_ENTER"
    FULL_ENTER = "FULL_ENTER"


class SignalStrength(Enum):
    """Signal strength classification."""
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


@dataclass(frozen=True)
class Signal:
    """Trading signal - published by research host to execution host."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    symbol: str = ""
    side: str = ""  # BUY or SELL
    signal_strength: float = 0.0  # 0.0 to 1.0
    target_position_pct: float = 0.0
    entry_mode: EntryDecision = EntryDecision.NO_TRADE
    max_slippage_bps: int = 8
    ttl_seconds: int = 900
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    risk_tags: tuple[str, ...] = field(default_factory=tuple)
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "side": self.side,
            "signal_strength": self.signal_strength,
            "target_position_pct": self.target_position_pct,
            "entry_mode": self.entry_mode.value,
            "max_slippage_bps": self.max_slippage_bps,
            "ttl_seconds": self.ttl_seconds,
            "created_at": self.created_at.isoformat(),
            "risk_tags": list(self.risk_tags),
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        ts = data["created_at"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            signal_id=data.get("signal_id", str(uuid.uuid4())),
            strategy_id=data.get("strategy_id", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            signal_strength=float(data.get("signal_strength", 0.0)),
            target_position_pct=float(data.get("target_position_pct", 0.0)),
            entry_mode=EntryDecision(data.get("entry_mode", "NO_TRADE")),
            max_slippage_bps=int(data.get("max_slippage_bps", 8)),
            ttl_seconds=int(data.get("ttl_seconds", 900)),
            created_at=ts,
            risk_tags=tuple(data.get("risk_tags", [])),
            signature=data.get("signature", ""),
        )


@dataclass(frozen=True)
class SignalAck:
    """Acknowledgment from execution host back to research host."""
    signal_id: str
    status: SignalStatus
    message: str = ""
    executed_price: float = 0.0
    executed_quantity: float = 0.0
    rejected_reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "status": self.status.value,
            "message": self.message,
            "executed_price": self.executed_price,
            "executed_quantity": self.executed_quantity,
            "rejected_reason": self.rejected_reason,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SignalAck":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts is None:
            ts = datetime.now(timezone.utc)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            signal_id=data["signal_id"],
            status=SignalStatus(data["status"]),
            message=data.get("message", ""),
            executed_price=float(data.get("executed_price", 0.0)),
            executed_quantity=float(data.get("executed_quantity", 0.0)),
            rejected_reason=data.get("rejected_reason", ""),
            timestamp=ts,
        )
