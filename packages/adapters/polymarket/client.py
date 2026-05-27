"""Polymarket adapter stub."""
from typing import Optional
import pandas as pd
from adapters.base import DataSourceABC


class PolymarketAdapter(DataSourceABC):
    """Polymarket prediction market data adapter."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://clob.polymarket.com"

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    def fetch_markets(self, filter_active: bool = True) -> pd.DataFrame:
        return pd.DataFrame(columns=["id", "question", "outcome", "probability", "volume"])

    def fetch_events(self, symbol: str = "") -> pd.DataFrame:
        return pd.DataFrame(columns=["event_id", "question", "start_date", "end_date"])

    def fetch_probability(self, market_id: str) -> dict:
        return {"market_id": market_id, "probability": 0.5, "timestamp": None}

    def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        return {"symbol": symbol, "bids": [], "asks": [], "timestamp": None}

    def fetch_funding_rate(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "rate"])

    def health_check(self) -> bool:
        return True
