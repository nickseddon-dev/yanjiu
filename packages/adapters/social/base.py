"""Social adapter base."""
from abc import ABC, abstractmethod
from adapters.base import DataSourceABC


class SocialAdapterABC(DataSourceABC):
    """Abstract base for social media adapters."""

    @abstractmethod
    def fetch_mentions(self, symbol: str, start: str = "", end: str = "") -> dict:
        """Fetch mention data for a symbol."""
        ...

    @abstractmethod
    def fetch_sentiment(self, symbol: str, start: str = "", end: str = "") -> dict:
        """Fetch sentiment data for a symbol."""
        ...
