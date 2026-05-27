"""Identifier schemas."""
from dataclasses import dataclass
from enum import Enum


class AssetClass(Enum):
    """Asset class classification."""
    CRYPTO = "CRYPTO"
    EQUITY = "EQUITY"
    FOREX = "FOREX"
    COMMODITY = "COMMODITY"


class Exchange(Enum):
    """Exchange venue identifiers."""
    BINANCE = "BINANCE"
    COINBASE = "COINBASE"
    KRAKEN = "KRAKEN"
    OKX = "OKX"
    MOCK = "MOCK"


@dataclass(frozen=True)
class Symbol:
    """Canonical symbol identifier."""
    symbol: str
    asset_class: AssetClass
    exchange: Exchange

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "exchange": self.exchange.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Symbol":
        return cls(
            symbol=data["symbol"],
            asset_class=AssetClass(data["asset_class"]),
            exchange=Exchange(data["exchange"]),
        )

    def __str__(self) -> str:
        return f"{self.exchange.value}:{self.symbol}"
