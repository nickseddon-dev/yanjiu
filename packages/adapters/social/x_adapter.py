"""X/Twitter adapter stub."""
from adapters.social.base import SocialAdapterABC


class XAdapter(SocialAdapterABC):
    """X/Twitter social data adapter."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://api.twitter.com/2"

    def fetch_mentions(self, symbol: str, start: str = "", end: str = "") -> dict:
        """Fetch mention count and velocity for a symbol."""
        return {
            "symbol": symbol,
            "mention_count": 0,
            "mention_velocity": 0.0,
            "z_score": 0.0,
            "top_keywords": [],
            "timestamp": None,
        }

    def fetch_sentiment(self, symbol: str, start: str = "", end: str = "") -> dict:
        """Fetch aggregated sentiment for a symbol."""
        return {
            "symbol": symbol,
            "sentiment_mean": 0.0,
            "sentiment_delta": 0.0,
            "polarity_skew": 0.0,
            "sample_size": 0,
            "timestamp": None,
        }

    def health_check(self) -> bool:
        return True
