"""Exchange venue and order schemas."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class VenueType(Enum):
    """Venue type classification."""
    SPOT = "SPOT"
    FUTURES = "FUTURES"
    PERPETUAL = "PERPETUAL"
    OPTIONS = "OPTIONS"
    MOCK = "MOCK"


class OrderSide(Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Venue:
    """Exchange venue configuration."""
    venue_id: str
    name: str
    venue_type: VenueType
    base_url: str = ""
    is_mock: bool = False

    def to_dict(self) -> dict:
        return {
            "venue_id": self.venue_id,
            "name": self.name,
            "venue_type": self.venue_type.value,
            "base_url": self.base_url,
            "is_mock": self.is_mock,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Venue":
        return cls(
            venue_id=data["venue_id"],
            name=data["name"],
            venue_type=VenueType(data["venue_type"]),
            base_url=data.get("base_url", ""),
            is_mock=data.get("is_mock", False),
        )


@dataclass(frozen=True)
class Order:
    """Trading order."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float = 0.0
    venue_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "venue_id": self.venue_id,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        ts = data.get("created_at")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts is None:
            ts = datetime.now(timezone.utc)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            order_type=OrderType(data["order_type"]),
            quantity=float(data["quantity"]),
            price=float(data.get("price", 0.0)),
            venue_id=data.get("venue_id", ""),
            status=OrderStatus(data.get("status", "PENDING")),
            filled_quantity=float(data.get("filled_quantity", 0.0)),
            avg_fill_price=float(data.get("avg_fill_price", 0.0)),
            created_at=ts,
        )


@dataclass(frozen=True)
class ExecutionReport:
    """Order fill report."""
    order_id: str
    fill_price: float
    fill_quantity: float
    commission: float = 0.0
    slippage_bps: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "fill_price": self.fill_price,
            "fill_quantity": self.fill_quantity,
            "commission": self.commission,
            "slippage_bps": self.slippage_bps,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionReport":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts is None:
            ts = datetime.now(timezone.utc)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            order_id=data["order_id"],
            fill_price=float(data["fill_price"]),
            fill_quantity=float(data["fill_quantity"]),
            commission=float(data.get("commission", 0.0)),
            slippage_bps=float(data.get("slippage_bps", 0.0)),
            timestamp=ts,
        )
