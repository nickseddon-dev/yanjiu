"""Portfolio schemas."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ImmutableDict


@dataclass(frozen=True)
class Position:
    """Single symbol position."""
    symbol: str
    quantity: float
    avg_entry_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(
            symbol=data["symbol"],
            quantity=float(data["quantity"]),
            avg_entry_price=float(data["avg_entry_price"]),
            market_value=float(data["market_value"]),
            unrealized_pnl=float(data["unrealized_pnl"]),
            realized_pnl=float(data["realized_pnl"]),
        )


@dataclass(frozen=True)
class PortfolioState:
    """Portfolio state at a point in time."""
    total_value: float
    cash: float
    positions: tuple[tuple[str, Position], ...]  # Immutable dict as tuples
    total_unrealized_pnl: float
    total_realized_pnl: float
    leverage: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "total_value": self.total_value,
            "cash": self.cash,
            "positions": {k: v.to_dict() for k, v in dict(self.positions)},
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "leverage": self.leverage,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PortfolioState":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts is None:
            ts = datetime.now(timezone.utc)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        positions = tuple(
            (k, Position.from_dict(v)) for k, v in data.get("positions", {}).items()
        )
        return cls(
            total_value=float(data["total_value"]),
            cash=float(data["cash"]),
            positions=positions,
            total_unrealized_pnl=float(data.get("total_unrealized_pnl", 0.0)),
            total_realized_pnl=float(data.get("total_realized_pnl", 0.0)),
            leverage=float(data.get("leverage", 1.0)),
            timestamp=ts,
        )


@dataclass(frozen=True)
class RiskBudget:
    """Risk budget limits."""
    max_position_pct: float = 0.1      # max 10% per position
    max_single_symbol_pct: float = 0.2  # max 20% in single symbol
    max_drawdown_pct: float = 0.05     # max 5% drawdown
    max_var_pct: float = 0.02           # max 2% VaR

    def to_dict(self) -> dict:
        return {
            "max_position_pct": self.max_position_pct,
            "max_single_symbol_pct": self.max_single_symbol_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_var_pct": self.max_var_pct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RiskBudget":
        return cls(
            max_position_pct=float(data.get("max_position_pct", 0.1)),
            max_single_symbol_pct=float(data.get("max_single_symbol_pct", 0.2)),
            max_drawdown_pct=float(data.get("max_drawdown_pct", 0.05)),
            max_var_pct=float(data.get("max_var_pct", 0.02)),
        )
