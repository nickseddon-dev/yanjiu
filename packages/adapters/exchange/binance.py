"""Binance exchange adapter stub."""
from typing import Optional
import pandas as pd
from adapters.base import DataSourceABC


class BinanceAdapter(DataSourceABC):
    """Binance exchange data adapter."""

    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = "https://testnet.binance.vision/api" if testnet else "https://api.binance.com"

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV from Binance klines endpoint."""
        # Stub: return empty DataFrame
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        """Fetch order book."""
        return {"symbol": symbol, "bids": [], "asks": [], "timestamp": None}

    def fetch_funding_rate(self, symbol: str) -> pd.DataFrame:
        """Fetch funding rate."""
        return pd.DataFrame(columns=["timestamp", "rate", "next_funding_time"])

    def health_check(self) -> bool:
        """Check Binance connectivity."""
        return True
