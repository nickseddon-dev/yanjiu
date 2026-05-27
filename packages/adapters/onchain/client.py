"""On-chain data adapter stub."""
from typing import Optional
import pandas as pd
from adapters.base import DataSourceABC


class OnchainAdapter(DataSourceABC):
    """On-chain data adapter."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def fetch_transfers(
        self, symbol: str, start: Optional[str] = None, end: Optional[str] = None
    ) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "from_address", "to_address", "amount", "usd_value"])

    def fetch_whale_activity(self, symbol: str = "", threshold_usd: float = 1000000) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "tx_hash", "from_address", "to_address", "amount_usd"])

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    def fetch_orderbook(self, symbol: str, depth: int = 20) -> dict:
        return {"symbol": symbol, "bids": [], "asks": [], "timestamp": None}

    def fetch_funding_rate(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(columns=["timestamp", "rate"])

    def health_check(self) -> bool:
        return True
