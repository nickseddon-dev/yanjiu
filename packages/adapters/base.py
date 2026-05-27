"""Data source adapter base - from dev doc Section 4.1.1."""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class DataSourceABC(ABC):
    """Abstract base for all data sources."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data."""
        ...

    @abstractmethod
    def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Fetch order book snapshot."""
        ...

    @abstractmethod
    def fetch_funding_rate(self, symbol: str) -> pd.DataFrame:
        """Fetch funding rate for perpetual futures."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Check if data source is accessible."""
        ...
