"""Technical indicators for crypto trading."""

from dataclasses import dataclass
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class TechnicalFeatures:
    """Technical indicator features for a crypto asset.

    Attributes:
        rsi_14: 14-period Relative Strength Index.
        macd: MACD line value (price - EMA_12 + EMA_26).
        macd_signal: MACD signal line (EMA_9 of MACD).
        macd_histogram: MACD histogram (MACD - signal).
        bollinger_upper: Upper Bollinger Band.
        bollinger_middle: Middle Bollinger Band (SMA_20).
        bollinger_lower: Lower Bollinger Band.
        volume_ratio: Current volume / average volume.
        price_momentum: Price momentum over lookback period.
        timestamp: Feature extraction timestamp.
    """
    rsi_14: float
    macd: float
    macd_signal: float
    macd_histogram: float
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    volume_ratio: float
    price_momentum: float
    timestamp: Optional[str] = None


def compute_rsi_14(closes: list[float]) -> float:
    """Compute 14-period RSI.

    Args:
        closes: List of closing prices.

    Returns:
        RSI value (0-100).
    """
    if len(closes) < 15:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-14:]]
    losses = [-d if d < 0 else 0 for d in deltas[-14:]]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 4)


def compute_macd(
    closes: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Tuple[float, float, float]:
    """Compute MACD indicator.

    Args:
        closes: List of closing prices.
        fast_period: Fast EMA period.
        slow_period: Slow EMA period.
        signal_period: Signal line period.

    Returns:
        Tuple of (macd, signal, histogram).
    """
    if len(closes) < slow_period + signal_period:
        return 0.0, 0.0, 0.0
    ema_fast = _ema(closes, fast_period)
    ema_slow = _ema(closes, slow_period)
    macd = ema_fast - ema_slow
    macd_series = [macd] * len(closes[-signal_period:])
    signal = _ema(macd_series, signal_period)
    histogram = macd - signal
    return round(macd, 4), round(signal, 4), round(histogram, 4)


def compute_bollinger_bands(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> Tuple[float, float, float]:
    """Compute Bollinger Bands.

    Args:
        closes: List of closing prices.
        period: SMA period.
        num_std: Number of standard deviations.

    Returns:
        Tuple of (upper, middle, lower).
    """
    if len(closes) < period:
        return 0.0, 0.0, 0.0
    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = variance ** 0.5
    upper = middle + num_std * std
    lower = middle - num_std * std
    return round(upper, 4), round(middle, 4), round(lower, 4)


def compute_volume_ratio(volumes: list[float], lookback: int = 20) -> float:
    """Compute volume ratio vs average.

    Args:
        volumes: List of volumes.
        lookback: Lookback period for average.

    Returns:
        Volume ratio.
    """
    if len(volumes) < lookback:
        return 1.0
    recent = volumes[-lookback:]
    avg_vol = sum(recent) / lookback
    if avg_vol == 0:
        return 1.0
    return round(volumes[-1] / avg_vol, 4)


def compute_price_momentum(closes: list[float], period: int = 10) -> float:
    """Compute price momentum.

    Args:
        closes: List of closing prices.
        period: Momentum period.

    Returns:
        Price momentum (percentage change).
    """
    if len(closes) < period + 1:
        return 0.0
    momentum = (closes[-1] - closes[-period - 1]) / closes[-period - 1]
    return round(momentum * 100, 4)


def _ema(prices: list[float], period: int) -> float:
    """Compute exponential moving average."""
    if not prices:
        return 0.0
    k = 2.0 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema