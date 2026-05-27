"""Reddit adapter stub."""
from adapters.social.base import SocialAdapterABC


class RedditAdapter(SocialAdapterABC):
    """Reddit social data adapter."""

    def __init__(self, client_id: str = "", client_secret: str = "", user_agent: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent

    def fetch_mentions(self, symbol: str, start: str = "", end: str = "") -> dict:
        return {
            "symbol": symbol,
            "post_count": 0,
            "comment_count": 0,
            "velocity": 0.0,
            "timestamp": None,
        }

    def fetch_sentiment(self, symbol: str, start: str = "", end: str = "") -> dict:
        return {
            "symbol": symbol,
            "sentiment_mean": 0.0,
            "sentiment_delta": 0.0,
            "timestamp": None,
        }

    def health_check(self) -> bool:
        return True
