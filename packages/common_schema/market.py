"""Market data schemas."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated
import pydantic


class _AwareDatetime:
    """Pydantic validator for timezone-aware datetimes."""
    @classmethod
    def __get_validators__(cls):
        yield cls._validate

    @classmethod
    def _validate(cls, v):
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError("must be datetime")


@dataclass(frozen=True)
class OHLCV:
    """OHLCV candlestick data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "turnover": self.turnover,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OHLCV":
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            symbol=data["symbol"],
            timestamp=ts,
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            turnover=float(data.get("turnover", 0.0)),
        )


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Limit order book snapshot."""
    symbol: str
    timestamp: datetime
    bids: tuple[tuple[float, float], ...]  # (price, quantity) tuples
    asks: tuple[tuple[float, float], ...]
    spread: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bids": list(self.bids),
            "asks": list(self.asks),
            "spread": self.spread,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrderBookSnapshot":
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            symbol=data["symbol"],
            timestamp=ts,
            bids=tuple(tuple(b) for b in data["bids"]),
            asks=tuple(tuple(a) for a in data["asks"]),
            spread=float(data.get("spread", 0.0)),
        )


@dataclass(frozen=True)
class FundingRate:
    """Perpetual futures funding rate."""
    symbol: str
    timestamp: datetime
    rate: float
    next_funding_time: datetime

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "rate": self.rate,
            "next_funding_time": self.next_funding_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FundingRate":
        def parse_ts(ts):
            if isinstance(ts, str):
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
        return cls(
            symbol=data["symbol"],
            timestamp=parse_ts(data["timestamp"]),
            rate=float(data["rate"]),
            next_funding_time=parse_ts(data["next_funding_time"]),
        )


@dataclass(frozen=True)
class Ticker:
    """24h ticker data."""
    symbol: str
    timestamp: datetime
    last_price: float
    bid: float
    ask: float
    volume_24h: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "last_price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "volume_24h": self.volume_24h,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ticker":
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return cls(
            symbol=data["symbol"],
            timestamp=ts,
            last_price=float(data["last_price"]),
            bid=float(data["bid"]),
            ask=float(data["ask"]),
            volume_24h=float(data["volume_24h"]),
        )
