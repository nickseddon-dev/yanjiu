"""Social sentiment features for crypto assets."""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SentimentFeatures:
    """Social sentiment features for a crypto asset.

    Attributes:
        social_score: Composite social sentiment score (0-100).
        mention_count: Number of social media mentions in period.
        bullish_ratio: Ratio of bullish vs bearish mentions (0-100).
        trend_momentum: Momentum of sentiment change (normalized).
        engagement_metrics: Engagement metrics dict (likes, retweets, replies).
        timestamp: Feature extraction timestamp.
    """
    social_score: float
    mention_count: int
    bullish_ratio: float
    trend_momentum: float
    engagement_metrics: dict
    timestamp: Optional[str] = None


def compute_social_score(positive: int, negative: int, neutral: int) -> float:
    """Compute composite social score from mention counts.

    Args:
        positive: Number of positive mentions.
        negative: Number of negative mentions.
        neutral: Number of neutral mentions.

    Returns:
        Social sentiment score (0-100).
    """
    total = positive + negative + neutral
    if total == 0:
        return 50.0
    score = (positive * 100 + neutral * 50) / total
    return round(score, 4)


def compute_bullish_ratio(positive: int, negative: int) -> float:
    """Compute bullish ratio.

    Args:
        positive: Number of bullish mentions.
        negative: Number of bearish mentions.

    Returns:
        Bullish ratio (0-100).
    """
    total = positive + negative
    if total == 0:
        return 50.0
    return round((positive / total) * 100, 4)


def compute_trend_momentum(scores: list[float], window: int = 12) -> float:
    """Compute sentiment trend momentum.

    Args:
        scores: Historical social scores.
        window: Lookback window.

    Returns:
        Trend momentum normalized score.
    """
    if len(scores) < 2:
        return 0.0
    recent = scores[-window:] if len(scores) >= window else scores
    if len(recent) < 2:
        return 0.0
    diffs = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
    avg_diff = sum(diffs) / len(diffs)
    return round(avg_diff, 6)


def compute_engagement_metrics(likes: int, retweets: int, replies: int, quotes: int = 0) -> dict:
    """Aggregate engagement metrics.

    Args:
        likes: Number of likes.
        retweets: Number of retweets.
        replies: Number of replies.
        quotes: Number of quotes (optional).

    Returns:
        Engagement metrics dict.
    """
    return {
        "total_engagement": likes + retweets + replies + quotes,
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "quotes": quotes,
    }